"""
Tests for email functionality
"""
from django.test import TestCase
from django.core import mail
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from ecommerce_crm.models import EcommerceClient, PasswordResetToken
from ecommerce_crm.email_utils import send_welcome_email, send_password_reset_email
from .test_utils import TestDataMixin


class WelcomeEmailTest(TestCase, TestDataMixin):
    """Test welcome email functionality"""

    def test_send_welcome_email(self):
        """Test sending welcome email"""
        client = self.create_test_client(
            email='newclient@example.com',
            first_name='John'
        )

        # Send welcome email
        result = send_welcome_email(client)

        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Check email details
        email = mail.outbox[0]
        self.assertIn('Welcome', email.subject)
        self.assertIn('newclient@example.com', email.to)
        self.assertIn('John', email.body)

    def test_welcome_email_on_registration(self):
        """Test that welcome email is sent on client registration"""
        client = APIClient()
        url = '/api/ecommerce/clients/register/'

        data = {
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': 'jane@example.com',
            'phone_number': '+995555123456',
            'password': 'securepass123',
            'password_confirm': 'securepass123'
        }

        # Clear any existing emails
        mail.outbox = []

        response = client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check that one email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Check email content
        email = mail.outbox[0]
        self.assertIn('Welcome', email.subject)
        self.assertIn('jane@example.com', email.to)


class PasswordResetEmailTest(TestCase, TestDataMixin):
    """Test password reset email functionality"""

    def test_send_password_reset_email(self):
        """Test sending password reset email"""
        client = self.create_test_client(
            email='test@example.com',
            first_name='Test'
        )
        token = 'test-reset-token-123'

        # Send password reset email
        result = send_password_reset_email(client, token)

        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Check email details
        email = mail.outbox[0]
        self.assertIn('Password', email.subject)
        self.assertIn('test@example.com', email.to)
        self.assertIn(token, email.body)

    def test_password_reset_email_on_request(self):
        """Test that password reset email is sent on reset request"""
        # Create client
        test_client = self.create_test_client(
            email='reset@example.com',
            password='oldpassword'
        )

        client = APIClient()
        url = '/api/ecommerce/clients/password-reset/request/'

        data = {
            'email': 'reset@example.com'
        }

        # Clear any existing emails
        mail.outbox = []

        response = client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that one email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Check email content
        email = mail.outbox[0]
        self.assertIn('Password', email.subject)
        self.assertIn('reset@example.com', email.to)

    def test_password_reset_email_contains_token(self):
        """Test that password reset email contains the reset token"""
        test_client = self.create_test_client(email='test@example.com')

        client = APIClient()
        url = '/api/ecommerce/clients/password-reset/request/'

        data = {'email': 'test@example.com'}

        # Clear any existing emails
        mail.outbox = []

        response = client.post(url, data, format='json')

        # Get the token from database
        token = PasswordResetToken.objects.filter(
            client=test_client,
            is_used=False
        ).first()

        # Check email contains token
        email = mail.outbox[0]
        self.assertIn(token.token, email.body)


class EmailTemplateTest(TestCase, TestDataMixin):
    """Test email templates"""

    def test_welcome_email_template_rendered(self):
        """Test that welcome email template is rendered correctly"""
        client = self.create_test_client(
            email='template@example.com',
            first_name='Template'
        )

        send_welcome_email(client)

        email = mail.outbox[0]

        # Check that email contains expected content
        self.assertIn('Template', email.body)
        self.assertIn('template@example.com', email.body)

    def test_password_reset_email_template_rendered(self):
        """Test that password reset email template is rendered correctly"""
        client = self.create_test_client(
            email='reset@example.com',
            first_name='Reset'
        )
        token = 'test-token-456'

        send_password_reset_email(client, token)

        email = mail.outbox[0]

        # Check that email contains expected content
        self.assertIn('Reset', email.body)
        self.assertIn(token, email.body)
        self.assertIn('reset-password', email.body)  # Reset URL should be included


class EmailContentTest(TestCase, TestDataMixin):
    """Test email content and formatting"""

    def test_welcome_email_has_html_version(self):
        """Test that welcome email has HTML alternative"""
        client = self.create_test_client(email='html@example.com')

        send_welcome_email(client)

        email = mail.outbox[0]

        # Check that email has alternatives (HTML version)
        self.assertGreater(len(email.alternatives), 0)

        # Check that HTML alternative is present
        html_content, content_type = email.alternatives[0]
        self.assertEqual(content_type, 'text/html')
        self.assertIn('html', html_content.lower())

    def test_password_reset_email_has_html_version(self):
        """Test that password reset email has HTML alternative"""
        client = self.create_test_client(email='html@example.com')
        token = 'test-token'

        send_password_reset_email(client, token)

        email = mail.outbox[0]

        # Check that email has alternatives (HTML version)
        self.assertGreater(len(email.alternatives), 0)

        # Check that HTML alternative is present
        html_content, content_type = email.alternatives[0]
        self.assertEqual(content_type, 'text/html')
        self.assertIn('html', html_content.lower())

    def test_email_from_address(self):
        """Test that emails are sent from correct address"""
        client = self.create_test_client(email='test@example.com')

        send_welcome_email(client)

        email = mail.outbox[0]

        # Check from address
        self.assertIn('echodesk', email.from_email.lower())
