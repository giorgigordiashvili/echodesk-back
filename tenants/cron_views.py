"""
HTTP endpoints for external cron services

These endpoints allow external services (like DigitalOcean Functions)
to trigger scheduled tasks via HTTP requests.

Secured with CRON_SECRET_TOKEN environment variable.

Tasks run synchronously via Django management commands.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings
from django.core.management import call_command
from io import StringIO
import logging

logger = logging.getLogger(__name__)


def _verify_cron_token(request):
    """Verify cron token from header or query param. Returns error Response or None."""
    token = request.headers.get('X-Cron-Token') or request.GET.get('token')
    expected_token = getattr(settings, 'CRON_SECRET_TOKEN', None)

    if not expected_token:
        logger.error('CRON_SECRET_TOKEN not configured in settings')
        return Response({'error': 'Cron service not configured'}, status=500)

    if not token or token != expected_token:
        logger.warning(f'Unauthorized cron access attempt from {request.META.get("REMOTE_ADDR")}')
        return Response({'error': 'Unauthorized'}, status=401)

    return None


def _run_command(request, command_name, app_label=None):
    """Run a management command and return the output as a Response."""
    error = _verify_cron_token(request)
    if error:
        return error

    out = StringIO()
    try:
        call_command(command_name, stdout=out)
        output = out.getvalue()
        logger.info(f'Completed {command_name}: {output[:200]}')
        return Response({'status': 'success', 'output': output})
    except Exception as e:
        logger.exception(f'Failed to run {command_name}')
        return Response({'status': 'error', 'error': str(e)}, status=500)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_recurring_payments(request):
    """Trigger recurring payment processing."""
    return _run_command(request, 'process_recurring_payments')


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_subscription_check(request):
    """Trigger subscription status check."""
    return _run_command(request, 'check_subscription_status')


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_process_trial_expirations(request):
    """Trigger trial expiration processing."""
    return _run_command(request, 'process_trial_expirations')


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_payment_retries(request):
    """Trigger payment retries."""
    return _run_command(request, 'process_payment_retries')


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_calculate_metrics(request):
    """Trigger platform metrics calculation."""
    return _run_command(request, 'calculate_metrics')


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_email_sync(request):
    """Trigger email sync for all tenants."""
    return _run_command(request, 'sync_emails')


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_generate_daily_posts(request):
    """Trigger daily AI post generation."""
    return _run_command(request, 'generate_daily_posts')


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_publish_approved_posts(request):
    """Trigger approved post publishing."""
    return _run_command(request, 'publish_approved_posts')


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
            'trial_expirations': '/api/cron/process-trial-expirations/',
            'payment_retries': '/api/cron/payment-retries/',
            'calculate_metrics': '/api/cron/calculate-metrics/',
            'email_sync': '/api/cron/email-sync/',
            'generate_daily_posts': '/api/cron/generate-daily-posts/',
            'publish_approved_posts': '/api/cron/publish-approved-posts/',
        }
    })
