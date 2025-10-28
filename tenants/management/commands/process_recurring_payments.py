"""
Django management command to process monthly recurring subscription payments

Run daily via cron:
0 2 * * * cd /path/to/project && python manage.py process_recurring_payments
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from tenants.models import TenantSubscription, PaymentOrder, Tenant
from tenants.bog_payment import bog_service
import logging
import uuid

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process recurring subscription payments for tenants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be charged without actually processing payments',
        )
        parser.add_argument(
            '--days-before',
            type=int,
            default=3,
            help='Process subscriptions expiring within N days (default: 3)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days_before = options['days_before']

        self.stdout.write(self.style.SUCCESS(
            f'Starting recurring payment processing (dry_run={dry_run}, days_before={days_before})'
        ))

        # Find subscriptions that need renewal
        cutoff_date = timezone.now() + timedelta(days=days_before)
        subscriptions_to_renew = TenantSubscription.objects.filter(
            is_active=True,
            next_billing_date__lte=cutoff_date,
            tenant__is_active=True
        ).select_related('tenant', 'package')

        self.stdout.write(f'Found {subscriptions_to_renew.count()} subscriptions to process')

        success_count = 0
        failed_count = 0
        skipped_count = 0

        for subscription in subscriptions_to_renew:
            tenant = subscription.tenant
            package = subscription.package

            try:
                # Find the original payment order with saved card
                payment_order = PaymentOrder.objects.filter(
                    tenant=tenant,
                    card_saved=True,
                    bog_order_id__isnull=False,
                    status='paid'
                ).order_by('-paid_at').first()

                if not payment_order:
                    self.stdout.write(self.style.WARNING(
                        f'⚠️  {tenant.schema_name}: No saved card found, skipping'
                    ))
                    skipped_count += 1
                    continue

                # Calculate amount
                from tenants.models import PricingModel
                if package.pricing_model == PricingModel.AGENT_BASED:
                    amount = float(package.price_gel) * subscription.agent_count
                else:
                    amount = float(package.price_gel)

                self.stdout.write(
                    f'📋 {tenant.schema_name}: Charging {amount} GEL '
                    f'(expires: {subscription.expires_at.date()})'
                )

                if dry_run:
                    self.stdout.write(self.style.WARNING('   [DRY RUN] Would charge saved card'))
                    success_count += 1
                    continue

                # Generate new order ID for this charge
                new_order_id = f"REC-{uuid.uuid4().hex[:12].upper()}"

                # Charge the saved card
                charge_result = bog_service.charge_saved_card(
                    parent_order_id=payment_order.bog_order_id,
                    amount=amount,
                    currency='GEL',
                    callback_url=f"https://api.echodesk.ge/api/payments/webhook/",
                    external_order_id=new_order_id
                )

                # Create new payment order for tracking
                new_payment_order = PaymentOrder.objects.create(
                    order_id=new_order_id,
                    bog_order_id=charge_result['order_id'],
                    tenant=tenant,
                    package=package,
                    amount=amount,
                    currency='GEL',
                    agent_count=subscription.agent_count,
                    status='pending',
                    card_saved=False,  # This is a charge, not a new card save
                    metadata={
                        'type': 'recurring',
                        'parent_order_id': payment_order.bog_order_id,
                        'subscription_id': subscription.id
                    }
                )

                self.stdout.write(self.style.SUCCESS(
                    f'   ✓ Charged saved card: new_order_id={new_order_id}'
                ))
                success_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'   ✗ {tenant.schema_name}: Failed - {str(e)}'
                ))
                logger.error(f'Recurring payment failed for {tenant.schema_name}: {e}')
                failed_count += 1

                # TODO: Send notification email to tenant about failed payment
                # TODO: Implement grace period logic (e.g., 7 days before suspending)

        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('Recurring Payment Processing Complete'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'✓ Success: {success_count}')
        self.stdout.write(f'✗ Failed:  {failed_count}')
        self.stdout.write(f'⊘ Skipped: {skipped_count} (no saved card)')
        self.stdout.write(self.style.SUCCESS('='*60))

        if not dry_run:
            logger.info(
                f'Recurring payments processed: '
                f'{success_count} success, {failed_count} failed, {skipped_count} skipped'
            )
