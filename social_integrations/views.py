import os
import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
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
        
        redirect_uri = request.build_absolute_uri(reverse('facebook-oauth-callback'))
        
        # Facebook OAuth URL for business pages with pages_messaging scope
        oauth_url = (
            f"https://www.facebook.com/v18.0/dialog/oauth?"
            f"client_id={fb_app_id}&"
            f"redirect_uri={redirect_uri}&"
            f"scope=pages_manage_metadata,pages_messaging,pages_read_engagement&"
            f"response_type=code"
        )
        
        return Response({
            'oauth_url': oauth_url,
            'redirect_uri': redirect_uri
        })
    except Exception as e:
        return Response({
            'error': f'Failed to generate OAuth URL: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def facebook_oauth_callback(request):
    """Handle Facebook OAuth callback and exchange code for access token"""
    try:
        code = request.GET.get('code')
        if not code:
            return Response({
                'error': 'Authorization code not provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        fb_config = getattr(settings, 'SOCIAL_INTEGRATIONS', {})
        app_id = fb_config.get('FACEBOOK_APP_ID')
        app_secret = fb_config.get('FACEBOOK_APP_SECRET')
        
        if not app_id or not app_secret:
            return Response({
                'error': 'Facebook app credentials not configured'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        redirect_uri = request.build_absolute_uri(reverse('facebook-oauth-callback'))
        
        # Exchange code for access token
        token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
        token_params = {
            'client_id': app_id,
            'client_secret': app_secret,
            'redirect_uri': redirect_uri,
            'code': code
        }
        
        token_response = requests.get(token_url, params=token_params)
        token_data = token_response.json()
        
        if 'access_token' not in token_data:
            return Response({
                'error': 'Failed to obtain access token',
                'details': token_data
            }, status=status.HTTP_400_BAD_REQUEST)
        
        access_token = token_data['access_token']
        
        # Get user's pages
        pages_url = f"https://graph.facebook.com/v18.0/me/accounts?access_token={access_token}"
        pages_response = requests.get(pages_url)
        pages_data = pages_response.json()
        
        if 'data' not in pages_data:
            return Response({
                'error': 'Failed to fetch pages',
                'details': pages_data
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save page connections
        pages_saved = 0
        for page in pages_data['data']:
            page_connection, created = FacebookPageConnection.objects.get_or_create(
                user=request.user,
                page_id=page['id'],
                defaults={
                    'page_name': page['name'],
                    'page_access_token': page['access_token'],
                    'is_active': True
                }
            )
            if created:
                pages_saved += 1
        
        return Response({
            'status': 'success',
            'pages_connected': pages_saved,
            'message': f'Successfully connected {pages_saved} Facebook pages'
        })
        
    except Exception as e:
        return Response({
            'error': f'OAuth callback failed: {str(e)}'
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
        # Webhook verification
        verify_token = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_VERIFY_TOKEN', 'verify_token')
        
        if request.GET.get('hub.verify_token') == verify_token:
            return JsonResponse({'challenge': request.GET.get('hub.challenge')})
        else:
            return JsonResponse({'error': 'Invalid verify token'}, status=403)
    
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
