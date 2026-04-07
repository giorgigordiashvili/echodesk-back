from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from notifications.views import NotificationViewSet


class NotificationViewSetTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='password123'
        )
        self.view = NotificationViewSet.as_view({'get': 'vapid_public_key'})

    @patch('notifications.views.get_vapid_keys')
    def test_vapid_public_key_returns_key_when_available(self, mock_get_vapid_keys):
        mock_get_vapid_keys.return_value = {'public_key': 'public-key-value'}

        request = self.factory.get('/notifications/vapid-public-key/')
        force_authenticate(request, user=self.user)
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'public_key': 'public-key-value'})

    @patch('notifications.views.get_vapid_keys')
    def test_vapid_public_key_returns_503_when_missing(self, mock_get_vapid_keys):
        mock_get_vapid_keys.return_value = None

        request = self.factory.get('/notifications/vapid-public-key/')
        force_authenticate(request, user=self.user)
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(
            response.data,
            {'error': 'Push notifications are temporarily unavailable'}
        )
