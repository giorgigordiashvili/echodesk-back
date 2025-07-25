from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings
import json

@api_view(['GET', 'OPTIONS'])
@permission_classes([AllowAny])
def cors_test(request):
    """
    Test endpoint to verify CORS configuration
    """
    return Response({
        'message': 'CORS test successful',
        'origin': request.META.get('HTTP_ORIGIN', 'No origin'),
        'host': request.META.get('HTTP_HOST', 'No host'),
        'method': request.method,
        'cors_settings': {
            'debug': settings.DEBUG,
            'main_domain': settings.MAIN_DOMAIN,
            'api_domain': settings.API_DOMAIN,
        },
        'headers': dict(request.headers),
        'timestamp': '2025-07-25T14:30:00Z'
    })

@api_view(['GET', 'OPTIONS'])
@permission_classes([AllowAny]) 
def preflight_test(request):
    """
    Specific test for preflight OPTIONS requests
    """
    if request.method == 'OPTIONS':
        return Response({'message': 'Preflight request successful'})
    return Response({'message': 'Regular request successful'})
