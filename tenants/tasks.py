import logging

from celery import shared_task
from django.core.management import call_command
from io import StringIO

logger = logging.getLogger(__name__)


@shared_task
def process_recurring_payments():
    output = StringIO()
    call_command('process_recurring_payments', stdout=output)
    result = output.getvalue()
    logger.info(f'process_recurring_payments completed: {result}')
    return result


@shared_task
def check_subscription_status():
    output = StringIO()
    call_command('check_subscription_status', stdout=output)
    result = output.getvalue()
    logger.info(f'check_subscription_status completed: {result}')
    return result


@shared_task
def process_trial_expirations():
    output = StringIO()
    call_command('process_trial_expirations', stdout=output)
    result = output.getvalue()
    logger.info(f'process_trial_expirations completed: {result}')
    return result


@shared_task
def process_payment_retries():
    output = StringIO()
    call_command('process_payment_retries', stdout=output)
    result = output.getvalue()
    logger.info(f'process_payment_retries completed: {result}')
    return result


@shared_task
def calculate_platform_metrics():
    output = StringIO()
    call_command('calculate_platform_metrics', stdout=output)
    result = output.getvalue()
    logger.info(f'calculate_platform_metrics completed: {result}')
    return result


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_pending_tenant(self, schema_name):
    try:
        output = StringIO()
        call_command('process_pending_tenants', '--schema-name', schema_name, stdout=output)
        result = output.getvalue()
        logger.info(f'process_pending_tenant({schema_name}) completed: {result}')
        return result
    except Exception as exc:
        logger.error(f'process_pending_tenant({schema_name}) failed: {exc}')
        raise self.retry(exc=exc)
