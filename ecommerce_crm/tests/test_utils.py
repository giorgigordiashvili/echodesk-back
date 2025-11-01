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

    _client_counter = 0
    _product_counter = 0
    _language_counter = 0

    @classmethod
    def create_test_client(cls, email=None, password='testpass123', **kwargs):
        """Create a test ecommerce client"""
        if email is None:
            cls._client_counter += 1
            email = f'testclient{cls._client_counter}@example.com'

        # Check if client already exists
        existing = EcommerceClient.objects.filter(email=email).first()
        if existing:
            return existing

        defaults = {
            'first_name': 'Test',
            'last_name': 'Client',
            'phone_number': f'+99555512{cls._client_counter:04d}',
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

    @classmethod
    def create_test_language(cls, code=None, is_default=False, **kwargs):
        """Create a test language"""
        if code is None:
            cls._language_counter += 1
            code = f'l{cls._language_counter}'

        # Check if language already exists
        existing = Language.objects.filter(code=code).first()
        if existing:
            return existing

        defaults = {
            'name': {'en': f'Language {code}', 'ka': f'ენა {code}'},
            'is_active': True,
            'sort_order': 0
        }
        defaults.update(kwargs)

        return Language.objects.create(
            code=code,
            is_default=is_default,
            **defaults
        )

    @classmethod
    def create_test_product(cls, sku=None, **kwargs):
        """Create a test product"""
        if sku is None:
            cls._product_counter += 1
            sku = f'TEST-{cls._product_counter:03d}'

        # Generate unique slug
        slug = kwargs.get('slug')
        if slug is None:
            slug = f'test-product-{cls._product_counter:03d}'

        defaults = {
            'slug': slug,
            'name': {'en': f'Test Product {sku}', 'ka': f'სატესტო პროდუქტი {sku}'},
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
    def create_test_address(client, **kwargs):
        """Create a test client address"""
        from ecommerce_crm.models import ClientAddress

        defaults = {
            'label': 'Home',
            'address': '123 Test Street',
            'city': 'Tbilisi',
            'is_default': True,
        }
        defaults.update(kwargs)

        return ClientAddress.objects.create(
            client=client,
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

    @classmethod
    def create_test_order(cls, client=None, **kwargs):
        """Create a test order"""
        from ecommerce_crm.models import Order

        if client is None:
            client = cls.create_test_client()

        # Create address if not provided
        if 'delivery_address' not in kwargs:
            kwargs['delivery_address'] = cls.create_test_address(client)

        defaults = {
            'order_number': f'ORD-TEST-{Order.objects.count() + 1:04d}',
            'status': 'pending',
            'total_amount': '0.00',
        }
        defaults.update(kwargs)

        return Order.objects.create(
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
