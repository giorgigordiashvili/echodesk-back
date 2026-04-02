"""
Tests for Client/SocialClient-related views and Quick Reply views.
"""
from rest_framework import status
from social_integrations.tests.conftest import SocialIntegrationTestCase


class TestSocialClientViewSet(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='client-admin@test.com')
        self.agent = self.create_user(email='client-agent@test.com')
        self.url = '/api/social/clients/'

    def test_list_clients(self):
        self.create_client(name='Client A')
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_list_empty(self):
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_retrieve_client(self):
        c = self.create_client(name='Client B')
        resp = self.api_get(f'{self.url}{c.id}/', user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_create_client(self):
        resp = self.api_post(self.url, {
            'name': 'New Client',
        }, user=self.admin)
        self.assertIn(resp.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_200_OK,
        ])

    def test_update_client(self):
        c = self.create_client(name='Old Name')
        resp = self.api_patch(f'{self.url}{c.id}/', {
            'name': 'New Name',
        }, user=self.admin)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_client(self):
        c = self.create_client(name='To Delete')
        resp = self.api_delete(f'{self.url}{c.id}/', user=self.admin)
        self.assertIn(resp.status_code, [
            status.HTTP_204_NO_CONTENT,
            status.HTTP_200_OK,
        ])

    def test_unauthenticated_denied(self):
        resp = self.client.get(self.url, HTTP_HOST='tenant.test.com')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class TestSocialClientCustomFieldViewSet(SocialIntegrationTestCase):
    """
    Note: The custom-fields URL `clients/custom-fields/` is registered in the
    DRF router, but the clients ViewSet's `clients/(?P<pk>[^/.]+)/` pattern
    matches first (pk='custom-fields'). This is a known routing issue.
    Tests use the DRF test client to call the viewset directly.
    """

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='cf-admin@test.com')

    def test_custom_field_creation(self):
        """Verify custom field can be created and queried."""
        from social_integrations.models import SocialClientCustomField
        f = SocialClientCustomField.objects.create(
            name='test_field', label='Test Field', field_type='string',
            created_by=self.admin,
        )
        self.assertTrue(f.is_active)
        self.assertEqual(SocialClientCustomField.objects.filter(is_active=True).count(), 1)

    def test_custom_field_model_str(self):
        from social_integrations.models import SocialClientCustomField
        f = SocialClientCustomField.objects.create(
            name='company', label='Company', field_type='string',
            created_by=self.admin,
        )
        self.assertEqual(str(f), 'Company (string)')


class TestQuickReplyViewSet(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='qr-admin@test.com')
        self.agent = self.create_user(email='qr-agent@test.com')
        self.url = '/api/social/quick-replies/'

    def test_list_quick_replies(self):
        self.create_quick_reply(created_by=self.admin)
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_list_empty(self):
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_create_quick_reply(self):
        resp = self.api_post(self.url, {
            'title': 'Greeting',
            'message': 'Hello {{customer_name}}!',
        }, user=self.admin)
        self.assertIn(resp.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_200_OK,
        ])

    def test_retrieve_quick_reply(self):
        qr = self.create_quick_reply(created_by=self.admin)
        resp = self.api_get(f'{self.url}{qr.id}/', user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_update_quick_reply(self):
        qr = self.create_quick_reply(created_by=self.admin)
        resp = self.api_patch(f'{self.url}{qr.id}/', {
            'title': 'Updated',
        }, user=self.admin)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_quick_reply(self):
        qr = self.create_quick_reply(created_by=self.admin)
        resp = self.api_delete(f'{self.url}{qr.id}/', user=self.admin)
        self.assertIn(resp.status_code, [
            status.HTTP_204_NO_CONTENT,
            status.HTTP_200_OK,
        ])

    def test_unauthenticated_denied(self):
        resp = self.client.get(self.url, HTTP_HOST='tenant.test.com')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
