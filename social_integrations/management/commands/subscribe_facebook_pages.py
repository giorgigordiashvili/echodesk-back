"""
Management command to subscribe existing Facebook pages to webhooks

This command subscribes all connected Facebook pages to the app's webhooks.
Useful for:
- Fixing pages that were connected before webhook subscription was automated
- Re-subscribing pages after app changes
- Testing webhook subscriptions

Usage:
    python manage.py subscribe_facebook_pages
    python manage.py subscribe_facebook_pages --tenant=amanati
"""

from django.core.management.base import BaseCommand
from tenant_schemas.utils import schema_context, get_public_schema_name
from tenants.models import Tenant
from social_integrations.models import FacebookPageConnection
import requests
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Subscribe all connected Facebook pages to webhooks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Process only a specific tenant schema (optional)',
        )

    def handle(self, *args, **options):
        tenant_name = options.get('tenant')

        if tenant_name:
            # Process specific tenant
            try:
                tenant = Tenant.objects.get(schema_name=tenant_name)
                self.process_tenant(tenant)
            except Tenant.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Tenant {tenant_name} not found'))
        else:
            # Process all tenants
            tenants = Tenant.objects.filter(is_active=True)
            self.stdout.write(f'Processing {tenants.count()} tenant(s)')

            for tenant in tenants:
                self.process_tenant(tenant)

    def process_tenant(self, tenant):
        """Process Facebook page subscriptions for a single tenant"""
        self.stdout.write(f'\nProcessing tenant: {tenant.schema_name}')

        with schema_context(tenant.schema_name):
            pages = FacebookPageConnection.objects.filter(is_active=True)

            if not pages.exists():
                self.stdout.write(f'  No Facebook pages found for {tenant.schema_name}')
                return

            self.stdout.write(f'  Found {pages.count()} Facebook page(s)')

            for page in pages:
                self.subscribe_page(page)

    def subscribe_page(self, page):
        """Subscribe a single Facebook page to webhooks"""
        try:
            subscribe_url = f"https://graph.facebook.com/v23.0/{page.page_id}/subscribed_apps"
            subscribe_params = {
                'subscribed_fields': 'messages,messaging_postbacks,message_reads,message_deliveries',
                'access_token': page.page_access_token
            }

            self.stdout.write(f'    Subscribing page: {page.page_name} ({page.page_id})...')
            subscribe_response = requests.post(subscribe_url, params=subscribe_params)
            subscribe_data = subscribe_response.json()

            if subscribe_response.status_code == 200 and subscribe_data.get('success'):
                self.stdout.write(self.style.SUCCESS(
                    f'    ✓ Successfully subscribed {page.page_name}'
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f'    ✗ Failed to subscribe {page.page_name}: {subscribe_data}'
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'    ✗ Error subscribing {page.page_name}: {str(e)}'
            ))
