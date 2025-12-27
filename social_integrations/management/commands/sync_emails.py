"""
Django management command to sync emails from IMAP servers.
Run this via cron every 5 minutes:
*/5 * * * * cd /path/to/echodesk-back && python manage.py sync_emails >> /var/log/echodesk/email_sync.log 2>&1
"""
import logging
from django.core.management.base import BaseCommand
from tenant_schemas.utils import schema_context
from tenants.models import Tenant

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync emails from IMAP servers for all tenants with active email connections'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Sync only for a specific tenant (by schema name)',
        )
        parser.add_argument(
            '--max-messages',
            type=int,
            default=500,
            help='Maximum messages to sync per connection (default: 500)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing',
        )

    def handle(self, *args, **options):
        from social_integrations.models import EmailConnection
        from social_integrations.email_utils import sync_imap_messages

        tenant_schema = options.get('tenant')
        max_messages = options.get('max_messages', 500)
        dry_run = options.get('dry_run', False)

        # Get tenants to process
        if tenant_schema:
            tenants = Tenant.objects.filter(schema_name=tenant_schema)
            if not tenants.exists():
                self.stderr.write(self.style.ERROR(f'Tenant {tenant_schema} not found'))
                return
        else:
            # Get all active tenants
            tenants = Tenant.objects.filter(is_active=True)

        total_synced = 0
        total_errors = 0

        for tenant in tenants:
            with schema_context(tenant.schema_name):
                try:
                    connections = EmailConnection.objects.filter(is_active=True)

                    if not connections.exists():
                        continue

                    for conn in connections:
                        if dry_run:
                            self.stdout.write(
                                f'[DRY RUN] Would sync {conn.email_address} for tenant {tenant.schema_name}'
                            )
                            continue

                        try:
                            self.stdout.write(
                                f'Syncing {conn.email_address} for tenant {tenant.schema_name}...'
                            )
                            count = sync_imap_messages(conn, max_messages=max_messages)
                            total_synced += count
                            self.stdout.write(
                                self.style.SUCCESS(f'  Synced {count} new messages')
                            )
                        except Exception as e:
                            total_errors += 1
                            self.stderr.write(
                                self.style.ERROR(f'  Error syncing {conn.email_address}: {e}')
                            )
                            logger.error(f'Email sync error for {conn.email_address}: {e}')

                except Exception as e:
                    total_errors += 1
                    self.stderr.write(
                        self.style.ERROR(f'Error processing tenant {tenant.schema_name}: {e}')
                    )
                    logger.error(f'Tenant processing error for {tenant.schema_name}: {e}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No emails were actually synced'))
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nSync complete: {total_synced} messages synced, {total_errors} errors')
            )
