"""
Tests for API endpoints
"""
from django.test import TestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from ecommerce_crm.models import (
    Product,
    Language,
    EcommerceClient,
    Cart,
    CartItem,
    FavoriteProduct,
    Order
)
from .test_utils import TestDataMixin

User = get_user_model()


class ProductAPITest(APITestCase, TestDataMixin):
    """Test Product API endpoints"""

    def setUp(self):
        self.client = APIClient()
        # Create admin user for authenticated requests
        self.user = User.objects.create_user(
            email='admin@echodesk.ge',
            password='adminpass123'
        )
        self.client.force_authenticate(user=self.user)

        # Create test product
        self.product = self.create_test_product(
            sku='TEST-001',
            price='99.99'
        )

    def test_list_products(self):
        """Test GET /api/ecommerce/products/"""
        response = self.client.get('/api/ecommerce/products/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data['results'], list)

    def test_retrieve_product(self):
        """Test GET /api/ecommerce/products/{id}/"""
        response = self.client.get(f'/api/ecommerce/products/{self.product.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sku'], 'TEST-001')

    def test_create_product(self):
        """Test POST /api/ecommerce/products/"""
        data = {
            'sku': 'NEW-001',
            'slug': 'new-product',
            'name': {'en': 'New Product'},
            'description': {'en': 'Description'},
            'price': '149.99',
            'status': 'draft',
            'track_inventory': False
        }

        response = self.client.post('/api/ecommerce/products/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['sku'], 'NEW-001')

        # Verify product was created
        product = Product.objects.get(sku='NEW-001')
        self.assertEqual(str(product.price), '149.99')

    def test_update_product(self):
        """Test PATCH /api/ecommerce/products/{id}/"""
        data = {
            'price': '119.99',
            'status': 'active'
        }

        response = self.client.patch(
            f'/api/ecommerce/products/{self.product.id}/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['price']), 119.99)

        # Verify product was updated
        self.product.refresh_from_db()
        self.assertEqual(str(self.product.price), '119.99')
        self.assertEqual(self.product.status, 'active')

    def test_delete_product(self):
        """Test DELETE /api/ecommerce/products/{id}/"""
        product_id = self.product.id

        response = self.client.delete(f'/api/ecommerce/products/{product_id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify product was deleted
        self.assertFalse(Product.objects.filter(id=product_id).exists())


class LanguageAPITest(APITestCase, TestDataMixin):
    """Test Language API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='admin@example.com',
            password='adminpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.language = self.create_test_language(code='en')

    def test_list_languages(self):
        """Test GET /api/ecommerce/languages/"""
        response = self.client.get('/api/ecommerce/languages/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)

    def test_retrieve_language(self):
        """Test GET /api/ecommerce/languages/{id}/"""
        response = self.client.get(f'/api/ecommerce/languages/{self.language.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'en')


class CartAPITest(APITestCase, TestDataMixin):
    """Test Cart API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='admin@example.com',
            password='adminpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.test_client = self.create_test_client()
        self.cart = self.create_test_cart(self.test_client)
        self.product = self.create_test_product()

    def test_list_carts(self):
        """Test GET /api/ecommerce/cart/"""
        response = self.client.get('/api/ecommerce/cart/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_or_create_cart(self):
        """Test GET /api/ecommerce/cart/get_or_create/"""
        new_client = self.create_test_client(
            email='new@example.com',
            phone_number='+995555999991'
        )

        response = self.client.get(
            f'/api/ecommerce/cart/get_or_create/?client={new_client.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('cart', response.data)

    def test_add_to_cart(self):
        """Test adding items to cart"""
        cart_item_data = {
            'cart': self.cart.id,
            'product': self.product.id,
            'quantity': 2
        }

        response = self.client.post(
            '/api/ecommerce/cart-items/',
            cart_item_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class FavoriteProductAPITest(APITestCase, TestDataMixin):
    """Test Favorite Products API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='admin@example.com',
            password='adminpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.test_client = self.create_test_client()
        self.product = self.create_test_product()

    def test_toggle_favorite(self):
        """Test POST /api/ecommerce/favorites/toggle/"""
        data = {
            'client': self.test_client.id,
            'product': self.product.id
        }

        # Add to favorites
        response = self.client.post(
            '/api/ecommerce/favorites/toggle/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_favorited'])

        # Remove from favorites
        response = self.client.post(
            '/api/ecommerce/favorites/toggle/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_favorited'])


class OrderAPITest(APITestCase, TestDataMixin):
    """Test Order API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='admin@example.com',
            password='adminpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.test_client = self.create_test_client()

    def test_list_orders(self):
        """Test GET /api/ecommerce/orders/"""
        response = self.client.get('/api/ecommerce/orders/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ClientAPITest(APITestCase, TestDataMixin):
    """Test Ecommerce Client API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='admin@example.com',
            password='adminpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_clients(self):
        """Test GET /api/ecommerce/clients/"""
        response = self.client.get('/api/ecommerce/clients/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_client(self):
        """Test GET /api/ecommerce/clients/{id}/"""
        test_client = self.create_test_client(email='test@example.com')

        response = self.client.get(f'/api/ecommerce/clients/{test_client.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'test@example.com')
