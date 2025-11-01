"""
Tests for password reset functionality
"""
from django.test import TestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

from ecommerce_crm.models import EcommerceClient, PasswordResetToken
from .test_utils import TestDataMixin


class PasswordResetRequestTest(APITestCase, TestDataMixin):
    """Test password reset request endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.request_url = '/api/ecommerce/clients/password-reset/request/'
        self.test_client = self.create_test_client(
            email='test@example.com',
            password='oldpassword123'
        )

    def test_request_password_reset_success(self):
        """Test successful password reset request"""
        data = {
            'email': 'test@example.com'
        }

        response = self.client.post(self.request_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

        # Verify token was created
        token = PasswordResetToken.objects.filter(client=self.test_client).first()
        self.assertIsNotNone(token)
        self.assertFalse(token.is_used)

    def test_request_password_reset_nonexistent_email(self):
        """Test password reset request for nonexistent email"""
        data = {
            'email': 'nonexistent@example.com'
        }

        response = self.client.post(self.request_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_request_password_reset_inactive_client(self):
        """Test password reset request for inactive client"""
        inactive_client = self.create_test_client(
            email='inactive@example.com',
            is_active=False
        )

        data = {
            'email': 'inactive@example.com'
        }

        response = self.client.post(self.request_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_request_password_reset_missing_email(self):
        """Test password reset request with missing email"""
        data = {}

        response = self.client.post(self.request_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmTest(APITestCase, TestDataMixin):
    """Test password reset confirmation endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.confirm_url = '/api/ecommerce/clients/password-reset/confirm/'
        self.test_client = self.create_test_client(
            email='test@example.com',
            password='oldpassword123'
        )
        self.reset_token = self.create_test_password_reset_token(self.test_client)

    def test_confirm_password_reset_success(self):
        """Test successful password reset confirmation"""
        data = {
            'token': self.reset_token.token,
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123'
        }

        response = self.client.post(self.confirm_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

        # Verify password was changed
        self.test_client.refresh_from_db()
        self.assertTrue(self.test_client.check_password('newpassword123'))
        self.assertFalse(self.test_client.check_password('oldpassword123'))

        # Verify token was marked as used
        self.reset_token.refresh_from_db()
        self.assertTrue(self.reset_token.is_used)
        self.assertIsNotNone(self.reset_token.used_at)

    def test_confirm_password_reset_password_mismatch(self):
        """Test password reset fails with password mismatch"""
        data = {
            'token': self.reset_token.token,
            'new_password': 'newpassword123',
            'new_password_confirm': 'different123'
        }

        response = self.client.post(self.confirm_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password_confirm', response.data)

    def test_confirm_password_reset_invalid_token(self):
        """Test password reset with invalid token"""
        data = {
            'token': 'invalid-token-xyz',
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123'
        }

        response = self.client.post(self.confirm_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_password_reset_expired_token(self):
        """Test password reset with expired token"""
        # Create expired token
        expired_token = PasswordResetToken.objects.create(
            client=self.test_client,
            token='expired-token-123',
            expires_at=timezone.now() - timedelta(hours=1)
        )

        data = {
            'token': expired_token.token,
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123'
        }

        response = self.client.post(self.confirm_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_password_reset_used_token(self):
        """Test password reset with already used token"""
        # Mark token as used
        self.reset_token.mark_as_used()

        data = {
            'token': self.reset_token.token,
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123'
        }

        response = self.client.post(self.confirm_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_password_reset_weak_password(self):
        """Test password reset with weak password"""
        data = {
            'token': self.reset_token.token,
            'new_password': '123',  # Too short
            'new_password_confirm': '123'
        }

        response = self.client.post(self.confirm_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PasswordResetFlowTest(APITestCase, TestDataMixin):
    """Test complete password reset flow"""

    def setUp(self):
        self.client = APIClient()
        self.request_url = '/api/ecommerce/clients/password-reset/request/'
        self.confirm_url = '/api/ecommerce/clients/password-reset/confirm/'
        self.login_url = '/api/ecommerce/clients/login/'

        self.test_client = self.create_test_client(
            email='test@example.com',
            password='oldpassword123'
        )

    def test_complete_password_reset_flow(self):
        """Test complete password reset flow from request to login"""
        # Step 1: Request password reset
        request_data = {'email': 'test@example.com'}
        response = self.client.post(self.request_url, request_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Step 2: Get the token from database
        token = PasswordResetToken.objects.filter(
            client=self.test_client,
            is_used=False
        ).first()
        self.assertIsNotNone(token)

        # Step 3: Confirm password reset with token
        confirm_data = {
            'token': token.token,
            'new_password': 'brandnewpassword123',
            'new_password_confirm': 'brandnewpassword123'
        }
        response = self.client.post(self.confirm_url, confirm_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Step 4: Try to login with old password (should fail)
        login_data = {
            'identifier': 'test@example.com',
            'password': 'oldpassword123'
        }
        response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Step 5: Login with new password (should succeed)
        login_data = {
            'identifier': 'test@example.com',
            'password': 'brandnewpassword123'
        }
        response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
