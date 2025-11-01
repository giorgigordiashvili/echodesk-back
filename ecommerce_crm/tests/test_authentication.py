"""
Tests for authentication endpoints (register, login, JWT)
"""
from django.test import TestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse

from ecommerce_crm.models import EcommerceClient
from .test_utils import TestDataMixin


class ClientRegistrationTest(APITestCase, TestDataMixin):
    """Test client registration endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.register_url = '/api/ecommerce/clients/register/'

    def test_register_client_success(self):
        """Test successful client registration"""
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'phone_number': '+995555123456',
            'password': 'securepass123',
            'password_confirm': 'securepass123'
        }

        response = self.client.post(self.register_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('email', response.data)
        self.assertEqual(response.data['email'], 'john.doe@example.com')

        # Verify client was created in database
        client = EcommerceClient.objects.get(email='john.doe@example.com')
        self.assertEqual(client.first_name, 'John')
        self.assertEqual(client.last_name, 'Doe')

    def test_register_client_password_mismatch(self):
        """Test registration fails with password mismatch"""
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'phone_number': '+995555123456',
            'password': 'password123',
            'password_confirm': 'different123'
        }

        response = self.client.post(self.register_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirm', response.data)

    def test_register_client_duplicate_email(self):
        """Test registration fails with duplicate email"""
        # Create existing client
        self.create_test_client(email='existing@example.com')

        data = {
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': 'existing@example.com',
            'phone_number': '+995555654321',
            'password': 'password123',
            'password_confirm': 'password123'
        }

        response = self.client.post(self.register_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_register_client_missing_required_fields(self):
        """Test registration fails with missing required fields"""
        data = {
            'first_name': 'John',
            # Missing last_name, email, phone_number, password
        }

        response = self.client.post(self.register_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_client_weak_password(self):
        """Test registration with weak password"""
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'phone_number': '+995555123456',
            'password': '123',  # Too short
            'password_confirm': '123'
        }

        response = self.client.post(self.register_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ClientLoginTest(APITestCase, TestDataMixin):
    """Test client login endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.login_url = '/api/ecommerce/clients/login/'
        self.test_client = self.create_test_client(
            email='test@example.com',
            password='testpass123'
        )

    def test_login_with_email_success(self):
        """Test successful login with email"""
        data = {
            'identifier': 'test@example.com',
            'password': 'testpass123'
        }

        response = self.client.post(self.login_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('client', response.data)
        self.assertEqual(response.data['client']['email'], 'test@example.com')

    def test_login_with_phone_success(self):
        """Test successful login with phone number"""
        data = {
            'identifier': '+995555123456',
            'password': 'testpass123'
        }

        response = self.client.post(self.login_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_wrong_password(self):
        """Test login fails with wrong password"""
        data = {
            'identifier': 'test@example.com',
            'password': 'wrongpassword'
        }

        response = self.client.post(self.login_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_nonexistent_user(self):
        """Test login fails for nonexistent user"""
        data = {
            'identifier': 'nonexistent@example.com',
            'password': 'anypassword'
        }

        response = self.client.post(self.login_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_inactive_client(self):
        """Test login fails for inactive client"""
        inactive_client = self.create_test_client(
            email='inactive@example.com',
            password='testpass123',
            is_active=False
        )

        data = {
            'identifier': 'inactive@example.com',
            'password': 'testpass123'
        }

        response = self.client.post(self.login_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_jwt_tokens_are_valid(self):
        """Test that returned JWT tokens are valid strings"""
        data = {
            'identifier': 'test@example.com',
            'password': 'testpass123'
        }

        response = self.client.post(self.login_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        access_token = response.data['access']
        refresh_token = response.data['refresh']

        # Tokens should be non-empty strings
        self.assertIsInstance(access_token, str)
        self.assertIsInstance(refresh_token, str)
        self.assertGreater(len(access_token), 0)
        self.assertGreater(len(refresh_token), 0)


class CurrentClientTest(APITestCase, TestDataMixin):
    """Test /me endpoint for getting current client"""

    def setUp(self):
        self.client = APIClient()
        self.me_url = '/api/ecommerce/clients/me/'
        self.test_client = self.create_test_client(
            email='test@example.com',
            password='testpass123'
        )

    def get_jwt_token(self):
        """Helper to get JWT token"""
        login_url = '/api/ecommerce/clients/login/'
        data = {
            'identifier': 'test@example.com',
            'password': 'testpass123'
        }
        response = self.client.post(login_url, data, format='json')
        return response.data['access']

    def test_get_current_client_with_token(self):
        """Test getting current client with valid JWT token"""
        token = self.get_jwt_token()

        # Set authorization header
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'test@example.com')
        self.assertIn('first_name', response.data)
        self.assertIn('last_name', response.data)

    def test_get_current_client_without_token(self):
        """Test getting current client without token fails"""
        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_current_client_with_invalid_token(self):
        """Test getting current client with invalid token fails"""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token-here')

        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
