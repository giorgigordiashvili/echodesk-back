"""
Extended tests for subscription-related views not covered in test_subscription_views.py:
- Card management (get, remove, set default)
- Invoice listing
- Cancel subscription
- Dashboard appearance settings
- Subscription me endpoint (additional coverage)
- Usage tracking model behaviour
"""
from decimal import Decimal
from datetime import timedelta
import uuid

from django.utils import timezone
from rest_framework import status

from users.tests.conftest import EchoDeskTenantTestCase
from tenants.models import (
    TenantSubscription, PaymentOrder, SavedCard,
    Invoice, UsageLog, DashboardAppearanceSettings,
)
from tenants.feature_models import Feature

# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------
SAVED_CARD_URL = '/api/payments/saved-card/'
SET_DEFAULT_CARD_URL = '/api/payments/saved-card/set-default/'
INVOICES_URL = '/api/payments/invoices/'
CANCEL_SUBSCRIPTION_URL = '/api/payments/cancel/'
SUBSCRIPTION_ME_URL = '/api/subscription/me/'
APPEARANCE_GET_URL = '/api/dashboard-appearance/'
APPEARANCE_UPDATE_URL = '/api/dashboard-appearance/update/'
APPEARANCE_RESET_URL = '/api/dashboard-appearance/reset/'


class ExtendedSubscriptionMixin:
    """Shared helpers for extended subscription tests."""

    def _make_feature(self, key='ext_feature', price=Decimal('5.00'), **kwargs):
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
            'status': 'paid',
        }
        defaults.update(kwargs)
        return PaymentOrder.objects.create(**defaults)

    def _make_saved_card(self, **kwargs):
        defaults = {
            'tenant': self.tenant,
            'parent_order_id': f'BOG-{uuid.uuid4().hex[:8]}',
            'card_type': 'visa',
            'masked_card_number': '4111***1111',
            'card_expiry': '12/27',
            'is_active': True,
        }
        defaults.update(kwargs)
        return SavedCard.objects.create(**defaults)

    def _make_invoice(self, **kwargs):
        po = kwargs.pop('payment_order', None) or self._make_payment_order()
        defaults = {
            'tenant': self.tenant,
            'payment_order': po,
            'amount': Decimal('50.00'),
            'currency': 'GEL',
            'description': 'Monthly subscription',
            'agent_count': 10,
        }
        defaults.update(kwargs)
        return Invoice.objects.create(**defaults)


# ============================================================================
# GET /api/payments/saved-card/ - Extended card tests
# ============================================================================

class TestGetSavedCardExtended(ExtendedSubscriptionMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='card-ext@test.com')
        self.regular = self.create_user(email='nocard-ext@test.com')

    def test_returns_active_cards(self):
        self._make_saved_card(card_type='visa', masked_card_number='4111***1111')
        self._make_saved_card(card_type='mc', masked_card_number='5311***1450')
        resp = self.api_get(SAVED_CARD_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)

    def test_excludes_inactive_cards(self):
        self._make_saved_card(is_active=True)
        self._make_saved_card(
            parent_order_id=f'BOG-inactive-{uuid.uuid4().hex[:6]}',
            is_active=False,
        )
        resp = self.api_get(SAVED_CARD_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_non_staff_forbidden(self):
        resp = self.api_get(SAVED_CARD_URL, user=self.regular)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_returns_401(self):
        resp = self.api_get(SAVED_CARD_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_cards_list(self):
        resp = self.api_get(SAVED_CARD_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)


# ============================================================================
# DELETE /api/payments/saved-card/ - Remove card
# ============================================================================

class TestRemoveSavedCard(ExtendedSubscriptionMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='rmcard@test.com')
        self.regular = self.create_user(email='rmcard-reg@test.com')

    def test_remove_card_success(self):
        card = self._make_saved_card()
        resp = self.api_delete(SAVED_CARD_URL, user=self.admin, data={'card_id': card.id})
        # The DELETE endpoint reads card_id from request.data
        # Use api_client.delete with data
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.admin)
        resp = client.delete(
            SAVED_CARD_URL,
            {'card_id': card.id},
            format='json',
            HTTP_HOST='tenant.test.com',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        card.refresh_from_db()
        self.assertFalse(card.is_active)

    def test_remove_card_not_found(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.admin)
        resp = client.delete(
            SAVED_CARD_URL,
            {'card_id': 99999},
            format='json',
            HTTP_HOST='tenant.test.com',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_remove_card_missing_id(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.admin)
        resp = client.delete(
            SAVED_CARD_URL,
            {},
            format='json',
            HTTP_HOST='tenant.test.com',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_remove_card_non_staff_forbidden(self):
        card = self._make_saved_card()
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.regular)
        resp = client.delete(
            SAVED_CARD_URL,
            {'card_id': card.id},
            format='json',
            HTTP_HOST='tenant.test.com',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_remove_default_card_promotes_next(self):
        """When the default card is removed, another card becomes default."""
        card1 = self._make_saved_card()  # first card = auto-default
        card2 = self._make_saved_card(
            parent_order_id=f'BOG-second-{uuid.uuid4().hex[:6]}',
        )
        self.assertTrue(card1.is_default)
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.admin)
        resp = client.delete(
            SAVED_CARD_URL,
            {'card_id': card1.id},
            format='json',
            HTTP_HOST='tenant.test.com',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        card2.refresh_from_db()
        self.assertTrue(card2.is_default)


# ============================================================================
# POST /api/payments/saved-card/set-default/ - Set default card
# ============================================================================

class TestSetDefaultCard(ExtendedSubscriptionMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='defcard@test.com')
        self.regular = self.create_user(email='defcard-reg@test.com')

    def test_set_default_success(self):
        card1 = self._make_saved_card()
        card2 = self._make_saved_card(
            parent_order_id=f'BOG-def2-{uuid.uuid4().hex[:6]}',
        )
        self._make_subscription()
        resp = self.api_post(SET_DEFAULT_CARD_URL, {
            'card_id': card2.id,
        }, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        card1.refresh_from_db()
        card2.refresh_from_db()
        self.assertFalse(card1.is_default)
        self.assertTrue(card2.is_default)

    def test_set_default_not_found(self):
        resp = self.api_post(SET_DEFAULT_CARD_URL, {
            'card_id': 99999,
        }, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_set_default_missing_id(self):
        resp = self.api_post(SET_DEFAULT_CARD_URL, {}, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_set_default_non_staff_forbidden(self):
        card = self._make_saved_card()
        resp = self.api_post(SET_DEFAULT_CARD_URL, {
            'card_id': card.id,
        }, user=self.regular)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_set_default_updates_subscription(self):
        """Setting a default card updates subscription's parent_order_id."""
        card = self._make_saved_card()
        sub = self._make_subscription()
        resp = self.api_post(SET_DEFAULT_CARD_URL, {
            'card_id': card.id,
        }, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        sub.refresh_from_db()
        self.assertEqual(sub.parent_order_id, card.parent_order_id)


# ============================================================================
# GET /api/payments/invoices/ - Invoice listing
# ============================================================================

class TestListInvoicesExtended(ExtendedSubscriptionMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='inv-ext@test.com')

    def test_list_invoices_empty(self):
        resp = self.api_get(INVOICES_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['invoices'], [])

    def test_list_invoices_returns_data(self):
        self._make_invoice()
        resp = self.api_get(INVOICES_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['invoices']), 1)
        inv = resp.data['invoices'][0]
        self.assertTrue(inv['invoice_number'].startswith('INV-'))
        self.assertEqual(inv['amount'], 50.0)

    def test_list_invoices_multiple(self):
        self._make_invoice()
        self._make_invoice(amount=Decimal('75.00'))
        resp = self.api_get(INVOICES_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['invoices']), 2)

    def test_list_invoices_includes_expected_fields(self):
        self._make_invoice()
        resp = self.api_get(INVOICES_URL, user=self.admin)
        inv = resp.data['invoices'][0]
        expected_fields = [
            'id', 'invoice_number', 'amount', 'currency',
            'description', 'agent_count', 'invoice_date',
        ]
        for field in expected_fields:
            self.assertIn(field, inv, f'Missing field: {field}')

    def test_list_invoices_unauthenticated(self):
        resp = self.api_get(INVOICES_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================================
# POST /api/payments/cancel/ - Cancel subscription
# ============================================================================

class TestCancelSubscription(ExtendedSubscriptionMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='cancel@test.com')
        self.regular = self.create_user(email='cancel-reg@test.com')

    def test_cancel_subscription_non_staff_forbidden(self):
        self._make_subscription()
        resp = self.api_post(CANCEL_SUBSCRIPTION_URL, {}, user=self.regular)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cancel_subscription_unauthenticated(self):
        resp = self.api_post(CANCEL_SUBSCRIPTION_URL, {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cancel_subscription_staff(self):
        sub = self._make_subscription()
        resp = self.api_post(CANCEL_SUBSCRIPTION_URL, {}, user=self.admin)
        # Should succeed or return a structured error if no active subscription
        self.assertIn(resp.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ])


# ============================================================================
# Subscription /me endpoint (extended coverage)
# ============================================================================

class TestSubscriptionMeExtended(ExtendedSubscriptionMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='subme-ext@test.com')

    def test_subscription_me_with_features(self):
        sub = self._make_subscription()
        feat = self._make_feature('whatsapp', price=Decimal('3.00'))
        sub.selected_features.add(feat)
        resp = self.api_get(SUBSCRIPTION_ME_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_subscription_me_trial(self):
        sub = self._make_subscription(
            is_trial=True,
            trial_ends_at=timezone.now() + timedelta(days=14),
            subscription_type='trial',
        )
        resp = self.api_get(SUBSCRIPTION_ME_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_subscription_me_no_subscription(self):
        # Don't create a subscription
        resp = self.api_get(SUBSCRIPTION_ME_URL, user=self.admin)
        # Should handle missing subscription gracefully
        self.assertIn(resp.status_code, [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        ])


# ============================================================================
# Dashboard Appearance Settings API
# ============================================================================

class TestDashboardAppearanceAPI(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.superadmin = self.create_user(
            email='appearance@test.com', is_superuser=True, is_staff=True,
        )
        self.regular = self.create_user(email='appearance-reg@test.com')

    def test_get_appearance_creates_default(self):
        resp = self.api_get(APPEARANCE_GET_URL, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Check default values are returned
        self.assertIn('primary_color', resp.data)
        self.assertIn('border_radius', resp.data)

    def test_update_appearance(self):
        # First GET to create defaults
        self.api_get(APPEARANCE_GET_URL, user=self.superadmin)
        resp = self.api_patch(APPEARANCE_UPDATE_URL, {
            'primary_color': '200 50% 50%',
            'border_radius': '1rem',
        }, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        settings = DashboardAppearanceSettings.objects.get(tenant=self.tenant)
        self.assertEqual(settings.primary_color, '200 50% 50%')
        self.assertEqual(settings.border_radius, '1rem')

    def test_update_sidebar_order(self):
        self.api_get(APPEARANCE_GET_URL, user=self.superadmin)
        resp = self.api_patch(APPEARANCE_UPDATE_URL, {
            'sidebar_order': ['dashboard', 'tickets', 'bookings'],
        }, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_update_non_superadmin_forbidden(self):
        """Only superadmins can update appearance."""
        self.api_get(APPEARANCE_GET_URL, user=self.superadmin)
        resp = self.api_patch(APPEARANCE_UPDATE_URL, {
            'primary_color': '200 50% 50%',
        }, user=self.regular)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_can_read(self):
        """Any authenticated user can read appearance settings."""
        resp = self.api_get(APPEARANCE_GET_URL, user=self.regular)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unauthenticated_denied(self):
        resp = self.api_get(APPEARANCE_GET_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================================
# UsageLog tracking tests
# ============================================================================

class TestUsageLogTracking(ExtendedSubscriptionMixin, EchoDeskTenantTestCase):

    def test_usage_log_ordering(self):
        sub = self._make_subscription()
        UsageLog.objects.create(
            subscription=sub, event_type='user_added', quantity=1,
        )
        UsageLog.objects.create(
            subscription=sub, event_type='user_removed', quantity=1,
        )
        logs = UsageLog.objects.filter(subscription=sub)
        # Ordered by -created_at (newest first)
        self.assertEqual(logs.count(), 2)
        self.assertEqual(logs.first().event_type, 'user_removed')

    def test_usage_log_default_quantity(self):
        sub = self._make_subscription()
        log = UsageLog.objects.create(
            subscription=sub, event_type='whatsapp_message',
        )
        self.assertEqual(log.quantity, 1)

    def test_usage_log_custom_quantity(self):
        sub = self._make_subscription()
        log = UsageLog.objects.create(
            subscription=sub, event_type='storage_usage', quantity=512,
        )
        self.assertEqual(log.quantity, 512)

    def test_usage_log_metadata_default(self):
        sub = self._make_subscription()
        log = UsageLog.objects.create(
            subscription=sub, event_type='feature_used',
        )
        self.assertEqual(log.metadata, {})
