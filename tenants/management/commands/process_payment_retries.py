"""
Process Payment Retries Management Command

Executes scheduled payment retries for failed payments.
Should be run via cron every hour.

Usage:
    python manage.py process_payment_retries [--dry-run]
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from tenants.models import PaymentRetrySchedule, SubscriptionEvent
from tenants.subscription_utils import execute_retry, suspend_subscription_for_payment_failure

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process scheduled payment retries for failed payments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually executing retries',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No actual retries will be executed'))

        # Find retries that are due
        pending_retries = PaymentRetrySchedule.objects.filter(
            status='pending',
            scheduled_for__lte=now
        ).select_related('subscription', 'tenant', 'payment_order', 'original_attempt').order_by('scheduled_for')

        retry_count = pending_retries.count()

        if retry_count == 0:
            self.stdout.write(self.style.SUCCESS('No retries scheduled for execution'))
            return

        self.stdout.write(f'Found {retry_count} retries to execute')

        # Process each retry
        success_count = 0
        failure_count = 0
        suspended_count = 0

        for retry in pending_retries:
            subscription = retry.subscription
            tenant = retry.tenant

            self.stdout.write(
                f'\nProcessing retry #{retry.retry_number} for {tenant.name} '
                f'(scheduled: {retry.scheduled_for})'
            )
            self.stdout.write(f'  Amount: {retry.payment_order.amount} GEL')
            self.stdout.write(f'  Original failure: {retry.original_attempt.attempted_at}')

            if dry_run:
                self.stdout.write(self.style.WARNING('  [DRY RUN] Would execute retry'))
                continue

            # Execute the retry
            result = execute_retry(retry)

            if result['success']:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Retry executed successfully'))
                self.stdout.write(f'  BOG Order ID: {result["bog_order_id"]}')
                success_count += 1

                # Note: Actual payment success/failure will be determined by webhook
                # This just means we successfully initiated the retry

            else:
                self.stdout.write(self.style.ERROR(f'  ✗ Retry execution failed: {result["error"]}'))
                failure_count += 1

                # Check if this was the last retry
                remaining_retries = PaymentRetrySchedule.objects.filter(
                    subscription=subscription,
                    status='pending',
                    retry_number__gt=retry.retry_number
                ).count()

                if remaining_retries == 0:
                    # All retries exhausted - suspend subscription
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ⚠ All retries exhausted for {tenant.name} - SUSPENDING subscription'
                        )
                    )

                    suspend_subscription_for_payment_failure(subscription)
                    suspended_count += 1

        # Summary
        if not dry_run:
            self.stdout.write('\n' + '='*50)
            self.stdout.write(self.style.SUCCESS(f'Retry Processing Complete:'))
            self.stdout.write(f'  Total retries: {retry_count}')
            self.stdout.write(self.style.SUCCESS(f'  Successfully initiated: {success_count}'))
            if failure_count > 0:
                self.stdout.write(self.style.ERROR(f'  Failed to initiate: {failure_count}'))
            if suspended_count > 0:
                self.stdout.write(self.style.ERROR(f'  Subscriptions suspended: {suspended_count}'))

            logger.info(
                f'Processed {retry_count} payment retries: '
                f'{success_count} initiated, {failure_count} failed, {suspended_count} suspended'
            )
