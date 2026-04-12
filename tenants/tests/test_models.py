"""
Tests for tenants model logic.
Covers TenantSubscription properties and methods, PaymentOrder status transitions,
TenantDomain creation/uniqueness, DashboardAppearanceSettings defaults,
UsageLog creation, SavedCard defaults, Invoice number generation, and
PendingRegistration expiration.
"""
from decimal import Decimal
from datetime import timedelta
import uuid

from django.utils import timezone
from django.db import IntegrityError

from users.tests.conftest import EchoDeskTenantTestCase
from tenants.models import (
    TenantSubscription,
    PaymentOrder,
    TenantDomain,
    DashboardAppearanceSettings,
    UsageLog,
    SavedCard,
    Invoice,
    PendingRegistration,
    SubscriptionEvent,
    PaymentAttempt,
    PaymentRetrySchedule,
    PlatformMetrics,
)
from tenants.feature_models import Feature


class SubscriptionModelTestMixin:
    """Shared helpers for subscription model tests."""

    def _make_feature(self, key='test_feature', price=Decimal('5.00'), **kwargs):
        defaults = {
            'key': key,
            'name': key.replace('_', ' ').title(),
            'price_per_user_gel': price,
            'price_unlimited_gel': Decimal('0'),
            'category': 'integration',
            'is_active': True,
        }
        defaults.update(kwargs)
        return Feature.objects.create(**defaults)

    def _make_subscription(self, **kwargs):
        defaults = {
            'tenant': self.tenant,
            'is_active': True,
            'starts_at': timezone.now(),
            'agent_count': 10,
            'payment_status': 'current',
        }
        defaults.update(kwargs)
        return TenantSubscription.objects.create(**defaults)

    def _make_payment_order(self, **kwargs):
        defaults = {
            'order_id': f'ORD-{uuid.uuid4().hex[:12]}',
            'tenant': self.tenant,
            'amount': Decimal('50.00'),
            'currency': 'GEL',
            'status': 'pending',
        }
        defaults.update(kwargs)
        return PaymentOrder.objects.create(**defaults)


# ============================================================================
# TenantSubscription
# ============================================================================

class TestTenantSubscription(SubscriptionModelTestMixin, EchoDeskTenantTestCase):

    def test_create_subscription(self):
        sub = self._make_subscription()
        self.assertTrue(sub.is_active)
        self.assertEqual(sub.agent_count, 10)

    def test_monthly_cost_no_features(self):
        sub = self._make_subscription()
        self.assertEqual(sub.monthly_cost, 0)

    def test_monthly_cost_with_features(self):
        sub = self._make_subscription(agent_count=10)
        feat = self._make_feature('cost_feat', price=Decimal('10.00'))
        sub.selected_features.add(feat)
        # 10.00 per user * 10 agents = 100.00
        self.assertEqual(sub.monthly_cost, Decimal('100.00'))

    def test_monthly_cost_multiple_features(self):
        sub = self._make_subscription(agent_count=20)
        f1 = self._make_feature('f1', price=Decimal('3.00'))
        f2 = self._make_feature('f2', price=Decimal('7.00'))
        sub.selected_features.add(f1, f2)
        # (3 + 7) * 20 = 200
        self.assertEqual(sub.monthly_cost, Decimal('200.00'))

    def test_is_over_user_limit(self):
        sub = self._make_subscription(agent_count=10)
        sub.current_users = 15
        sub.save()
        self.assertTrue(sub.is_over_user_limit)

    def test_is_not_over_user_limit(self):
        sub = self._make_subscription(agent_count=10)
        sub.current_users = 5
        sub.save()
        self.assertFalse(sub.is_over_user_limit)

    def test_is_over_whatsapp_limit(self):
        sub = self._make_subscription()
        sub.whatsapp_messages_used = 15000
        sub.save()
        self.assertTrue(sub.is_over_whatsapp_limit)

    def test_is_not_over_whatsapp_limit(self):
        sub = self._make_subscription()
        sub.whatsapp_messages_used = 5000
        sub.save()
        self.assertFalse(sub.is_over_whatsapp_limit)

    def test_is_over_storage_limit(self):
        sub = self._make_subscription()
        sub.storage_used_gb = Decimal('150')
        sub.save()
        self.assertTrue(sub.is_over_storage_limit)

    def test_is_not_over_storage_limit(self):
        sub = self._make_subscription()
        sub.storage_used_gb = Decimal('50')
        sub.save()
        self.assertFalse(sub.is_over_storage_limit)

    def test_can_add_user_true(self):
        sub = self._make_subscription(agent_count=10)
        sub.current_users = 5
        sub.save()
        self.assertTrue(sub.can_add_user())

    def test_can_add_user_false(self):
        sub = self._make_subscription(agent_count=10)
        sub.current_users = 10
        sub.save()
        self.assertFalse(sub.can_add_user())

    def test_can_send_whatsapp_message(self):
        """WhatsApp limits removed; always returns True."""
        sub = self._make_subscription()
        self.assertTrue(sub.can_send_whatsapp_message())

    def test_mark_payment_failed(self):
        sub = self._make_subscription()
        sub.mark_payment_failed()
        sub.refresh_from_db()
        self.assertEqual(sub.payment_status, 'retrying')
        self.assertEqual(sub.failed_payment_count, 1)
        self.assertIsNotNone(sub.last_payment_failure)

    def test_mark_payment_failed_increments(self):
        sub = self._make_subscription()
        sub.mark_payment_failed()
        sub.mark_payment_failed()
        sub.refresh_from_db()
        self.assertEqual(sub.failed_payment_count, 2)

    def test_mark_payment_succeeded(self):
        sub = self._make_subscription()
        sub.failed_payment_count = 3
        sub.payment_status = 'retrying'
        sub.last_payment_failure = timezone.now()
        sub.save()
        sub.mark_payment_succeeded()
        sub.refresh_from_db()
        self.assertEqual(sub.payment_status, 'current')
        self.assertEqual(sub.failed_payment_count, 0)
        self.assertIsNone(sub.last_payment_failure)

    def test_has_payment_issues_true(self):
        sub = self._make_subscription(payment_status='overdue')
        self.assertTrue(sub.has_payment_issues)

    def test_has_payment_issues_retrying(self):
        sub = self._make_subscription(payment_status='retrying')
        self.assertTrue(sub.has_payment_issues)

    def test_has_payment_issues_failed(self):
        sub = self._make_subscription(payment_status='failed')
        self.assertTrue(sub.has_payment_issues)

    def test_has_payment_issues_false(self):
        sub = self._make_subscription(payment_status='current')
        self.assertFalse(sub.has_payment_issues)

    def test_days_until_next_billing(self):
        sub = self._make_subscription()
        # Add extra hours to avoid off-by-one from sub-second elapsed time
        sub.next_billing_date = timezone.now() + timedelta(days=15, hours=1)
        sub.save()
        self.assertEqual(sub.days_until_next_billing, 15)

    def test_days_until_next_billing_none(self):
        sub = self._make_subscription()
        self.assertIsNone(sub.days_until_next_billing)

    def test_payment_health_status_display(self):
        sub = self._make_subscription(payment_status='current')
        self.assertIn('Current', sub.payment_health_status)

    def test_str_representation(self):
        sub = self._make_subscription()
        s = str(sub)
        self.assertIn('Test Tenant', s)
        self.assertIn('10', s)

    def test_trial_fields(self):
        sub = self._make_subscription(
            is_trial=True,
            trial_ends_at=timezone.now() + timedelta(days=14),
            subscription_type='trial',
        )
        self.assertTrue(sub.is_trial)
        self.assertFalse(sub.trial_converted)
        self.assertEqual(sub.subscription_type, 'trial')


# ============================================================================
# PaymentOrder
# ============================================================================

class TestPaymentOrder(SubscriptionModelTestMixin, EchoDeskTenantTestCase):

    def test_create_payment_order(self):
        po = self._make_payment_order()
        self.assertEqual(po.status, 'pending')
        self.assertEqual(po.amount, Decimal('50.00'))

    def test_status_transitions(self):
        po = self._make_payment_order(status='pending')
        po.status = 'paid'
        po.paid_at = timezone.now()
        po.save()
        po.refresh_from_db()
        self.assertEqual(po.status, 'paid')
        self.assertIsNotNone(po.paid_at)

    def test_status_to_failed(self):
        po = self._make_payment_order(status='pending')
        po.status = 'failed'
        po.save()
        po.refresh_from_db()
        self.assertEqual(po.status, 'failed')

    def test_status_to_cancelled(self):
        po = self._make_payment_order(status='pending')
        po.status = 'cancelled'
        po.save()
        po.refresh_from_db()
        self.assertEqual(po.status, 'cancelled')

    def test_order_id_unique(self):
        order_id = f'ORD-{uuid.uuid4().hex[:12]}'
        self._make_payment_order(order_id=order_id)
        with self.assertRaises(IntegrityError):
            self._make_payment_order(order_id=order_id)

    def test_str_representation(self):
        po = self._make_payment_order()
        self.assertIn('Test Tenant', str(po))
        self.assertIn('pending', str(po))

    def test_trial_payment(self):
        po = self._make_payment_order(
            amount=Decimal('0.00'), is_trial_payment=True,
        )
        self.assertTrue(po.is_trial_payment)
        self.assertEqual(po.amount, Decimal('0.00'))

    def test_card_saved_flag(self):
        po = self._make_payment_order(card_saved=True)
        self.assertTrue(po.card_saved)

    def test_payment_provider_default(self):
        po = self._make_payment_order()
        self.assertEqual(po.payment_provider, 'bog')


# ============================================================================
# TenantDomain
# ============================================================================

class TestTenantDomain(EchoDeskTenantTestCase):

    def test_create_domain(self):
        domain = TenantDomain.objects.create(
            tenant=self.tenant, domain='shop.example.com',
        )
        self.assertEqual(domain.domain, 'shop.example.com')
        self.assertFalse(domain.is_verified)
        self.assertFalse(domain.is_primary)

    def test_domain_normalized_to_lowercase(self):
        domain = TenantDomain.objects.create(
            tenant=self.tenant, domain='SHOP.EXAMPLE.COM',
        )
        self.assertEqual(domain.domain, 'shop.example.com')

    def test_domain_uniqueness(self):
        TenantDomain.objects.create(
            tenant=self.tenant, domain='unique.example.com',
        )
        with self.assertRaises(IntegrityError):
            TenantDomain.objects.create(
                tenant=self.tenant, domain='unique.example.com',
            )

    def test_primary_domain_uniqueness(self):
        """Setting a new primary domain unsets the previous one."""
        d1 = TenantDomain.objects.create(
            tenant=self.tenant, domain='d1.example.com', is_primary=True,
        )
        d2 = TenantDomain.objects.create(
            tenant=self.tenant, domain='d2.example.com', is_primary=True,
        )
        d1.refresh_from_db()
        d2.refresh_from_db()
        self.assertFalse(d1.is_primary)
        self.assertTrue(d2.is_primary)

    def test_str_representation(self):
        domain = TenantDomain.objects.create(
            tenant=self.tenant, domain='test.example.com',
        )
        s = str(domain)
        self.assertIn('test.example.com', s)
        self.assertIn('Test Tenant', s)


# ============================================================================
# DashboardAppearanceSettings
# ============================================================================

class TestDashboardAppearanceSettings(EchoDeskTenantTestCase):

    def test_create_with_defaults(self):
        settings = DashboardAppearanceSettings.objects.create(tenant=self.tenant)
        self.assertEqual(settings.primary_color, '240 5.9% 10%')
        self.assertEqual(settings.primary_color_dark, '0 0% 98%')
        self.assertEqual(settings.secondary_color, '239 49% 32%')
        self.assertEqual(settings.accent_color, '240 4.8% 95.9%')
        self.assertEqual(settings.sidebar_background, '0 0% 100%')
        self.assertEqual(settings.sidebar_primary, '240 5.9% 10%')
        self.assertEqual(settings.border_radius, '0.5rem')
        self.assertEqual(settings.sidebar_order, [])

    def test_custom_values(self):
        settings = DashboardAppearanceSettings.objects.create(
            tenant=self.tenant,
            primary_color='200 50% 50%',
            border_radius='1rem',
            sidebar_order=['dashboard', 'tickets', 'settings'],
        )
        self.assertEqual(settings.primary_color, '200 50% 50%')
        self.assertEqual(settings.border_radius, '1rem')
        self.assertEqual(len(settings.sidebar_order), 3)

    def test_str_representation(self):
        settings = DashboardAppearanceSettings.objects.create(tenant=self.tenant)
        self.assertIn('Test Tenant', str(settings))

    def test_one_to_one_with_tenant(self):
        DashboardAppearanceSettings.objects.create(tenant=self.tenant)
        with self.assertRaises(IntegrityError):
            DashboardAppearanceSettings.objects.create(tenant=self.tenant)


# ============================================================================
# UsageLog
# ============================================================================

class TestUsageLog(SubscriptionModelTestMixin, EchoDeskTenantTestCase):

    def test_create_usage_log(self):
        sub = self._make_subscription()
        log = UsageLog.objects.create(
            subscription=sub,
            event_type='user_added',
            quantity=1,
            metadata={'user_email': 'new@test.com'},
        )
        self.assertEqual(log.event_type, 'user_added')
        self.assertEqual(log.quantity, 1)

    def test_usage_log_str(self):
        sub = self._make_subscription()
        log = UsageLog.objects.create(
            subscription=sub,
            event_type='whatsapp_message',
            quantity=5,
        )
        s = str(log)
        self.assertIn('Test Tenant', s)
        self.assertIn('whatsapp_message', s)

    def test_multiple_event_types(self):
        sub = self._make_subscription()
        for event_type in ['user_added', 'user_removed', 'whatsapp_message', 'storage_usage', 'feature_used']:
            log = UsageLog.objects.create(
                subscription=sub,
                event_type=event_type,
                quantity=1,
            )
            self.assertEqual(log.event_type, event_type)

    def test_usage_log_metadata(self):
        sub = self._make_subscription()
        meta = {'feature_key': 'whatsapp', 'action': 'send'}
        log = UsageLog.objects.create(
            subscription=sub,
            event_type='feature_used',
            quantity=1,
            metadata=meta,
        )
        self.assertEqual(log.metadata['feature_key'], 'whatsapp')


# ============================================================================
# SavedCard
# ============================================================================

class TestSavedCard(EchoDeskTenantTestCase):

    def test_create_saved_card(self):
        card = SavedCard.objects.create(
            tenant=self.tenant,
            parent_order_id='BOG-12345',
            card_type='visa',
            masked_card_number='4111***1111',
            card_expiry='12/27',
        )
        self.assertTrue(card.is_active)
        # First card should be made default automatically
        self.assertTrue(card.is_default)

    def test_second_card_not_default(self):
        SavedCard.objects.create(
            tenant=self.tenant,
            parent_order_id='BOG-111',
            card_type='visa',
            masked_card_number='4111***1111',
        )
        card2 = SavedCard.objects.create(
            tenant=self.tenant,
            parent_order_id='BOG-222',
            card_type='mc',
            masked_card_number='5311***1450',
        )
        self.assertFalse(card2.is_default)

    def test_set_new_default_unsets_old(self):
        card1 = SavedCard.objects.create(
            tenant=self.tenant,
            parent_order_id='BOG-AAA',
            is_default=True,
        )
        card2 = SavedCard.objects.create(
            tenant=self.tenant,
            parent_order_id='BOG-BBB',
            is_default=True,
        )
        card1.refresh_from_db()
        card2.refresh_from_db()
        self.assertFalse(card1.is_default)
        self.assertTrue(card2.is_default)

    def test_str_representation(self):
        card = SavedCard.objects.create(
            tenant=self.tenant,
            parent_order_id='BOG-STR',
            card_type='mc',
            masked_card_number='531125***1450',
        )
        s = str(card)
        self.assertIn('MC', s)
        self.assertIn('531125***1450', s)

    def test_parent_order_id_unique(self):
        SavedCard.objects.create(
            tenant=self.tenant, parent_order_id='UNIQUE-POI',
        )
        with self.assertRaises(IntegrityError):
            SavedCard.objects.create(
                tenant=self.tenant, parent_order_id='UNIQUE-POI',
            )


# ============================================================================
# Invoice
# ============================================================================

class TestInvoice(SubscriptionModelTestMixin, EchoDeskTenantTestCase):

    def test_create_invoice(self):
        po = self._make_payment_order(status='paid')
        inv = Invoice.objects.create(
            tenant=self.tenant,
            payment_order=po,
            amount=Decimal('100.00'),
            description='Monthly subscription',
        )
        self.assertTrue(inv.invoice_number.startswith('INV-'))
        self.assertEqual(inv.amount, Decimal('100.00'))

    def test_auto_generate_invoice_number(self):
        po = self._make_payment_order(status='paid')
        inv = Invoice(
            tenant=self.tenant,
            payment_order=po,
            amount=Decimal('50.00'),
            description='Test',
        )
        inv.save()
        self.assertTrue(inv.invoice_number.startswith('INV-'))

    def test_invoice_number_sequence(self):
        po1 = self._make_payment_order(status='paid')
        po2 = self._make_payment_order(status='paid')
        inv1 = Invoice.objects.create(
            tenant=self.tenant, payment_order=po1,
            amount=Decimal('50.00'), description='First',
        )
        inv2 = Invoice.objects.create(
            tenant=self.tenant, payment_order=po2,
            amount=Decimal('60.00'), description='Second',
        )
        # Both should have unique invoice numbers
        self.assertNotEqual(inv1.invoice_number, inv2.invoice_number)

    def test_str_representation(self):
        po = self._make_payment_order(status='paid')
        inv = Invoice.objects.create(
            tenant=self.tenant, payment_order=po,
            amount=Decimal('75.00'), description='Test',
        )
        s = str(inv)
        self.assertIn('INV-', s)
        self.assertIn('Test Tenant', s)


# ============================================================================
# PendingRegistration
# ============================================================================

class TestPendingRegistration(EchoDeskTenantTestCase):

    def _make_pending(self, **kwargs):
        defaults = {
            'schema_name': f'pending_{uuid.uuid4().hex[:8]}',
            'name': 'Pending Tenant',
            'admin_email': 'pending@test.com',
            'admin_password': 'hashed_password',
            'admin_first_name': 'Test',
            'admin_last_name': 'Admin',
            'order_id': f'ORD-{uuid.uuid4().hex[:12]}',
            'expires_at': timezone.now() + timedelta(hours=1),
        }
        defaults.update(kwargs)
        return PendingRegistration.objects.create(**defaults)

    def test_create_pending_registration(self):
        pr = self._make_pending()
        self.assertFalse(pr.is_processed)
        self.assertFalse(pr.is_expired)

    def test_is_expired(self):
        pr = self._make_pending(
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertTrue(pr.is_expired)

    def test_can_process_true(self):
        pr = self._make_pending()
        self.assertTrue(pr.can_process())

    def test_can_process_false_when_processed(self):
        pr = self._make_pending(is_processed=True)
        self.assertFalse(pr.can_process())

    def test_can_process_false_when_expired(self):
        pr = self._make_pending(
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertFalse(pr.can_process())

    def test_auto_set_expiration(self):
        """If expires_at not set, save() should set it to +1 hour."""
        pr = PendingRegistration(
            schema_name=f'auto_{uuid.uuid4().hex[:8]}',
            name='Auto',
            admin_email='auto@test.com',
            admin_password='pass',
            admin_first_name='A',
            admin_last_name='B',
            order_id=f'ORD-{uuid.uuid4().hex[:12]}',
        )
        # Remove expires_at to let save() set it
        pr.expires_at = None
        pr.save()
        pr.refresh_from_db()
        self.assertIsNotNone(pr.expires_at)

    def test_str_representation(self):
        pr = self._make_pending()
        s = str(pr)
        self.assertIn('Pending Tenant', s)
        self.assertIn('Pending', s)


# ============================================================================
# SubscriptionEvent
# ============================================================================

class TestSubscriptionEvent(SubscriptionModelTestMixin, EchoDeskTenantTestCase):

    def test_create_event(self):
        sub = self._make_subscription()
        event = SubscriptionEvent.objects.create(
            subscription=sub,
            tenant=self.tenant,
            event_type='created',
            description='Subscription created',
        )
        self.assertEqual(event.event_type, 'created')

    def test_event_with_metadata(self):
        sub = self._make_subscription()
        event = SubscriptionEvent.objects.create(
            subscription=sub,
            tenant=self.tenant,
            event_type='feature_added',
            description='Added whatsapp',
            metadata={'feature_key': 'whatsapp'},
        )
        self.assertEqual(event.metadata['feature_key'], 'whatsapp')

    def test_event_str(self):
        sub = self._make_subscription()
        event = SubscriptionEvent.objects.create(
            subscription=sub,
            tenant=self.tenant,
            event_type='payment_success',
            description='Payment succeeded',
        )
        s = str(event)
        self.assertIn('Test Tenant', s)


# ============================================================================
# PaymentAttempt
# ============================================================================

class TestPaymentAttempt(SubscriptionModelTestMixin, EchoDeskTenantTestCase):

    def test_create_attempt(self):
        po = self._make_payment_order()
        sub = self._make_subscription()
        attempt = PaymentAttempt.objects.create(
            payment_order=po,
            subscription=sub,
            tenant=self.tenant,
            amount=Decimal('50.00'),
            attempt_number=1,
        )
        self.assertEqual(attempt.status, 'pending')
        self.assertEqual(attempt.attempt_number, 1)

    def test_duration_property(self):
        po = self._make_payment_order()
        attempt = PaymentAttempt.objects.create(
            payment_order=po,
            tenant=self.tenant,
            amount=Decimal('50.00'),
        )
        self.assertIsNone(attempt.duration)
        attempt.completed_at = attempt.attempted_at + timedelta(seconds=5)
        attempt.save()
        self.assertIsNotNone(attempt.duration)
        self.assertGreater(attempt.duration, 0)

    def test_str_representation(self):
        po = self._make_payment_order()
        attempt = PaymentAttempt.objects.create(
            payment_order=po,
            tenant=self.tenant,
            amount=Decimal('50.00'),
        )
        s = str(attempt)
        self.assertIn('Test Tenant', s)
        self.assertIn('50', s)


# ============================================================================
# PlatformMetrics
# ============================================================================

class TestPlatformMetrics(EchoDeskTenantTestCase):

    def test_create_metrics(self):
        from datetime import date
        metrics = PlatformMetrics.objects.create(
            date=date.today(),
            total_subscriptions=100,
            active_subscriptions=90,
            successful_payments=80,
            failed_payments=20,
            mrr=Decimal('5000.00'),
        )
        self.assertEqual(metrics.active_subscriptions, 90)
        self.assertEqual(metrics.mrr, Decimal('5000.00'))

    def test_payment_success_rate(self):
        from datetime import date
        metrics = PlatformMetrics.objects.create(
            date=date.today(),
            successful_payments=75,
            failed_payments=25,
        )
        self.assertEqual(metrics.payment_success_rate, 75.0)

    def test_payment_success_rate_zero(self):
        from datetime import date
        metrics = PlatformMetrics.objects.create(
            date=date.today() - timedelta(days=1),
            successful_payments=0,
            failed_payments=0,
        )
        self.assertEqual(metrics.payment_success_rate, 0)

    def test_str_representation(self):
        from datetime import date
        metrics = PlatformMetrics.objects.create(
            date=date.today() - timedelta(days=2),
        )
        s = str(metrics)
        self.assertIn('Metrics', s)
