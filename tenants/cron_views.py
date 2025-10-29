"""
HTTP endpoints for external cron services

These endpoints allow external services (like DigitalOcean Functions)
to trigger scheduled tasks via HTTP requests.

Secured with CRON_SECRET_TOKEN environment variable.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings
from django.core.management import call_command
from io import StringIO
import logging

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_recurring_payments(request):
    """
    HTTP endpoint to trigger recurring payment processing

    Security: Requires CRON_SECRET_TOKEN in header or query param

    Usage:
    curl -X GET "https://api.echodesk.ge/api/cron/recurring-payments/" \
         -H "X-Cron-Token: your-secret-token"

    Or with query param:
    https://api.echodesk.ge/api/cron/recurring-payments/?token=your-secret-token
    """
    # Verify token
    token = request.headers.get('X-Cron-Token') or request.GET.get('token')
    expected_token = getattr(settings, 'CRON_SECRET_TOKEN', None)

    if not expected_token:
        logger.error('CRON_SECRET_TOKEN not configured in settings')
        return Response({
            'error': 'Cron service not configured'
        }, status=500)

    if not token or token != expected_token:
        logger.warning(f'Unauthorized cron access attempt from {request.META.get("REMOTE_ADDR")}')
        return Response({
            'error': 'Unauthorized'
        }, status=401)

    # Run command
    try:
        output = StringIO()
        call_command('process_recurring_payments', stdout=output)

        output_text = output.getvalue()
        logger.info(f'Recurring payments cron executed successfully')

        return Response({
            'status': 'success',
            'message': 'Recurring payments processed',
            'output': output_text
        })
    except Exception as e:
        logger.error(f'Recurring payments cron failed: {e}')
        return Response({
            'status': 'error',
            'error': str(e)
        }, status=500)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_subscription_check(request):
    """
    HTTP endpoint to trigger subscription status check

    Security: Requires CRON_SECRET_TOKEN in header or query param

    Usage:
    curl -X GET "https://api.echodesk.ge/api/cron/subscription-check/" \
         -H "X-Cron-Token: your-secret-token"

    Or with query param:
    https://api.echodesk.ge/api/cron/subscription-check/?token=your-secret-token
    """
    # Verify token
    token = request.headers.get('X-Cron-Token') or request.GET.get('token')
    expected_token = getattr(settings, 'CRON_SECRET_TOKEN', None)

    if not expected_token:
        logger.error('CRON_SECRET_TOKEN not configured in settings')
        return Response({
            'error': 'Cron service not configured'
        }, status=500)

    if not token or token != expected_token:
        logger.warning(f'Unauthorized cron access attempt from {request.META.get("REMOTE_ADDR")}')
        return Response({
            'error': 'Unauthorized'
        }, status=401)

    # Run command
    try:
        output = StringIO()
        call_command('check_subscription_status', stdout=output)

        output_text = output.getvalue()
        logger.info(f'Subscription check cron executed successfully')

        return Response({
            'status': 'success',
            'message': 'Subscription status checked',
            'output': output_text
        })
    except Exception as e:
        logger.error(f'Subscription check cron failed: {e}')
        return Response({
            'status': 'error',
            'error': str(e)
        }, status=500)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_process_trial_expirations(request):
    """
    HTTP endpoint to process trial subscription expirations

    Checks for trials ending today and charges saved cards automatically

    Security: Requires CRON_SECRET_TOKEN in header or query param

    Usage:
    curl -X GET "https://api.echodesk.ge/api/cron/process-trial-expirations/" \
         -H "X-Cron-Token: your-secret-token"
    """
    # Verify token
    token = request.headers.get('X-Cron-Token') or request.GET.get('token')
    expected_token = getattr(settings, 'CRON_SECRET_TOKEN', None)

    if not expected_token:
        logger.error('CRON_SECRET_TOKEN not configured in settings')
        return Response({
            'error': 'Cron service not configured'
        }, status=500)

    if not token or token != expected_token:
        logger.warning(f'Unauthorized cron access attempt from {request.META.get("REMOTE_ADDR")}')
        return Response({
            'error': 'Unauthorized'
        }, status=401)

    # Run command
    try:
        output = StringIO()
        call_command('process_trial_expirations', stdout=output)

        output_text = output.getvalue()
        logger.info(f'Trial expirations cron executed successfully')

        return Response({
            'status': 'success',
            'message': 'Trial expirations processed',
            'output': output_text
        })
    except Exception as e:
        logger.error(f'Trial expirations cron failed: {e}')
        return Response({
            'status': 'error',
            'error': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def cron_health_check(request):
    """
    Health check endpoint for monitoring cron service availability

    No authentication required - just checks if service is running
    """
    return Response({
        'status': 'healthy',
        'service': 'echodesk-cron',
        'endpoints': {
            'recurring_payments': '/api/cron/recurring-payments/',
            'subscription_check': '/api/cron/subscription-check/',
            'trial_expirations': '/api/cron/process-trial-expirations/'
        }
    })
