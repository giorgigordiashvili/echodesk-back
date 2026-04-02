"""
Tests for Email-related views.
"""
from unittest.mock import patch
from rest_framework import status
from social_integrations.tests.conftest import SocialIntegrationTestCase


class TestEmailConnectionStatus(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='email-agent@test.com')
        self.url = '/api/social/email/status/'

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

    def test_with_connection(self):
        self.create_email_connection()
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class TestEmailConnect(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='email-conn-admin@test.com')
        self.agent = self.create_user(email='email-conn-agent@test.com')
        self.url = '/api/social/email/connect/'

    def test_admin_can_connect(self):
        data = {
            'email_address': 'new@example.com',
            'imap_server': 'imap.example.com',
            'imap_port': 993,
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'username': 'new@example.com',
            'password': 'pass123',
        }
        resp = self.api_post(self.url, data, user=self.admin)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_agent_cannot_connect(self):
        resp = self.api_post(self.url, {}, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class TestEmailDisconnect(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='email-disc-admin@test.com')
        self.agent = self.create_user(email='email-disc-agent@test.com')
        self.url = '/api/social/email/disconnect/'

    def test_admin_can_disconnect(self):
        resp = self.api_post(self.url, {}, user=self.admin)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_agent_cannot_disconnect(self):
        resp = self.api_post(self.url, {}, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class TestEmailFolders(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='email-folders@test.com')
        self.url = '/api/social/email/folders/'

    def test_returns_folders(self):
        resp = self.api_get(self.url, user=self.agent)
        # May return 200 or 404 if no connection, but not 403
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_feature_denied(self):
        """Fix 8 verification: email_folders requires feature."""
        with patch('users.models.User.has_feature', return_value=False):
            resp = self.api_get(self.url, user=self.agent)
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class TestEmailMessageViewSet(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='email-msgs@test.com')
        self.url = '/api/social/email-messages/'

    def test_list_messages(self):
        conn = self.create_email_connection()
        self.create_email_message(connection=conn)
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_list_empty(self):
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class TestEmailDraftViewSet(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='email-drafts@test.com')
        self.url = '/api/social/email-drafts/'

    def test_list_drafts(self):
        conn = self.create_email_connection()
        self.create_email_draft(connection=conn, created_by=self.agent)
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class TestEmailSignatureView(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='email-sig-admin@test.com')
        self.url = '/api/social/email/signature/'

    def test_get_signature(self):
        resp = self.api_get(self.url, user=self.admin)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_signature(self):
        resp = self.api_put(self.url, {
            'sender_name': 'Support',
            'signature_html': '<p>Thanks</p>',
            'is_enabled': True,
        }, user=self.admin)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class TestEmailAssignments(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='email-assign-admin@test.com')
        self.agent = self.create_user(email='email-assign-agent@test.com')

    def test_list_assignments(self):
        resp = self.api_get('/api/social/email/assignments/', user=self.admin)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_assignment(self):
        conn = self.create_email_connection()
        resp = self.api_post('/api/social/email/assignments/create/', {
            'connection_id': conn.id,
            'user_id': self.agent.id,
        }, user=self.admin)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
