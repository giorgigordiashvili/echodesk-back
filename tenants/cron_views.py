"""
HTTP endpoints for external cron services

These endpoints allow external services (like DigitalOcean Functions)
to trigger scheduled tasks via HTTP requests.

Secured with CRON_SECRET_TOKEN environment variable.

Tasks are dispatched asynchronously via Celery.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings
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


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_recurring_payments(request):
    """Trigger recurring payment processing via Celery."""
    error = _verify_cron_token(request)
    if error:
        return error

    from tenants.tasks import process_recurring_payments
    result = process_recurring_payments.delay()
    logger.info('Dispatched process_recurring_payments task')
    return Response({'status': 'accepted', 'task_id': result.id})


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_subscription_check(request):
    """Trigger subscription status check via Celery."""
    error = _verify_cron_token(request)
    if error:
        return error

    from tenants.tasks import check_subscription_status
    result = check_subscription_status.delay()
    logger.info('Dispatched check_subscription_status task')
    return Response({'status': 'accepted', 'task_id': result.id})


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_process_trial_expirations(request):
    """Trigger trial expiration processing via Celery."""
    error = _verify_cron_token(request)
    if error:
        return error

    from tenants.tasks import process_trial_expirations
    result = process_trial_expirations.delay()
    logger.info('Dispatched process_trial_expirations task')
    return Response({'status': 'accepted', 'task_id': result.id})


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_payment_retries(request):
    """Trigger payment retries via Celery."""
    error = _verify_cron_token(request)
    if error:
        return error

    from tenants.tasks import process_payment_retries
    result = process_payment_retries.delay()
    logger.info('Dispatched process_payment_retries task')
    return Response({'status': 'accepted', 'task_id': result.id})


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_calculate_metrics(request):
    """Trigger platform metrics calculation via Celery."""
    error = _verify_cron_token(request)
    if error:
        return error

    from tenants.tasks import calculate_platform_metrics
    result = calculate_platform_metrics.delay()
    logger.info('Dispatched calculate_platform_metrics task')
    return Response({'status': 'accepted', 'task_id': result.id})


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_email_sync(request):
    """Trigger email sync for all tenants via Celery."""
    error = _verify_cron_token(request)
    if error:
        return error

    from social_integrations.tasks import sync_all_tenant_emails
    result = sync_all_tenant_emails.delay()
    logger.info('Dispatched sync_all_tenant_emails task')
    return Response({'status': 'accepted', 'task_id': result.id})


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_generate_daily_posts(request):
    """Trigger daily AI post generation via Celery."""
    error = _verify_cron_token(request)
    if error:
        return error

    from social_integrations.tasks import generate_daily_posts
    result = generate_daily_posts.delay()
    logger.info('Dispatched generate_daily_posts task')
    return Response({'status': 'accepted', 'task_id': result.id})


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_publish_approved_posts(request):
    """Trigger approved post publishing via Celery."""
    error = _verify_cron_token(request)
    if error:
        return error

    from social_integrations.tasks import publish_approved_posts
    result = publish_approved_posts.delay()
    logger.info('Dispatched publish_approved_posts task')
    return Response({'status': 'accepted', 'task_id': result.id})


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
