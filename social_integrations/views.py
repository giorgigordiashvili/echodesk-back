import os
import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
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
            logger = logging.getLogger(__name__)
            
            data = json.loads(request.body)
            
            # Process messaging events
            if 'entry' in data:
                for entry in data['entry']:
                    page_id = entry.get('id')
                    
                    # Find the page connection
                    try:
                        page_connection = FacebookPageConnection.objects.get(
                            page_id=page_id, 
                            is_active=True
                        )
                    except FacebookPageConnection.DoesNotExist:
                        # Log for debugging but continue processing other entries
                        logger.warning(f"No active page connection found for page_id: {page_id}")
                        continue
                    
                    # Process messaging events
                    if 'messaging' in entry:
                        for message_event in entry['messaging']:
                            if 'message' in message_event:
                                message_data = message_event['message']
                                sender_id = message_event['sender']['id']
                                
                                # Skip if this is an echo (message sent by the page)
                                if message_data.get('is_echo'):
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
                                        
                                    except Exception as e:
                                        logger.error(f"Failed to fetch profile for {sender_id}: {e}")
                                
                                # Save the message (avoid duplicates)
                                message_id = message_data.get('mid', '')
                                if message_id and not FacebookMessage.objects.filter(message_id=message_id).exists():
                                    try:
                                        FacebookMessage.objects.create(
                                            page_connection=page_connection,
                                            message_id=message_id,
                                            sender_id=sender_id,
                                            sender_name=sender_name,
                                            message_text=message_data.get('text', ''),
                                            timestamp=message_event.get('timestamp', 0),
                                            is_from_page=(sender_id == page_id),
                                            profile_pic_url=profile_pic_url
                                        )
                                        logger.info(f"Saved Facebook message from {sender_name}")
                                    except Exception as e:
                                        logger.error(f"Failed to save Facebook message: {e}")
            
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
    return Response({
        'method': request.method,
        'path': request.path,
        'full_url': request.build_absolute_uri(),
        'get_params': dict(request.GET.items()),
        'post_params': dict(request.POST.items()) if hasattr(request, 'POST') else {},
        'headers': {k: v for k, v in request.META.items() if k.startswith('HTTP_')},
        'message': 'This endpoint shows exactly what Facebook sends to the callback'
    })


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
                                    timestamp=message_event.get('timestamp', 0),
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
