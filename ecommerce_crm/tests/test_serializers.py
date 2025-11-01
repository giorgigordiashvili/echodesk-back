"""
Tests for serializers
"""
from django.test import TestCase
from decimal import Decimal

from ecommerce_crm.serializers import (
    LanguageSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    EcommerceClientSerializer,
    ClientRegistrationSerializer,
    ClientLoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)
from ecommerce_crm.models import EcommerceClient, PasswordResetToken
from .test_utils import TestDataMixin


class LanguageSerializerTest(TestCase, TestDataMixin):
    """Test Language serializer"""

    def test_serialize_language(self):
        """Test serializing a language"""
        language = self.create_test_language(code='en')
        serializer = LanguageSerializer(language)

        data = serializer.data

        self.assertEqual(data['code'], 'en')
        self.assertIn('name', data)
        self.assertTrue(data['is_default'])


class ProductSerializerTest(TestCase, TestDataMixin):
    """Test Product serializers"""

    def test_product_list_serializer(self):
        """Test ProductListSerializer"""
        product = self.create_test_product(
            sku='TEST-001',
            price='99.99'
        )
        serializer = ProductListSerializer(product)

        data = serializer.data

        self.assertEqual(data['sku'], 'TEST-001')
        self.assertEqual(Decimal(data['price']), Decimal('99.99'))
        self.assertIn('name', data)

    def test_product_detail_serializer(self):
        """Test ProductDetailSerializer"""
        product = self.create_test_product(sku='TEST-001')
        serializer = ProductDetailSerializer(product)

        data = serializer.data

        self.assertEqual(data['sku'], 'TEST-001')
        self.assertIn('description', data)
        self.assertIn('images', data)
        self.assertIn('attribute_values', data)


class ClientRegistrationSerializerTest(TestCase, TestDataMixin):
    """Test ClientRegistrationSerializer"""

    def test_valid_registration_data(self):
        """Test serializer with valid data"""
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'phone_number': '+995555123456',
            'password': 'securepass123',
            'password_confirm': 'securepass123'
        }

        serializer = ClientRegistrationSerializer(data=data)

        self.assertTrue(serializer.is_valid())
        client = serializer.save()

        self.assertEqual(client.email, 'john@example.com')
        self.assertTrue(client.check_password('securepass123'))

    def test_password_mismatch(self):
        """Test serializer with password mismatch"""
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'phone_number': '+995555123456',
            'password': 'password123',
            'password_confirm': 'different123'
        }

        serializer = ClientRegistrationSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('password_confirm', serializer.errors)

    def test_duplicate_email(self):
        """Test serializer with duplicate email"""
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

        serializer = ClientRegistrationSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)


class ClientLoginSerializerTest(TestCase, TestDataMixin):
    """Test ClientLoginSerializer"""

    def setUp(self):
        self.client = self.create_test_client(
            email='test@example.com',
            password='testpass123'
        )

    def test_valid_login_with_email(self):
        """Test serializer with valid email login"""
        data = {
            'identifier': 'test@example.com',
            'password': 'testpass123'
        }

        serializer = ClientLoginSerializer(data=data)

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['client'], self.client)

    def test_valid_login_with_phone(self):
        """Test serializer with valid phone login"""
        data = {
            'identifier': '+995555123456',
            'password': 'testpass123'
        }

        serializer = ClientLoginSerializer(data=data)

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['client'], self.client)

    def test_invalid_password(self):
        """Test serializer with invalid password"""
        data = {
            'identifier': 'test@example.com',
            'password': 'wrongpassword'
        }

        serializer = ClientLoginSerializer(data=data)

        self.assertFalse(serializer.is_valid())

    def test_nonexistent_client(self):
        """Test serializer with nonexistent client"""
        data = {
            'identifier': 'nonexistent@example.com',
            'password': 'anypassword'
        }

        serializer = ClientLoginSerializer(data=data)

        self.assertFalse(serializer.is_valid())


class PasswordResetSerializerTest(TestCase, TestDataMixin):
    """Test password reset serializers"""

    def test_password_reset_request_valid(self):
        """Test PasswordResetRequestSerializer with valid email"""
        client = self.create_test_client(email='test@example.com')

        data = {'email': 'test@example.com'}

        serializer = PasswordResetRequestSerializer(data=data)

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.context.get('client'), client)

    def test_password_reset_request_invalid_email(self):
        """Test PasswordResetRequestSerializer with invalid email"""
        data = {'email': 'nonexistent@example.com'}

        serializer = PasswordResetRequestSerializer(data=data)

        self.assertFalse(serializer.is_valid())

    def test_password_reset_confirm_valid(self):
        """Test PasswordResetConfirmSerializer with valid data"""
        client = self.create_test_client()
        reset_token = self.create_test_password_reset_token(client)

        data = {
            'token': reset_token.token,
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123'
        }

        serializer = PasswordResetConfirmSerializer(data=data)

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['reset_token'], reset_token)

    def test_password_reset_confirm_password_mismatch(self):
        """Test PasswordResetConfirmSerializer with password mismatch"""
        client = self.create_test_client()
        reset_token = self.create_test_password_reset_token(client)

        data = {
            'token': reset_token.token,
            'new_password': 'newpassword123',
            'new_password_confirm': 'different123'
        }

        serializer = PasswordResetConfirmSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('new_password_confirm', serializer.errors)

    def test_password_reset_confirm_invalid_token(self):
        """Test PasswordResetConfirmSerializer with invalid token"""
        data = {
            'token': 'invalid-token',
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123'
        }

        serializer = PasswordResetConfirmSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('token', serializer.errors)


class EcommerceClientSerializerTest(TestCase, TestDataMixin):
    """Test EcommerceClientSerializer"""

    def test_serialize_client(self):
        """Test serializing a client"""
        client = self.create_test_client(
            email='test@example.com',
            first_name='John',
            last_name='Doe'
        )

        serializer = EcommerceClientSerializer(client)

        data = serializer.data

        self.assertEqual(data['email'], 'test@example.com')
        self.assertEqual(data['first_name'], 'John')
        self.assertEqual(data['last_name'], 'Doe')
        self.assertEqual(data['full_name'], 'John Doe')
        self.assertIn('addresses', data)
        self.assertIn('favorites', data)
