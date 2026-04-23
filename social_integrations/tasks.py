import logging
from datetime import timedelta

from celery import shared_task
from django.core.management import call_command
from django.utils import timezone
from io import StringIO

logger = logging.getLogger(__name__)


# Ephemeral SIP creds issued by /api/widget/public/call/credentials/ live
# for this long. Keep this matched with the ``ttl_hours`` default in
# ``AsteriskStateSync.sync_widget_guest_endpoint``.
WIDGET_SIP_TTL = timedelta(hours=4)


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


def _reap_widget_endpoints(dry_run: bool = False) -> dict:
    """Shared body for the Celery task and the management command.

    Returns a dict summary of {tenant_schema: [session_ids reaped]}. When
    ``dry_run`` is True, callers can inspect what would be deleted without
    actually tombstoning the PJSIP rows.
    """
    from tenant_schemas.utils import get_public_schema_name, schema_context
    from widget_registry.models import WidgetConnection
    from social_integrations.models import WidgetSession
    from crm.asterisk_db import get_active_pbx_for_current_tenant
    from crm.asterisk_sync import AsteriskStateSync

    cutoff = timezone.now() - WIDGET_SIP_TTL

    # Find every tenant that has at least one voice-enabled connection.
    with schema_context(get_public_schema_name()):
        voice_conns = list(
            WidgetConnection.objects.filter(voice_enabled=True)
            .values_list('tenant_schema', 'id')
        )

    by_tenant: dict[str, list[int]] = {}
    for tenant_schema, conn_id in voice_conns:
        by_tenant.setdefault(tenant_schema, []).append(conn_id)

    reaped: dict[str, list[str]] = {}
    for tenant_schema, conn_ids in by_tenant.items():
        try:
            pbx = None
            try:
                with schema_context(tenant_schema):
                    pbx = get_active_pbx_for_current_tenant()
            except Exception:
                pbx = None
            if pbx is None:
                continue
            sync = AsteriskStateSync(tenant_schema, pbx=pbx)
            with schema_context(tenant_schema):
                stale = list(
                    WidgetSession.objects
                    .filter(connection_id__in=conn_ids, last_seen_at__lt=cutoff)
                    .values_list('session_id', flat=True)
                )
            if not stale:
                continue
            reaped.setdefault(tenant_schema, [])
            for session_id in stale:
                if not dry_run:
                    sync.tombstone_widget_guest_endpoint(session_id)
                reaped[tenant_schema].append(session_id)
        except Exception:
            logger.exception(
                'reap_stale_widget_endpoints failed for tenant=%s', tenant_schema,
            )
    return reaped


@shared_task(name='social_integrations.reap_stale_widget_endpoints')
def reap_stale_widget_endpoints():
    """Delete PsEndpoint / PsAuth / PsAor rows for widget sessions that
    haven't been active in the last :data:`WIDGET_SIP_TTL`.

    Called hourly by Celery beat. Iterates over each tenant that has
    widget voice enabled, pulls the stale WidgetSession rows, and
    deletes the matching realtime rows.
    """
    reaped = _reap_widget_endpoints(dry_run=False)
    total = sum(len(v) for v in reaped.values())
    if total:
        logger.info('reap_stale_widget_endpoints reaped %d rows', total)
    return total
