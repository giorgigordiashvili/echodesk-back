"""
Calculate Platform Metrics Management Command

Calculates daily platform-wide subscription and revenue metrics.
Should be run via cron once per day (e.g., at midnight).

Usage:
    python manage.py calculate_platform_metrics [--date YYYY-MM-DD]
"""
import logging
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum, Count, Q
from tenants.models import (
    TenantSubscription,
    PaymentAttempt,
    PaymentRetrySchedule,
    SubscriptionEvent,
    PlatformMetrics,
    Package,
)
from tenants.subscription_utils import calculate_mrr, calculate_churn_rate

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Calculate daily platform metrics for analytics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date to calculate metrics for (YYYY-MM-DD format, defaults to today)',
        )

    def handle(self, *args, **options):
        # Parse date
        if options['date']:
            try:
                from datetime import datetime
                calc_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            calc_date = timezone.now().date()

        self.stdout.write(f'Calculating metrics for {calc_date}...')

        # Check if metrics already exist
        existing = PlatformMetrics.objects.filter(date=calc_date).first()
        if existing:
            self.stdout.write(self.style.WARNING(f'Metrics for {calc_date} already exist. Updating...'))
            metrics = existing
        else:
            metrics = PlatformMetrics(date=calc_date)

        # 1. Subscription counts
        all_subs = TenantSubscription.objects.all()

        metrics.total_subscriptions = all_subs.count()
        metrics.active_subscriptions = all_subs.filter(is_active=True).count()
        metrics.trial_subscriptions = all_subs.filter(is_trial=True, is_active=True).count()
        metrics.suspended_subscriptions = all_subs.filter(is_active=False).count()

        # Cancelled subscriptions (have cancelled event)
        metrics.cancelled_subscriptions = SubscriptionEvent.objects.filter(
            event_type='cancelled'
        ).values('subscription').distinct().count()

        # New subscriptions today
        start_of_day = timezone.make_aware(
            timezone.datetime.combine(calc_date, timezone.datetime.min.time())
        )
        end_of_day = start_of_day + timedelta(days=1)

        metrics.new_subscriptions_today = SubscriptionEvent.objects.filter(
            event_type='created',
            created_at__range=[start_of_day, end_of_day]
        ).count()

        # Cancelled today
        metrics.cancelled_today = SubscriptionEvent.objects.filter(
            event_type='cancelled',
            created_at__range=[start_of_day, end_of_day]
        ).count()

        self.stdout.write(f'  Subscriptions: {metrics.active_subscriptions} active, {metrics.trial_subscriptions} trial')

        # 2. Revenue metrics
        metrics.mrr = calculate_mrr(calc_date)
        metrics.arr = metrics.mrr * 12

        # Total revenue today (successful payments)
        revenue_today = PaymentAttempt.objects.filter(
            status='success',
            completed_at__range=[start_of_day, end_of_day]
        ).aggregate(total=Sum('amount'))['total'] or Decimal(0)

        metrics.total_revenue_today = revenue_today

        self.stdout.write(f'  Revenue: MRR={metrics.mrr} GEL, ARR={metrics.arr} GEL, Today={revenue_today} GEL')

        # 3. Payment metrics
        payments_today = PaymentAttempt.objects.filter(
            attempted_at__range=[start_of_day, end_of_day]
        )

        metrics.successful_payments = payments_today.filter(status='success').count()
        metrics.failed_payments = payments_today.filter(status='failed').count()

        # Retry success rate (retries that succeeded)
        retries_today = payments_today.filter(is_retry=True)
        retry_successes = retries_today.filter(status='success').count()
        retry_total = retries_today.count()

        if retry_total > 0:
            metrics.retry_success_rate = (Decimal(retry_successes) / Decimal(retry_total)) * 100
        else:
            metrics.retry_success_rate = Decimal(0)

        self.stdout.write(
            f'  Payments: {metrics.successful_payments} successful, '
            f'{metrics.failed_payments} failed, '
            f'Retry success: {metrics.retry_success_rate}%'
        )

        # 4. Churn metrics
        # Calculate 30-day churn rate
        thirty_days_ago = calc_date - timedelta(days=30)
        metrics.churn_rate = calculate_churn_rate(thirty_days_ago, calc_date)
        metrics.retention_rate = 100 - metrics.churn_rate

        self.stdout.write(f'  Churn: {metrics.churn_rate}%, Retention: {metrics.retention_rate}%')

        # 5. Package distribution
        package_dist = {}
        revenue_by_pkg = {}

        # Active subscriptions by package
        for pkg in Package.objects.all():
            subs_count = TenantSubscription.objects.filter(
                package=pkg,
                is_active=True
            ).count()

            if subs_count > 0:
                package_dist[pkg.name] = subs_count

                # Calculate revenue for this package
                pkg_revenue = sum(
                    sub.monthly_cost
                    for sub in TenantSubscription.objects.filter(package=pkg, is_active=True)
                )
                revenue_by_pkg[pkg.name] = float(pkg_revenue)

        # Feature-based subscriptions (no package)
        feature_based = TenantSubscription.objects.filter(
            package__isnull=True,
            is_active=True
        ).count()

        if feature_based > 0:
            package_dist['feature_based'] = feature_based
            feature_revenue = sum(
                sub.monthly_cost
                for sub in TenantSubscription.objects.filter(package__isnull=True, is_active=True)
            )
            revenue_by_pkg['feature_based'] = float(feature_revenue)

        metrics.package_distribution = package_dist
        metrics.revenue_by_package = revenue_by_pkg

        # Save metrics
        metrics.save()

        self.stdout.write(self.style.SUCCESS(f'\n✓ Metrics calculated and saved for {calc_date}'))

        # Display package breakdown
        if package_dist:
            self.stdout.write('\nPackage Distribution:')
            for pkg_name, count in package_dist.items():
                revenue = revenue_by_pkg.get(pkg_name, 0)
                self.stdout.write(f'  {pkg_name}: {count} subscriptions ({revenue} GEL/month)')

        logger.info(f'Platform metrics calculated for {calc_date}: MRR={metrics.mrr}, Active={metrics.active_subscriptions}')
