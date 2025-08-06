"""
Public schema URL configuration.
This handles routes for the public schema (tenant management).
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from social_integrations import legal_views
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

def websocket_diagnostic(request):
    """
    Diagnostic endpoint to check WebSocket configuration
    """
    import django
    from django.conf import settings
    
    # Check if Django Channels is installed
    try:
        import channels
        channels_version = channels.__version__
        channels_installed = True
    except ImportError:
        channels_version = None
        channels_installed = False
    
    # Check if ASGI application is configured
    asgi_application = getattr(settings, 'ASGI_APPLICATION', None)
    
    # Check if channel layers are configured
    channel_layers = getattr(settings, 'CHANNEL_LAYERS', None)
    
    # Check server type
    server_type = "ASGI configured" if asgi_application else "WSGI only"
    
    # Check Redis connection if configured
    redis_status = "Not configured"
    if channel_layers and 'default' in channel_layers:
        backend = channel_layers['default'].get('BACKEND', '')
        if 'redis' in backend.lower():
            redis_status = "Redis configured"
    
    return JsonResponse({
        'django_version': django.get_version(),
        'channels_installed': channels_installed,
        'channels_version': channels_version,
        'asgi_application': asgi_application,
        'server_type': server_type,
        'channel_layers_configured': channel_layers is not None,
        'redis_status': redis_status,
        'websocket_urls_should_be_available': [
            '/ws/messages/<tenant_schema>/',
            '/ws/typing/<tenant_schema>/<conversation_id>/'
        ] if channels_installed and asgi_application else [],
        'debug_mode': settings.DEBUG,
        'deployment_issue': 'WebSocket 404 means server is not running with ASGI or WebSocket routing is missing'
    })

@csrf_exempt
def test_websocket_notification(request):
    """
    Test endpoint to manually trigger a WebSocket notification
    """
    from django.http import JsonResponse
    import json
    import time
    import traceback
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tenant_schema = data.get('tenant_schema', 'echodesk_georgeguajabidze_gmail_com')
            message_text = data.get('message', 'Test WebSocket message')
            
            # Check if channel layer is available
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            
            if channel_layer is None:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Channel layer not configured',
                    'suggestion': 'WebSocket functionality requires Django Channels with Redis or InMemory backend'
                })
            
            # Try to send WebSocket notification
            from asgiref.sync import async_to_sync
            from social_integrations.consumers import send_new_message_notification
            
            test_message_data = {
                'id': 999999,
                'message_id': 'test_' + str(int(time.time())),
                'sender_id': 'test_sender',
                'sender_name': 'WebSocket Test',
                'message_text': message_text,
                'timestamp': '2024-01-01T00:00:00Z',
                'is_from_page': False,
                'page_name': 'Test Page',
            }
            
            async_to_sync(send_new_message_notification)(
                tenant_schema=tenant_schema,
                conversation_id='test_conversation',
                message_data=test_message_data
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'WebSocket notification sent successfully',
                'tenant_schema': tenant_schema,
                'test_data': test_message_data,
                'channel_backend': str(type(channel_layer).__name__)
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e),
                'traceback': traceback.format_exc(),
                'suggestion': 'Check if Redis is running or configure InMemory channel layer'
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'POST request required',
        'example': {
            'tenant_schema': 'echodesk_georgeguajabidze_gmail_com',
            'message': 'Test message'
        }
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # WebSocket diagnostic and testing
    path('websocket-diagnostic/', websocket_diagnostic, name='websocket_diagnostic'),
    path('test-websocket/', test_websocket_notification, name='test_websocket'),
    
    # Legal pages (required for Facebook app compliance)
    path('legal/privacy-policy/', legal_views.privacy_policy, name='privacy-policy'),
    path('legal/terms-of-service/', legal_views.terms_of_service, name='terms-of-service'),
    path('legal/data-deletion/', legal_views.user_data_deletion, name='data-deletion'),
    path('legal/data-deletion-status/', legal_views.data_deletion_status, name='data-deletion-status'),
    path('legal/deauthorize/', legal_views.deauthorize_callback, name='deauthorize-callback'),
    
    # Social integrations (needed for OAuth callbacks)
    path('api/social/', include('social_integrations.urls')),
    
    # Public/tenant management endpoints
    path('', include('tenants.urls')),
]
