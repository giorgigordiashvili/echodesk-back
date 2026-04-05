"""
Tests for Security endpoints (IP whitelist, security logs):
  - GET  /api/security/logs/                  → list_security_logs
  - GET  /api/security/logs/stats/            → security_logs_stats
  - GET  /api/security/logs/me/               → my_security_logs
  - GET  /api/security/ip-whitelist/          → list_ip_whitelist
  - POST /api/security/ip-whitelist/create/   → create_ip_whitelist
  - PUT/DELETE /api/security/ip-whitelist/<pk>/→ manage_ip_whitelist
  - POST /api/security/ip-whitelist/toggle/   → toggle_ip_whitelist
  - GET  /api/security/current-ip/            → get_current_ip
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from rest_framework import status

from users.tests.conftest import EchoDeskTenantTestCase, TEST_MIDDLEWARE
from tenants.models import SecurityLog, TenantIPWhitelist

User = get_user_model()

# Strip IPWhitelistMiddleware from test middleware so it doesn't block requests
_TEST_MIDDLEWARE_NO_IP = [
    m for m in TEST_MIDDLEWARE
    if m != 'tenants.ip_whitelist_middleware.IPWhitelistMiddleware'
]

# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------
LOGS_URL = '/api/security/logs/'
LOGS_STATS_URL = '/api/security/logs/stats/'
LOGS_ME_URL = '/api/security/logs/me/'
IP_LIST_URL = '/api/security/ip-whitelist/'
IP_CREATE_URL = '/api/security/ip-whitelist/create/'
IP_TOGGLE_URL = '/api/security/ip-whitelist/toggle/'
CURRENT_IP_URL = '/api/security/current-ip/'


def _ip_manage_url(pk):
    return f'/api/security/ip-whitelist/{pk}/'


class SecurityTestMixin:
    """Shared helpers for security tests."""

    def _patch_whitelist_fk(self):
        """Patch serializer save to strip created_by (cross-schema FK issue)."""
        from tenants.serializers import TenantIPWhitelistSerializer
        from rest_framework.serializers import Serializer

        _original_save = Serializer.save

        def _patched_save(ser_self, **kwargs):
            kwargs.pop('created_by', None)
            return _original_save(ser_self, **kwargs)

        patcher = patch.object(TenantIPWhitelistSerializer, 'save', _patched_save)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _make_log(self, event_type='login_success', user=None, **kwargs):
        defaults = {
            'tenant': self.tenant,
            'event_type': event_type,
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0',
            'device_type': 'desktop',
            'browser': 'Chrome',
            'operating_system': 'macOS',
        }
        if user:
            defaults['user_id'] = user.id
            defaults['attempted_email'] = user.email
        defaults.update(kwargs)
        return SecurityLog.objects.create(**defaults)

    def _make_whitelist(self, ip='10.0.0.1', **kwargs):
        """Create whitelist entry without created_by (cross-schema FK issue)."""
        defaults = {
            'tenant': self.tenant,
            'ip_address': ip,
            'description': 'Office',
            'is_active': True,
            'created_by': None,
        }
        defaults.update(kwargs)
        return TenantIPWhitelist.objects.create(**defaults)


# ============================================================
# Security Logs
# ============================================================
class TestListSecurityLogs(SecurityTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.superadmin = self.create_user(
            email='secsuper@test.com', is_superuser=True, is_staff=True,
        )
        self.regular = self.create_user(email='secreg@test.com')

    def test_superadmin_can_list_logs(self):
        self._make_log(user=self.regular)
        self._make_log(event_type='login_failed', attempted_email='bad@test.com')
        resp = self.api_get(LOGS_URL, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data['count'], 2)

    def test_regular_user_forbidden(self):
        resp = self.api_get(LOGS_URL, user=self.regular)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_returns_401(self):
        resp = self.api_get(LOGS_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_by_event_type(self):
        self._make_log(event_type='login_success')
        self._make_log(event_type='login_failed', attempted_email='x@test.com')
        resp = self.api_get(
            f'{LOGS_URL}?event_type=login_failed', user=self.superadmin,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for entry in resp.data['results']:
            self.assertEqual(entry['event_type'], 'login_failed')

    def test_filter_by_ip_address(self):
        self._make_log(ip_address='1.2.3.4')
        self._make_log(ip_address='5.6.7.8')
        resp = self.api_get(
            f'{LOGS_URL}?ip_address=1.2.3', user=self.superadmin,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for entry in resp.data['results']:
            self.assertIn('1.2.3', entry['ip_address'])

    def test_search_filter(self):
        self._make_log(attempted_email='findme@test.com')
        resp = self.api_get(
            f'{LOGS_URL}?search=findme', user=self.superadmin,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data['count'], 1)


class TestSecurityLogsStats(SecurityTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.superadmin = self.create_user(
            email='statsuper@test.com', is_superuser=True, is_staff=True,
        )
        self.regular = self.create_user(email='statreg@test.com')

    def test_returns_stats(self):
        self._make_log(event_type='login_success', user=self.regular)
        self._make_log(event_type='login_failed', attempted_email='bad@test.com')
        resp = self.api_get(LOGS_STATS_URL, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('total_logins', resp.data)
        self.assertIn('failed_logins', resp.data)
        self.assertIn('unique_ips', resp.data)
        self.assertIn('by_event_type', resp.data)

    def test_regular_user_forbidden(self):
        resp = self.api_get(LOGS_STATS_URL, user=self.regular)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_respects_days_param(self):
        resp = self.api_get(f'{LOGS_STATS_URL}?days=7', user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['period_days'], 7)


class TestMySecurityLogs(SecurityTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.superadmin = self.create_user(
            email='mylogsuper@test.com', is_superuser=True, is_staff=True,
        )
        self.user = self.create_user(email='mylog@test.com')

    def test_returns_own_logs_only(self):
        self._make_log(user=self.user)
        self._make_log(user=self.superadmin)
        resp = self.api_get(LOGS_ME_URL, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for entry in resp.data['results']:
            self.assertEqual(entry['user_id'], self.user.id)

    def test_unauthenticated_returns_401(self):
        resp = self.api_get(LOGS_ME_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================
# IP Whitelist
# ============================================================
class TestListIPWhitelist(SecurityTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.superadmin = self.create_user(
            email='wlsuper@test.com', is_superuser=True, is_staff=True,
        )
        self.regular = self.create_user(email='wlreg@test.com')

    def test_superadmin_can_list(self):
        self._make_whitelist()
        resp = self.api_get(IP_LIST_URL, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('entries', resp.data)
        self.assertIn('ip_whitelist_enabled', resp.data)
        self.assertGreaterEqual(len(resp.data['entries']), 1)

    def test_regular_user_forbidden(self):
        resp = self.api_get(IP_LIST_URL, user=self.regular)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class TestCreateIPWhitelist(SecurityTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self._patch_whitelist_fk()
        self.superadmin = self.create_user(
            email='wlcreate@test.com', is_superuser=True, is_staff=True,
        )

    def test_create_entry(self):
        resp = self.api_post(IP_CREATE_URL, {
            'ip_address': '192.168.1.1',
            'description': 'Office VPN',
        }, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['ip_address'], '192.168.1.1')

    def test_create_duplicate_rejected(self):
        # Create first entry via API
        self.api_post(IP_CREATE_URL, {
            'ip_address': '10.0.0.1',
        }, user=self.superadmin)
        # Try to create duplicate
        resp = self.api_post(IP_CREATE_URL, {
            'ip_address': '10.0.0.1',
        }, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_invalid_ip_rejected(self):
        resp = self.api_post(IP_CREATE_URL, {
            'ip_address': 'not-an-ip',
        }, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class TestManageIPWhitelist(SecurityTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self._patch_whitelist_fk()
        self.superadmin = self.create_user(
            email='wlmanage@test.com', is_superuser=True, is_staff=True,
        )
        # Create entry via API
        resp = self.api_post(IP_CREATE_URL, {
            'ip_address': '172.16.0.1',
            'description': 'Test entry',
        }, user=self.superadmin)
        self.entry_pk = resp.data['id']

    def test_update_entry(self):
        resp = self.api_put(_ip_manage_url(self.entry_pk), {
            'ip_address': '172.16.0.1',
            'description': 'Updated description',
        }, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        entry = TenantIPWhitelist.objects.get(pk=self.entry_pk)
        self.assertEqual(entry.description, 'Updated description')

    def test_delete_entry(self):
        resp = self.api_delete(_ip_manage_url(self.entry_pk), user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TenantIPWhitelist.objects.filter(pk=self.entry_pk).exists())

    def test_delete_nonexistent_returns_404(self):
        resp = self.api_delete(_ip_manage_url(99999), user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(MIDDLEWARE=_TEST_MIDDLEWARE_NO_IP)
class TestToggleIPWhitelist(SecurityTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self._patch_whitelist_fk()
        self.superadmin = self.create_user(
            email='wltoggle@test.com', is_superuser=True, is_staff=True,
        )

    def test_enable_without_entries_fails(self):
        resp = self.api_post(IP_TOGGLE_URL, {
            'enabled': True,
        }, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot enable', resp.data.get('error', ''))

    def test_enable_with_entries_succeeds(self):
        # Create entry via API
        self.api_post(IP_CREATE_URL, {
            'ip_address': '10.0.0.1',
        }, user=self.superadmin)
        resp = self.api_post(IP_TOGGLE_URL, {
            'enabled': True,
        }, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['ip_whitelist_enabled'])

    def test_disable_whitelist(self):
        resp = self.api_post(IP_TOGGLE_URL, {
            'enabled': False,
        }, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['ip_whitelist_enabled'])

    def test_toggle_superadmin_bypass(self):
        resp = self.api_post(IP_TOGGLE_URL, {
            'superadmin_bypass': False,
        }, user=self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['superadmin_bypass_whitelist'])


class TestGetCurrentIP(SecurityTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='curip@test.com')

    @patch('tenants.security_views.SecurityService')
    def test_returns_ip(self, mock_svc):
        mock_svc.get_client_ip.return_value = '203.0.113.42'
        mock_svc.get_ip_location.return_value = {
            'city': 'Tbilisi', 'country': 'Georgia', 'country_code': 'GE',
        }
        resp = self.api_get(CURRENT_IP_URL, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['ip_address'], '203.0.113.42')
        self.assertEqual(resp.data['city'], 'Tbilisi')

    def test_unauthenticated_returns_401(self):
        resp = self.api_get(CURRENT_IP_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
