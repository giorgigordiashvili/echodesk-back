"""
Tests for Instagram-related views.
"""
from unittest.mock import patch
from rest_framework import status
from social_integrations.tests.conftest import SocialIntegrationTestCase


class TestInstagramConnectionStatus(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='ig-agent@test.com')
        self.url = '/api/social/instagram/status/'

    def test_returns_status(self):
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unauthenticated_denied(self):
        resp = self.client.get(self.url, HTTP_HOST='tenant.test.com')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_feature_denied(self):
        with patch('users.models.User.has_feature', return_value=False):
            resp = self.api_get(self.url, user=self.agent)
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_with_connections(self):
        fb = self.create_fb_connection()
        self.create_ig_connection(fb_page=fb)
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class TestInstagramDisconnect(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='ig-disc-admin@test.com')
        self.agent = self.create_user(email='ig-disc-agent@test.com')
        self.url = '/api/social/instagram/disconnect/'

    def test_admin_can_disconnect(self):
        resp = self.api_post(self.url, {}, user=self.admin)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_agent_cannot_disconnect(self):
        resp = self.api_post(self.url, {}, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class TestInstagramMessageViewSet(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='ig-msgs@test.com')
        self.url = '/api/social/instagram-messages/'

    def test_list_messages(self):
        conn = self.create_ig_connection()
        self.create_ig_message(account_connection=conn)
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_list_empty(self):
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class TestInstagramAccountViewSet(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='ig-acct@test.com')
        self.url = '/api/social/instagram-accounts/'

    def test_list_accounts(self):
        self.create_ig_connection(username='shop_ig')
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_retrieve_account(self):
        conn = self.create_ig_connection()
        resp = self.api_get(f'{self.url}{conn.id}/', user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class TestInstagramSendMessage(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='ig-send@test.com')
        self.url = '/api/social/instagram/send-message/'

    def test_send_no_body_returns_error(self):
        resp = self.api_post(self.url, {}, user=self.agent)
        self.assertIn(resp.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ])

    def test_unauthenticated_denied(self):
        resp = self.client.post(self.url, {}, HTTP_HOST='tenant.test.com', content_type='application/json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
