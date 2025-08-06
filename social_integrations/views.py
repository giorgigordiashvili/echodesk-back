import os
import requests
from datetime import datetime
from django.conf import settings
from django.contrib.auth.decorators import login_required
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
from .models import (
    FacebookPageConnection, FacebookMessage, 
    InstagramAccountConnection, InstagramMessage,
    WhatsAppBusinessConnection, WhatsAppMessage
)
from .serializers import (
    FacebookPageConnectionSerializer, FacebookMessageSerializer, 
    InstagramAccountConnectionSerializer, InstagramMessageSerializer,
    WhatsAppBusinessConnectionSerializer, WhatsAppMessageSerializer
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
        return FacebookPageConnection.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class FacebookMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FacebookMessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user_pages = FacebookPageConnection.objects.filter(user=self.request.user)
        return FacebookMessage.objects.filter(page_connection__in=user_pages)


class InstagramAccountConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = InstagramAccountConnectionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return InstagramAccountConnection.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class InstagramMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InstagramMessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user_accounts = InstagramAccountConnection.objects.filter(user=self.request.user)
        return InstagramMessage.objects.filter(account_connection__in=user_accounts)


class WhatsAppBusinessConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = WhatsAppBusinessConnectionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return WhatsAppBusinessConnection.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WhatsAppMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WhatsAppMessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user_connections = WhatsAppBusinessConnection.objects.filter(user=self.request.user)
        return WhatsAppMessage.objects.filter(connection__in=user_connections)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def facebook_oauth_start(request):
    """Generate Facebook OAuth URL for business pages access"""
    try:
        fb_app_id = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_APP_ID')
        if not fb_app_id:
            return Response({
                'error': 'Facebook App ID not configured'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Use public callback URL since Facebook needs a consistent redirect URI
        redirect_uri = 'https://api.echodesk.ge/api/social/facebook/oauth/callback/'
        
        # Include tenant info in state parameter for multi-tenant support
        state = f'tenant={getattr(request, "tenant", "amanati")}&user={request.user.id}'
        
        # Facebook OAuth URL for business pages with pages_messaging scope
        oauth_url = (
            f"https://www.facebook.com/v23.0/dialog/oauth?"
            f"client_id={fb_app_id}&"
            f"redirect_uri={redirect_uri}&"
            f"scope=pages_manage_metadata,pages_messaging,pages_read_engagement&"
            f"state={state}&"
            f"response_type=code"
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
    """Handle Facebook OAuth callback and exchange code for access token"""
    try:
        # Get all parameters from Facebook callback
        code = request.GET.get('code')
        error = request.GET.get('error')
        error_description = request.GET.get('error_description')
        error_reason = request.GET.get('error_reason')
        state = request.GET.get('state')
        
        # Debug: Log all received parameters
        all_params = dict(request.GET.items())
        
        # Handle Facebook errors (user denied, etc.)
        if error:
            return Response({
                'status': 'error',
                'error': error,
                'error_description': error_description,
                'error_reason': error_reason,
                'message': 'Facebook OAuth was denied or failed',
                'received_params': all_params
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle missing code
        if not code:
            return Response({
                'status': 'error',
                'error': 'Authorization code not provided',
                'message': 'Facebook did not return an authorization code',
                'received_params': all_params,
                'help': 'This usually means the OAuth flow was not completed or user denied permission'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Success case - we have the code
        return Response({
            'status': 'success',
            'message': 'Facebook OAuth callback received successfully',
            'code': code[:10] + '...' if len(code) > 10 else code,  # Truncate for security
            'state': state,
            'received_params': {k: v for k, v in all_params.items() if k != 'code'},  # Don't expose full code
            'next_steps': 'Code received successfully. Integration can be completed in tenant dashboard.'
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'error': f'OAuth callback processing failed: {str(e)}',
            'received_params': dict(request.GET.items())
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def facebook_connection_status(request):
    """Check Facebook connection status for current user"""
    try:
        pages = FacebookPageConnection.objects.filter(user=request.user, is_active=True)
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
    """Disconnect Facebook integration for current user"""
    try:
        updated_count = FacebookPageConnection.objects.filter(
            user=request.user
        ).update(is_active=False)
        
        return Response({
            'status': 'disconnected',
            'pages_disconnected': updated_count,
            'message': f'Disconnected {updated_count} Facebook pages'
        })
    except Exception as e:
        return Response({
            'error': f'Failed to disconnect: {str(e)}'
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
                                    
                                    # Also write to file for debugging
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
                    'user_email': pc.user.email if pc.user else 'No user',
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


# Instagram Integration Functions

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instagram_oauth_start(request):
    """Generate Instagram OAuth URL for business account access"""
    try:
        fb_app_id = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_APP_ID')
        if not fb_app_id:
            return Response({
                'error': 'Facebook App ID not configured (required for Instagram)'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Use public callback URL since Instagram needs a consistent redirect URI
        redirect_uri = 'https://api.echodesk.ge/api/social/instagram/oauth/callback/'
        
        # Include tenant info in state parameter for multi-tenant support
        state = f'tenant={getattr(request, "tenant", "amanati")}&user={request.user.id}'
        
        # Instagram OAuth URL (using Facebook OAuth with Instagram permissions)
        oauth_url = (
            f"https://www.facebook.com/v18.0/dialog/oauth?"
            f"client_id={fb_app_id}&"
            f"redirect_uri={redirect_uri}&"
            f"scope=instagram_basic,instagram_manage_messages,pages_show_list&"
            f"state={state}&"
            f"response_type=code"
        )
        
        return Response({
            'oauth_url': oauth_url,
            'redirect_uri': redirect_uri,
            'instructions': 'Visit the OAuth URL to connect your Instagram business account'
        })
    except Exception as e:
        return Response({
            'error': f'Failed to generate Instagram OAuth URL: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([])  # No authentication required for Instagram callbacks
def instagram_oauth_callback(request):
    """Handle Instagram OAuth callback and exchange code for access token"""
    try:
        # Get all parameters from Instagram/Facebook callback
        code = request.GET.get('code')
        error = request.GET.get('error')
        error_description = request.GET.get('error_description')
        error_reason = request.GET.get('error_reason')
        state = request.GET.get('state')
        
        # Debug: Log all received parameters
        all_params = dict(request.GET.items())
        
        # Handle Instagram errors (user denied, etc.)
        if error:
            return Response({
                'status': 'error',
                'error': error,
                'error_description': error_description,
                'error_reason': error_reason,
                'message': 'Instagram OAuth was denied or failed',
                'received_params': all_params
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle missing code
        if not code:
            return Response({
                'status': 'error',
                'error': 'Authorization code not provided',
                'message': 'Instagram did not return an authorization code',
                'received_params': all_params,
                'help': 'This usually means the OAuth flow was not completed or user denied permission'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Success case - we have the code
        return Response({
            'status': 'success',
            'message': 'Instagram OAuth callback received successfully',
            'code': code[:10] + '...' if len(code) > 10 else code,  # Truncate for security
            'state': state,
            'received_params': {k: v for k, v in all_params.items() if k != 'code'},  # Don't expose full code
            'next_steps': 'Code received successfully. Instagram integration can be completed in tenant dashboard.'
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'error': f'Instagram OAuth callback processing failed: {str(e)}',
            'received_params': dict(request.GET.items())
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instagram_connection_status(request):
    """Check Instagram connection status for current user"""
    try:
        accounts = InstagramAccountConnection.objects.filter(user=request.user, is_active=True)
        accounts_data = []
        
        for account in accounts:
            accounts_data.append({
                'id': account.id,
                'instagram_account_id': account.instagram_account_id,
                'username': account.username,
                'account_name': account.account_name,
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
            'error': f'Failed to get Instagram connection status: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def instagram_disconnect(request):
    """Disconnect Instagram integration for current user"""
    try:
        updated_count = InstagramAccountConnection.objects.filter(
            user=request.user
        ).update(is_active=False)
        
        return Response({
            'status': 'disconnected',
            'accounts_disconnected': updated_count,
            'message': f'Disconnected {updated_count} Instagram accounts'
        })
    except Exception as e:
        return Response({
            'error': f'Failed to disconnect Instagram: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def instagram_webhook(request):
    """Handle Instagram webhook events for direct messages"""
    if request.method == 'GET':
        # Webhook verification - Instagram sends these parameters
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        # Verify token from settings
        verify_token = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('INSTAGRAM_VERIFY_TOKEN', 'echodesk_instagram_webhook_token_2024')
        
        # Log the verification attempt for debugging
        print(f"[INSTAGRAM WEBHOOK] Verification attempt:")
        print(f"  Mode: {mode}")
        print(f"  Token received: {token}")
        print(f"  Token expected: {verify_token}")
        print(f"  Challenge: {challenge}")
        
        # Verify the mode and token
        if mode == 'subscribe' and token == verify_token:
            print(f"[INSTAGRAM WEBHOOK] Verification successful, returning challenge")
            # Return the challenge as plain text (not JSON)
            from django.http import HttpResponse
            return HttpResponse(challenge, content_type='text/plain')
        else:
            print(f"[INSTAGRAM WEBHOOK] Verification failed")
            return JsonResponse({
                'error': 'Invalid verify token or mode',
                'expected_token': verify_token,
                'received_token': token,
                'mode': mode
            }, status=403)
    
    elif request.method == 'POST':
        # Handle webhook events
        try:
            import json
            data = json.loads(request.body)
            
            # Process Instagram messaging events
            if 'entry' in data:
                for entry in data['entry']:
                    instagram_account_id = entry.get('id')
                    
                    # Find the Instagram account connection
                    try:
                        account_connection = InstagramAccountConnection.objects.get(
                            instagram_account_id=instagram_account_id, 
                            is_active=True
                        )
                    except InstagramAccountConnection.DoesNotExist:
                        continue
                    
                    # Process messaging events
                    if 'messaging' in entry:
                        for message_event in entry['messaging']:
                            if 'message' in message_event:
                                message_data = message_event['message']
                                sender_id = message_event['sender']['id']
                                
                                # Determine message type and content
                                message_text = message_data.get('text', '')
                                message_type = 'text'
                                attachment_url = None
                                
                                # Handle attachments (images, videos, etc.)
                                if 'attachments' in message_data:
                                    attachments = message_data['attachments']
                                    if attachments:
                                        attachment = attachments[0]
                                        message_type = attachment.get('type', 'unknown')
                                        if 'payload' in attachment and 'url' in attachment['payload']:
                                            attachment_url = attachment['payload']['url']
                                
                                # Save the Instagram message
                                InstagramMessage.objects.create(
                                    account_connection=account_connection,
                                    message_id=message_data.get('mid', ''),
                                    conversation_id=message_event.get('recipient', {}).get('id', ''),
                                    sender_id=sender_id,
                                    sender_username='Unknown',  # Can be enriched with additional API call
                                    message_text=message_text,
                                    message_type=message_type,
                                    attachment_url=attachment_url,
                                    timestamp=convert_facebook_timestamp(message_event.get('timestamp', 0)),
                                    is_from_business=(sender_id == instagram_account_id)
                                )
            
            return JsonResponse({'status': 'received'})
            
        except Exception as e:
            return JsonResponse({
                'error': f'Instagram webhook processing failed: {str(e)}'
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# WhatsApp Business API endpoints
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def whatsapp_connection_setup(request):
    """Start WhatsApp Business API connection setup"""
    try:
        # Return instructions for WhatsApp Business API setup
        setup_info = {
            'status': 'setup_required',
            'message': 'WhatsApp Business API requires manual setup',
            'instructions': [
                '1. Create a WhatsApp Business Account at business.whatsapp.com',
                '2. Get your Business Account ID and Phone Number ID from Meta Business Manager',
                '3. Generate a permanent access token',
                '4. Configure webhook URL in your WhatsApp Business API settings',
                '5. Add your credentials to connect your WhatsApp account'
            ],
            'webhook_url': request.build_absolute_uri(reverse('whatsapp_webhook')),
            'verify_token': getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('WHATSAPP_VERIFY_TOKEN', 'echodesk_whatsapp_webhook_token_2024')
        }
        
        return Response(setup_info)
        
    except Exception as e:
        return Response({
            'error': f'Failed to get WhatsApp setup info: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def whatsapp_connect_account(request):
    """Connect a WhatsApp Business Account"""
    try:
        business_account_id = request.data.get('business_account_id')
        phone_number_id = request.data.get('phone_number_id')
        access_token = request.data.get('access_token')
        
        if not all([business_account_id, phone_number_id, access_token]):
            return Response({
                'error': 'Missing required fields: business_account_id, phone_number_id, access_token'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify the WhatsApp Business Account
        verify_url = f"https://graph.facebook.com/v18.0/{phone_number_id}"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = requests.get(verify_url, headers=headers)
        if response.status_code != 200:
            return Response({
                'error': 'Invalid WhatsApp credentials or phone number ID'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        phone_data = response.json()
        
        # Create or update the WhatsApp connection
        connection, created = WhatsAppBusinessConnection.objects.update_or_create(
            user=request.user,
            phone_number_id=phone_number_id,
            defaults={
                'business_account_id': business_account_id,
                'phone_number': phone_data.get('display_phone_number', ''),
                'display_phone_number': phone_data.get('display_phone_number', ''),
                'verified_name': phone_data.get('verified_name', ''),
                'access_token': access_token,
                'is_active': True
            }
        )
        
        serializer = WhatsAppBusinessConnectionSerializer(connection)
        return Response({
            'status': 'connected' if created else 'updated',
            'connection': serializer.data
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to connect WhatsApp account: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def whatsapp_connection_status(request):
    """Get WhatsApp connection status for the current user"""
    try:
        connections = WhatsAppBusinessConnection.objects.filter(user=request.user, is_active=True)
        serializer = WhatsAppBusinessConnectionSerializer(connections, many=True)
        
        return Response({
            'connected': connections.exists(),
            'connections': serializer.data
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to get WhatsApp connection status: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def whatsapp_disconnect(request):
    """Disconnect WhatsApp Business Account"""
    try:
        phone_number_id = request.data.get('phone_number_id')
        
        if not phone_number_id:
            return Response({
                'error': 'phone_number_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        connection = WhatsAppBusinessConnection.objects.filter(
            user=request.user,
            phone_number_id=phone_number_id
        ).first()
        
        if not connection:
            return Response({
                'error': 'WhatsApp connection not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        connection.is_active = False
        connection.save()
        
        return Response({'status': 'disconnected'})
        
    except Exception as e:
        return Response({
            'error': f'Failed to disconnect WhatsApp: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    """Handle WhatsApp Business API webhook"""
    if request.method == 'GET':
        # Webhook verification
        hub_mode = request.GET.get('hub.mode')
        hub_challenge = request.GET.get('hub.challenge')
        hub_verify_token = request.GET.get('hub.verify_token')
        
        # Get verify token from settings
        verify_token = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('WHATSAPP_VERIFY_TOKEN', 'echodesk_whatsapp_webhook_token_2024')
        
        if hub_mode == 'subscribe' and hub_verify_token == verify_token:
            return HttpResponse(hub_challenge, content_type='text/plain')
        else:
            return HttpResponse('Forbidden', status=403)
    
    elif request.method == 'POST':
        # Handle incoming WhatsApp messages
        try:
            import json
            from datetime import datetime
            
            data = json.loads(request.body.decode('utf-8'))
            
            # WhatsApp webhook structure
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    
                    # Process messages
                    for message in value.get('messages', []):
                        phone_number_id = value.get('metadata', {}).get('phone_number_id')
                        
                        if not phone_number_id:
                            continue
                        
                        # Find the WhatsApp connection
                        connection = WhatsAppBusinessConnection.objects.filter(
                            phone_number_id=phone_number_id,
                            is_active=True
                        ).first()
                        
                        if not connection:
                            continue
                        
                        message_id = message.get('id')
                        from_number = message.get('from')
                        timestamp = datetime.fromtimestamp(int(message.get('timestamp')))
                        message_type = message.get('type', 'text')
                        
                        # Extract message content
                        message_text = ''
                        media_url = ''
                        media_mime_type = ''
                        
                        if message_type == 'text':
                            message_text = message.get('text', {}).get('body', '')
                        elif message_type in ['image', 'document', 'audio', 'video']:
                            media_data = message.get(message_type, {})
                            media_url = media_data.get('url', '')
                            media_mime_type = media_data.get('mime_type', '')
                            message_text = media_data.get('caption', '')
                        elif message_type == 'location':
                            location = message.get('location', {})
                            message_text = f"Location: {location.get('latitude')}, {location.get('longitude')}"
                        
                        # Get contact name if available
                        contact_name = ''
                        for contact in value.get('contacts', []):
                            if contact.get('wa_id') == from_number:
                                profile = contact.get('profile', {})
                                contact_name = profile.get('name', '')
                                break
                        
                        # Save the WhatsApp message
                        WhatsAppMessage.objects.update_or_create(
                            message_id=message_id,
                            defaults={
                                'connection': connection,
                                'from_number': from_number,
                                'to_number': connection.phone_number,
                                'contact_name': contact_name,
                                'message_text': message_text,
                                'message_type': message_type,
                                'media_url': media_url,
                                'media_mime_type': media_mime_type,
                                'timestamp': timestamp,
                                'is_from_business': False,
                                'is_read': False,
                                'delivery_status': 'delivered'
                            }
                        )
                    
                    # Process message status updates
                    for status_update in value.get('statuses', []):
                        message_id = status_update.get('id')
                        status_value = status_update.get('status')
                        
                        # Update message delivery status
                        WhatsAppMessage.objects.filter(message_id=message_id).update(
                            delivery_status=status_value
                        )
            
            return JsonResponse({'status': 'received'})
            
        except Exception as e:
            return JsonResponse({
                'error': f'WhatsApp webhook processing failed: {str(e)}'
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
