import os
import requests
import logging
from datetime import datetime
from urllib.parse import urlencode, quote_plus
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth.decorators import login_required
from tenant_schemas.utils import schema_context
from django.db.models import F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from .models import (
    FacebookPageConnection, FacebookMessage, OrphanedFacebookMessage,
    InstagramAccountConnection, InstagramMessage,
    WhatsAppBusinessAccount, WhatsAppMessage, WhatsAppMessageTemplate,
    SocialIntegrationSettings
)
from .serializers import (
    FacebookPageConnectionSerializer, FacebookMessageSerializer, FacebookSendMessageSerializer,
    InstagramAccountConnectionSerializer, InstagramMessageSerializer, InstagramSendMessageSerializer,
    WhatsAppBusinessAccountSerializer, WhatsAppMessageSerializer, WhatsAppSendMessageSerializer,
    WhatsAppMessageTemplateSerializer, WhatsAppTemplateCreateSerializer, WhatsAppTemplateSendSerializer,
    SocialIntegrationSettingsSerializer
)
from .permissions import (
    CanManageSocialConnections, CanViewSocialMessages,
    CanSendSocialMessages, CanManageSocialSettings
)

# Initialize logger
logger = logging.getLogger(__name__)


def convert_facebook_timestamp(timestamp):
    """Convert Facebook timestamp (Unix timestamp in milliseconds or seconds) to datetime object"""
    try:
        if timestamp == 0:
            return timezone.now()

        # Facebook timestamps can be in seconds or milliseconds
        # If timestamp is very large, it's probably in milliseconds
        if timestamp > 10000000000:  # If timestamp is greater than year 2286 in seconds, it's milliseconds
            timestamp = timestamp / 1000

        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (ValueError, TypeError):
        return timezone.now()


def extract_customer_information(message_event):
    """
    Extract customer information from messaging_customer_information field in webhook.

    Facebook Messenger can include customer information collected through instant forms
    or customer information features. This extracts that data when available.

    Args:
        message_event: The messaging event dict from Facebook webhook

    Returns:
        dict with keys like: name, email, phone, address_line_1, address_line_2,
        locality, administrative_area, country, zipcode, etc.
    """
    customer_info = {}

    messaging_customer_info = message_event.get('messaging_customer_information', {})
    if not messaging_customer_info:
        return customer_info

    # Extract responses from all screens
    screens = messaging_customer_info.get('screens', [])
    for screen in screens:
        responses = screen.get('responses', [])
        for response in responses:
            key = response.get('key')
            value = response.get('value')
            if key and value:
                customer_info[key] = value

    return customer_info


def send_websocket_notification(tenant_schema, message_data, conversation_id):
    """Send WebSocket notification for new message"""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.warning("WebSocket channel layer not configured")
            return

        # Send to general messages group for this tenant
        group_name = f'messages_{tenant_schema}'

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'new_message',
                'message': message_data,
                'conversation_id': conversation_id,
                'timestamp': message_data.get('timestamp')
            }
        )

    except Exception as e:
        logger.error(f"Failed to send WebSocket notification: {e}")


def find_tenant_by_page_id(page_id):
    """Find which tenant schema contains the given Facebook page ID"""
    from django.db import connection
    from tenants.models import Tenant
    from tenant_schemas.utils import schema_context

    # Get all tenant schemas
    tenants = Tenant.objects.all()

    for tenant in tenants:
        try:
            # Switch to tenant schema and check if page exists
            with schema_context(tenant.schema_name):
                from social_integrations.models import FacebookPageConnection
                if FacebookPageConnection.objects.filter(page_id=page_id, is_active=True).exists():
                    return tenant.schema_name
        except Exception as e:
            # Skip tenant if there's an error (e.g., table doesn't exist)
            continue

    return None


def find_tenant_by_whatsapp_phone_number_id(phone_number_id):
    """Find which tenant schema contains the given WhatsApp phone number ID"""
    from django.db import connection
    from tenants.models import Tenant
    from tenant_schemas.utils import schema_context

    # Get all tenant schemas
    tenants = Tenant.objects.all()

    for tenant in tenants:
        try:
            # Switch to tenant schema and check if WhatsApp account exists
            with schema_context(tenant.schema_name):
                from social_integrations.models import WhatsAppBusinessAccount
                if WhatsAppBusinessAccount.objects.filter(phone_number_id=phone_number_id, is_active=True).exists():
                    return tenant.schema_name
        except Exception as e:
            # Skip tenant if there's an error (e.g., table doesn't exist)
            continue

    return None


class FacebookPageConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = FacebookPageConnectionSerializer
    permission_classes = [IsAuthenticated, CanManageSocialConnections]

    def get_queryset(self):
        return FacebookPageConnection.objects.all()  # Tenant schema provides isolation

    def perform_create(self, serializer):
        serializer.save()  # No user assignment needed in multi-tenant setup


class FacebookMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FacebookMessageSerializer
    permission_classes = [IsAuthenticated, CanViewSocialMessages]

    def get_queryset(self):
        tenant_pages = FacebookPageConnection.objects.all()  # All pages for this tenant
        return FacebookMessage.objects.filter(page_connection__in=tenant_pages)


@api_view(['GET'])
@permission_classes([IsAuthenticated, CanManageSocialConnections])
def facebook_oauth_start(request):
    """Generate Facebook OAuth URL for business pages access"""
    logger = logging.getLogger(__name__)
    
    try:
        fb_app_id = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_APP_ID')
        if not fb_app_id:
            return Response({
                'error': 'Facebook App ID not configured'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Use public callback URL since Facebook needs a consistent redirect URI
        redirect_uri = 'https://api.echodesk.ge/api/social/facebook/oauth/callback/'
        
        # Include tenant info in state parameter - no user_id needed since tenant is unique
        from urllib.parse import quote
        tenant_obj = getattr(request, "tenant", None)
        
        # Extract tenant schema name from Tenant object or use default
        if tenant_obj and hasattr(tenant_obj, 'schema_name'):
            tenant_name = tenant_obj.schema_name
        elif tenant_obj and hasattr(tenant_obj, 'name'):
            tenant_name = tenant_obj.name
        else:
            tenant_name = "amanati"  # Default fallback
        
        # Simplified state parameter with just tenant schema
        state_raw = f'tenant={tenant_name}'
        state = quote(state_raw)  # URL encode the state
        logger.info(f"Tenant object: {tenant_obj}")
        logger.info(f"Extracted tenant schema: {tenant_name}")
        logger.info(f"Generated raw state parameter: {state_raw}")
        logger.info(f"URL encoded state parameter: {state}")
        
        # Facebook OAuth URL for business pages with Messenger Platform for Instagram
        # Using pages_messaging for both Facebook and Instagram messaging
        # instagram_basic for accessing connected Instagram accounts
        # instagram_manage_messages for reading and responding to Instagram DMs (requires app review)
        # https://developers.facebook.com/docs/messenger-platform/instagram/get-started
        oauth_url = (
            f"https://www.facebook.com/v23.0/dialog/oauth?"
            f"client_id={fb_app_id}&"
            f"redirect_uri={quote(redirect_uri)}&"
            f"scope=business_management,pages_show_list,pages_manage_metadata,pages_messaging,pages_read_engagement,instagram_basic,instagram_manage_messages,public_profile,email&"
            f"state={state}&"
            f"response_type=code&"
            f"display=popup"
        )
        
        return Response({
            'oauth_url': oauth_url,
            'redirect_uri': redirect_uri,
            'instructions': 'Visit the OAuth URL to connect your Facebook pages'
        })
    except Exception as e:
        return Response({
            'error': f'Failed to generate OAuth URL: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([])  # No authentication required for Facebook callbacks
def facebook_oauth_callback(request):
    """Handle Facebook OAuth callback, exchange code for access token, and save page connections"""
    logger = logging.getLogger(__name__)
    
    try:
        # Get all parameters from Facebook callback
        code = request.GET.get('code')
        error = request.GET.get('error')
        error_description = request.GET.get('error_description')
        error_reason = request.GET.get('error_reason')
        state = request.GET.get('state')
        
        # Parse state to get tenant info - no user_id needed
        tenant_name = None
        if state:
            from urllib.parse import unquote
            # URL decode the state parameter in case it's encoded
            decoded_state = unquote(state)
            logger.info(f"Raw state parameter: {state}")
            logger.info(f"Decoded state parameter: {decoded_state}")
            
            # State format: "tenant=amanati" (simplified)
            try:
                for param in decoded_state.split('&'):
                    if param.startswith('tenant='):
                        tenant_name = param.split('=', 1)[1]
                        logger.info(f"Parsed tenant_name: {tenant_name}")
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing state parameter: {e}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'Invalid state parameter format: {state}',
                    'error': str(e),
                    'expected_format': 'tenant=TenantName'
                })
        
        # Validate that we have required parameters
        if not tenant_name:
            logger.error(f"No tenant_name found in state: {state}")
            frontend_url = "https://amanati.echodesk.ge"  # Default fallback
            error_msg = "Tenant name not found in state parameter"
            from urllib.parse import quote_plus
            return redirect(f"{frontend_url}/?facebook_status=error&message={quote_plus(error_msg)}")
        
        # Extract tenant schema name from tenant_name - use tenant_name directly as schema
        tenant_schema = tenant_name if tenant_name else 'amanati'
        
        # Frontend dashboard URL using tenant name
        frontend_url = f"https://{tenant_schema}.echodesk.ge"
        
        # Find a suitable user for this tenant (superuser or admin)
        from tenant_schemas.utils import schema_context
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user_id = None
        with schema_context(tenant_schema):
            # Try to find a superuser first
            superuser = User.objects.filter(is_superuser=True, is_active=True).first()
            if superuser:
                user_id = superuser.id
                logger.info(f"Found superuser for tenant {tenant_schema}: {superuser.email}")
            else:
                # If no superuser, try to find an admin
                admin_user = User.objects.filter(role='admin', is_active=True).first()
                if admin_user:
                    user_id = admin_user.id
                    logger.info(f"Found admin user for tenant {tenant_schema}: {admin_user.email}")
                else:
                    # If no admin, use any active user
                    any_user = User.objects.filter(is_active=True).first()
                    if any_user:
                        user_id = any_user.id
                        logger.info(f"Found active user for tenant {tenant_schema}: {any_user.email}")
        
        if not user_id:
            logger.error(f"No active users found in tenant {tenant_schema}")
            frontend_url = f"https://{tenant_schema}.echodesk.ge"
            error_msg = f"No active users found in tenant {tenant_schema}"
            from urllib.parse import quote_plus
            return redirect(f"{frontend_url}/?facebook_status=error&message={quote_plus(error_msg)}")
        
        # Frontend dashboard URL
        frontend_url = f"https://{tenant_schema}.echodesk.ge"
        
        # Handle Facebook errors (user denied, etc.)
        if error:
            error_msg = f"Facebook OAuth failed: {error_description or error}"
            logger.error(f"Facebook OAuth error: {error} - {error_description}")
            from urllib.parse import quote_plus
            return redirect(f"{frontend_url}/?facebook_status=error&message={quote_plus(error_msg)}")
        
        # Handle missing code
        if not code:
            error_msg = "Authorization code not provided by Facebook"
            logger.error("Facebook OAuth callback missing authorization code")
            from urllib.parse import quote_plus
            return redirect(f"{frontend_url}/?facebook_status=error&message={quote_plus(error_msg)}")
        
        # Exchange authorization code for access token
        token_url = f"https://graph.facebook.com/{getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_API_VERSION', 'v23.0')}/oauth/access_token"
        token_params = {
            'client_id': getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_APP_ID'),
            'client_secret': getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_APP_SECRET'),
            'redirect_uri': 'https://api.echodesk.ge/api/social/facebook/oauth/callback/',  # Must match OAuth URL exactly
            'code': code
        }
        
        logger.info(f"Exchanging Facebook code for access token using URL: {token_url}")
        logger.info(f"Token exchange parameters: {dict(token_params, client_secret='[HIDDEN]')}")
        token_response = requests.get(token_url, params=token_params)
        token_data = token_response.json()
        
        if 'error' in token_data:
            error_msg = f"Token exchange failed: {token_data.get('error', {}).get('message', 'Unknown error')}"
            logger.error(f"Facebook token exchange error: {token_data}")
            from urllib.parse import quote_plus
            return redirect(f"{frontend_url}/?facebook_status=error&message={quote_plus(error_msg)}")
        
        user_access_token = token_data.get('access_token')
        if not user_access_token:
            error_msg = "No access token received from Facebook"
            logger.error("Facebook token exchange did not return access token")
            from urllib.parse import quote_plus
            return redirect(f"{frontend_url}/?facebook_status=error&message={quote_plus(error_msg)}")
        
        # Get user's Facebook pages - simplified approach
        pages_url = f"https://graph.facebook.com/{getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_API_VERSION', 'v23.0')}/me/accounts"
        pages_params = {
            'access_token': user_access_token,
            'fields': 'id,name,access_token,category'
        }
        
        logger.info(f"Fetching Facebook pages for tenant {tenant_name}...")
        logger.info(f"Pages API URL: {pages_url}")
        logger.info(f"Pages API params: {dict(pages_params, access_token='[HIDDEN]')}")
        
        pages_response = requests.get(pages_url, params=pages_params)
        pages_data = pages_response.json()
        
        logger.info(f"Pages API response status: {pages_response.status_code}")
        logger.info(f"Pages API response data: {pages_data}")
        
        if 'error' in pages_data:
            error_msg = f"Failed to fetch pages: {pages_data.get('error', {}).get('message', 'Unknown error')}"
            logger.error(f"Facebook pages fetch error: {pages_data}")
            from urllib.parse import quote_plus
            return redirect(f"{frontend_url}/?facebook_status=error&message={quote_plus(error_msg)}")
        
        pages = pages_data.get('data', [])
        
        # Enhanced debugging for no pages scenario
        if not pages:
            logger.warning("User has no Facebook pages to connect")
            
            # Also try to get user info to see what we can access
            user_info_url = f"https://graph.facebook.com/{getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_API_VERSION', 'v23.0')}/me"
            user_info_params = {
                'access_token': user_access_token,
                'fields': 'id,name,email'
            }
            user_info_response = requests.get(user_info_url, params=user_info_params)
            user_info_data = user_info_response.json()
            
            return JsonResponse({
                'status': 'error', 
                'message': 'No Facebook pages found for this account.',
                'help': 'This could be because your app is in Development Mode. Only pages you admin can be accessed.',
                'debug_info': {
                    'pages_response': pages_data,
                    'user_info': user_info_data,
                    'api_url': pages_url,
                    'app_mode': 'Development Mode - limited access',
                    'solutions': [
                        'Make sure you are an admin of the Facebook page',
                        'Create a Facebook business page at facebook.com/pages/create',
                        'Switch app to Live Mode (requires app review)',
                        'Add your Facebook account as a developer/tester in the app'
                    ]
                }
            })
        
        # Import tenant schema context for multi-tenant database operations
        from tenant_schemas.utils import schema_context
        
        # Save page connections to database with proper tenant context
        saved_pages = 0
        with schema_context(tenant_schema):
            # First, delete all existing Facebook page connections for this tenant
            existing_connections = FacebookPageConnection.objects.all()
            deleted_count = existing_connections.count()
            if deleted_count > 0:
                existing_connections.delete()
                logger.info(f"🗑️ Deleted {deleted_count} existing Facebook page connections for tenant {tenant_schema}")
            
            # Create new connections for all pages from callback
            saved_instagram_accounts = 0
            for page in pages:
                page_id = page.get('id')
                page_name = page.get('name')
                page_access_token = page.get('access_token')

                if page_id and page_access_token and page_name:
                    # Create new page connection for this tenant
                    page_connection = FacebookPageConnection.objects.create(
                        page_id=page_id,
                        page_name=page_name,
                        page_access_token=page_access_token,
                        is_active=True
                    )

                    logger.info(f"✅ Created Facebook page connection: {page_name} ({page_id}) in schema {tenant_schema}")
                    saved_pages += 1

                    # Subscribe page to webhooks
                    try:
                        subscribe_url = f"https://graph.facebook.com/v23.0/{page_id}/subscribed_apps"
                        subscribe_params = {
                            'subscribed_fields': 'messages,messaging_postbacks,message_reads,message_deliveries',
                            'access_token': page_access_token
                        }
                        logger.info(f"📡 Subscribing page {page_name} ({page_id}) to webhooks...")
                        subscribe_response = requests.post(subscribe_url, params=subscribe_params)
                        subscribe_data = subscribe_response.json()

                        if subscribe_response.status_code == 200 and subscribe_data.get('success'):
                            logger.info(f"✅ Subscribed page {page_name} ({page_id}) to webhooks")
                        else:
                            logger.error(f"❌ Failed to subscribe page {page_name} to webhooks: {subscribe_data}")
                    except Exception as subscribe_error:
                        logger.error(f"❌ Error subscribing page {page_name} to webhooks: {subscribe_error}")

                    # Try to fetch Instagram Business Account connected to this page
                    try:
                        instagram_url = f"https://graph.facebook.com/v23.0/{page_id}"
                        instagram_params = {
                            'fields': 'instagram_business_account',
                            'access_token': page_access_token
                        }
                        instagram_response = requests.get(instagram_url, params=instagram_params)

                        if instagram_response.status_code == 200:
                            instagram_data = instagram_response.json()
                            instagram_account = instagram_data.get('instagram_business_account')

                            if instagram_account:
                                instagram_account_id = instagram_account.get('id')

                                # Fetch Instagram account details
                                ig_details_url = f"https://graph.facebook.com/v23.0/{instagram_account_id}"
                                ig_details_params = {
                                    'fields': 'id,username,profile_picture_url',
                                    'access_token': page_access_token
                                }
                                ig_details_response = requests.get(ig_details_url, params=ig_details_params)

                                if ig_details_response.status_code == 200:
                                    ig_details = ig_details_response.json()

                                    # Create or update Instagram account connection
                                    InstagramAccountConnection.objects.update_or_create(
                                        instagram_account_id=ig_details.get('id'),
                                        defaults={
                                            'username': ig_details.get('username', ''),
                                            'profile_picture_url': ig_details.get('profile_picture_url', ''),
                                            'access_token': page_access_token,
                                            'facebook_page': page_connection,
                                            'is_active': True
                                        }
                                    )

                                    logger.info(f"✅ Connected Instagram account: @{ig_details.get('username')} to page {page_name}")
                                    saved_instagram_accounts += 1
                    except Exception as e:
                        logger.warning(f"⚠️ Could not fetch Instagram account for page {page_name}: {e}")
                        # Continue processing other pages even if Instagram fetch fails
                else:
                    logger.warning(f"⚠️ Skipped page with missing data: {page}")
        
        # Return success response with redirect to tenant frontend
        if saved_instagram_accounts > 0:
            success_msg = f"Successfully connected {saved_pages} Facebook page(s) and {saved_instagram_accounts} Instagram account(s)"
        else:
            success_msg = f"Successfully connected {saved_pages} Facebook page(s)"
        logger.info(f"Facebook OAuth completed successfully: {saved_pages} pages and {saved_instagram_accounts} Instagram accounts saved")
        
        # Redirect to tenant frontend with success parameters
        from urllib.parse import quote_plus
        return redirect(f"{frontend_url}/?facebook_status=connected&pages={saved_pages}&message={quote_plus(success_msg)}")
        
    except Exception as e:
        logger.error(f"Facebook OAuth callback processing failed: {e}")
        # Redirect to frontend with error message
        frontend_url = f"https://amanati.echodesk.ge"  # Default fallback
        if 'tenant_schema' in locals() and tenant_schema:
            frontend_url = f"https://{tenant_schema}.echodesk.ge"
        
        error_msg = f"OAuth processing failed: {str(e)}"
        from urllib.parse import quote_plus
        return redirect(f"{frontend_url}/?facebook_status=error&message={quote_plus(error_msg)}")


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def facebook_connection_status(request):
    """Check Facebook connection status for current tenant"""
    try:
        # Only count ACTIVE pages for connection status
        active_pages = FacebookPageConnection.objects.filter(is_active=True)
        all_pages = FacebookPageConnection.objects.all()

        pages_data = []
        for page in all_pages:
            pages_data.append({
                'id': page.id,
                'page_id': page.page_id,
                'page_name': page.page_name,
                'is_active': page.is_active,
                'connected_at': page.created_at.isoformat()
            })

        return Response({
            'connected': active_pages.exists(),  # Only active pages count as connected
            'pages_count': active_pages.count(),  # Only count active pages
            'pages': pages_data  # But show all pages with their is_active status
        })
    except Exception as e:
        return Response({
            'error': f'Failed to get connection status: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, CanManageSocialConnections])
def facebook_disconnect(request):
    """
    Disconnect Facebook integration for current tenant

    By default, performs soft delete (sets is_active=False) to preserve data.
    Pass hard_delete=true in request body to permanently delete.
    """
    try:
        logger = logging.getLogger(__name__)

        # Check if hard delete is requested
        hard_delete = request.data.get('hard_delete', False) if hasattr(request, 'data') else False

        # Get all pages for this tenant
        pages_to_disconnect = FacebookPageConnection.objects.all()
        page_count = pages_to_disconnect.count()
        page_names = list(pages_to_disconnect.values_list('page_name', flat=True))

        if page_count == 0:
            return Response({
                'status': 'no_pages',
                'message': 'No Facebook pages found to disconnect'
            })

        if hard_delete:
            # HARD DELETE: Permanently remove pages and messages
            facebook_message_count = 0
            for page in pages_to_disconnect:
                messages_deleted = FacebookMessage.objects.filter(
                    page_connection=page
                ).count()
                FacebookMessage.objects.filter(page_connection=page).delete()
                facebook_message_count += messages_deleted

            pages_to_disconnect.delete()

            logger.info(f"✅ Facebook hard disconnect completed:")
            logger.info(f"   - Facebook pages deleted: {page_count}")
            logger.info(f"   - Facebook messages deleted: {facebook_message_count}")

            return Response({
                'status': 'hard_disconnected',
                'facebook_pages_deleted': page_count,
                'facebook_messages_deleted': facebook_message_count,
                'deleted_pages': page_names,
                'message': f'Permanently removed {page_count} Facebook page(s) and {facebook_message_count} messages'
            })
        else:
            # SOFT DELETE: Deactivate pages, keep data for audit trail
            from django.utils import timezone

            now = timezone.now()
            deactivated_count = pages_to_disconnect.update(
                is_active=False,
                deactivated_at=now,
                deactivation_reason='manual',
                updated_at=now
            )

            logger.info(f"✅ Facebook soft disconnect completed:")
            logger.info(f"   - Facebook pages deactivated: {deactivated_count}")
            logger.info(f"   - Deactivation reason: manual")
            logger.info(f"   - Messages preserved for audit trail")
            logger.info(f"   - Webhooks will now return 404 for these pages")

            return Response({
                'status': 'disconnected',
                'facebook_pages_deactivated': deactivated_count,
                'deactivated_pages': page_names,
                'message': f'Deactivated {deactivated_count} Facebook page(s). Messages preserved. Webhooks will be rejected.',
                'note': 'Pages are soft-deleted. Pass hard_delete=true to permanently remove data.'
            })

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to disconnect Facebook: {e}")
        return Response({
            'error': f'Failed to disconnect: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, CanManageSocialConnections])
def facebook_page_disconnect(request, page_id):
    """
    Disconnect a specific Facebook page by page_id

    Performs soft delete (sets is_active=False) by default.
    Pass hard_delete=true to permanently delete.
    """
    try:
        logger = logging.getLogger(__name__)

        # Check if hard delete is requested
        hard_delete = request.data.get('hard_delete', False) if hasattr(request, 'data') else False

        # Get the specific page for this tenant
        try:
            page = FacebookPageConnection.objects.get(page_id=page_id)
        except FacebookPageConnection.DoesNotExist:
            return Response({
                'error': f'Facebook page {page_id} not found for this tenant'
            }, status=status.HTTP_404_NOT_FOUND)

        page_name = page.page_name

        if hard_delete:
            # HARD DELETE: Permanently remove page and messages
            message_count = FacebookMessage.objects.filter(page_connection=page).count()
            FacebookMessage.objects.filter(page_connection=page).delete()
            page.delete()

            logger.info(f"✅ Hard deleted Facebook page: {page_name} (ID: {page_id})")
            logger.info(f"   - Messages deleted: {message_count}")

            return Response({
                'status': 'hard_disconnected',
                'page_id': page_id,
                'page_name': page_name,
                'messages_deleted': message_count,
                'message': f'Permanently removed Facebook page "{page_name}" and {message_count} messages'
            })
        else:
            # SOFT DELETE: Deactivate page, keep data
            from django.utils import timezone

            now = timezone.now()
            page.is_active = False
            page.deactivated_at = now
            page.deactivation_reason = 'manual'
            page.updated_at = now
            page.save()

            logger.info(f"✅ Soft disconnected Facebook page: {page_name} (ID: {page_id})")
            logger.info(f"   - Messages preserved for audit trail")
            logger.info(f"   - Webhooks will now return 404 for this page")

            return Response({
                'status': 'disconnected',
                'page_id': page_id,
                'page_name': page_name,
                'message': f'Deactivated Facebook page "{page_name}". Messages preserved. Webhooks will be rejected.',
                'note': 'Page is soft-deleted. Pass hard_delete=true to permanently remove data.'
            })

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to disconnect Facebook page {page_id}: {e}")
        return Response({
            'error': f'Failed to disconnect page: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    request=FacebookSendMessageSerializer,
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'},
                'facebook_message_id': {'type': 'string'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'details': {'type': 'object'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        }
    },
    description="Send a message to a Facebook user",
    summary="Send Facebook Message"
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, CanSendSocialMessages])
def facebook_send_message(request):
    """Send a message to a Facebook user"""
    try:
        # Validate input data using serializer
        serializer = FacebookSendMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        recipient_id = validated_data['recipient_id']
        message_text = validated_data['message']
        page_id = validated_data['page_id']
        
        # Get the page connection for this tenant
        try:
            page_connection = FacebookPageConnection.objects.get(
                page_id=page_id,
                is_active=True
            )
        except FacebookPageConnection.DoesNotExist:
            return Response({
                'error': 'Page not found or not connected to this tenant'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Send message using Facebook Graph API
        send_url = f"https://graph.facebook.com/v23.0/me/messages"
        
        message_data = {
            'recipient': {'id': recipient_id},
            'message': {'text': message_text},
            'messaging_type': 'RESPONSE'  # Responding to user message
        }
        
        headers = {
            'Content-Type': 'application/json',
        }
        
        params = {
            'access_token': page_connection.page_access_token
        }

        logger.info(f"Sending message to {recipient_id} via {page_connection.page_name}")

        response = requests.post(
            send_url,
            json=message_data,
            headers=headers,
            params=params
        )
        
        if response.status_code == 200:
            response_data = response.json()
            message_id = response_data.get('message_id')
            
            # Optionally save the sent message to our database
            try:
                FacebookMessage.objects.create(
                    page_connection=page_connection,
                    message_id=message_id or f"sent_{datetime.now().timestamp()}",
                    sender_id=page_id,  # Page is the sender
                    sender_name=page_connection.page_name,
                    message_text=message_text,
                    timestamp=datetime.now(),
                    is_from_page=True
                )
            except Exception as e:
                logger.warning(f"Failed to save sent message: {e}")
            
            return Response({
                'status': 'sent',
                'message_id': message_id,
                'recipient_id': recipient_id
            })
        else:
            error_data = response.json() if response.content else {}
            error_info = error_data.get('error', {})
            error_message = error_info.get('message', 'Unknown error')
            error_code = error_info.get('code')
            error_type = error_info.get('type', '')

            # Auto-deactivate page on authentication/permission errors
            OAUTH_ERROR_CODES = [
                190,  # OAuthException - Access token expired/invalid
                102,  # API Session - Session expired
                10,   # API Permission Denied
                200,  # Permissions Error
                2500, # Permissions Error - deprecated API
            ]

            if error_code in OAUTH_ERROR_CODES or 'OAuthException' in error_type:
                # Automatically deactivate the page
                from django.utils import timezone

                now = timezone.now()

                # Determine specific deactivation reason
                if error_code == 190:
                    deactivation_reason = 'token_expired'
                elif error_code in [10, 200]:
                    deactivation_reason = 'permission_revoked'
                else:
                    deactivation_reason = 'oauth_error'

                page_connection.is_active = False
                page_connection.deactivated_at = now
                page_connection.deactivation_reason = deactivation_reason
                page_connection.deactivation_error_code = str(error_code) if error_code else None
                page_connection.updated_at = now
                page_connection.save()

                logger.warning(
                    f"🔴 Auto-deactivated Facebook page '{page_connection.page_name}' "
                    f"(reason: {deactivation_reason}, error {error_code}: {error_message})"
                )

                return Response({
                    'error': f'Facebook authentication error: {error_message}',
                    'facebook_error': error_data,
                    'page_deactivated': True,
                    'reason': 'Token expired or permissions revoked. Please reconnect your Facebook page.',
                    'error_code': error_code
                }, status=status.HTTP_401_UNAUTHORIZED)

            return Response({
                'error': f'Failed to send message: {error_message}',
                'facebook_error': error_data
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Exception in facebook_send_message: {e}")
        return Response({
            'error': f'Failed to send message: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def facebook_webhook(request):
    """Handle Facebook webhook events for page messages"""
    if request.method == 'GET':
        # Webhook verification - Facebook sends these parameters
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        # Verify token from settings
        verify_token = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_VERIFY_TOKEN', 'echodesk_webhook_token_2024')
        
        # Verify the mode and token
        if mode == 'subscribe' and token == verify_token:
            # Return the challenge as plain text (not JSON)
            return HttpResponse(challenge, content_type='text/plain')
        else:
            return JsonResponse({
                'error': 'Invalid verify token or mode'
            }, status=403)
    
    elif request.method == 'POST':
        # Handle webhook events
        try:
            import json
            import logging
            from datetime import datetime
            from tenant_schemas.utils import schema_context
            logger = logging.getLogger(__name__)
            
            # Parse webhook data
            data = json.loads(request.body)

            # Log webhook data for debugging
            logger.info(f"📩 FACEBOOK WEBHOOK RECEIVED:")
            logger.info(f"   Raw data: {json.dumps(data, indent=2)}")
            logger.info(f"   Headers: User-Agent={request.headers.get('User-Agent')}, X-Hub-Signature={request.headers.get('X-Hub-Signature')}")
            
            # Extract page_id to determine which tenant to use
            page_id = None

            # Handle Facebook Developer Console test format
            if 'field' in data and 'value' in data and data['field'] == 'messages':
                test_value = data['value']
                page_id = (test_value.get('metadata', {}).get('page_id') or
                          test_value.get('page_id') or
                          test_value.get('recipient', {}).get('id'))

            # Handle standard webhook format (real messages)
            elif 'entry' in data and len(data['entry']) > 0:
                page_id = data['entry'][0].get('id')

            if not page_id:
                logger.error("No page_id found in webhook data")
                return JsonResponse({'error': 'No page_id found'}, status=400)

            # Find which tenant this page belongs to
            tenant_schema = find_tenant_by_page_id(page_id)

            if not tenant_schema:
                logger.warning(f"No tenant found for page_id: {page_id} - Saving as orphaned message")

                # Extract message details from webhook data
                try:
                    # Extract messages from webhook data
                    messages_to_save = []

                    # Handle test format
                    if 'field' in data and 'value' in data and data['field'] == 'messages':
                        test_value = data['value']
                        sender_id = test_value.get('sender', {}).get('id', 'unknown')
                        message_data = test_value.get('message', {})
                        timestamp = test_value.get('timestamp', 0)

                        messages_to_save.append({
                            'sender_id': sender_id,
                            'sender_name': test_value.get('sender', {}).get('name', ''),
                            'message_id': message_data.get('mid', ''),
                            'message_text': message_data.get('text', '[No text content]'),
                            'timestamp': convert_facebook_timestamp(int(timestamp) if timestamp else 0)
                        })

                    # Handle standard webhook format
                    elif 'entry' in data:
                        for entry in data['entry']:
                            if 'messaging' in entry:
                                for message_event in entry['messaging']:
                                    if 'message' in message_event:
                                        message_data = message_event['message']
                                        # Skip echo messages
                                        if not message_data.get('is_echo'):
                                            sender_id = message_event.get('sender', {}).get('id', 'unknown')
                                            timestamp = message_event.get('timestamp', 0)

                                            messages_to_save.append({
                                                'sender_id': sender_id,
                                                'sender_name': '',  # Not available in standard webhook
                                                'message_id': message_data.get('mid', ''),
                                                'message_text': message_data.get('text', '[No text content]'),
                                                'timestamp': convert_facebook_timestamp(int(timestamp) if timestamp else 0)
                                            })

                    # Save orphaned messages to public schema
                    saved_count = 0
                    for msg in messages_to_save:
                        OrphanedFacebookMessage.objects.create(
                            page_id=page_id,
                            sender_id=msg['sender_id'],
                            sender_name=msg['sender_name'],
                            message_id=msg['message_id'],
                            message_text=msg['message_text'],
                            timestamp=msg['timestamp'],
                            raw_webhook_data=data,
                            error_reason='page_not_found'
                        )
                        saved_count += 1
                        logger.info(f"✅ Saved orphaned message from {msg['sender_id']}: {msg['message_text'][:50]}")

                    logger.info(f"✅ Saved {saved_count} orphaned message(s) for page_id: {page_id}")

                    # Return success so Facebook doesn't keep retrying
                    return JsonResponse({
                        'status': 'received',
                        'message': f'Saved {saved_count} orphaned message(s) for review'
                    })

                except Exception as e:
                    logger.error(f"Failed to save orphaned message: {e}")
                    # Still return success to avoid Facebook retries
                    return JsonResponse({
                        'status': 'received',
                        'message': 'Page not found, webhook acknowledged'
                    })

            logger.info(f"Processing webhook for page_id {page_id} in tenant: {tenant_schema}")
            
            # Process webhook within the correct tenant context
            with schema_context(tenant_schema):
                # Handle Facebook Developer Console test format
                if 'field' in data and 'value' in data and data['field'] == 'messages':
                    # This is a test message from Facebook Developer Console
                    test_value = data['value']
                    
                    # Extract data from test format
                    sender_id = test_value.get('sender', {}).get('id', 'test_sender')
                    message_data = test_value.get('message', {})
                    timestamp = test_value.get('timestamp', 0)
                    
                    logger.info(f"Processing test message from sender {sender_id}")
                    
                    if page_id and sender_id and message_data:
                        # Find the page connection
                        try:
                            page_connection = FacebookPageConnection.objects.get(
                                page_id=page_id, 
                                is_active=True
                            )
                            logger.info(f"Found page connection: {page_connection}")
                            
                            # Process the test message
                            message_id = message_data.get('mid', f'test_mid_{timestamp}')
                            message_text = message_data.get('text', 'Test message from Facebook')

                            # Skip if this is an echo (message sent by the page)
                            if message_data.get('is_echo'):
                                return JsonResponse({'status': 'received'})

                            # For test messages, use simple sender info
                            sender_name = f"Test User {sender_id}"
                            profile_pic_url = None

                            # Save the message (avoid duplicates)
                            if message_id and not FacebookMessage.objects.filter(message_id=message_id).exists():
                                try:
                                    message_obj = FacebookMessage.objects.create(
                                        page_connection=page_connection,
                                        message_id=message_id,
                                        sender_id=sender_id,
                                        sender_name=sender_name,
                                        message_text=message_text,
                                        timestamp=convert_facebook_timestamp(int(timestamp) if timestamp else 0),
                                        is_from_page=(sender_id == page_id),
                                        profile_pic_url=profile_pic_url
                                    )
                                    logger.info(f"✅ Saved test message: {message_text}")

                                    # Send WebSocket notification for real-time updates
                                    from django.db import connection
                                    current_schema = getattr(connection, 'schema_name', None)
                                    if current_schema:
                                        ws_message_data = {
                                            'id': message_obj.id,
                                            'message_id': message_obj.message_id,
                                            'sender_id': message_obj.sender_id,
                                            'sender_name': message_obj.sender_name,
                                            'message_text': message_obj.message_text,
                                            'timestamp': message_obj.timestamp.isoformat() if message_obj.timestamp else None,
                                            'is_from_page': message_obj.is_from_page,
                                        }
                                        # Conversation ID is the sender_id (the customer)
                                        ws_conversation_id = sender_id
                                        send_websocket_notification(current_schema, ws_message_data, ws_conversation_id)

                                except Exception as e:
                                    logger.error(f"Failed to save test message: {e}")

                        except FacebookPageConnection.DoesNotExist:
                            logger.warning(f"No active page connection found for page_id: {page_id}")
                            return JsonResponse({'error': f'No page connection found for page_id: {page_id}'}, status=404)
                    
                    return JsonResponse({'status': 'received'})
                
                # Handle standard webhook format (real messages)
                elif 'entry' in data:
                    logger.info(f"🔄 Processing STANDARD webhook format with {len(data['entry'])} entries")
                    
                    for entry in data['entry']:
                        page_id = entry.get('id')
                        logger.info(f"🔍 Processing entry for page_id: {page_id}")
                        
                        # Find the page connection
                        try:
                            page_connection = FacebookPageConnection.objects.get(
                                page_id=page_id, 
                                is_active=True
                            )
                            logger.info(f"✅ Found page connection: {page_connection.page_name}")
                        except FacebookPageConnection.DoesNotExist:
                            # Log for debugging but continue processing other entries
                            logger.warning(f"❌ No active page connection found for page_id: {page_id}")
                            # List available connections for debugging
                            all_connections = FacebookPageConnection.objects.filter(is_active=True)
                            logger.warning(f"Available connections: {[(conn.page_id, conn.page_name) for conn in all_connections]}")
                            continue
                        
                        # Process messaging events
                        if 'messaging' in entry:
                            logger.info(f"📨 Found {len(entry['messaging'])} messaging events")
                            for message_event in entry['messaging']:
                                
                                if 'message' in message_event:
                                    message_data = message_event['message']
                                    sender_id = message_event['sender']['id']
                                    
                                    # Handle echo messages (messages sent by the page)
                                    if message_data.get('is_echo'):
                                        logger.info("📤 Processing echo message to update timestamp")
                                        message_id = message_data.get('mid')

                                        if message_id:
                                            try:
                                                # Update the timestamp of the message we saved when sending
                                                fb_timestamp = message_event.get('timestamp')
                                                if fb_timestamp:
                                                    timestamp_dt = convert_facebook_timestamp(fb_timestamp)

                                                    updated = FacebookMessage.objects.filter(
                                                        page_connection=page_connection,
                                                        message_id=message_id
                                                    ).update(timestamp=timestamp_dt)

                                                    if updated > 0:
                                                        logger.info(f"✅ Updated echo message timestamp to {timestamp_dt}")
                                                    else:
                                                        logger.info(f"⚠️ Echo message not found in database: {message_id}")
                                            except Exception as e:
                                                logger.error(f"❌ Failed to update echo message timestamp: {e}")

                                        continue
                                    
                                    # Get sender information
                                    sender_name = 'Messenger User'  # Fallback name
                                    profile_pic_url = None
                                    customer_email = None
                                    customer_phone = None

                                    # Get message_id for API calls
                                    message_id = message_data.get('mid', '')

                                    if sender_id != page_id:  # Don't fetch profile for page itself
                                        # First try: Extract customer information from webhook
                                        customer_info = extract_customer_information(message_event)

                                        if customer_info:
                                            # Use customer information from webhook (most reliable)
                                            sender_name = customer_info.get('name', '').strip() or 'Messenger User'
                                            customer_email = customer_info.get('email')
                                            customer_phone = customer_info.get('phone')
                                            logger.info(f"👤 Using customer info from webhook: {sender_name}")
                                            if customer_email:
                                                logger.info(f"   Email: {customer_email}")
                                            if customer_phone:
                                                logger.info(f"   Phone: {customer_phone}")
                                        elif message_id:
                                            # Second try: Fetch sender info from message object (works in Live Mode!)
                                            try:
                                                message_url = f"https://graph.facebook.com/v23.0/{message_id}"
                                                message_params = {
                                                    'fields': 'from',
                                                    'access_token': page_connection.page_access_token
                                                }
                                                message_response = requests.get(message_url, params=message_params, timeout=10)

                                                if message_response.status_code == 200:
                                                    message_api_data = message_response.json()
                                                    from_data = message_api_data.get('from', {})

                                                    sender_name = from_data.get('name', '').strip() or 'Messenger User'
                                                    # Note: from_data.get('email') is usually a fake email like "psid@facebook.com"

                                                    logger.info(f"👤 Fetched sender name from message object: {sender_name}")
                                                else:
                                                    logger.warning(f"Could not fetch message info: status={message_response.status_code}")
                                            except Exception as e:
                                                logger.warning(f"Exception fetching message info: {e}")
                                    
                                    # Save the message (avoid duplicates)
                                    message_id = message_data.get('mid', '')
                                    message_text = message_data.get('text', '')

                                    # Extract attachment information
                                    attachment_type = ''
                                    attachment_url = None
                                    attachments = []

                                    if 'attachments' in message_data:
                                        raw_attachments = message_data.get('attachments', [])
                                        for att in raw_attachments:
                                            att_type = att.get('type', '')
                                            payload = att.get('payload', {})
                                            att_url = payload.get('url', '')

                                            # Build attachment object for storage
                                            attachment_obj = {
                                                'type': att_type,
                                                'url': att_url,
                                            }

                                            # Add sticker_id if present (for stickers)
                                            if payload.get('sticker_id'):
                                                attachment_obj['sticker_id'] = payload.get('sticker_id')

                                            attachments.append(attachment_obj)

                                            # Set primary attachment type and URL (first attachment)
                                            if not attachment_type:
                                                attachment_type = att_type
                                                attachment_url = att_url

                                        logger.info(f"📎 Found {len(attachments)} attachment(s): {[a['type'] for a in attachments]}")

                                    if message_id and not FacebookMessage.objects.filter(message_id=message_id).exists():
                                        try:
                                            message_obj = FacebookMessage.objects.create(
                                                page_connection=page_connection,
                                                message_id=message_id,
                                                sender_id=sender_id,
                                                sender_name=sender_name,
                                                message_text=message_text,
                                                attachment_type=attachment_type,
                                                attachment_url=attachment_url,
                                                attachments=attachments,
                                                timestamp=convert_facebook_timestamp(message_event.get('timestamp', 0)),
                                                is_from_page=(sender_id == page_id),
                                                profile_pic_url=profile_pic_url
                                            )
                                            logger.info(f"✅ Saved message from {sender_name}: {message_text[:50] if message_text else f'[{attachment_type}]'}")

                                            # Send WebSocket notification for real-time updates
                                            from django.db import connection
                                            current_schema = getattr(connection, 'schema_name', None)
                                            if current_schema:
                                                ws_message_data = {
                                                    'id': message_obj.id,
                                                    'message_id': message_obj.message_id,
                                                    'sender_id': message_obj.sender_id,
                                                    'sender_name': message_obj.sender_name,
                                                    'message_text': message_obj.message_text,
                                                    'attachment_type': message_obj.attachment_type,
                                                    'attachment_url': message_obj.attachment_url,
                                                    'attachments': message_obj.attachments,
                                                    'timestamp': message_obj.timestamp.isoformat() if message_obj.timestamp else None,
                                                    'is_from_page': message_obj.is_from_page,
                                                }
                                                # Conversation ID is the sender_id (the customer)
                                                ws_conversation_id = sender_id
                                                send_websocket_notification(current_schema, ws_message_data, ws_conversation_id)

                                        except Exception as e:
                                            logger.error(f"❌ Failed to save message: {e}")
                                    else:
                                        if not message_id:
                                            logger.warning(f"⚠️ No message_id provided, skipping save")
                                        else:
                                            logger.warning(f"⚠️ Message {message_id} already exists, skipping save")

                                # Handle read receipts
                                elif 'read' in message_event:
                                    read_data = message_event['read']
                                    sender_id = message_event['sender']['id']
                                    watermark = int(read_data.get('watermark', 0))

                                    logger.info(f"📖 Read receipt from {sender_id}, watermark: {watermark}")

                                    # Mark all messages from this sender before the watermark as read
                                    try:
                                        from django.utils import timezone
                                        watermark_datetime = convert_facebook_timestamp(watermark)

                                        # Find messages sent by the page to this user before the watermark
                                        messages_to_mark = FacebookMessage.objects.filter(
                                            page_connection=page_connection,
                                            sender_id=page_id,  # Messages sent BY the page
                                            timestamp__lte=watermark_datetime,
                                            is_read=False
                                        )

                                        updated_count = messages_to_mark.update(
                                            is_read=True,
                                            read_at=timezone.now()
                                        )

                                        logger.info(f"✅ Marked {updated_count} messages as read for conversation with {sender_id}")

                                        # Send WebSocket notification for read receipts
                                        if updated_count > 0:
                                            from django.db import connection
                                            current_schema = getattr(connection, 'schema_name', None)
                                            if current_schema:
                                                # Get the IDs of updated messages
                                                updated_message_ids = list(FacebookMessage.objects.filter(
                                                    page_connection=page_connection,
                                                    sender_id=page_id,
                                                    timestamp__lte=watermark_datetime,
                                                    is_read=True
                                                ).values_list('id', flat=True))

                                                read_receipt_data = {
                                                    'type': 'read_receipt',
                                                    'sender_id': sender_id,
                                                    'watermark': watermark,
                                                    'message_ids': updated_message_ids,
                                                    'updated_count': updated_count,
                                                    'timestamp': timezone.now().isoformat()
                                                }
                                                # Conversation ID is the sender_id (the customer who read the messages)
                                                ws_conversation_id = sender_id
                                                send_websocket_notification(current_schema, read_receipt_data, ws_conversation_id)

                                    except Exception as e:
                                        logger.error(f"❌ Failed to process read receipt: {e}")

                                # Handle delivery receipts
                                elif 'delivery' in message_event:
                                    delivery_data = message_event['delivery']
                                    sender_id = message_event['sender']['id']
                                    watermark = int(delivery_data.get('watermark', 0))
                                    message_ids = delivery_data.get('mids', [])

                                    logger.info(f"📬 Delivery receipt from {sender_id}, watermark: {watermark}")

                                    # Mark all messages from this sender before the watermark as delivered
                                    try:
                                        from django.utils import timezone
                                        watermark_datetime = convert_facebook_timestamp(watermark)

                                        # Find messages sent by the page to this user before the watermark
                                        messages_to_mark = FacebookMessage.objects.filter(
                                            page_connection=page_connection,
                                            sender_id=page_id,  # Messages sent BY the page
                                            timestamp__lte=watermark_datetime,
                                            is_delivered=False
                                        )

                                        updated_count = messages_to_mark.update(
                                            is_delivered=True,
                                            delivered_at=timezone.now()
                                        )

                                        logger.info(f"✅ Marked {updated_count} messages as delivered for conversation with {sender_id}")

                                        # Send WebSocket notification for delivery receipts
                                        if updated_count > 0:
                                            from django.db import connection
                                            current_schema = getattr(connection, 'schema_name', None)
                                            if current_schema:
                                                # Get the IDs of updated messages
                                                updated_message_ids = list(FacebookMessage.objects.filter(
                                                    page_connection=page_connection,
                                                    sender_id=page_id,
                                                    timestamp__lte=watermark_datetime,
                                                    is_delivered=True
                                                ).values_list('id', flat=True))

                                                delivery_receipt_data = {
                                                    'type': 'delivery_receipt',
                                                    'sender_id': sender_id,
                                                    'watermark': watermark,
                                                    'message_ids': updated_message_ids,
                                                    'updated_count': updated_count,
                                                    'timestamp': timezone.now().isoformat()
                                                }
                                                # Conversation ID is the sender_id (the customer who received the messages)
                                                ws_conversation_id = sender_id
                                                send_websocket_notification(current_schema, delivery_receipt_data, ws_conversation_id)

                                    except Exception as e:
                                        logger.error(f"❌ Failed to process delivery receipt: {e}")

                                else:
                                    logger.info(f"ℹ️ Message event has no 'message', 'read', or 'delivery' field: {message_event}")
                        else:
                            logger.info(f"ℹ️ Entry has no 'messaging' field: {entry}")
                else:
                    logger.warning(f"⚠️ Unknown webhook format - no 'entry' or 'field' found in data: {data}")
            
            return JsonResponse({'status': 'received'})
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            return JsonResponse({
                'error': f'Webhook processing failed: {str(e)}'
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@api_view(['GET'])
@permission_classes([])  # No authentication required for debugging
def facebook_debug_callback(request):
    """Debug endpoint to see what Facebook is actually sending"""
    # Also log to file for debugging
    try:
        from datetime import datetime
        with open('/tmp/facebook_debug_log.txt', 'a') as f:
            f.write(f"\n=== DEBUG ENDPOINT HIT ===\n")
            f.write(f"Time: {datetime.now()}\n")
            f.write(f"Method: {request.method}\n")
            f.write("=" * 50 + "\n")
    except:
        pass
    
    return Response({
        'method': request.method,
        'path': request.path,
        'full_url': request.build_absolute_uri(),
        'get_params': dict(request.GET.items()),
        'post_params': dict(request.POST.items()) if hasattr(request, 'POST') else {},
        'headers': {k: v for k, v in request.META.items() if k.startswith('HTTP_')},
        'message': 'This endpoint shows exactly what Facebook sends to the callback',
        'timestamp': str(datetime.now())
    })


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([])
def webhook_test_endpoint(request):
    """Simple test endpoint to verify webhook connectivity"""
    from datetime import datetime
    import os
    
    # Log everything to file
    try:
        log_file = os.path.join(os.getcwd(), 'webhook_test_log.txt')
        with open(log_file, 'a') as f:
            f.write(f"\n=== WEBHOOK TEST ===\n")
            f.write(f"Time: {datetime.now()}\n")
            f.write(f"Method: {request.method}\n")
            f.write(f"Body: {request.body.decode('utf-8') if request.body else 'No body'}\n")
            f.write("=" * 50 + "\n")
        print(f"TEST: Logged to {log_file}")
    except Exception as e:
        print(f"TEST: Failed to write to log file: {e}")
        print(f"TEST WEBHOOK at {datetime.now()}: {request.method} - {request.body.decode('utf-8') if request.body else 'No body'}")
    
    return Response({
        'status': 'success',
        'message': 'Webhook test endpoint working',
        'method': request.method,
        'timestamp': str(datetime.now()),
        'body_received': request.body.decode('utf-8') if request.body else None,
        'log_file': os.path.join(os.getcwd(), 'webhook_test_log.txt')
    })


@csrf_exempt
@api_view(['GET'])
@permission_classes([])
def debug_facebook_pages(request):
    """Debug endpoint to show available Facebook page connections"""
    try:
        from tenant_schemas.utils import schema_context
        from social_integrations.models import FacebookPageConnection, FacebookMessage
        
        result = {}
        
        with schema_context('amanati'):
            # Get all page connections
            page_connections = FacebookPageConnection.objects.all()
            result['page_connections'] = []
            
            for pc in page_connections:
                page_info = {
                    'page_id': pc.page_id,
                    'page_name': pc.page_name,
                    'is_active': pc.is_active,
                    'created_at': pc.created_at.isoformat() if pc.created_at else None,
                    'message_count': FacebookMessage.objects.filter(page_connection=pc).count()
                }
                result['page_connections'].append(page_info)
            
            # Get recent messages
            recent_messages = FacebookMessage.objects.all().order_by('-created_at')[:5]
            result['recent_messages'] = []
            
            for msg in recent_messages:
                msg_info = {
                    'message_id': msg.message_id,
                    'sender_name': msg.sender_name,
                    'message_text': msg.message_text[:100],
                    'page_name': msg.page_connection.page_name,
                    'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
                    'created_at': msg.created_at.isoformat() if msg.created_at else None
                }
                result['recent_messages'].append(msg_info)
            
            result['total_pages'] = len(result['page_connections'])
            result['total_messages'] = FacebookMessage.objects.count()
            
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({
            'error': f'Debug failed: {str(e)}'
        }, status=500)


@csrf_exempt
@api_view(['GET'])
@permission_classes([])
def debug_database_status(request):
    """Debug endpoint to check database table status"""
    from django.db import connection
    
    try:
        # Check if tables exist
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE '%social_integrations%'
            """)
            tables = [row[0] for row in cursor.fetchall()]
        
        # Try to count records
        try:
            page_count = FacebookPageConnection.objects.count()
            message_count = FacebookMessage.objects.count()
        except Exception as e:
            page_count = f"Error: {e}"
            message_count = f"Error: {e}"
        
        # Check migrations
        from django.db.migrations.recorder import MigrationRecorder
        try:
            applied_migrations = MigrationRecorder.Migration.objects.filter(app='social_integrations')
            migrations_list = [f"{m.app}.{m.name}" for m in applied_migrations]
        except Exception as e:
            migrations_list = f"Error: {e}"
        
        return Response({
            'database_tables': tables,
            'page_connections_count': page_count,
            'messages_count': message_count,
            'applied_migrations': migrations_list,
            'database_url': getattr(settings, 'DATABASE_URL', 'Not found')[:50] + '...' if hasattr(settings, 'DATABASE_URL') else 'Not configured'
        })
        
    except Exception as e:
        return Response({
            'error': f'Database check failed: {str(e)}'
        }, status=500)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([])
def test_facebook_api_access(request):
    """Test Facebook API access with current permissions"""
    try:
        access_token = request.GET.get('access_token') or request.POST.get('access_token')
        
        if not access_token:
            return JsonResponse({
                'error': 'access_token parameter required',
                'usage': 'GET /api/social/facebook/api/test/?access_token=YOUR_TOKEN',
                'note': 'Use this to test what Facebook APIs return with your current access token'
            })
        
        api_version = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_API_VERSION', 'v23.0')
        results = {}
        
        # Test 1: Get user info
        try:
            user_url = f"https://graph.facebook.com/{api_version}/me"
            user_params = {
                'access_token': access_token,
                'fields': 'id,name,email'
            }
            user_response = requests.get(user_url, params=user_params)
            results['user_info'] = {
                'status_code': user_response.status_code,
                'data': user_response.json()
            }
        except Exception as e:
            results['user_info'] = {'error': str(e)}
        
        # Test 2: Get user permissions
        try:
            permissions_url = f"https://graph.facebook.com/{api_version}/me/permissions"
            permissions_params = {'access_token': access_token}
            permissions_response = requests.get(permissions_url, params=permissions_params)
            results['permissions'] = {
                'status_code': permissions_response.status_code,
                'data': permissions_response.json()
            }
        except Exception as e:
            results['permissions'] = {'error': str(e)}
        
        # Test 3: Get pages using /me/accounts (traditional way)
        try:
            accounts_url = f"https://graph.facebook.com/{api_version}/me/accounts"
            accounts_params = {
                'access_token': access_token,
                'fields': 'id,name,access_token,category,about,is_published,tasks'
            }
            accounts_response = requests.get(accounts_url, params=accounts_params)
            results['me_accounts'] = {
                'status_code': accounts_response.status_code,
                'data': accounts_response.json()
            }
        except Exception as e:
            results['me_accounts'] = {'error': str(e)}
        
        # Test 4: Get businesses (with business_management permission)
        try:
            businesses_url = f"https://graph.facebook.com/{api_version}/me/businesses"
            businesses_params = {
                'access_token': access_token,
                'fields': 'id,name,verification_status'
            }
            businesses_response = requests.get(businesses_url, params=businesses_params)
            results['businesses'] = {
                'status_code': businesses_response.status_code,
                'data': businesses_response.json()
            }
        except Exception as e:
            results['businesses'] = {'error': str(e)}
        
        # Test 5: Try pages via business management (if we have businesses)
        try:
            if 'businesses' in results and 'data' in results['businesses'] and results['businesses']['data'].get('data'):
                business_id = results['businesses']['data']['data'][0]['id']
                business_pages_url = f"https://graph.facebook.com/{api_version}/{business_id}/owned_pages"
                business_pages_params = {
                    'access_token': access_token,
                    'fields': 'id,name,category,about'
                }
                business_pages_response = requests.get(business_pages_url, params=business_pages_params)
                results['business_pages'] = {
                    'status_code': business_pages_response.status_code,
                    'data': business_pages_response.json()
                }
            else:
                results['business_pages'] = {'skipped': 'No businesses found'}
        except Exception as e:
            results['business_pages'] = {'error': str(e)}
        
        return JsonResponse({
            'status': 'success',
            'api_version': api_version,
            'tests_performed': len(results),
            'results': results,
            'recommendations': [
                'Check permissions data to see what permissions are granted',
                'If no pages in me/accounts, user may not have admin role on any pages',
                'If business_management permission is granted, check businesses and business_pages',
                'Ensure your Facebook app has business_management permission configured'
            ]
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'API test failed: {str(e)}'
        }, status=500)


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([])
def test_database_save(request):
    """Test endpoint to manually create a Facebook message in database"""
    try:
        # Find the first active page connection
        page_connection = FacebookPageConnection.objects.filter(is_active=True).first()

        if not page_connection:
            return Response({
                'error': 'No active Facebook page connections found',
                'available_connections': list(FacebookPageConnection.objects.values('page_id', 'page_name', 'is_active'))
            }, status=400)

        # Create a test message
        from datetime import datetime
        import random

        test_message = FacebookMessage.objects.create(
            page_connection=page_connection,
            message_id=f"test_message_{random.randint(1000, 9999)}",
            sender_id="test_sender_123",
            sender_name="Test User",
            message_text="This is a test message created manually",
            timestamp=timezone.now(),
            is_from_page=False,
            profile_pic_url=None
        )

        return Response({
            'success': True,
            'message_id': test_message.id,
            'message_text': test_message.message_text,
            'page_connection': {
                'page_id': page_connection.page_id,
                'page_name': page_connection.page_name
            },
            'admin_url': f'https://amanati.api.echodesk.ge/admin/social_integrations/facebookmessage/{test_message.id}/change/'
        })

    except Exception as e:
        return Response({
            'error': f'Failed to create test message: {str(e)}'
        }, status=500)


# ============================================================================
# INSTAGRAM VIEWS
# ============================================================================

class InstagramAccountConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = InstagramAccountConnectionSerializer
    permission_classes = [IsAuthenticated, CanManageSocialConnections]

    def get_queryset(self):
        return InstagramAccountConnection.objects.all()  # Tenant schema provides isolation

    def perform_create(self, serializer):
        serializer.save()  # No user assignment needed in multi-tenant setup


class InstagramMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InstagramMessageSerializer
    permission_classes = [IsAuthenticated, CanViewSocialMessages]

    def get_queryset(self):
        tenant_accounts = InstagramAccountConnection.objects.all()  # All accounts for this tenant
        return InstagramMessage.objects.filter(account_connection__in=tenant_accounts)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instagram_connection_status(request):
    """Check Instagram connection status for current tenant"""
    try:
        accounts = InstagramAccountConnection.objects.all()  # All accounts for this tenant
        accounts_data = []

        for account in accounts:
            accounts_data.append({
                'id': account.id,
                'instagram_account_id': account.instagram_account_id,
                'username': account.username,
                'profile_picture_url': account.profile_picture_url,
                'is_active': account.is_active,
                'connected_at': account.created_at.isoformat()
            })

        return Response({
            'connected': accounts.exists(),
            'accounts_count': accounts.count(),
            'accounts': accounts_data
        })
    except Exception as e:
        return Response({
            'error': f'Failed to get connection status: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, CanManageSocialConnections])
def instagram_disconnect(request):
    """Disconnect Instagram integration for current tenant"""
    try:
        logger = logging.getLogger(__name__)

        # Get count before deletion for response
        accounts_to_delete = InstagramAccountConnection.objects.all()  # All accounts for this tenant
        account_count = accounts_to_delete.count()
        usernames = list(accounts_to_delete.values_list('username', flat=True))

        if account_count == 0:
            return Response({
                'status': 'no_accounts',
                'message': 'No Instagram accounts found to disconnect'
            })

        # Delete Instagram messages
        instagram_message_count = 0
        for account in accounts_to_delete:
            messages_deleted = InstagramMessage.objects.filter(
                account_connection=account
            ).count()
            InstagramMessage.objects.filter(account_connection=account).delete()
            instagram_message_count += messages_deleted

        # Delete Instagram account connections
        accounts_to_delete.delete()

        logger.info(f"✅ Instagram disconnect completed:")
        logger.info(f"   - Instagram accounts deleted: {account_count}")
        logger.info(f"   - Instagram messages deleted: {instagram_message_count}")

        return Response({
            'status': 'disconnected',
            'instagram_accounts_deleted': account_count,
            'instagram_messages_deleted': instagram_message_count,
            'deleted_accounts': usernames,
            'message': f'Permanently removed {account_count} Instagram account(s) and {instagram_message_count} messages'
        })

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to disconnect Instagram: {e}")
        return Response({
            'error': f'Failed to disconnect: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    request=InstagramSendMessageSerializer,
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'},
                'instagram_message_id': {'type': 'string'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'details': {'type': 'object'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        }
    },
    description="Send a message to an Instagram user",
    summary="Send Instagram Message"
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, CanSendSocialMessages])
def instagram_send_message(request):
    """Send a message to an Instagram user"""
    try:
        # Validate input data using serializer
        serializer = InstagramSendMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        recipient_id = validated_data['recipient_id']
        message_text = validated_data['message']
        instagram_account_id = validated_data['instagram_account_id']

        # Get the Instagram account connection for this tenant
        try:
            account_connection = InstagramAccountConnection.objects.get(
                instagram_account_id=instagram_account_id,
                is_active=True
            )
        except InstagramAccountConnection.DoesNotExist:
            return Response({
                'error': 'Instagram account not found or not connected to this tenant'
            }, status=status.HTTP_404_NOT_FOUND)

        # Send message using Facebook Pages Messaging API
        # Instagram messages are sent through the Facebook Page, not the Instagram account directly
        # We use the Page ID in the URL, not the Instagram account ID
        if not account_connection.facebook_page:
            return Response({
                'error': 'Instagram account is not linked to a Facebook Page'
            }, status=status.HTTP_400_BAD_REQUEST)

        page_id = account_connection.facebook_page.page_id

        # Check if we have any messages from this recipient (to verify they messaged us first)
        recent_messages = InstagramMessage.objects.filter(
            account_connection=account_connection,
            sender_id=recipient_id,
            is_from_business=False
        ).order_by('-timestamp')

        if not recent_messages.exists():
            return Response({
                'error': 'Cannot send message: No conversation found with this user. The user must message you first on Instagram.',
                'details': 'Instagram requires the user to initiate the conversation before you can send messages.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check 24-hour window
        latest_message = recent_messages.first()
        time_since_message = datetime.now(latest_message.timestamp.tzinfo) - latest_message.timestamp
        hours_passed = time_since_message.total_seconds() / 3600

        if hours_passed > 24:
            return Response({
                'error': f'Cannot send message: 24-hour response window expired ({hours_passed:.1f} hours ago)',
                'details': 'Instagram only allows responses within 24 hours of the last message from the user.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Instagram messaging through Messenger Platform API
        # Use Page ID in URL and specify platform=instagram in params
        # https://developers.facebook.com/docs/messenger-platform/instagram/get-started
        send_url = f"https://graph.facebook.com/v23.0/me/messages"

        message_data = {
            'recipient': {'id': recipient_id},
            'message': {'text': message_text},
            'messaging_type': 'RESPONSE'  # Required for Instagram within 24hr window
        }

        headers = {
            'Content-Type': 'application/json',
        }

        # Use the Facebook Page's access token
        access_token = account_connection.facebook_page.page_access_token

        params = {
            'access_token': access_token,
            'platform': 'instagram'  # Specify Instagram platform
        }

        print(f"🚀 Sending Instagram message:")
        print(f"   Instagram Account: @{account_connection.username} (ID: {instagram_account_id})")
        print(f"   Facebook Page ID: {page_id}")
        print(f"   To recipient: {recipient_id}")
        print(f"   Last message from user: {latest_message.timestamp}")
        print(f"   Time since last message: {hours_passed:.1f} hours (must be < 24)")
        print(f"   Message: {message_text}")
        print(f"   URL: {send_url}")
        print(f"   Messaging Type: RESPONSE")
        print(f"   Using Page access token: {access_token[:20]}...")

        response = requests.post(
            send_url,
            json=message_data,
            headers=headers,
            params=params
        )

        print(f"📤 Instagram API Response: {response.status_code} - {response.text}")

        if response.status_code == 200:
            response_data = response.json()
            message_id = response_data.get('message_id')

            # Optionally save the sent message to our database
            try:
                InstagramMessage.objects.create(
                    account_connection=account_connection,
                    message_id=message_id or f"sent_{datetime.now().timestamp()}",
                    sender_id=instagram_account_id,  # Account is the sender
                    sender_username=account_connection.username,
                    message_text=message_text,
                    timestamp=datetime.now(),
                    is_from_business=True
                )
                print(f"✅ Saved sent message to database")
            except Exception as e:
                print(f"⚠️ Failed to save sent message to database: {e}")

            return Response({
                'status': 'sent',
                'message_id': message_id,
                'recipient_id': recipient_id
            })
        else:
            error_data = response.json() if response.content else {}
            error_message = error_data.get('error', {}).get('message', 'Unknown error')

            return Response({
                'error': f'Failed to send message: {error_message}',
                'instagram_error': error_data
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        print(f"❌ Exception in instagram_send_message: {e}")
        return Response({
            'error': f'Failed to send message: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def find_tenant_by_instagram_account_id(instagram_account_id):
    """Find which tenant schema contains the given Instagram account ID"""
    from django.db import connection
    from tenants.models import Tenant
    from tenant_schemas.utils import schema_context

    # Get all tenant schemas
    tenants = Tenant.objects.all()

    for tenant in tenants:
        try:
            # Switch to tenant schema and check if account exists
            with schema_context(tenant.schema_name):
                if InstagramAccountConnection.objects.filter(instagram_account_id=instagram_account_id, is_active=True).exists():
                    return tenant.schema_name
        except Exception as e:
            # Skip tenant if there's an error (e.g., table doesn't exist)
            continue

    return None


@csrf_exempt
@require_http_methods(["GET", "POST"])
def instagram_webhook(request):
    """Handle Instagram webhook events for messages"""
    logger = logging.getLogger(__name__)

    if request.method == 'GET':
        # Webhook verification - Instagram/Facebook sends these parameters
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        # Verify token from settings (same as Facebook)
        verify_token = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_VERIFY_TOKEN', 'echodesk_webhook_token_2024')

        # Verify the mode and token
        if mode == 'subscribe' and token == verify_token:
            # Return the challenge as plain text
            return HttpResponse(challenge, content_type='text/plain')
        else:
            return JsonResponse({
                'error': 'Invalid verify token or mode'
            }, status=403)

    elif request.method == 'POST':
        # Handle webhook events
        try:
            import json
            from tenant_schemas.utils import schema_context

            data = json.loads(request.body)
            logger.info(f"📸 Instagram webhook received: {data}")

            # Instagram webhooks have similar structure to Facebook
            if 'entry' not in data:
                logger.warning("No 'entry' field in Instagram webhook data")
                return JsonResponse({'status': 'received'})

            for entry in data['entry']:
                # Get Instagram account ID from entry
                instagram_account_id = entry.get('id')

                if not instagram_account_id:
                    logger.warning("No Instagram account ID in entry")
                    continue

                # Find which tenant this Instagram account belongs to
                tenant_schema = find_tenant_by_instagram_account_id(instagram_account_id)

                if not tenant_schema:
                    logger.error(f"No tenant found for Instagram account: {instagram_account_id}")
                    continue

                logger.info(f"Processing Instagram webhook for account {instagram_account_id} in tenant: {tenant_schema}")

                # Process webhook within the correct tenant context
                with schema_context(tenant_schema):
                    # Get the Instagram account connection
                    try:
                        account_connection = InstagramAccountConnection.objects.get(
                            instagram_account_id=instagram_account_id,
                            is_active=True
                        )
                    except InstagramAccountConnection.DoesNotExist:
                        logger.error(f"Instagram account connection not found: {instagram_account_id}")
                        continue

                    # Process messaging events
                    if 'messaging' in entry:
                        for message_event in entry['messaging']:
                            if 'message' in message_event:
                                message_data = message_event['message']
                                sender_id = message_event['sender']['id']

                                logger.info(f"📨 Instagram webhook message_event: {message_event}")

                                # Handle echo messages (messages sent by the business)
                                if message_data.get('is_echo'):
                                    logger.info("📤 Processing Instagram echo message to update timestamp")
                                    message_id = message_data.get('mid')

                                    if message_id:
                                        try:
                                            # Update the timestamp of the message we saved when sending
                                            ig_timestamp = message_event.get('timestamp')
                                            if ig_timestamp:
                                                timestamp_dt = convert_facebook_timestamp(ig_timestamp)

                                                updated = InstagramMessage.objects.filter(
                                                    account_connection=account_connection,
                                                    message_id=message_id
                                                ).update(timestamp=timestamp_dt)

                                                if updated > 0:
                                                    logger.info(f"✅ Updated Instagram echo message timestamp to {timestamp_dt}")
                                                else:
                                                    logger.info(f"⚠️ Instagram echo message not found in database: {message_id}")
                                        except Exception as e:
                                            logger.error(f"❌ Failed to update Instagram echo message timestamp: {e}")

                                    continue

                                # Get sender info - fetch from Instagram Graph API
                                sender_username = sender_id  # Use the ID as username by default
                                sender_profile_pic = None

                                # Try to fetch the sender's Instagram username and profile pic
                                if sender_id != instagram_account_id:  # Don't fetch profile for business account itself
                                    try:
                                        # Use Instagram Graph API to get user info
                                        profile_url = f"https://graph.facebook.com/v23.0/{sender_id}"
                                        profile_params = {
                                            'fields': 'username,profile_pic',
                                            'access_token': account_connection.access_token
                                        }
                                        logger.info(f"👤 Fetching Instagram profile for sender {sender_id}")
                                        profile_response = requests.get(profile_url, params=profile_params, timeout=10)

                                        logger.info(f"👤 Instagram profile fetch response: status={profile_response.status_code}")
                                        if profile_response.status_code == 200:
                                            profile_data = profile_response.json()
                                            logger.info(f"👤 Instagram profile data received: {profile_data}")
                                            sender_username = profile_data.get('username', sender_id)
                                            sender_profile_pic = profile_data.get('profile_pic')
                                            logger.info(f"👤 Set sender_username to: {sender_username}")

                                            # Validate URL length to prevent database errors
                                            if sender_profile_pic and len(sender_profile_pic) > 500:
                                                logger.warning(f"Instagram profile pic URL too long ({len(sender_profile_pic)} chars), truncating")
                                                sender_profile_pic = None
                                        else:
                                            error_data = profile_response.json() if profile_response.content else {}
                                            logger.error(f"❌ Failed to fetch Instagram profile for {sender_id}: status={profile_response.status_code}, error={error_data}")

                                    except Exception as e:
                                        logger.error(f"❌ Exception fetching Instagram profile for {sender_id}: {type(e).__name__}: {e}")

                                # Save the message
                                message_id = message_data.get('mid', '')
                                message_text = message_data.get('text', '')

                                # Extract attachment information for Instagram
                                attachment_type = ''
                                attachment_url = None
                                attachments = []

                                if 'attachments' in message_data:
                                    raw_attachments = message_data.get('attachments', [])
                                    for att in raw_attachments:
                                        att_type = att.get('type', '')
                                        payload = att.get('payload', {})
                                        att_url = payload.get('url', '')

                                        attachment_obj = {
                                            'type': att_type,
                                            'url': att_url,
                                        }

                                        # Add sticker_id if present
                                        if payload.get('sticker_id'):
                                            attachment_obj['sticker_id'] = payload.get('sticker_id')

                                        attachments.append(attachment_obj)

                                        # Set primary attachment type and URL (first attachment)
                                        if not attachment_type:
                                            attachment_type = att_type
                                            attachment_url = att_url

                                    logger.info(f"📎 Found {len(attachments)} Instagram attachment(s): {[a['type'] for a in attachments]}")

                                logger.info(f"💾 Saving Instagram message from sender_id: {sender_id}, username: {sender_username}")

                                if message_id and not InstagramMessage.objects.filter(message_id=message_id).exists():
                                    try:
                                        message_obj = InstagramMessage.objects.create(
                                            account_connection=account_connection,
                                            message_id=message_id,
                                            sender_id=sender_id,
                                            sender_username=sender_username,
                                            sender_profile_pic=sender_profile_pic,
                                            message_text=message_text,
                                            attachment_type=attachment_type,
                                            attachment_url=attachment_url,
                                            attachments=attachments,
                                            timestamp=convert_facebook_timestamp(message_event.get('timestamp', 0)),
                                            is_from_business=False
                                        )
                                        logger.info(f"✅ Saved Instagram message from {sender_username}: {message_text[:50] if message_text else f'[{attachment_type}]'}")

                                        # Send WebSocket notification for real-time updates
                                        from django.db import connection
                                        current_schema = getattr(connection, 'schema_name', None)
                                        if current_schema:
                                            ws_message_data = {
                                                'id': message_obj.id,
                                                'message_id': message_obj.message_id,
                                                'sender_id': message_obj.sender_id,
                                                'sender_username': message_obj.sender_username,
                                                'message_text': message_obj.message_text,
                                                'attachment_type': message_obj.attachment_type,
                                                'attachment_url': message_obj.attachment_url,
                                                'attachments': message_obj.attachments,
                                                'timestamp': message_obj.timestamp.isoformat() if message_obj.timestamp else None,
                                                'is_from_business': message_obj.is_from_business,
                                            }
                                            # Conversation ID is the sender_id (the customer)
                                            ws_conversation_id = sender_id
                                            send_websocket_notification(current_schema, ws_message_data, ws_conversation_id)
                                        else:
                                            logger.warning(f"⚠️ WebSocket: Could not determine tenant schema - skipping notification")

                                    except Exception as e:
                                        logger.error(f"❌ Failed to save Instagram message: {e}")

            return JsonResponse({'status': 'received'})

        except Exception as e:
            logger.error(f"Instagram webhook processing failed: {e}")
            return JsonResponse({
                'error': f'Webhook processing failed: {str(e)}'
            }, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ============================================================================
# WEBHOOK DEBUGGING ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def webhook_debug_logs(request):
    """
    Get recent webhook activity logs for debugging.
    Shows last 50 webhook events from the log file.
    """
    import os
    from datetime import datetime

    log_file = os.path.join(os.getcwd(), 'facebook_webhook_log.txt')

    if not os.path.exists(log_file):
        return Response({
            'status': 'no_logs',
            'message': 'No webhook logs found yet. Send a test webhook to create logs.',
            'log_file_path': log_file
        })

    try:
        # Read the last 100 lines of the log file
        with open(log_file, 'r') as f:
            lines = f.readlines()

        # Get last 100 lines
        recent_lines = lines[-100:] if len(lines) > 100 else lines

        # Parse into events
        events = []
        current_event = {}

        for line in recent_lines:
            if '=== WEBHOOK RECEIVED ===' in line:
                if current_event:
                    events.append(current_event)
                current_event = {'raw': ''}

            current_event['raw'] = current_event.get('raw', '') + line

            if line.startswith('Time:'):
                current_event['timestamp'] = line.replace('Time:', '').strip()
            elif line.startswith('Method:'):
                current_event['method'] = line.replace('Method:', '').strip()
            elif line.startswith('Body:'):
                current_event['body'] = line.replace('Body:', '').strip()

        if current_event:
            events.append(current_event)

        return Response({
            'status': 'success',
            'total_events': len(events),
            'events': events[-20:],  # Last 20 events
            'log_file_path': log_file,
            'file_size_bytes': os.path.getsize(log_file)
        })

    except Exception as e:
        return Response({
            'error': f'Failed to read webhook logs: {str(e)}',
            'log_file_path': log_file
        }, status=500)


@api_view(['POST'])
@permission_classes([])  # Public endpoint for testing
def webhook_test_receiver(request):
    """
    Test endpoint to receive and log any webhook data.
    Use this to test if webhooks are reaching your server.

    Usage:
    POST https://api.echodesk.ge/api/social/webhook-test/

    Send any JSON data and it will be logged and returned.
    """
    import json
    from datetime import datetime
    import os

    # Log everything we receive
    log_data = {
        'timestamp': str(datetime.now()),
        'method': request.method,
        'headers': dict(request.headers),
        'query_params': dict(request.GET),
        'body': request.body.decode('utf-8') if request.body else None,
    }

    try:
        log_data['parsed_body'] = json.loads(request.body) if request.body else None
    except:
        log_data['parsed_body'] = 'Could not parse as JSON'

    # Write to test log file
    test_log_file = os.path.join(os.getcwd(), 'webhook_test_log.txt')
    with open(test_log_file, 'a') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"WEBHOOK TEST RECEIVED at {datetime.now()}\n")
        f.write(json.dumps(log_data, indent=2))
        f.write(f"\n{'='*80}\n")

    print(f"✅ Webhook test received and logged to {test_log_file}")
    print(json.dumps(log_data, indent=2))

    return Response({
        'status': 'received',
        'message': 'Webhook test successful! Your data has been logged.',
        'received_data': log_data,
        'logged_to': test_log_file
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def webhook_status(request):
    """
    Check webhook configuration and recent activity.
    Shows webhook URLs, verify tokens, and recent activity.
    """
    import os
    from datetime import datetime

    # Check log files
    fb_log = os.path.join(os.getcwd(), 'facebook_webhook_log.txt')
    test_log = os.path.join(os.getcwd(), 'webhook_test_log.txt')

    fb_log_exists = os.path.exists(fb_log)
    test_log_exists = os.path.exists(test_log)

    fb_log_size = os.path.getsize(fb_log) if fb_log_exists else 0
    test_log_size = os.path.getsize(test_log) if test_log_exists else 0

    # Count webhook events
    fb_event_count = 0
    if fb_log_exists:
        with open(fb_log, 'r') as f:
            fb_event_count = f.read().count('=== WEBHOOK RECEIVED ===')

    test_event_count = 0
    if test_log_exists:
        with open(test_log, 'r') as f:
            test_event_count = f.read().count('WEBHOOK TEST RECEIVED')

    verify_token = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_VERIFY_TOKEN', 'echodesk_webhook_token_2024')

    return Response({
        'status': 'configured',
        'webhook_urls': {
            'facebook': request.build_absolute_uri('/api/social/facebook/webhook/'),
            'instagram': request.build_absolute_uri('/api/social/instagram/webhook/'),
            'test_endpoint': request.build_absolute_uri('/api/social/webhook-test/')
        },
        'verify_token': verify_token,
        'activity': {
            'facebook_webhooks': {
                'total_received': fb_event_count,
                'log_file_exists': fb_log_exists,
                'log_file_size_bytes': fb_log_size,
                'log_file_path': fb_log
            },
            'test_webhooks': {
                'total_received': test_event_count,
                'log_file_exists': test_log_exists,
                'log_file_size_bytes': test_log_size,
                'log_file_path': test_log
            }
        },
        'instructions': {
            'test_webhook': 'Send POST request to /api/social/webhook-test/ with any JSON data',
            'view_logs': 'GET /api/social/webhook-logs/ to see recent webhook activity',
            'facebook_setup': 'Configure webhook in Facebook App → Messenger → Settings',
            'instagram_setup': 'Instagram uses same webhook as Facebook (Pages Messaging API)'
        }
    })


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated, CanManageSocialSettings])
def social_settings(request):
    """Get or update social integration settings for the current tenant"""
    logger = logging.getLogger(__name__)

    try:
        # Get or create settings for this tenant (singleton pattern)
        settings_obj, created = SocialIntegrationSettings.objects.get_or_create(
            defaults={'refresh_interval': 5000}
        )

        if request.method == 'GET':
            serializer = SocialIntegrationSettingsSerializer(settings_obj)
            return Response(serializer.data)

        elif request.method in ['PUT', 'PATCH']:
            partial = request.method == 'PATCH'
            serializer = SocialIntegrationSettingsSerializer(
                settings_obj,
                data=request.data,
                partial=partial
            )

            if serializer.is_valid():
                serializer.save()
                logger.info(f"Updated social integration settings: {serializer.data}")
                return Response(serializer.data)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Error managing social settings: {e}")
        return Response({
            'error': f'Failed to manage settings: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_messages_count(request):
    """
    Get the total count of unread messages across all social platforms.
    Returns counts for Facebook, Instagram, WhatsApp, and total.
    """
    logger = logging.getLogger(__name__)

    try:
        # Count unread Facebook messages (incoming messages not read by staff)
        facebook_unread = FacebookMessage.objects.filter(
            is_from_page=False,  # Messages FROM customers TO the page
            is_read=False
        ).count()

        # Count unread Instagram messages (incoming messages not read by staff)
        instagram_unread = InstagramMessage.objects.filter(
            is_from_business=False,  # Messages FROM customers TO the business
            is_read=False
        ).count()

        # Count unread WhatsApp messages (incoming messages not read by staff)
        whatsapp_unread = WhatsAppMessage.objects.filter(
            is_from_business=False,  # Messages FROM customers TO the business
            is_read=False
        ).count()

        total_unread = facebook_unread + instagram_unread + whatsapp_unread

        return Response({
            'total': total_unread,
            'facebook': facebook_unread,
            'instagram': instagram_unread,
            'whatsapp': whatsapp_unread
        })

    except Exception as e:
        logger.error(f"Error getting unread message count: {e}")
        return Response({
            'error': f'Failed to get unread count: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================
# WHATSAPP BUSINESS API VIEWS
# ===========================

class WhatsAppBusinessAccountViewSet(viewsets.ModelViewSet):
    serializer_class = WhatsAppBusinessAccountSerializer
    permission_classes = [IsAuthenticated, CanManageSocialConnections]

    def get_queryset(self):
        return WhatsAppBusinessAccount.objects.all()  # Tenant schema provides isolation

    def perform_create(self, serializer):
        serializer.save()  # No user assignment needed in multi-tenant setup


class WhatsAppMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WhatsAppMessageSerializer
    permission_classes = [IsAuthenticated, CanViewSocialMessages]

    def get_queryset(self):
        tenant_accounts = WhatsAppBusinessAccount.objects.all()  # All accounts for this tenant
        return WhatsAppMessage.objects.filter(business_account__in=tenant_accounts)


@api_view(['GET'])
@permission_classes([IsAuthenticated, CanManageSocialConnections])
def whatsapp_oauth_start(request):
    """Generate WhatsApp Business OAuth URL"""
    logger = logging.getLogger(__name__)

    try:
        fb_app_id = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_APP_ID')
        if not fb_app_id:
            return Response({
                'error': 'Facebook App ID not configured'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # WhatsApp Embedded Signup config ID
        config_id = '4254308474803749'

        # Use public callback URL since Facebook needs a consistent redirect URI
        redirect_uri = 'https://api.echodesk.ge/api/social/whatsapp/embedded-signup/callback/'

        # Include tenant info in state parameter
        from urllib.parse import quote
        tenant_obj = getattr(request, "tenant", None)

        # Extract tenant schema name from Tenant object or use default
        if tenant_obj and hasattr(tenant_obj, 'schema_name'):
            tenant_name = tenant_obj.schema_name
        elif tenant_obj and hasattr(tenant_obj, 'name'):
            tenant_name = tenant_obj.name
        else:
            tenant_name = "amanati"  # Default fallback

        # Simplified state parameter with just tenant schema
        state_raw = f'tenant={tenant_name}'
        state = quote(state_raw)  # URL encode the state
        logger.info(f"WhatsApp OAuth - Tenant: {tenant_name}")
        logger.info(f"WhatsApp OAuth - State parameter: {state}")

        # WhatsApp Embedded Signup OAuth URL
        oauth_url = (
            f"https://www.facebook.com/v23.0/dialog/oauth?"
            f"client_id={fb_app_id}&"
            f"redirect_uri={quote(redirect_uri)}&"
            f"config_id={config_id}&"
            f"response_type=code&"
            f"scope=whatsapp_business_management,whatsapp_business_messaging&"
            f"state={state}"
        )

        logger.info(f"WhatsApp OAuth URL: {oauth_url}")

        # Return OAuth URL to frontend (similar to Facebook pattern)
        return Response({
            'oauth_url': oauth_url,
            'redirect_uri': redirect_uri,
            'instructions': 'Visit the OAuth URL to connect your WhatsApp Business Account'
        })

    except Exception as e:
        logger.error(f"Failed to generate WhatsApp OAuth URL: {str(e)}")
        return Response({
            'error': f'Failed to generate WhatsApp OAuth URL: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([])  # No authentication required for embedded signup callback
def whatsapp_embedded_signup_callback(request):
    """
    Handle WhatsApp Embedded Signup callback from Facebook OAuth redirect.
    This receives the authorization code and exchanges it for access tokens,
    then retrieves WhatsApp Business Account details and saves them.
    """
    logger.info("📱 WhatsApp Embedded Signup callback received")

    try:
        # Handle both GET (OAuth redirect) and POST (API call)
        if request.method == 'GET':
            # OAuth redirect from Facebook
            code = request.GET.get('code')
            state = request.GET.get('state', '')
            error = request.GET.get('error')
            error_description = request.GET.get('error_description')

            # Parse tenant from state
            tenant_name = None
            if state:
                from urllib.parse import unquote
                decoded_state = unquote(state)
                # State format: "tenant=amanati"
                try:
                    for param in decoded_state.split('&'):
                        if param.startswith('tenant='):
                            tenant_name = param.split('=', 1)[1]
                except (ValueError, IndexError):
                    pass
        else:
            # POST request from API
            code = request.data.get('code')
            tenant_name = request.data.get('tenant')

        # Handle Facebook errors
        if request.method == 'GET' and error:
            error_msg = error_description or error
            logger.error(f"Facebook OAuth error: {error_msg}")
            # Redirect to frontend with error
            frontend_url = f"https://{tenant_name}.echodesk.ge" if tenant_name else "https://amanati.echodesk.ge"
            from urllib.parse import quote_plus
            return redirect(f"{frontend_url}/social/connections?whatsapp_status=error&message={quote_plus(error_msg)}")

        if not code:
            error_msg = 'Authorization code is required'
            if request.method == 'GET':
                frontend_url = f"https://{tenant_name}.echodesk.ge" if tenant_name else "https://amanati.echodesk.ge"
                from urllib.parse import quote_plus
                return redirect(f"{frontend_url}/social/connections?whatsapp_status=error&message={quote_plus(error_msg)}")
            return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        if not tenant_name:
            error_msg = 'Tenant name is required'
            if request.method == 'GET':
                frontend_url = "https://amanati.echodesk.ge"
                from urllib.parse import quote_plus
                return redirect(f"{frontend_url}/social/connections?whatsapp_status=error&message={quote_plus(error_msg)}")
            return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"Processing WhatsApp signup for tenant: {tenant_name}")

        # Exchange code for access token
        fb_app_id = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_APP_ID')
        fb_app_secret = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_APP_SECRET')
        fb_api_version = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_API_VERSION', 'v23.0')

        token_url = f"https://graph.facebook.com/{fb_api_version}/oauth/access_token"
        redirect_uri = 'https://api.echodesk.ge/api/social/whatsapp/embedded-signup/callback/'
        token_params = {
            'client_id': fb_app_id,
            'client_secret': fb_app_secret,
            'redirect_uri': redirect_uri,
            'code': code
        }

        logger.info(f"Exchanging code for access token...")
        logger.info(f"Token URL: {token_url}")
        logger.info(f"Token params: {token_params}")

        # Make the request and log the exact URL being called
        token_response = requests.get(token_url, params=token_params)
        logger.info(f"Actual request URL: {token_response.url}")

        token_data = token_response.json()
        logger.info(f"Token response: {token_data}")

        if 'error' in token_data:
            error_msg = token_data.get('error', {}).get('message', 'Unknown error')
            logger.error(f"Token exchange failed: {error_msg}")
            return Response({
                'error': f'Token exchange failed: {error_msg}'
            }, status=status.HTTP_400_BAD_REQUEST)

        access_token = token_data.get('access_token')
        if not access_token:
            return Response({
                'error': 'No access token received from Facebook'
            }, status=status.HTTP_400_BAD_REQUEST)

        logger.info("✅ Successfully obtained access token")

        # Debug: Check token permissions and extract WABA IDs from granular scopes
        debug_url = f"https://graph.facebook.com/{fb_api_version}/debug_token"
        debug_params = {
            'input_token': access_token,
            'access_token': f"{fb_app_id}|{fb_app_secret}"
        }

        waba_ids = []
        try:
            debug_response = requests.get(debug_url, params=debug_params)
            debug_data = debug_response.json()
            logger.info(f"🔍 Token debug info: {debug_data}")

            if 'data' in debug_data:
                scopes = debug_data['data'].get('scopes', [])
                logger.info(f"📋 Granted permissions: {scopes}")

                # Extract WABA IDs from granular_scopes
                granular_scopes = debug_data['data'].get('granular_scopes', [])
                for scope in granular_scopes:
                    if scope.get('scope') == 'whatsapp_business_management':
                        waba_ids = scope.get('target_ids', [])
                        logger.info(f"✅ Found WABA IDs in granular scopes: {waba_ids}")
                        break

                # Check if required WhatsApp permissions are present
                required_perms = ['whatsapp_business_management', 'whatsapp_business_messaging']
                missing_perms = [p for p in required_perms if p not in scopes]
                if missing_perms:
                    logger.warning(f"⚠️ Missing required permissions: {missing_perms}")
        except Exception as e:
            logger.error(f"Failed to debug token: {str(e)}")

        if not waba_ids:
            return Response({
                'error': 'No WhatsApp Business Account IDs found in token'
            }, status=status.HTTP_404_NOT_FOUND)

        # Fetch details for each WABA directly
        whatsapp_accounts = []
        for waba_id in waba_ids:
            logger.info(f"Fetching details for WABA: {waba_id}")
            waba_url = f"https://graph.facebook.com/{fb_api_version}/{waba_id}"
            waba_params = {
                'access_token': access_token,
                'fields': 'id,name,timezone_id,message_template_namespace'
            }

            waba_response = requests.get(waba_url, params=waba_params)
            waba_data = waba_response.json()

            if 'error' in waba_data:
                error_msg = waba_data.get('error', {}).get('message', 'Unknown error')
                logger.error(f"Failed to fetch WABA {waba_id}: {error_msg}")
                continue

            whatsapp_accounts.append(waba_data)
            logger.info(f"✅ Successfully fetched WABA: {waba_data.get('name', waba_id)}")

        if not whatsapp_accounts:
            return Response({
                'error': 'No WhatsApp Business Accounts found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Process WhatsApp accounts and save to tenant database
        from tenant_schemas.utils import schema_context

        saved_accounts = []
        with schema_context(tenant_name):
            for wa_account in whatsapp_accounts:
                waba_id = wa_account.get('id')

                # Get phone numbers for this WABA
                phone_url = f"https://graph.facebook.com/{fb_api_version}/{waba_id}/phone_numbers"
                phone_params = {
                    'access_token': access_token,
                    'fields': 'id,verified_name,display_phone_number,quality_rating'
                }

                phone_response = requests.get(phone_url, params=phone_params)
                phone_data = phone_response.json()

                phones = phone_data.get('data', [])
                if not phones:
                    logger.warning(f"No phone numbers found for WABA {waba_id}")
                    continue

                # Save each phone number as a separate business account
                for phone in phones:
                    phone_number_id = phone.get('id')
                    display_phone_number = phone.get('display_phone_number', '')
                    verified_name = phone.get('verified_name', wa_account.get('name', 'WhatsApp Business'))
                    quality_rating = phone.get('quality_rating', '')

                    # Create or update WhatsApp Business Account
                    account, created = WhatsAppBusinessAccount.objects.update_or_create(
                        waba_id=waba_id,
                        phone_number_id=phone_number_id,
                        defaults={
                            'business_name': verified_name,
                            'phone_number': display_phone_number.replace(' ', ''),
                            'display_phone_number': display_phone_number,
                            'access_token': access_token,
                            'quality_rating': quality_rating,
                            'is_active': True
                        }
                    )

                    action = "Created" if created else "Updated"
                    logger.info(f"✅ {action} WhatsApp Business Account: {verified_name} ({display_phone_number})")

                    # Register the phone number (required to activate it)
                    try:
                        register_url = f"https://graph.facebook.com/{fb_api_version}/{phone_number_id}/register"
                        register_data = {
                            'messaging_product': 'whatsapp',
                            'pin': '123456'  # Default PIN for 2FA recovery
                        }
                        register_headers = {
                            'Authorization': f'Bearer {access_token}',
                            'Content-Type': 'application/json'
                        }
                        register_response = requests.post(register_url, headers=register_headers, json=register_data)
                        if register_response.status_code == 200:
                            logger.info(f"✅ Registered phone number {phone_number_id}")
                        else:
                            # 500 error usually means already registered, which is fine
                            register_error = register_response.json()
                            if register_response.status_code == 500:
                                logger.info(f"ℹ️ Phone number {phone_number_id} likely already registered")
                            else:
                                logger.warning(f"⚠️ Phone registration response: {register_error}")
                    except Exception as e:
                        logger.error(f"❌ Error registering phone number: {e}")

                    saved_accounts.append({
                        'id': account.id,
                        'waba_id': account.waba_id,
                        'business_name': account.business_name,
                        'phone_number': account.display_phone_number,
                        'quality_rating': account.quality_rating
                    })

                    # Subscribe to webhooks
                    try:
                        webhook_url = f"https://graph.facebook.com/{fb_api_version}/{waba_id}/subscribed_apps"
                        webhook_params = {
                            'access_token': access_token,
                            'subscribed_fields': 'messages,message_template_status_update'
                        }
                        webhook_response = requests.post(webhook_url, params=webhook_params)
                        if webhook_response.status_code == 200:
                            logger.info(f"✅ Subscribed WABA {waba_id} to webhooks with fields: messages, message_template_status_update")
                        else:
                            logger.warning(f"⚠️ Failed to subscribe WABA {waba_id} to webhooks: {webhook_response.json()}")
                    except Exception as e:
                        logger.error(f"❌ Error subscribing to webhooks: {e}")

        if not saved_accounts:
            error_msg = 'No WhatsApp phone numbers could be configured'
            if request.method == 'GET':
                frontend_url = f"https://{tenant_name}.echodesk.ge"
                from urllib.parse import quote_plus
                return redirect(f"{frontend_url}/social/connections?whatsapp_status=error&message={quote_plus(error_msg)}")
            return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        # Success! Redirect back to frontend
        if request.method == 'GET':
            frontend_url = f"https://{tenant_name}.echodesk.ge"
            from urllib.parse import quote_plus
            success_msg = f'Successfully connected {len(saved_accounts)} WhatsApp Business Account(s)'
            return redirect(f"{frontend_url}/social/connections?whatsapp_status=connected&accounts={len(saved_accounts)}&message={quote_plus(success_msg)}")

        return Response({
            'status': 'success',
            'message': f'Successfully connected {len(saved_accounts)} WhatsApp Business Account(s)',
            'accounts': saved_accounts
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"WhatsApp embedded signup callback failed: {e}")
        error_msg = f'Failed to process WhatsApp signup: {str(e)}'
        if request.method == 'GET':
            frontend_url = f"https://{tenant_name if 'tenant_name' in locals() else 'amanati'}.echodesk.ge"
            from urllib.parse import quote_plus
            return redirect(f"{frontend_url}/social/connections?whatsapp_status=error&message={quote_plus(error_msg)}")
        return Response({
            'error': error_msg
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def whatsapp_connection_status(request):
    """Check WhatsApp connection status for current tenant"""
    try:
        accounts = WhatsAppBusinessAccount.objects.filter(is_active=True)
        accounts_data = []

        for account in accounts:
            accounts_data.append({
                'id': account.id,
                'waba_id': account.waba_id,
                'business_name': account.business_name,
                'phone_number': account.display_phone_number or account.phone_number,
                'quality_rating': account.quality_rating,
                'is_active': account.is_active,
                'connected_at': account.created_at.isoformat()
            })

        return Response({
            'connected': accounts.exists(),
            'accounts_count': accounts.count(),
            'accounts': accounts_data
        })
    except Exception as e:
        logger.error(f"Failed to get WhatsApp connection status: {e}")
        return Response({
            'error': f'Failed to get connection status: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, CanManageSocialConnections])
def whatsapp_disconnect(request):
    """Disconnect WhatsApp Business Account(s) and delete all related data"""
    try:
        waba_id = request.data.get('waba_id')

        if waba_id:
            # Disconnect specific account
            account = WhatsAppBusinessAccount.objects.filter(waba_id=waba_id).first()
            if account:
                business_name = account.business_name

                # Count related data before deletion
                messages_count = WhatsAppMessage.objects.filter(business_account=account).count()
                templates_count = WhatsAppMessageTemplate.objects.filter(business_account=account).count()

                # Delete the account (will cascade delete messages and templates)
                account.delete()

                logger.info(
                    f"Deleted WhatsApp Business Account: {business_name} "
                    f"({messages_count} messages, {templates_count} templates)"
                )
                return Response({
                    'status': 'success',
                    'message': f'Disconnected and deleted WhatsApp Business Account: {business_name}',
                    'deleted': {
                        'messages': messages_count,
                        'templates': templates_count
                    }
                })
            else:
                return Response({
                    'error': 'WhatsApp Business Account not found'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            # Disconnect all accounts
            accounts = WhatsAppBusinessAccount.objects.all()
            count = accounts.count()

            # Count all related data
            total_messages = WhatsAppMessage.objects.count()
            total_templates = WhatsAppMessageTemplate.objects.count()

            # Delete all accounts (will cascade delete all messages and templates)
            accounts.delete()

            logger.info(
                f"Deleted all {count} WhatsApp Business Account(s) "
                f"({total_messages} messages, {total_templates} templates)"
            )
            return Response({
                'status': 'success',
                'message': f'Disconnected and deleted {count} WhatsApp Business Account(s)',
                'deleted': {
                    'accounts': count,
                    'messages': total_messages,
                    'templates': total_templates
                }
            })

    except Exception as e:
        logger.error(f"Failed to disconnect WhatsApp: {e}")
        return Response({
            'error': f'Failed to disconnect: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    request=WhatsAppSendMessageSerializer,
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'},
                'whatsapp_message_id': {'type': 'string'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'details': {'type': 'object'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        }
    },
    description="Send a WhatsApp message",
    summary="Send WhatsApp Message"
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, CanSendSocialMessages])
def whatsapp_send_message(request):
    """Send a WhatsApp message"""
    try:
        serializer = WhatsAppSendMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        to_number = serializer.validated_data['to_number']
        message_text = serializer.validated_data['message']
        waba_id = serializer.validated_data['waba_id']

        # Get WhatsApp Business Account
        try:
            account = WhatsAppBusinessAccount.objects.get(waba_id=waba_id, is_active=True)
        except WhatsAppBusinessAccount.DoesNotExist:
            return Response({
                'error': 'WhatsApp Business Account not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)

        # Send message via WhatsApp Cloud API
        fb_api_version = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('WHATSAPP_API_VERSION', 'v23.0')
        send_url = f"https://graph.facebook.com/{fb_api_version}/{account.phone_number_id}/messages"

        message_payload = {
            'messaging_product': 'whatsapp',
            'to': to_number,
            'type': 'text',
            'text': {
                'body': message_text
            }
        }

        headers = {
            'Authorization': f'Bearer {account.access_token}',
            'Content-Type': 'application/json'
        }

        logger.info(f"Sending WhatsApp message to {to_number} from {account.display_phone_number}")
        response = requests.post(send_url, json=message_payload, headers=headers)
        response_data = response.json()

        if response.status_code != 200 or 'error' in response_data:
            error_msg = response_data.get('error', {}).get('message', 'Unknown error')
            logger.error(f"Failed to send WhatsApp message: {error_msg}")
            return Response({
                'error': f'Failed to send message: {error_msg}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Save sent message to database
        message_id = response_data.get('messages', [{}])[0].get('id', '')
        if message_id:
            WhatsAppMessage.objects.create(
                business_account=account,
                message_id=message_id,
                from_number=account.phone_number,
                to_number=to_number,
                message_text=message_text,
                message_type='text',
                timestamp=timezone.now(),
                is_from_business=True,
                status='sent'
            )
            logger.info(f"✅ Saved sent WhatsApp message: {message_id}")

        return Response({
            'status': 'success',
            'message': 'Message sent successfully',
            'message_id': message_id
        })

    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
        return Response({
            'error': f'Failed to send message: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    """Handle WhatsApp webhook events for messages"""
    if request.method == 'GET':
        # Webhook verification
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        verify_token = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('WHATSAPP_VERIFY_TOKEN', 'echodesk_whatsapp_webhook_token_2024')

        if mode == 'subscribe' and token == verify_token:
            logger.info("✅ WhatsApp webhook verified successfully")
            return HttpResponse(challenge, content_type='text/plain')
        else:
            logger.warning(f"❌ WhatsApp webhook verification failed - invalid token")
            return JsonResponse({
                'error': 'Invalid verify token or mode'
            }, status=403)

    elif request.method == 'POST':
        # Handle webhook events
        try:
            import json
            from tenant_schemas.utils import schema_context

            data = json.loads(request.body)
            logger.info(f"📱 WhatsApp webhook received: {json.dumps(data, indent=2)}")

            # Extract phone number ID to determine which tenant
            entry = data.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})
            metadata = value.get('metadata', {})
            phone_number_id = metadata.get('phone_number_id')

            if not phone_number_id:
                logger.error("No phone_number_id found in webhook data")
                return JsonResponse({'status': 'error', 'message': 'No phone_number_id found'}, status=400)

            # Find tenant for this phone number
            tenant_schema = find_tenant_by_whatsapp_phone_number_id(phone_number_id)
            if not tenant_schema:
                logger.error(f"No tenant found for phone_number_id: {phone_number_id}")
                return JsonResponse({'status': 'error', 'message': 'No tenant found'}, status=404)

            logger.info(f"Processing WhatsApp webhook for tenant: {tenant_schema}")

            # Process webhook within tenant context
            with schema_context(tenant_schema):
                # Get business account
                try:
                    account = WhatsAppBusinessAccount.objects.get(
                        phone_number_id=phone_number_id,
                        is_active=True
                    )
                except WhatsAppBusinessAccount.DoesNotExist:
                    logger.error(f"No active WhatsApp Business Account found for phone_number_id: {phone_number_id}")
                    return JsonResponse({'status': 'error', 'message': 'Account not found'}, status=404)

                # Handle messages
                messages = value.get('messages', [])
                for message in messages:
                    message_id = message.get('id')
                    from_number = message.get('from')
                    timestamp = message.get('timestamp', '')
                    message_type = message.get('type', 'text')

                    # Skip if message already exists
                    if WhatsAppMessage.objects.filter(message_id=message_id).exists():
                        logger.info(f"Skipping duplicate message: {message_id}")
                        continue

                    # Extract message content based on type
                    message_text = ''
                    media_url = ''
                    media_mime_type = ''
                    attachments = []

                    if message_type == 'text':
                        message_text = message.get('text', {}).get('body', '')
                    elif message_type == 'image':
                        image_data = message.get('image', {})
                        message_text = image_data.get('caption', '')
                        media_id = image_data.get('id', '')
                        media_mime_type = image_data.get('mime_type', '')
                        # Fetch media URL using WhatsApp API
                        if media_id and account.access_token:
                            try:
                                media_info_url = f"https://graph.facebook.com/v23.0/{media_id}"
                                media_response = requests.get(
                                    media_info_url,
                                    headers={'Authorization': f'Bearer {account.access_token}'},
                                    timeout=10
                                )
                                if media_response.status_code == 200:
                                    media_url = media_response.json().get('url', '')
                                    logger.info(f"📎 Fetched WhatsApp image URL: {media_url[:50]}...")
                            except Exception as e:
                                logger.error(f"Failed to fetch WhatsApp media URL: {e}")
                        attachments.append({
                            'type': 'image',
                            'media_id': media_id,
                            'url': media_url,
                            'mime_type': media_mime_type,
                        })
                    elif message_type == 'video':
                        video_data = message.get('video', {})
                        message_text = video_data.get('caption', '')
                        media_id = video_data.get('id', '')
                        media_mime_type = video_data.get('mime_type', '')
                        if media_id and account.access_token:
                            try:
                                media_info_url = f"https://graph.facebook.com/v23.0/{media_id}"
                                media_response = requests.get(
                                    media_info_url,
                                    headers={'Authorization': f'Bearer {account.access_token}'},
                                    timeout=10
                                )
                                if media_response.status_code == 200:
                                    media_url = media_response.json().get('url', '')
                                    logger.info(f"📎 Fetched WhatsApp video URL")
                            except Exception as e:
                                logger.error(f"Failed to fetch WhatsApp media URL: {e}")
                        attachments.append({
                            'type': 'video',
                            'media_id': media_id,
                            'url': media_url,
                            'mime_type': media_mime_type,
                        })
                    elif message_type == 'document':
                        doc_data = message.get('document', {})
                        message_text = doc_data.get('filename', '')
                        media_id = doc_data.get('id', '')
                        media_mime_type = doc_data.get('mime_type', '')
                        if media_id and account.access_token:
                            try:
                                media_info_url = f"https://graph.facebook.com/v23.0/{media_id}"
                                media_response = requests.get(
                                    media_info_url,
                                    headers={'Authorization': f'Bearer {account.access_token}'},
                                    timeout=10
                                )
                                if media_response.status_code == 200:
                                    media_url = media_response.json().get('url', '')
                            except Exception as e:
                                logger.error(f"Failed to fetch WhatsApp media URL: {e}")
                        attachments.append({
                            'type': 'document',
                            'media_id': media_id,
                            'url': media_url,
                            'mime_type': media_mime_type,
                            'filename': doc_data.get('filename', ''),
                        })
                    elif message_type == 'audio':
                        audio_data = message.get('audio', {})
                        media_id = audio_data.get('id', '')
                        media_mime_type = audio_data.get('mime_type', '')
                        if media_id and account.access_token:
                            try:
                                media_info_url = f"https://graph.facebook.com/v23.0/{media_id}"
                                media_response = requests.get(
                                    media_info_url,
                                    headers={'Authorization': f'Bearer {account.access_token}'},
                                    timeout=10
                                )
                                if media_response.status_code == 200:
                                    media_url = media_response.json().get('url', '')
                                    logger.info(f"📎 Fetched WhatsApp audio URL")
                            except Exception as e:
                                logger.error(f"Failed to fetch WhatsApp media URL: {e}")
                        attachments.append({
                            'type': 'audio',
                            'media_id': media_id,
                            'url': media_url,
                            'mime_type': media_mime_type,
                        })
                    elif message_type == 'sticker':
                        sticker_data = message.get('sticker', {})
                        media_id = sticker_data.get('id', '')
                        media_mime_type = sticker_data.get('mime_type', 'image/webp')
                        if media_id and account.access_token:
                            try:
                                media_info_url = f"https://graph.facebook.com/v23.0/{media_id}"
                                media_response = requests.get(
                                    media_info_url,
                                    headers={'Authorization': f'Bearer {account.access_token}'},
                                    timeout=10
                                )
                                if media_response.status_code == 200:
                                    media_url = media_response.json().get('url', '')
                                    logger.info(f"📎 Fetched WhatsApp sticker URL")
                            except Exception as e:
                                logger.error(f"Failed to fetch WhatsApp media URL: {e}")
                        attachments.append({
                            'type': 'sticker',
                            'media_id': media_id,
                            'url': media_url,
                            'mime_type': media_mime_type,
                        })

                    # Get contact name
                    contacts = value.get('contacts', [])
                    contact_name = ''
                    if contacts:
                        profile = contacts[0].get('profile', {})
                        contact_name = profile.get('name', '')

                    # Save message
                    message_timestamp = datetime.fromtimestamp(int(timestamp), tz=timezone.utc) if timestamp else timezone.now()

                    message_obj = WhatsAppMessage.objects.create(
                        business_account=account,
                        message_id=message_id,
                        from_number=from_number,
                        to_number=account.phone_number,
                        contact_name=contact_name,
                        message_text=message_text,
                        message_type=message_type,
                        media_url=media_url,
                        media_mime_type=media_mime_type,
                        attachments=attachments,
                        timestamp=message_timestamp,
                        is_from_business=False,
                        status='delivered',
                        is_delivered=True,
                        delivered_at=timezone.now()
                    )

                    logger.info(f"✅ Saved WhatsApp message from {contact_name or from_number}: {message_text[:50] if message_text else f'[{message_type}]'}")

                    # Send WebSocket notification
                    ws_message_data = {
                        'id': message_obj.id,
                        'message_id': message_obj.message_id,
                        'from_number': message_obj.from_number,
                        'contact_name': message_obj.contact_name,
                        'message_text': message_obj.message_text,
                        'message_type': message_obj.message_type,
                        'media_url': message_obj.media_url,
                        'attachments': message_obj.attachments,
                        'timestamp': message_obj.timestamp.isoformat(),
                        'is_from_business': message_obj.is_from_business,
                    }
                    send_websocket_notification(tenant_schema, ws_message_data, from_number)

                # Handle message status updates
                statuses = value.get('statuses', [])
                for status_update in statuses:
                    message_id = status_update.get('id')
                    status_value = status_update.get('status')  # sent, delivered, read, failed
                    timestamp_value = status_update.get('timestamp', '')

                    # Update message status
                    try:
                        message_obj = WhatsAppMessage.objects.get(message_id=message_id)
                        message_obj.status = status_value

                        if status_value == 'delivered':
                            message_obj.is_delivered = True
                            message_obj.delivered_at = datetime.fromtimestamp(int(timestamp_value), tz=timezone.utc) if timestamp_value else timezone.now()
                        elif status_value == 'read':
                            message_obj.is_read = True
                            message_obj.read_at = datetime.fromtimestamp(int(timestamp_value), tz=timezone.utc) if timestamp_value else timezone.now()
                        elif status_value == 'failed':
                            error_info = status_update.get('errors', [{}])[0]
                            message_obj.error_message = error_info.get('message', 'Failed to deliver')

                        message_obj.save()
                        logger.info(f"✅ Updated WhatsApp message status: {message_id} -> {status_value}")
                    except WhatsAppMessage.DoesNotExist:
                        logger.warning(f"Message not found for status update: {message_id}")

            return JsonResponse({'status': 'success'})

        except Exception as e:
            logger.error(f"WhatsApp webhook processing failed: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


# ==================== WHATSAPP TEMPLATE MANAGEMENT ====================

@extend_schema(
    summary="List WhatsApp message templates",
    description="Fetch all message templates for a WhatsApp Business Account from the database and optionally sync from Meta",
    responses={200: WhatsAppMessageTemplateSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, CanManageSocialConnections])
def whatsapp_list_templates(request, waba_id):
    """List all WhatsApp message templates for a given WABA"""
    tenant_schema = request.tenant.schema_name

    with schema_context(tenant_schema):
        try:
            # Get WABA
            waba = WhatsAppBusinessAccount.objects.get(waba_id=waba_id)

            # Get templates from database
            templates = WhatsAppMessageTemplate.objects.filter(business_account=waba)

            serializer = WhatsAppMessageTemplateSerializer(templates, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except WhatsAppBusinessAccount.DoesNotExist:
            return Response({
                'error': 'WhatsApp Business Account not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error listing WhatsApp templates: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Sync WhatsApp templates from Meta",
    description="Fetch all templates from Meta's API and sync them to the database",
    responses={200: WhatsAppMessageTemplateSerializer(many=True)}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, CanManageSocialConnections])
def whatsapp_sync_templates(request, waba_id):
    """Sync templates from Meta API to database"""
    tenant_schema = request.tenant.schema_name

    with schema_context(tenant_schema):
        try:
            # Get WABA
            waba = WhatsAppBusinessAccount.objects.get(waba_id=waba_id)

            # Fetch templates from Meta
            fb_api_version = settings.FACEBOOK_APP_VERSION
            templates_url = f"https://graph.facebook.com/{fb_api_version}/{waba_id}/message_templates"
            params = {
                'access_token': waba.access_token,
                'fields': 'id,name,language,status,category,components',
                'limit': 100
            }

            response = requests.get(templates_url, params=params)

            if response.status_code != 200:
                return Response({
                    'error': 'Failed to fetch templates from Meta',
                    'details': response.json()
                }, status=response.status_code)

            meta_templates = response.json().get('data', [])

            # Sync to database
            synced_count = 0
            for meta_template in meta_templates:
                template_obj, created = WhatsAppMessageTemplate.objects.update_or_create(
                    business_account=waba,
                    name=meta_template['name'],
                    language=meta_template['language'],
                    defaults={
                        'template_id': meta_template['id'],
                        'status': meta_template['status'],
                        'category': meta_template.get('category', 'UTILITY'),
                        'components': meta_template.get('components', []),
                        'created_by': request.user
                    }
                )
                synced_count += 1

            # Get all templates after sync
            templates = WhatsAppMessageTemplate.objects.filter(business_account=waba)
            serializer = WhatsAppMessageTemplateSerializer(templates, many=True)

            return Response({
                'synced': synced_count,
                'templates': serializer.data
            }, status=status.HTTP_200_OK)

        except WhatsAppBusinessAccount.DoesNotExist:
            return Response({
                'error': 'WhatsApp Business Account not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error syncing WhatsApp templates: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Create WhatsApp message template",
    description="Create a new message template via Meta's API",
    request=WhatsAppTemplateCreateSerializer,
    responses={201: WhatsAppMessageTemplateSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, CanManageSocialConnections])
def whatsapp_create_template(request):
    """Create a new WhatsApp message template"""
    tenant_schema = request.tenant.schema_name

    with schema_context(tenant_schema):
        serializer = WhatsAppTemplateCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            waba_id = serializer.validated_data['waba_id']
            waba = WhatsAppBusinessAccount.objects.get(waba_id=waba_id)

            # Create template via Meta API
            fb_api_version = settings.FACEBOOK_APP_VERSION
            create_url = f"https://graph.facebook.com/{fb_api_version}/{waba_id}/message_templates"

            payload = {
                'name': serializer.validated_data['name'],
                'language': serializer.validated_data['language'],
                'category': serializer.validated_data['category'],
                'components': serializer.validated_data['components']
            }

            headers = {
                'Authorization': f'Bearer {waba.access_token}',
                'Content-Type': 'application/json'
            }

            response = requests.post(create_url, json=payload, headers=headers)

            if response.status_code not in [200, 201]:
                return Response({
                    'error': 'Failed to create template in Meta',
                    'details': response.json()
                }, status=response.status_code)

            meta_response = response.json()

            # Save to database
            template = WhatsAppMessageTemplate.objects.create(
                business_account=waba,
                template_id=meta_response.get('id', ''),
                name=serializer.validated_data['name'],
                language=serializer.validated_data['language'],
                status='PENDING',  # New templates start as pending
                category=serializer.validated_data['category'],
                components=serializer.validated_data['components'],
                created_by=request.user
            )

            response_serializer = WhatsAppMessageTemplateSerializer(template)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except WhatsAppBusinessAccount.DoesNotExist:
            return Response({
                'error': 'WhatsApp Business Account not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error creating WhatsApp template: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Delete WhatsApp message template",
    description="Delete a message template from both Meta and database",
    responses={200: {'description': 'Template deleted successfully'}}
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, CanManageSocialConnections])
def whatsapp_delete_template(request, template_id):
    """Delete a WhatsApp message template"""
    tenant_schema = request.tenant.schema_name

    with schema_context(tenant_schema):
        try:
            template = WhatsAppMessageTemplate.objects.get(id=template_id)
            waba = template.business_account

            # Delete from Meta if template_id exists
            if template.template_id:
                fb_api_version = settings.FACEBOOK_APP_VERSION
                delete_url = f"https://graph.facebook.com/{fb_api_version}/{waba.waba_id}/message_templates"
                params = {
                    'access_token': waba.access_token,
                    'name': template.name
                }

                response = requests.delete(delete_url, params=params)

                if response.status_code not in [200, 204]:
                    logger.warning(f"Failed to delete template from Meta: {response.json()}")
                    # Continue with database deletion even if Meta deletion fails

            # Delete from database
            template.delete()

            return Response({
                'message': 'Template deleted successfully'
            }, status=status.HTTP_200_OK)

        except WhatsAppMessageTemplate.DoesNotExist:
            return Response({
                'error': 'Template not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error deleting WhatsApp template: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Send WhatsApp template message",
    description="Send a message using a WhatsApp message template with parameters",
    request=WhatsAppTemplateSendSerializer,
    responses={200: WhatsAppMessageSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, CanSendSocialMessages])
def whatsapp_send_template_message(request):
    """Send a WhatsApp message using a template"""
    tenant_schema = request.tenant.schema_name

    with schema_context(tenant_schema):
        serializer = WhatsAppTemplateSendSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            waba_id = serializer.validated_data['waba_id']
            template_id = serializer.validated_data['template_id']
            to_number = serializer.validated_data['to_number']
            parameters = serializer.validated_data.get('parameters', {})

            # Get WABA and template
            waba = WhatsAppBusinessAccount.objects.get(waba_id=waba_id)
            template = WhatsAppMessageTemplate.objects.get(id=template_id)

            # Check template status
            if template.status != 'APPROVED':
                return Response({
                    'error': f'Template status is {template.status}. Only APPROVED templates can be sent.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Build template components with parameters
            components = []
            for component in template.components:
                if component.get('type') == 'BODY' and parameters:
                    # Extract parameter placeholders from body text
                    body_text = component.get('text', '')
                    import re
                    param_placeholders = re.findall(r'\{\{(\d+)\}\}', body_text)

                    # Build parameters array
                    body_parameters = []
                    for i, placeholder in enumerate(param_placeholders, 1):
                        param_key = f'param{i}' if f'param{i}' in parameters else list(parameters.keys())[i-1] if len(parameters) >= i else None
                        if param_key and param_key in parameters:
                            body_parameters.append({
                                'type': 'text',
                                'text': str(parameters[param_key])
                            })

                    if body_parameters:
                        components.append({
                            'type': 'body',
                            'parameters': body_parameters
                        })

            # Send via WhatsApp Cloud API
            fb_api_version = settings.FACEBOOK_APP_VERSION
            send_url = f"https://graph.facebook.com/{fb_api_version}/{waba.phone_number_id}/messages"

            message_payload = {
                'messaging_product': 'whatsapp',
                'to': to_number.lstrip('+'),
                'type': 'template',
                'template': {
                    'name': template.name,
                    'language': {
                        'code': template.language
                    }
                }
            }

            if components:
                message_payload['template']['components'] = components

            headers = {
                'Authorization': f'Bearer {waba.access_token}',
                'Content-Type': 'application/json'
            }

            response = requests.post(send_url, json=message_payload, headers=headers)

            if response.status_code != 200:
                return Response({
                    'error': 'Failed to send template message',
                    'details': response.json()
                }, status=response.status_code)

            meta_response = response.json()
            message_id = meta_response.get('messages', [{}])[0].get('id', '')

            # Save to database
            message = WhatsAppMessage.objects.create(
                business_account=waba,
                message_id=message_id,
                from_number=waba.phone_number,
                to_number=to_number,
                message_text=f"Template: {template.name}",
                message_type='template',
                template=template,
                template_parameters=parameters,
                timestamp=timezone.now(),
                is_from_business=True,
                status='sent'
            )

            response_serializer = WhatsAppMessageSerializer(message)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except WhatsAppBusinessAccount.DoesNotExist:
            return Response({
                'error': 'WhatsApp Business Account not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except WhatsAppMessageTemplate.DoesNotExist:
            return Response({
                'error': 'Template not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error sending WhatsApp template message: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)