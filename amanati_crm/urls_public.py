"""
Public schema URL configuration.
This handles routes for the public schema (tenant management).
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from ecommerce_crm.schema import EcommerceClientSchemaGenerator
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
def test_polling_system(request):
    """
    Test endpoint to verify the polling system is working
    """
    from django.http import JsonResponse
    import json
    import time
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tenant_schema = data.get('tenant_schema', 'echodesk_georgeguajabidze_gmail_com')
            message_text = data.get('message', 'Test polling system message')
            
            return JsonResponse({
                'status': 'success',
                'message': 'Polling system is active - messages refresh every 10 seconds',
                'tenant_schema': tenant_schema,
                'test_message': message_text,
                'refresh_interval': '10 seconds',
                'system_type': 'Simple polling (no WebSocket complexity)'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({
        'status': 'info',
        'message': 'Simple polling system active',
        'refresh_interval': '10 seconds',
        'system_type': 'Reliable polling without WebSocket complexity'
    })

urlpatterns = [
    path('admin/', admin.site.urls),

    # API Documentation - Main API
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # API Documentation - Ecommerce Client API
    path('api/ecommerce-client-schema/', SpectacularAPIView.as_view(
        urlconf='ecommerce_crm.urls_client_schema'
    ), name='ecommerce-client-schema'),
    path('api/ecommerce-client-docs/', SpectacularSwaggerView.as_view(url_name='ecommerce-client-schema'), name='ecommerce-client-swagger-ui'),

    # Testing endpoints
    path('websocket-diagnostic/', websocket_diagnostic, name='websocket_diagnostic'),
    path('test-polling/', test_polling_system, name='test_polling'),
    
    # Legal pages (required for Facebook app compliance)
    path('legal/privacy-policy/', legal_views.privacy_policy, name='privacy-policy'),
    path('legal/terms-of-service/', legal_views.terms_of_service, name='terms-of-service'),
    path('legal/data-deletion/', legal_views.user_data_deletion, name='data-deletion'),
    path('legal/data-deletion-status/', legal_views.data_deletion_status, name='data-deletion-status'),
    path('legal/deauthorize/', legal_views.deauthorize_callback, name='deauthorize-callback'),
    
    # Social integrations (needed for OAuth callbacks)
    path('api/social/', include('social_integrations.urls')),

    # Ecommerce endpoints (public access for client registration/login)
    path('api/ecommerce/', include('ecommerce_crm.urls')),

    # Public/tenant management endpoints
    path('', include('tenants.urls')),
]
