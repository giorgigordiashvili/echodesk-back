"""
Test utilities and helper functions
"""
from django.utils import timezone
from datetime import timedelta
from ecommerce_crm.models import (
    EcommerceClient,
    Product,
    Language,
    AttributeDefinition,
    Cart,
    Order,
    PasswordResetToken
)


class TestDataMixin:
    """Mixin providing common test data creation methods"""

    @staticmethod
    def create_test_client(email='test@example.com', password='testpass123', **kwargs):
        """Create a test ecommerce client"""
        defaults = {
            'first_name': 'Test',
            'last_name': 'Client',
            'phone_number': '+995555123456',
            'is_active': True,
        }
        defaults.update(kwargs)

        client = EcommerceClient.objects.create(
            email=email,
            **defaults
        )
        client.set_password(password)
        client.save()
        return client

    @staticmethod
    def create_test_language(code='en', is_default=True, **kwargs):
        """Create a test language"""
        defaults = {
            'name': {'en': 'English', 'ka': 'ინგლისური'},
            'is_active': True,
            'sort_order': 0
        }
        defaults.update(kwargs)

        return Language.objects.create(
            code=code,
            is_default=is_default,
            **defaults
        )

    @staticmethod
    def create_test_product(sku='TEST-001', **kwargs):
        """Create a test product"""
        defaults = {
            'slug': 'test-product-001',
            'name': {'en': 'Test Product', 'ka': 'სატესტო პროდუქტი'},
            'description': {'en': 'Test description', 'ka': 'სატესტო აღწერა'},
            'price': '99.99',
            'status': 'active',
            'track_inventory': False,
        }
        defaults.update(kwargs)

        return Product.objects.create(
            sku=sku,
            **defaults
        )

    @staticmethod
    def create_test_attribute(key='test_attr', **kwargs):
        """Create a test attribute definition"""
        defaults = {
            'name': {'en': 'Test Attribute', 'ka': 'სატესტო ატრიბუტი'},
            'attribute_type': 'text',
            'is_active': True,
            'sort_order': 0
        }
        defaults.update(kwargs)

        return AttributeDefinition.objects.create(
            key=key,
            **defaults
        )

    @staticmethod
    def create_test_cart(client, **kwargs):
        """Create a test shopping cart"""
        defaults = {
            'status': 'active'
        }
        defaults.update(kwargs)

        return Cart.objects.create(
            client=client,
            **defaults
        )

    @staticmethod
    def create_test_password_reset_token(client):
        """Create a test password reset token"""
        token = PasswordResetToken.generate_token()
        expires_at = timezone.now() + timedelta(hours=24)

        return PasswordResetToken.objects.create(
            client=client,
            token=token,
            expires_at=expires_at
        )
