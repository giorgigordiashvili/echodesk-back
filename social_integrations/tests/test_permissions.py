"""
Tests for social_integrations permission classes.
Verifies feature gating, role checks, and method-level access control.
"""
from unittest.mock import patch, MagicMock
from rest_framework import status
from social_integrations.tests.conftest import SocialIntegrationTestCase


class TestCanManageSocialConnections(SocialIntegrationTestCase):
    """Tests for CanManageSocialConnections permission class."""

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='perm-admin@test.com')
        self.agent = self.create_user(email='perm-agent@test.com', role='agent')
        self.url = '/api/social/facebook/status/'

    def test_unauthenticated_user_denied(self):
        resp = self.client.get(self.url, HTTP_HOST='tenant.test.com')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_read_allowed_with_feature(self):
        resp = self.api_get(self.url, user=self.agent)
        # Should not be 403 (may be 200 or other, but not permission denied)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_read_denied_without_feature(self):
        with patch('users.models.User.has_feature', return_value=False):
            resp = self.api_get(self.url, user=self.agent)
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_write_denied_without_feature(self):
        """Fix 1 verification: write path should check has_feature."""
        url = '/api/social/facebook/disconnect/'
        with patch('users.models.User.has_feature', return_value=False):
            resp = self.api_post(url, {}, user=self.admin)
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_write_allowed_for_admin_with_feature(self):
        url = '/api/social/facebook/disconnect/'
        resp = self.api_post(url, {}, user=self.admin)
        # Should not be 403 (the endpoint may fail for other reasons but permission passes)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_write_denied_for_agent_without_permission(self):
        url = '/api/social/facebook/disconnect/'
        resp = self.api_post(url, {}, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class TestCanViewSocialMessages(SocialIntegrationTestCase):
    """Tests for CanViewSocialMessages permission class."""

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='view-agent@test.com', role='agent')

    def test_allowed_with_feature(self):
        resp = self.api_get('/api/social/unread-count/', user=self.agent)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_denied_without_feature(self):
        with patch('users.models.User.has_feature', return_value=False):
            resp = self.api_get('/api/social/unread-count/', user=self.agent)
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class TestCanManageSocialSettings(SocialIntegrationTestCase):
    """Tests for CanManageSocialSettings permission class."""

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='settings-admin@test.com')
        self.agent = self.create_user(email='settings-agent@test.com', role='agent')
        self.url = '/api/social/settings/'

    def test_read_allowed_with_feature(self):
        resp = self.api_get(self.url, user=self.agent)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_write_denied_without_feature(self):
        """Fix 2 verification: write path should check has_feature."""
        with patch('users.models.User.has_feature', return_value=False):
            resp = self.api_put(self.url, {'refresh_interval': 5000}, user=self.admin)
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_write_denied_for_agent(self):
        resp = self.api_put(self.url, {'refresh_interval': 5000}, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_write_allowed_for_admin_with_feature(self):
        resp = self.api_put(self.url, {'refresh_interval': 5000}, user=self.admin)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class TestIsStaffUser(SocialIntegrationTestCase):
    """Tests for IsStaffUser permission class."""

    def setUp(self):
        super().setUp()
        self.staff = self.create_user(email='staff@test.com', is_staff=True)
        self.agent = self.create_user(email='nostaff@test.com', role='agent')

    def test_staff_allowed_webhook_debug(self):
        resp = self.api_get('/api/social/webhook-logs/', user=self.staff)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_staff_denied_webhook_debug(self):
        """Fix 9 verification: webhook debug requires staff."""
        resp = self.api_get('/api/social/webhook-logs/', user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_staff_denied_webhook_status(self):
        resp = self.api_get('/api/social/webhook-status/', user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_allowed_rating_statistics(self):
        """Fix 3 verification: rating_statistics uses IsStaffUser."""
        resp = self.api_get('/api/social/rating-statistics/', user=self.staff)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_staff_denied_rating_statistics(self):
        resp = self.api_get('/api/social/rating-statistics/', user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
