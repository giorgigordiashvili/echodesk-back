from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET', 'POST', 'OPTIONS'])
@permission_classes([AllowAny])
def cors_test(request):
    """
    Test endpoint to verify CORS configuration is working
    """
    origin = request.META.get('HTTP_ORIGIN', 'unknown')
    host = request.META.get('HTTP_HOST', 'unknown')
    
    return Response({
        'message': 'CORS is working correctly!',
        'method': request.method,
        'origin': origin,
        'host': host,
        'headers': dict(request.headers),
        'timestamp': request.META.get('HTTP_DATE'),
        'cors_enabled': True
    })


@csrf_exempt
@require_http_methods(["GET", "POST", "OPTIONS"])
def simple_cors_test(request):
    """
    Simple CORS test endpoint (non-DRF)
    """
    response = JsonResponse({
        'status': 'success',
        'message': 'CORS test endpoint working',
        'method': request.method,
        'origin': request.META.get('HTTP_ORIGIN', 'unknown'),
        'host': request.META.get('HTTP_HOST', 'unknown')
    })
    
    # Manual CORS headers as backup
    origin = request.META.get('HTTP_ORIGIN')
    if origin:
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Allow-Credentials'] = 'true'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PUT, DELETE, PATCH'
        response['Access-Control-Allow-Headers'] = 'Origin, Content-Type, Accept, Authorization, X-Requested-With'
    
    return response
