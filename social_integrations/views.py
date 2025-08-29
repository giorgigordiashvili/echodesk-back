import os
import requests
import logging
from datetime import datetime
from urllib.parse import urlencode, quote_plus
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth.decorators import login_required
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
    FacebookPageConnection, FacebookMessage
)
from .serializers import (
    FacebookPageConnectionSerializer, FacebookMessageSerializer, FacebookSendMessageSerializer
)


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


class FacebookPageConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = FacebookPageConnectionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return FacebookPageConnection.objects.all()  # Tenant schema provides isolation
    
    def perform_create(self, serializer):
        serializer.save()  # No user assignment needed in multi-tenant setup


class FacebookMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FacebookMessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        tenant_pages = FacebookPageConnection.objects.all()  # All pages for this tenant
        return FacebookMessage.objects.filter(page_connection__in=tenant_pages)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
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
        
        # Facebook OAuth URL for business pages with business_management permission
        oauth_url = (
            f"https://www.facebook.com/v23.0/dialog/oauth?"
            f"client_id={fb_app_id}&"
            f"redirect_uri={quote(redirect_uri)}&"
            f"scope=business_management,pages_show_list,pages_manage_metadata,pages_messaging,pages_read_engagement,public_profile,email&"
            f"state={state}&"
            f"response_type=code&"
            f"auth_type=rerequest"
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
            'redirect_uri': request.build_absolute_uri(reverse('social_integrations:facebook_oauth_callback')),
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
                else:
                    logger.warning(f"⚠️ Skipped page with missing data: {page}")
        
        # Return success response with redirect to tenant frontend
        success_msg = f"Successfully connected {saved_pages} Facebook page(s)"
        logger.info(f"Facebook OAuth completed successfully: {saved_pages} pages saved")
        
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
        pages = FacebookPageConnection.objects.all()  # All pages for this tenant
        pages_data = []
        
        for page in pages:
            pages_data.append({
                'id': page.id,
                'page_id': page.page_id,
                'page_name': page.page_name,
                'is_active': page.is_active,
                'connected_at': page.created_at.isoformat()
            })
        
        return Response({
            'connected': pages.exists(),
            'pages_count': pages.count(),
            'pages': pages_data
        })
    except Exception as e:
        return Response({
            'error': f'Failed to get connection status: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def facebook_disconnect(request):
    """Disconnect Facebook integration for current tenant"""
    try:
        logger = logging.getLogger(__name__)
        
        # Get count before deletion for response
        pages_to_delete = FacebookPageConnection.objects.all()  # All pages for this tenant
        page_count = pages_to_delete.count()
        page_names = list(pages_to_delete.values_list('page_name', flat=True))
        
        if page_count == 0:
            return Response({
                'status': 'no_pages',
                'message': 'No Facebook pages found to disconnect'
            })
        
        # Delete Facebook messages
        facebook_message_count = 0
        for page in pages_to_delete:
            messages_deleted = FacebookMessage.objects.filter(
                page_connection=page
            ).count()
            FacebookMessage.objects.filter(page_connection=page).delete()
            facebook_message_count += messages_deleted
        
        # Delete Facebook page connections
        pages_to_delete.delete()
        
        logger.info(f"✅ Facebook disconnect completed:")
        logger.info(f"   - Facebook pages deleted: {page_count}")
        logger.info(f"   - Facebook messages deleted: {facebook_message_count}")
        
        return Response({
            'status': 'disconnected',
            'facebook_pages_deleted': page_count,
            'facebook_messages_deleted': facebook_message_count,
            'deleted_pages': page_names,
            'message': f'Permanently removed {page_count} Facebook page(s) and {facebook_message_count} messages'
        })
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to disconnect Facebook: {e}")
        return Response({
            'error': f'Failed to disconnect: {str(e)}'
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
@permission_classes([IsAuthenticated])
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
        
        print(f"🚀 Sending Facebook message:")
        print(f"   Page: {page_connection.page_name}")
        print(f"   To: {recipient_id}")
        print(f"   Message: {message_text}")
        
        response = requests.post(
            send_url,
            json=message_data,
            headers=headers,
            params=params
        )
        
        print(f"📤 Facebook API Response: {response.status_code} - {response.text}")
        
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
                'facebook_error': error_data
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        print(f"❌ Exception in facebook_send_message: {e}")
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
            
            print(f"🔵 WEBHOOK POST PROCESSING STARTED at {datetime.now()}")
            
            # Simple file logging to verify we're receiving callbacks
            try:
                import os
                log_file = os.path.join(os.getcwd(), 'facebook_webhook_log.txt')
                with open(log_file, 'a') as f:
                    f.write(f"\n=== WEBHOOK RECEIVED ===\n")
                    f.write(f"Time: {datetime.now()}\n")
                    f.write(f"Method: {request.method}\n")
                    f.write(f"Headers: {dict(request.headers)}\n")
                    f.write(f"Body: {request.body.decode('utf-8')}\n")
                    f.write("=" * 50 + "\n")
                print(f"WEBHOOK: Logged to {log_file}")
            except Exception as e:
                print(f"WEBHOOK: Failed to write to log file: {e}")
                # Also try to write to stdout as fallback
                print(f"WEBHOOK RECEIVED at {datetime.now()}: {request.body.decode('utf-8')}")
            
            data = json.loads(request.body)
            print(f"🔍 PARSED WEBHOOK DATA: {data}")
            logger.info(f"Webhook received data: {data}")
            
            # First, extract page_id to determine which tenant to use
            page_id = None
            print(f"🔍 EXTRACTING PAGE_ID from data: {data}")
            
            # Handle Facebook Developer Console test format
            if 'field' in data and 'value' in data and data['field'] == 'messages':
                test_value = data['value']
                # Try multiple places where Facebook might put the page ID
                page_id = (test_value.get('metadata', {}).get('page_id') or 
                          test_value.get('page_id') or 
                          test_value.get('recipient', {}).get('id'))
                print(f"🔍 TEST FORMAT - Extracted page_id: {page_id}")
            
            # Handle standard webhook format (real messages)  
            elif 'entry' in data and len(data['entry']) > 0:
                page_id = data['entry'][0].get('id')
                print(f"🔍 STANDARD FORMAT - Extracted page_id: {page_id}")
            
            if not page_id:
                print(f"❌ NO PAGE_ID FOUND in webhook data: {data}")
                logger.error("No page_id found in webhook data")
                return JsonResponse({'error': 'No page_id found'}, status=400)
            
            # Find which tenant this page belongs to
            print(f"🔍 FINDING TENANT for page_id: {page_id}")
            tenant_schema = find_tenant_by_page_id(page_id)
            print(f"🔍 TENANT RESULT: {tenant_schema}")
            
            if not tenant_schema:
                print(f"❌ NO TENANT FOUND for page_id: {page_id}")
                logger.error(f"No tenant found for page_id: {page_id}")
                return JsonResponse({'error': f'No tenant found for page_id: {page_id}'}, status=404)
            
            logger.info(f"Processing webhook for page_id {page_id} in tenant: {tenant_schema}")
            
            # Enhanced debug logging
            logger.info(f"🔍 WEBHOOK DEBUG - Data structure: {data}")
            logger.info(f"🔍 WEBHOOK DEBUG - Looking for tenant with page_id: {page_id}")
            logger.info(f"🔍 WEBHOOK DEBUG - Found tenant: {tenant_schema}")
            
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
                    
                    logger.info(f"Processing test message - page_id: {page_id}, sender_id: {sender_id}")
                    logger.info(f"Test value structure: {test_value}")
                    
                    # Log to file for debugging
                    try:
                        import os
                        log_file = os.path.join(os.getcwd(), 'facebook_webhook_log.txt')
                        with open(log_file, 'a') as f:
                            f.write(f"\n=== FACEBOOK TEST MESSAGE ===\n")
                            f.write(f"Time: {datetime.now()}\n")
                            f.write(f"Tenant: {tenant_schema}\n")
                            f.write(f"Page ID: {page_id}\n")
                            f.write(f"Sender ID: {sender_id}\n")
                            f.write(f"Message Data: {message_data}\n")
                            f.write(f"Full Test Value: {test_value}\n")
                            f.write("=" * 50 + "\n")
                    except Exception as log_error:
                        logger.error(f"Failed to write test log: {log_error}")
                    
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
                            
                            logger.info(f"Processing message - ID: {message_id}, Text: {message_text}")
                            
                            # Skip if this is an echo (message sent by the page)
                            if message_data.get('is_echo'):
                                logger.info("Skipping echo message")
                                return JsonResponse({'status': 'received'})
                            
                            # For test messages, use simple sender info
                            sender_name = f"Test User {sender_id}"
                            profile_pic_url = None
                            
                            # Save the message (avoid duplicates)
                            if message_id and not FacebookMessage.objects.filter(message_id=message_id).exists():
                                try:
                                    # Debug field lengths before saving
                                    print(f"🔍 FIELD LENGTHS DEBUG:")
                                    print(f"   message_id: '{message_id}' (length: {len(message_id)})")
                                    print(f"   sender_id: '{sender_id}' (length: {len(sender_id)})")
                                    print(f"   sender_name: '{sender_name}' (length: {len(sender_name)})")
                                    print(f"   message_text: '{message_text}' (length: {len(message_text)})")
                                    if profile_pic_url:
                                        print(f"   profile_pic_url: '{profile_pic_url}' (length: {len(profile_pic_url)})")
                                    
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
                                    print(f"✅ SUCCESSFULLY SAVED MESSAGE TO DATABASE - ID: {message_obj.id}, Text: '{message_text}'")
                                    logger.info(f"✅ SUCCESSFULLY SAVED MESSAGE TO DATABASE - ID: {message_obj.id}, Text: '{message_text}'")
                                    
                                    # WebSocket notifications removed - using simple polling instead
                                    print(f"📧 Message saved successfully. Frontend will pick it up on next refresh.")
                                    
                                    # Write to file for debugging
                                    try:
                                        with open(log_file, 'a') as f:
                                            f.write(f"✅ SAVED TO DATABASE: Message ID {message_obj.id} - '{message_text}'\n")
                                    except:
                                        pass
                                            
                                except Exception as e:
                                    print(f"❌ FAILED TO SAVE MESSAGE TO DATABASE: {e}")
                                    print(f"❌ Error details: {e}")
                                    logger.error(f"❌ FAILED TO SAVE MESSAGE TO DATABASE: {e}")
                                    try:
                                        with open(log_file, 'a') as f:
                                            f.write(f"❌ DATABASE SAVE FAILED: {e}\n")
                                    except:
                                        pass
                            else:
                                reason = "No message_id provided" if not message_id else f"Message {message_id} already exists"
                                logger.info(f"⚠️ SKIPPED SAVING MESSAGE: {reason}")
                                try:
                                    with open(log_file, 'a') as f:
                                        f.write(f"⚠️ SKIPPED: {reason}\n")
                                except:
                                    pass
                            
                        except FacebookPageConnection.DoesNotExist:
                            logger.warning(f"No active page connection found for page_id: {page_id}")
                            # List available connections for debugging
                            all_connections = FacebookPageConnection.objects.filter(is_active=True)
                            logger.warning(f"Available connections: {[(conn.page_id, conn.page_name) for conn in all_connections]}")
                            
                            # Log to file for debugging
                            try:
                                import os
                                log_file = os.path.join(os.getcwd(), 'facebook_webhook_log.txt')
                                with open(log_file, 'a') as f:
                                    f.write(f"\n❌ NO PAGE CONNECTION FOUND ❌\n")
                                    f.write(f"Time: {datetime.now()}\n")
                                    f.write(f"Looking for page_id: {page_id}\n")
                                    f.write(f"Available pages: {[(conn.page_id, conn.page_name) for conn in all_connections]}\n")
                                    f.write(f"Test value structure: {test_value}\n")
                                    f.write("=" * 50 + "\n")
                            except Exception as log_error:
                                logger.error(f"Failed to write error log: {log_error}")
                            
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
                            print(f"🔍 DEBUG: Processing {len(entry['messaging'])} messaging events for page {page_id}")
                            for message_event in entry['messaging']:
                                logger.info(f"🔍 Processing message event: {message_event}")
                                
                                if 'message' in message_event:
                                    message_data = message_event['message']
                                    sender_id = message_event['sender']['id']
                                    logger.info(f"📝 Message from {sender_id}: {message_data}")
                                    
                                    # Skip if this is an echo (message sent by the page)
                                    if message_data.get('is_echo'):
                                        logger.info("⏭️ Skipping echo message")
                                        continue
                                    
                                    # Get sender profile information including profile picture
                                    sender_name = 'Unknown'
                                    profile_pic_url = None
                                    
                                    if sender_id != page_id:  # Don't fetch profile for page itself
                                        try:
                                            # Use the page access token to get user profile
                                            profile_url = f"https://graph.facebook.com/v23.0/{sender_id}"
                                            profile_params = {
                                                'fields': 'first_name,last_name,profile_pic',
                                                'access_token': page_connection.page_access_token
                                            }
                                            profile_response = requests.get(profile_url, params=profile_params, timeout=10)
                                            
                                            if profile_response.status_code == 200:
                                                profile_data = profile_response.json()
                                                first_name = profile_data.get('first_name', '')
                                                last_name = profile_data.get('last_name', '')
                                                sender_name = f"{first_name} {last_name}".strip() or 'Unknown'
                                                profile_pic_url = profile_data.get('profile_pic')
                                                
                                                # Validate URL length to prevent database errors
                                                if profile_pic_url and len(profile_pic_url) > 500:
                                                    logger.warning(f"Profile pic URL too long ({len(profile_pic_url)} chars), truncating: {profile_pic_url[:50]}...")
                                                    profile_pic_url = None  # Don't save extremely long URLs
                                            
                                        except Exception as e:
                                            logger.error(f"Failed to fetch profile for {sender_id}: {e}")
                                    
                                    # Save the message (avoid duplicates)
                                    message_id = message_data.get('mid', '')
                                    message_text = message_data.get('text', '')
                                    logger.info(f"💾 Attempting to save message: ID={message_id}, Text='{message_text}'")
                                    
                                    # Enhanced debugging - check field lengths
                                    print(f"🔍 FIELD LENGTH DEBUG:")
                                    print(f"   message_id length: {len(message_id)} chars - '{message_id}'")
                                    print(f"   sender_id length: {len(sender_id)} chars - '{sender_id}'")
                                    print(f"   sender_name length: {len(sender_name)} chars - '{sender_name}'")
                                    print(f"   message_text length: {len(message_text)} chars - '{message_text}'")
                                    print(f"   page_id length: {len(str(page_id))} chars - '{page_id}'")
                                    if profile_pic_url:
                                        print(f"   profile_pic_url length: {len(profile_pic_url)} chars - '{profile_pic_url[:50]}...'")
                                    else:
                                        print(f"   profile_pic_url: None")
                                    
                                    if message_id and not FacebookMessage.objects.filter(message_id=message_id).exists():
                                        try:
                                            print(f"🔄 Creating FacebookMessage object...")
                                            message_obj = FacebookMessage.objects.create(
                                                page_connection=page_connection,
                                                message_id=message_id,
                                                sender_id=sender_id,
                                                sender_name=sender_name,
                                                message_text=message_text,
                                                timestamp=convert_facebook_timestamp(message_event.get('timestamp', 0)),
                                                is_from_page=(sender_id == page_id),
                                                profile_pic_url=profile_pic_url
                                            )
                                            logger.info(f"✅ SUCCESSFULLY SAVED MESSAGE TO DATABASE - ID: {message_obj.id}, Text: '{message_text}'")
                                            print(f"✅ SUCCESS: Message saved with ID {message_obj.id}")
                                            
                                            # WebSocket notifications removed - using simple polling instead
                                            print(f"📧 Message saved successfully. Frontend will pick it up on next refresh.")
                                            
                                        except Exception as e:
                                            logger.error(f"❌ FAILED TO SAVE MESSAGE TO DATABASE: {e}")
                                            logger.error(f"❌ Error details: {str(e)}")
                                            print(f"❌ SAVE FAILED: {e}")
                                            print(f"❌ Error type: {type(e).__name__}")
                                            
                                            # Log to file for debugging
                                            try:
                                                import os
                                                log_file = os.path.join(os.getcwd(), 'facebook_webhook_log.txt')
                                                with open(log_file, 'a') as f:
                                                    f.write(f"\n❌ STANDARD FORMAT SAVE FAILED ❌\n")
                                                    f.write(f"Time: {datetime.now()}\n")
                                                    f.write(f"Error: {e}\n")
                                                    f.write(f"Error type: {type(e).__name__}\n")
                                                    f.write(f"Page ID: {page_id}\n")
                                                    f.write(f"Message ID: {message_id}\n")
                                                    f.write(f"Sender ID: {sender_id}\n")
                                                    f.write(f"Message text: {message_text}\n")
                                                    f.write("=" * 50 + "\n")
                                            except Exception as log_error:
                                                logger.error(f"Failed to write error log: {log_error}")
                                    else:
                                        if not message_id:
                                            logger.warning(f"⚠️ No message_id provided, skipping save")
                                        else:
                                            logger.warning(f"⚠️ Message {message_id} already exists, skipping save")
                                else:
                                    logger.info(f"ℹ️ Message event has no 'message' field: {message_event}")
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