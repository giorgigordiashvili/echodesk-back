"""
Tests for Tenant Subscription & Payment endpoints:
  - GET  /api/subscription/me/                      → get_subscription_me
  - GET  /api/subscription/features/available/       → get_available_features
  - POST /api/subscription/features/add/             → add_feature_to_subscription
  - POST /api/subscription/features/remove/          → remove_feature_from_subscription
  - PUT  /api/subscription/agent-count/              → update_agent_count
  - GET  /api/payments/invoices/                     → list_invoices
  - GET  /api/payments/saved-card/                   → get_saved_card
  - GET  /api/features/                              → FeatureViewSet list
"""
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status

from users.tests.conftest import EchoDeskTenantTestCase
from tenants.models import (
    TenantSubscription, Invoice, PaymentOrder, SavedCard,
)
from tenants.feature_models import Feature

# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------
SUBSCRIPTION_ME_URL = '/api/subscription/me/'
FEATURES_AVAILABLE_URL = '/api/subscription/features/available/'
FEATURES_ADD_URL = '/api/subscription/features/add/'
FEATURES_REMOVE_URL = '/api/subscription/features/remove/'
AGENT_COUNT_URL = '/api/subscription/agent-count/'
INVOICES_URL = '/api/payments/invoices/'
SAVED_CARD_URL = '/api/payments/saved-card/'
FEATURES_LIST_URL = '/api/features/'


class SubscriptionTestMixin:
    """Shared helpers for subscription tests."""

    def _make_feature(self, key, name='Test Feature', price=Decimal('5.00'),
                      category='integration', **kwargs):
        return Feature.objects.create(
            key=key, name=name,
            price_per_user_gel=price,
            price_unlimited_gel=Decimal('0'),
            category=category,
            is_active=True,
            **kwargs,
        )

    def _make_subscription(self, tenant=None, **kwargs):
        defaults = {
            'tenant': tenant or self.tenant,
            'is_active': True,
            'starts_at': timezone.now(),
            'agent_count': 10,
            'payment_status': 'current',
        }
        defaults.update(kwargs)
        return TenantSubscription.objects.create(**defaults)

    def _make_payment_order(self, tenant=None, **kwargs):
        import uuid
        defaults = {
            'order_id': f'ORD-{uuid.uuid4().hex[:12]}',
            'tenant': tenant or self.tenant,
            'amount': Decimal('50.00'),
            'currency': 'GEL',
            'status': 'paid',
        }
        defaults.update(kwargs)
        return PaymentOrder.objects.create(**defaults)

    def _make_invoice(self, tenant=None, **kwargs):
        t = tenant or self.tenant
        po = kwargs.pop('payment_order', None) or self._make_payment_order(tenant=t)
        defaults = {
            'tenant': t,
            'payment_order': po,
            'amount': Decimal('50.00'),
            'currency': 'GEL',
            'description': 'Monthly subscription',
            'agent_count': 10,
        }
        defaults.update(kwargs)
        return Invoice.objects.create(**defaults)


# ============================================================
# GET /api/subscription/me/
# ============================================================
class TestGetSubscriptionMe(SubscriptionTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='subadmin@test.com')
        self.sub = self._make_subscription()

    def test_returns_subscription_info(self):
        resp = self.api_get(SUBSCRIPTION_ME_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        resp = self.api_get(SUBSCRIPTION_ME_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================
# GET /api/subscription/features/available/
# ============================================================
class TestGetAvailableFeatures(SubscriptionTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='featadmin@test.com')
        self.sub = self._make_subscription()
        self.feat = self._make_feature('whatsapp', name='WhatsApp', price=Decimal('3.00'))

    def test_returns_features_grouped_by_category(self):
        resp = self.api_get(FEATURES_AVAILABLE_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('features_by_category', resp.data)
        self.assertIn('agent_count', resp.data)

    def test_marks_selected_features(self):
        self.sub.selected_features.add(self.feat)
        resp = self.api_get(FEATURES_AVAILABLE_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Find the feature in response
        for cat_features in resp.data['features_by_category'].values():
            for f in cat_features:
                if f['key'] == 'whatsapp':
                    self.assertTrue(f['is_selected'])

    def test_unauthenticated_returns_401(self):
        resp = self.api_get(FEATURES_AVAILABLE_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================
# POST /api/subscription/features/add/
# ============================================================
class TestAddFeature(SubscriptionTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='addft@test.com')
        self.sub = self._make_subscription()
        self.feat = self._make_feature('analytics', name='Analytics', price=Decimal('2.00'))

    def test_add_feature_no_payment_when_zero_cost(self):
        """Feature with 0 prorated cost gets added directly."""
        self.sub.next_billing_date = timezone.now()  # 0 days remaining → cost = 0
        self.sub.save()
        resp = self.api_post(FEATURES_ADD_URL, {
            'feature_id': self.feat.id,
            'charge_immediately': True,
        }, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('success'))
        self.assertTrue(self.sub.selected_features.filter(id=self.feat.id).exists())

    def test_add_feature_missing_id(self):
        resp = self.api_post(FEATURES_ADD_URL, {}, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_feature_nonexistent(self):
        resp = self.api_post(FEATURES_ADD_URL, {'feature_id': 99999}, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_add_feature_already_added(self):
        self.sub.selected_features.add(self.feat)
        resp = self.api_post(FEATURES_ADD_URL, {
            'feature_id': self.feat.id,
        }, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already added', resp.data.get('error', ''))

    def test_unauthenticated_returns_401(self):
        resp = self.api_post(FEATURES_ADD_URL, {'feature_id': self.feat.id})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================
# POST /api/subscription/features/remove/
# ============================================================
class TestRemoveFeature(SubscriptionTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='rmft@test.com')
        self.sub = self._make_subscription()
        self.feat = self._make_feature('email_int', name='Email', price=Decimal('4.00'))
        self.sub.selected_features.add(self.feat)

    def test_remove_feature_success(self):
        resp = self.api_post(FEATURES_REMOVE_URL, {
            'feature_id': self.feat.id,
        }, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('success'))
        self.assertFalse(self.sub.selected_features.filter(id=self.feat.id).exists())

    def test_remove_core_feature_rejected(self):
        core = self._make_feature('core_crm', name='Core CRM', category='core')
        self.sub.selected_features.add(core)
        resp = self.api_post(FEATURES_REMOVE_URL, {
            'feature_id': core.id,
        }, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Core features', resp.data.get('error', ''))

    def test_remove_feature_not_in_subscription(self):
        other = self._make_feature('other_feat', name='Other')
        resp = self.api_post(FEATURES_REMOVE_URL, {
            'feature_id': other.id,
        }, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_remove_feature_missing_id(self):
        resp = self.api_post(FEATURES_REMOVE_URL, {}, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ============================================================
# PUT /api/subscription/agent-count/
# ============================================================
class TestUpdateAgentCount(SubscriptionTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='agcnt@test.com')
        self.sub = self._make_subscription(agent_count=10)
        self.feat = self._make_feature('base', name='Base', price=Decimal('5.00'))
        self.sub.selected_features.add(self.feat)

    def test_update_agent_count_success(self):
        resp = self.api_put(AGENT_COUNT_URL, {'agent_count': 20}, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('success'))
        self.assertEqual(resp.data['new_agent_count'], 20)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.agent_count, 20)

    def test_update_agent_count_recalculates_cost(self):
        resp = self.api_put(AGENT_COUNT_URL, {'agent_count': 20}, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # 5.00 per user × 20 agents = 100.00
        self.assertEqual(resp.data['new_monthly_cost'], 100.0)

    def test_update_agent_count_invalid(self):
        resp = self.api_put(AGENT_COUNT_URL, {'agent_count': 0}, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_agent_count_missing(self):
        resp = self.api_put(AGENT_COUNT_URL, {}, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_agent_count_unauthenticated(self):
        resp = self.api_put(AGENT_COUNT_URL, {'agent_count': 20})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================
# GET /api/payments/invoices/
# ============================================================
class TestListInvoices(SubscriptionTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='inv@test.com')

    def test_list_invoices_empty(self):
        resp = self.api_get(INVOICES_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['invoices'], [])

    def test_list_invoices_returns_data(self):
        self._make_invoice()
        resp = self.api_get(INVOICES_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['invoices']), 1)
        self.assertTrue(resp.data['invoices'][0]['invoice_number'].startswith('INV-'))

    def test_list_invoices_includes_amount(self):
        self._make_invoice(amount=Decimal('99.50'))
        resp = self.api_get(INVOICES_URL, user=self.admin)
        self.assertEqual(resp.data['invoices'][0]['amount'], 99.5)


# ============================================================
# GET /api/payments/saved-card/
# ============================================================
class TestGetSavedCard(SubscriptionTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='card@test.com')
        self.regular_user = self.create_user(email='nocard@test.com')

    def test_staff_can_view_cards(self):
        resp = self.api_get(SAVED_CARD_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_non_staff_forbidden(self):
        resp = self.api_get(SAVED_CARD_URL, user=self.regular_user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_returns_401(self):
        resp = self.api_get(SAVED_CARD_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================
# GET /api/features/  (public)
# ============================================================
class TestFeatureList(SubscriptionTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self._make_feature('f1', name='Feature One')
        self._make_feature('f2', name='Feature Two')

    def test_list_features_unauthenticated(self):
        """Features endpoint is public (AllowAny)."""
        resp = self.api_get(FEATURES_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 2)

    def test_features_have_expected_fields(self):
        resp = self.api_get(FEATURES_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        first = resp.data[0] if not isinstance(resp.data, dict) else resp.data['results'][0]
        self.assertIn('key', first)
        self.assertIn('name', first)
        self.assertIn('price_per_user_gel', first)


# ============================================================
# TenantSubscription model property tests
# ============================================================
class TestSubscriptionModel(SubscriptionTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.sub = self._make_subscription()
        self.feat = self._make_feature('prop_test', price=Decimal('10.00'))

    def test_monthly_cost_no_features(self):
        self.assertEqual(self.sub.monthly_cost, 0)

    def test_monthly_cost_with_features(self):
        self.sub.selected_features.add(self.feat)
        # 10.00 per user × 10 agents = 100.00
        self.assertEqual(self.sub.monthly_cost, Decimal('100.00'))

    def test_is_over_user_limit(self):
        self.sub.current_users = 15
        self.sub.save()
        self.assertTrue(self.sub.is_over_user_limit)

    def test_can_add_user(self):
        self.sub.current_users = 5
        self.sub.save()
        self.assertTrue(self.sub.can_add_user())

    def test_mark_payment_failed(self):
        self.sub.mark_payment_failed()
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.payment_status, 'retrying')
        self.assertEqual(self.sub.failed_payment_count, 1)

    def test_mark_payment_succeeded(self):
        self.sub.failed_payment_count = 3
        self.sub.payment_status = 'retrying'
        self.sub.save()
        self.sub.mark_payment_succeeded()
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.payment_status, 'current')
        self.assertEqual(self.sub.failed_payment_count, 0)

    def test_has_payment_issues(self):
        self.sub.payment_status = 'failed'
        self.assertTrue(self.sub.has_payment_issues)
        self.sub.payment_status = 'current'
        self.assertFalse(self.sub.has_payment_issues)
