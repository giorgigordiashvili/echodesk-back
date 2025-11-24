"""
Management command to subscribe WhatsApp Business Accounts to webhooks

This command subscribes all connected WhatsApp Business Accounts to the necessary webhook fields.
Useful for:
- Fixing accounts that were connected without proper webhook subscriptions
- Re-subscribing after webhook configuration changes

Usage:
    python manage.py subscribe_whatsapp_webhooks
    python manage.py subscribe_whatsapp_webhooks --tenant=groot
"""

from django.core.management.base import BaseCommand
from tenant_schemas.utils import schema_context
from tenants.models import Tenant
from social_integrations.models import WhatsAppBusinessAccount
import requests
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Subscribe all connected WhatsApp Business Accounts to webhooks'

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
        """Process WhatsApp webhook subscriptions for a single tenant"""
        self.stdout.write(f'\nProcessing tenant: {tenant.schema_name}')

        with schema_context(tenant.schema_name):
            accounts = WhatsAppBusinessAccount.objects.filter(is_active=True)

            if not accounts.exists():
                self.stdout.write(f'  No WhatsApp accounts found for {tenant.schema_name}')
                return

            self.stdout.write(f'  Found {accounts.count()} WhatsApp account(s)')

            for account in accounts:
                self.subscribe_account(account)

    def subscribe_account(self, account):
        """Subscribe a single WhatsApp Business Account to webhooks"""
        try:
            # Subscribe WABA to webhooks with required fields
            subscribe_url = f"https://graph.facebook.com/v23.0/{account.waba_id}/subscribed_apps"
            subscribe_params = {
                'access_token': account.access_token,
                'subscribed_fields': 'messages,message_template_status_update'
            }

            self.stdout.write(f'    Subscribing: {account.business_name} ({account.display_phone_number})...')
            subscribe_response = requests.post(subscribe_url, params=subscribe_params)
            subscribe_data = subscribe_response.json()

            if subscribe_response.status_code == 200 and subscribe_data.get('success'):
                self.stdout.write(self.style.SUCCESS(
                    f'    ✓ Successfully subscribed {account.business_name}'
                ))

                # Verify subscription
                verify_url = f"https://graph.facebook.com/v23.0/{account.waba_id}/subscribed_apps"
                verify_params = {
                    'access_token': account.access_token
                }
                verify_response = requests.get(verify_url, params=verify_params)
                verify_data = verify_response.json()

                if verify_data.get('data'):
                    self.stdout.write(f'    ✓ Verified: App is subscribed')
                else:
                    self.stdout.write(self.style.WARNING(
                        f'    ⚠ Warning: Could not verify subscription'
                    ))
            else:
                self.stdout.write(self.style.ERROR(
                    f'    ✗ Failed to subscribe {account.business_name}: {subscribe_data}'
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'    ✗ Error subscribing {account.business_name}: {str(e)}'
            ))
