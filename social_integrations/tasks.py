import logging

from celery import shared_task
from django.core.management import call_command
from io import StringIO

logger = logging.getLogger(__name__)


@shared_task
def sync_all_tenant_emails():
    from tenant_schemas.utils import schema_context
    from tenants.models import Tenant
    from social_integrations.models import EmailConnection
    from social_integrations.email_utils import sync_imap_messages

    tenants = Tenant.objects.exclude(schema_name='public')
    total_synced = 0

    for tenant in tenants:
        try:
            with schema_context(tenant.schema_name):
                connections = EmailConnection.objects.filter(is_active=True)
                for connection in connections:
                    try:
                        count = sync_imap_messages(connection)
                        total_synced += count
                        logger.info(f"Email sync {tenant.schema_name}/{connection.email_address}: {count} new")
                    except Exception as e:
                        logger.error(f"Email sync failed {tenant.schema_name}/{connection.email_address}: {e}")
        except Exception as e:
            logger.error(f"Email sync failed for tenant {tenant.schema_name}: {e}")

    logger.info(f'sync_all_tenant_emails completed: {total_synced} total messages')
    return total_synced


@shared_task
def generate_daily_posts():
    output = StringIO()
    call_command('generate_daily_posts', stdout=output)
    result = output.getvalue()
    logger.info(f'generate_daily_posts completed: {result}')
    return result


@shared_task
def publish_approved_posts():
    output = StringIO()
    call_command('publish_approved_posts', stdout=output)
    result = output.getvalue()
    logger.info(f'publish_approved_posts completed: {result}')
    return result


@shared_task(soft_time_limit=120, time_limit=180)
def generate_ai_post_for_tenant(schema_name):
    output = StringIO()
    call_command('generate_daily_posts', '--schema-name', schema_name, stdout=output)
    result = output.getvalue()
    logger.info(f'generate_ai_post_for_tenant({schema_name}) completed: {result}')
    return result


@shared_task
def sync_tenant_emails(schema_name):
    from tenant_schemas.utils import schema_context
    from social_integrations.models import EmailConnection
    from social_integrations.email_utils import sync_imap_messages

    total = 0
    with schema_context(schema_name):
        connections = EmailConnection.objects.filter(is_active=True)
        for connection in connections:
            try:
                count = sync_imap_messages(connection)
                total += count
                logger.info(f"Email sync {schema_name}/{connection.email_address}: {count} new")
            except Exception as e:
                logger.error(f"Email sync failed {schema_name}/{connection.email_address}: {e}")

    return total


