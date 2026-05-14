"""
Tests for WhatsApp-related views.
"""
from unittest.mock import patch
from rest_framework import status
from social_integrations.tests.conftest import SocialIntegrationTestCase


class TestWhatsAppConnectionStatus(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='wa-agent@test.com')
        self.url = '/api/social/whatsapp/status/'

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

    def test_with_account(self):
        self.create_wa_account()
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class TestWhatsAppDisconnect(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='wa-disc-admin@test.com')
        self.agent = self.create_user(email='wa-disc-agent@test.com')
        self.url = '/api/social/whatsapp/disconnect/'

    def test_admin_can_disconnect(self):
        resp = self.api_post(self.url, {}, user=self.admin)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_agent_cannot_disconnect(self):
        resp = self.api_post(self.url, {}, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_disconnect_all_soft_deletes_and_preserves_messages(self):
        from social_integrations.models import (
            WhatsAppBusinessAccount, WhatsAppMessage,
        )
        acct = self.create_wa_account()
        self.create_wa_message(business_account=acct)
        self.create_wa_message(business_account=acct)

        resp = self.api_post(self.url, {}, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        acct.refresh_from_db()
        self.assertFalse(acct.is_active)
        self.assertEqual(
            WhatsAppMessage.objects.filter(business_account=acct).count(), 2
        )
        self.assertEqual(WhatsAppBusinessAccount.objects.count(), 1)

    def test_disconnect_specific_waba_id_soft_deletes_only_that_account(self):
        from social_integrations.models import WhatsAppBusinessAccount
        keep = self.create_wa_account(waba_id='waba_keep')
        target = self.create_wa_account(waba_id='waba_target')

        resp = self.api_post(self.url, {'waba_id': 'waba_target'}, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        keep.refresh_from_db()
        target.refresh_from_db()
        self.assertTrue(keep.is_active)
        self.assertFalse(target.is_active)
        self.assertEqual(WhatsAppBusinessAccount.objects.count(), 2)


class TestWhatsAppMessageViewSet(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='wa-msgs@test.com')
        self.url = '/api/social/whatsapp-messages/'

    def test_list_messages(self):
        acct = self.create_wa_account()
        self.create_wa_message(business_account=acct)
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_list_empty(self):
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class TestWhatsAppAccountViewSet(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='wa-acct@test.com')
        self.url = '/api/social/whatsapp-accounts/'

    def test_list_accounts(self):
        self.create_wa_account()
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_retrieve_account(self):
        acct = self.create_wa_account()
        resp = self.api_get(f'{self.url}{acct.id}/', user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class TestWhatsAppContactViewSet(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='wa-contacts@test.com')
        self.url = '/api/social/whatsapp-contacts/'

    def test_list_contacts(self):
        acct = self.create_wa_account()
        self.create_wa_contact(account=acct)
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class TestWhatsAppSendMessage(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email='wa-send@test.com')
        self.url = '/api/social/whatsapp/send-message/'

    def test_send_no_body_returns_error(self):
        resp = self.api_post(self.url, {}, user=self.agent)
        self.assertIn(resp.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ])

    def test_unauthenticated_denied(self):
        resp = self.client.post(self.url, {}, HTTP_HOST='tenant.test.com', content_type='application/json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class TestWhatsAppTemplateViews(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='wa-tmpl-admin@test.com')
        self.agent = self.create_user(email='wa-tmpl-agent@test.com')

    def test_list_templates(self):
        acct = self.create_wa_account()
        self.create_wa_template(business_account=acct)
        url = f'/api/social/whatsapp/{acct.waba_id}/templates/'
        resp = self.api_get(url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_list_templates_empty(self):
        acct = self.create_wa_account()
        url = f'/api/social/whatsapp/{acct.waba_id}/templates/'
        resp = self.api_get(url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
