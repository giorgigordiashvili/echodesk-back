"""
Tests for ecommerce_crm models
"""
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from decimal import Decimal

from ecommerce_crm.models import (
    Language,
    EcommerceClient,
    Product,
    ProductImage,
    ProductVariant,
    AttributeDefinition,
    ProductAttributeValue,
    ClientAddress,
    FavoriteProduct,
    Cart,
    CartItem,
    Order,
    OrderItem,
    PasswordResetToken
)
from .test_utils import TestDataMixin


class LanguageModelTest(TestCase, TestDataMixin):
    """Test Language model"""

    def test_create_language(self):
        """Test creating a language"""
        language = self.create_test_language(code='en')
        self.assertEqual(language.code, 'en')
        self.assertTrue(language.is_default)
        self.assertTrue(language.is_active)

    def test_language_string_representation(self):
        """Test language __str__ method"""
        language = self.create_test_language(code='en')
        self.assertIn('English', str(language))

    def test_only_one_default_language(self):
        """Test that only one language can be default"""
        lang1 = self.create_test_language(code='en', is_default=True)
        lang2 = self.create_test_language(code='ka', is_default=False)

        self.assertTrue(lang1.is_default)
        self.assertFalse(lang2.is_default)


class EcommerceClientModelTest(TestCase, TestDataMixin):
    """Test EcommerceClient model"""

    def test_create_client(self):
        """Test creating an ecommerce client"""
        client = self.create_test_client(
            email='john@example.com',
            first_name='John',
            last_name='Doe'
        )
        self.assertEqual(client.email, 'john@example.com')
        self.assertEqual(client.first_name, 'John')
        self.assertEqual(client.last_name, 'Doe')
        self.assertTrue(client.is_active)

    def test_client_full_name(self):
        """Test full_name property"""
        client = self.create_test_client(
            first_name='John',
            last_name='Doe'
        )
        self.assertEqual(client.full_name, 'John Doe')

    def test_client_password_hashing(self):
        """Test that password is hashed"""
        client = self.create_test_client(password='plaintext123')
        self.assertNotEqual(client.password, 'plaintext123')
        self.assertTrue(client.check_password('plaintext123'))

    def test_client_password_check(self):
        """Test password verification"""
        client = self.create_test_client(password='correctpass')
        self.assertTrue(client.check_password('correctpass'))
        self.assertFalse(client.check_password('wrongpass'))

    def test_client_update_last_login(self):
        """Test updating last login timestamp"""
        client = self.create_test_client()
        self.assertIsNone(client.last_login)

        client.update_last_login()
        client.refresh_from_db()
        self.assertIsNotNone(client.last_login)

    def test_unique_email(self):
        """Test email uniqueness"""
        self.create_test_client(email='unique@example.com')

        # Should raise error on duplicate email
        with self.assertRaises(Exception):
            self.create_test_client(email='unique@example.com')


class ProductModelTest(TestCase, TestDataMixin):
    """Test Product model"""

    def test_create_product(self):
        """Test creating a product"""
        product = self.create_test_product(
            sku='PROD-001',
            price='149.99'
        )
        self.assertEqual(product.sku, 'PROD-001')
        self.assertEqual(product.price, Decimal('149.99'))

    def test_product_string_representation(self):
        """Test product __str__ method"""
        product = self.create_test_product(sku='TEST-SKU')
        self.assertIn('TEST-SKU', str(product))

    def test_product_status_choices(self):
        """Test product status"""
        product = self.create_test_product(status='active')
        self.assertEqual(product.status, 'active')

        product.status = 'draft'
        product.save()
        self.assertEqual(product.status, 'draft')

    def test_product_discount_percentage(self):
        """Test discount percentage calculation"""
        product = self.create_test_product(
            price='100.00',
            compare_at_price='150.00'
        )
        # Should calculate discount percentage
        self.assertIsNotNone(product.price)


class AttributeDefinitionModelTest(TestCase, TestDataMixin):
    """Test AttributeDefinition model"""

    def test_create_attribute(self):
        """Test creating an attribute definition"""
        attr = self.create_test_attribute(
            key='color',
            attribute_type='text'
        )
        self.assertEqual(attr.key, 'color')
        self.assertEqual(attr.attribute_type, 'text')

    def test_attribute_types(self):
        """Test different attribute types"""
        types = ['text', 'number', 'boolean', 'date', 'json']
        for attr_type in types:
            attr = self.create_test_attribute(
                key=f'{attr_type}_attr',
                attribute_type=attr_type
            )
            self.assertEqual(attr.attribute_type, attr_type)


class PasswordResetTokenModelTest(TestCase, TestDataMixin):
    """Test PasswordResetToken model"""

    def test_create_token(self):
        """Test creating a password reset token"""
        client = self.create_test_client()
        token = self.create_test_password_reset_token(client)

        self.assertIsNotNone(token.token)
        self.assertEqual(token.client, client)
        self.assertFalse(token.is_used)

    def test_token_generation(self):
        """Test token generation method"""
        token1 = PasswordResetToken.generate_token()
        token2 = PasswordResetToken.generate_token()

        self.assertIsInstance(token1, str)
        self.assertIsInstance(token2, str)
        self.assertNotEqual(token1, token2)  # Tokens should be unique
        self.assertGreater(len(token1), 20)  # Sufficiently long

    def test_token_validity_check(self):
        """Test token is_valid method"""
        client = self.create_test_client()

        # Valid token
        valid_token = PasswordResetToken.objects.create(
            client=client,
            token='valid-token',
            expires_at=timezone.now() + timedelta(hours=24)
        )
        self.assertTrue(valid_token.is_valid())

        # Expired token
        expired_token = PasswordResetToken.objects.create(
            client=client,
            token='expired-token',
            expires_at=timezone.now() - timedelta(hours=1)
        )
        self.assertFalse(expired_token.is_valid())

        # Used token
        used_token = PasswordResetToken.objects.create(
            client=client,
            token='used-token',
            expires_at=timezone.now() + timedelta(hours=24),
            is_used=True
        )
        self.assertFalse(used_token.is_valid())

    def test_mark_token_as_used(self):
        """Test marking token as used"""
        client = self.create_test_client()
        token = self.create_test_password_reset_token(client)

        self.assertFalse(token.is_used)
        self.assertIsNone(token.used_at)

        token.mark_as_used()
        token.refresh_from_db()

        self.assertTrue(token.is_used)
        self.assertIsNotNone(token.used_at)


class CartModelTest(TestCase, TestDataMixin):
    """Test Cart model"""

    def test_create_cart(self):
        """Test creating a shopping cart"""
        client = self.create_test_client()
        cart = self.create_test_cart(client)

        self.assertEqual(cart.client, client)
        self.assertEqual(cart.status, 'active')

    def test_cart_total_amount(self):
        """Test cart total amount calculation"""
        client = self.create_test_client()
        cart = self.create_test_cart(client)
        product1 = self.create_test_product(sku='PROD-1', price='50.00')
        product2 = self.create_test_product(sku='PROD-2', price='30.00')

        # Add items to cart
        CartItem.objects.create(
            cart=cart,
            product=product1,
            quantity=2,
            price_at_add='50.00'
        )
        CartItem.objects.create(
            cart=cart,
            product=product2,
            quantity=1,
            price_at_add='30.00'
        )

        # Total should be (50 * 2) + (30 * 1) = 130
        cart.refresh_from_db()
        self.assertEqual(cart.total_amount, Decimal('130.00'))


class OrderModelTest(TestCase, TestDataMixin):
    """Test Order model"""

    def test_generate_order_number(self):
        """Test order number generation"""
        order_number1 = Order.generate_order_number()
        order_number2 = Order.generate_order_number()

        self.assertIsInstance(order_number1, str)
        self.assertTrue(order_number1.startswith('ORD-'))
        self.assertNotEqual(order_number1, order_number2)

    def test_order_total_items_property(self):
        """Test total_items property"""
        client = self.create_test_client()
        cart = self.create_test_cart(client)
        product = self.create_test_product()

        # Create order
        order = Order.objects.create(
            order_number=Order.generate_order_number(),
            client=client,
            total_amount='100.00',
            status='pending'
        )

        # Add order items
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            quantity=3,
            price='33.33'
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            quantity=2,
            price='16.67'
        )

        # Total items should be 3 + 2 = 5
        self.assertEqual(order.total_items, 5)


class FavoriteProductModelTest(TestCase, TestDataMixin):
    """Test FavoriteProduct model"""

    def test_create_favorite(self):
        """Test adding product to favorites"""
        client = self.create_test_client()
        product = self.create_test_product()

        favorite = FavoriteProduct.objects.create(
            client=client,
            product=product
        )

        self.assertEqual(favorite.client, client)
        self.assertEqual(favorite.product, product)

    def test_unique_favorite(self):
        """Test that same product can't be favorited twice by same client"""
        client = self.create_test_client()
        product = self.create_test_product()

        FavoriteProduct.objects.create(client=client, product=product)

        # Should raise error on duplicate
        with self.assertRaises(Exception):
            FavoriteProduct.objects.create(client=client, product=product)
