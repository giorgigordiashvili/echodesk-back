"""
Management command to sync Facebook & Instagram message history.

This command syncs historical messages from Facebook Messenger and Instagram DMs
using the Graph API conversations endpoint.

Usage:
    # Sync all platforms for all tenants
    python manage.py sync_social_messages

    # Sync specific tenant
    python manage.py sync_social_messages --tenant=amanati

    # Sync specific platform
    python manage.py sync_social_messages --platform=facebook
    python manage.py sync_social_messages --platform=instagram

    # Sync only pending connections (new connections that haven't synced yet)
    python manage.py sync_social_messages --pending-only

    # Force resync even if already completed
    python manage.py sync_social_messages --force

    # Sync specific account
    python manage.py sync_social_messages --account-id=123456789 --platform=facebook

Cron setup:
    # Every 15 minutes - sync all platforms
    */15 * * * * python manage.py sync_social_messages

    # Every 5 minutes - new connections only
    */5 * * * * python manage.py sync_social_messages --pending-only
"""

import logging
from django.core.management.base import BaseCommand
from tenant_schemas.utils import schema_context
from tenants.models import Tenant

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync Facebook & Instagram message history for all tenants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Sync only for a specific tenant (by schema name)',
        )
        parser.add_argument(
            '--platform',
            choices=['facebook', 'instagram', 'all'],
            default='all',
            help='Platform to sync: facebook, instagram, or all (default: all)',
        )
        parser.add_argument(
            '--account-id',
            type=str,
            help='Sync only a specific account (page_id for Facebook, instagram_account_id for Instagram)',
        )
        parser.add_argument(
            '--pending-only',
            action='store_true',
            help='Only sync connections with pending status (new connections)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force resync even if already completed',
        )
        parser.add_argument(
            '--max-conversations',
            type=int,
            default=100,
            help='Maximum conversations to sync per account (default: 100)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing',
        )

    def handle(self, *args, **options):
        from social_integrations.models import FacebookPageConnection, InstagramAccountConnection
        from social_integrations.facebook_sync_utils import (
            sync_facebook_conversations,
            sync_instagram_conversations,
        )

        tenant_schema = options.get('tenant')
        platform = options.get('platform', 'all')
        account_id = options.get('account_id')
        pending_only = options.get('pending_only', False)
        force = options.get('force', False)
        max_conversations = options.get('max_conversations', 100)
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

        # Statistics
        total_stats = {
            'facebook_pages': 0,
            'facebook_conversations': 0,
            'facebook_messages': 0,
            'instagram_accounts': 0,
            'instagram_conversations': 0,
            'instagram_messages': 0,
            'errors': 0,
        }

        for tenant in tenants:
            with schema_context(tenant.schema_name):
                try:
                    # Sync Facebook
                    if platform in ['facebook', 'all']:
                        self._sync_facebook(
                            tenant,
                            FacebookPageConnection,
                            sync_facebook_conversations,
                            account_id,
                            pending_only,
                            force,
                            max_conversations,
                            dry_run,
                            total_stats,
                        )

                    # Sync Instagram
                    if platform in ['instagram', 'all']:
                        self._sync_instagram(
                            tenant,
                            InstagramAccountConnection,
                            sync_instagram_conversations,
                            account_id,
                            pending_only,
                            force,
                            max_conversations,
                            dry_run,
                            total_stats,
                        )

                except Exception as e:
                    total_stats['errors'] += 1
                    self.stderr.write(
                        self.style.ERROR(f'Error processing tenant {tenant.schema_name}: {e}')
                    )
                    logger.error(f'Tenant processing error for {tenant.schema_name}: {e}')

        # Print summary
        self._print_summary(total_stats, dry_run)

    def _sync_facebook(
        self,
        tenant,
        model_class,
        sync_func,
        account_id,
        pending_only,
        force,
        max_conversations,
        dry_run,
        stats,
    ):
        """Sync Facebook pages for a tenant"""
        pages = model_class.objects.filter(is_active=True)

        if account_id:
            pages = pages.filter(page_id=account_id)

        if pending_only:
            pages = pages.filter(sync_status='pending')

        if not pages.exists():
            return

        for page in pages:
            if dry_run:
                self.stdout.write(
                    f'[DRY RUN] Would sync Facebook page: {page.page_name} '
                    f'({page.page_id}) for tenant {tenant.schema_name}'
                )
                stats['facebook_pages'] += 1
                continue

            try:
                self.stdout.write(
                    f'Syncing Facebook page: {page.page_name} ({page.page_id}) '
                    f'for tenant {tenant.schema_name}...'
                )

                result = sync_func(page, max_conversations=max_conversations, force=force)

                stats['facebook_pages'] += 1
                stats['facebook_conversations'] += result['conversations_synced']
                stats['facebook_messages'] += result['messages_synced']

                if result['errors']:
                    stats['errors'] += len(result['errors'])
                    for error in result['errors'][:3]:  # Show first 3 errors
                        self.stderr.write(self.style.WARNING(f'  Warning: {error}'))

                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Synced {result["conversations_synced"]} conversations, '
                        f'{result["messages_synced"]} messages'
                    )
                )

            except Exception as e:
                stats['errors'] += 1
                self.stderr.write(
                    self.style.ERROR(f'  Error syncing {page.page_name}: {e}')
                )
                logger.error(f'Facebook sync error for {page.page_name}: {e}')

    def _sync_instagram(
        self,
        tenant,
        model_class,
        sync_func,
        account_id,
        pending_only,
        force,
        max_conversations,
        dry_run,
        stats,
    ):
        """Sync Instagram accounts for a tenant"""
        accounts = model_class.objects.filter(is_active=True)

        if account_id:
            accounts = accounts.filter(instagram_account_id=account_id)

        if pending_only:
            accounts = accounts.filter(sync_status='pending')

        if not accounts.exists():
            return

        for account in accounts:
            if dry_run:
                self.stdout.write(
                    f'[DRY RUN] Would sync Instagram account: @{account.username} '
                    f'({account.instagram_account_id}) for tenant {tenant.schema_name}'
                )
                stats['instagram_accounts'] += 1
                continue

            try:
                self.stdout.write(
                    f'Syncing Instagram account: @{account.username} '
                    f'({account.instagram_account_id}) for tenant {tenant.schema_name}...'
                )

                result = sync_func(account, max_conversations=max_conversations, force=force)

                stats['instagram_accounts'] += 1
                stats['instagram_conversations'] += result['conversations_synced']
                stats['instagram_messages'] += result['messages_synced']

                if result['errors']:
                    stats['errors'] += len(result['errors'])
                    for error in result['errors'][:3]:  # Show first 3 errors
                        self.stderr.write(self.style.WARNING(f'  Warning: {error}'))

                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Synced {result["conversations_synced"]} conversations, '
                        f'{result["messages_synced"]} messages'
                    )
                )

            except Exception as e:
                stats['errors'] += 1
                self.stderr.write(
                    self.style.ERROR(f'  Error syncing @{account.username}: {e}')
                )
                logger.error(f'Instagram sync error for @{account.username}: {e}')

    def _print_summary(self, stats, dry_run):
        """Print sync summary"""
        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN] No messages were actually synced'))
            self.stdout.write(f'  Would sync {stats["facebook_pages"]} Facebook pages')
            self.stdout.write(f'  Would sync {stats["instagram_accounts"]} Instagram accounts')
            return

        self.stdout.write(self.style.SUCCESS('=== Sync Complete ==='))
        self.stdout.write(f'  Facebook pages: {stats["facebook_pages"]}')
        self.stdout.write(f'    Conversations: {stats["facebook_conversations"]}')
        self.stdout.write(f'    Messages: {stats["facebook_messages"]}')
        self.stdout.write(f'  Instagram accounts: {stats["instagram_accounts"]}')
        self.stdout.write(f'    Conversations: {stats["instagram_conversations"]}')
        self.stdout.write(f'    Messages: {stats["instagram_messages"]}')

        if stats['errors'] > 0:
            self.stdout.write(self.style.WARNING(f'  Errors: {stats["errors"]}'))
        else:
            self.stdout.write(self.style.SUCCESS('  Errors: 0'))
