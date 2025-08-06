from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import django
from django.conf import settings

@csrf_exempt
def websocket_diagnostic(request):
    """
    Diagnostic endpoint to check WebSocket configuration
    """
    
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
    
    # Check if this is running under ASGI or WSGI
    server_type = "Unknown"
    try:
        # This will be available if running under ASGI
        from django.core.asgi import get_asgi_application
        server_type = "ASGI (WebSocket supported)"
    except:
        try:
            # This indicates WSGI
            from django.core.wsgi import get_wsgi_application
            server_type = "WSGI (WebSocket NOT supported)"
        except:
            pass
    
    # Check Redis connection if configured
    redis_status = "Not configured"
    if channel_layers and 'default' in channel_layers:
        backend = channel_layers['default'].get('BACKEND', '')
        if 'redis' in backend.lower():
            try:
                from channels.layers import get_channel_layer
                channel_layer = get_channel_layer()
                redis_status = "Configured (Redis)"
            except Exception as e:
                redis_status = f"Configured but error: {str(e)}"
    
    return JsonResponse({
        'django_version': django.get_version(),
        'channels_installed': channels_installed,
        'channels_version': channels_version,
        'asgi_application': asgi_application,
        'server_type': server_type,
        'channel_layers_configured': channel_layers is not None,
        'redis_status': redis_status,
        'websocket_urls_available': [
            '/ws/messages/<tenant_schema>/',
            '/ws/typing/<tenant_schema>/<conversation_id>/'
        ] if channels_installed else [],
        'debug_mode': settings.DEBUG,
        'message': 'WebSocket functionality requires ASGI server and Django Channels'
    })
