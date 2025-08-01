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
from .models import FacebookPageConnection, FacebookMessage
from .serializers import FacebookPageConnectionSerializer, FacebookMessageSerializer


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
            f"https://www.facebook.com/v18.0/dialog/oauth?"
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
        
        # Log the verification attempt for debugging
        print(f"[WEBHOOK] Verification attempt:")
        print(f"  Mode: {mode}")
        print(f"  Token received: {token}")
        print(f"  Token expected: {verify_token}")
        print(f"  Challenge: {challenge}")
        
        # Verify the mode and token
        if mode == 'subscribe' and token == verify_token:
            print(f"[WEBHOOK] Verification successful, returning challenge")
            # Return the challenge as plain text (not JSON)
            from django.http import HttpResponse
            return HttpResponse(challenge, content_type='text/plain')
        else:
            print(f"[WEBHOOK] Verification failed")
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
                        continue
                    
                    # Process messaging events
                    if 'messaging' in entry:
                        for message_event in entry['messaging']:
                            if 'message' in message_event:
                                message_data = message_event['message']
                                sender_id = message_event['sender']['id']
                                
                                # Save the message
                                FacebookMessage.objects.create(
                                    page_connection=page_connection,
                                    message_id=message_data.get('mid', ''),
                                    sender_id=sender_id,
                                    sender_name='Unknown',  # Can be enriched with additional API call
                                    message_text=message_data.get('text', ''),
                                    timestamp=message_event.get('timestamp', 0),
                                    is_from_page=(sender_id == page_id)
                                )
            
            return JsonResponse({'status': 'received'})
            
        except Exception as e:
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
