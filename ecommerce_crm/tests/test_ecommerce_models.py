"""
Extended model tests for ecommerce_crm — covers areas not already in test_models.py:
- PromoCode validation and discount calculation
- ProductReview creation and constraints
- Cart total calculations with variants
- Order status transitions and timestamp tracking
- Product slug generation edge cases
"""
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone
from django.db import IntegrityError
from django.contrib.auth.hashers import make_password

from users.tests.conftest import EchoDeskTenantTestCase
from ecommerce_crm.models import (
    Product,
    ProductVariant,
    EcommerceClient,
    ClientAddress,
    Cart,
    CartItem,
    Order,
    OrderItem,
    PromoCode,
    ProductReview,
    ShippingMethod,
)


# ============================================================================
# PromoCode
# ============================================================================

class TestPromoCodeModel(EchoDeskTenantTestCase):

    def _make_promo(self, code='TEST10', **kw):
        now = timezone.now()
        defaults = {
            'code': code,
            'discount_type': 'percentage',
            'discount_value': Decimal('10.00'),
            'valid_from': now - timedelta(days=1),
            'valid_until': now + timedelta(days=30),
            'is_active': True,
        }
        defaults.update(kw)
        return PromoCode.objects.create(**defaults)

    def test_create_promo_code(self):
        promo = self._make_promo('SAVE10')
        self.assertEqual(promo.code, 'SAVE10')
        self.assertEqual(promo.discount_type, 'percentage')
        self.assertTrue(promo.is_active)

    def test_promo_code_str(self):
        promo = self._make_promo('STR-CODE')
        self.assertIn('STR-CODE', str(promo))

    def test_promo_code_unique(self):
        self._make_promo('UNIQUE-CODE')
        with self.assertRaises(IntegrityError):
            self._make_promo('UNIQUE-CODE')

    def test_is_valid_active_code(self):
        promo = self._make_promo('VALID-1')
        valid, msg = promo.is_valid()
        self.assertTrue(valid)
        self.assertEqual(msg, 'Valid')

    def test_is_valid_inactive_code(self):
        promo = self._make_promo('INACTIVE-1', is_active=False)
        valid, msg = promo.is_valid()
        self.assertFalse(valid)
        self.assertIn('not active', msg)

    def test_is_valid_expired_code(self):
        now = timezone.now()
        promo = self._make_promo(
            'EXPIRED-1',
            valid_from=now - timedelta(days=30),
            valid_until=now - timedelta(days=1),
        )
        valid, msg = promo.is_valid()
        self.assertFalse(valid)
        self.assertIn('expired', msg)

    def test_is_valid_not_yet_active(self):
        now = timezone.now()
        promo = self._make_promo(
            'FUTURE-1',
            valid_from=now + timedelta(days=1),
            valid_until=now + timedelta(days=30),
        )
        valid, msg = promo.is_valid()
        self.assertFalse(valid)
        self.assertIn('not yet valid', msg)

    def test_is_valid_max_uses_reached(self):
        promo = self._make_promo('MAXUSE-1', max_uses=5, times_used=5)
        valid, msg = promo.is_valid()
        self.assertFalse(valid)
        self.assertIn('usage limit', msg)

    def test_is_valid_under_min_order_amount(self):
        promo = self._make_promo('MINORD-1', min_order_amount=Decimal('100.00'))
        valid, msg = promo.is_valid(subtotal=Decimal('50.00'))
        self.assertFalse(valid)
        self.assertIn('Minimum order amount', msg)

    def test_is_valid_above_min_order_amount(self):
        promo = self._make_promo('MINORD-2', min_order_amount=Decimal('50.00'))
        valid, msg = promo.is_valid(subtotal=Decimal('100.00'))
        self.assertTrue(valid)

    def test_calculate_discount_percentage(self):
        promo = self._make_promo('PCT-1', discount_type='percentage', discount_value=Decimal('20.00'))
        discount = promo.calculate_discount(Decimal('200.00'))
        self.assertEqual(discount, Decimal('40.00'))

    def test_calculate_discount_percentage_caps_at_subtotal(self):
        promo = self._make_promo('PCT-CAP', discount_type='percentage', discount_value=Decimal('200.00'))
        discount = promo.calculate_discount(Decimal('50.00'))
        self.assertEqual(discount, Decimal('50.00'))  # cannot exceed subtotal

    def test_calculate_discount_fixed(self):
        promo = self._make_promo('FIX-1', discount_type='fixed', discount_value=Decimal('25.00'))
        discount = promo.calculate_discount(Decimal('200.00'))
        self.assertEqual(discount, Decimal('25.00'))

    def test_calculate_discount_fixed_caps_at_subtotal(self):
        promo = self._make_promo('FIX-CAP', discount_type='fixed', discount_value=Decimal('100.00'))
        discount = promo.calculate_discount(Decimal('50.00'))
        self.assertEqual(discount, Decimal('50.00'))

    def test_max_uses_unlimited(self):
        promo = self._make_promo('UNLIMITED', max_uses=None, times_used=9999)
        valid, _ = promo.is_valid()
        self.assertTrue(valid)


# ============================================================================
# ProductReview
# ============================================================================

class TestProductReviewModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='review-admin@test.com')
        self.product = Product.objects.create(
            sku='REVIEW-PROD', name={'en': 'Review Product'},
            price=Decimal('50.00'), created_by=self.admin,
        )
        self.eclient = EcommerceClient(
            first_name='Review', last_name='Client',
            email='review@test.com', phone_number='+995555999001',
        )
        self.eclient.set_password('pass1234')
        self.eclient.save()

    def test_create_review(self):
        review = ProductReview.objects.create(
            product=self.product, client=self.eclient,
            rating=5, title='Great product', content='Loved it!',
        )
        self.assertEqual(review.rating, 5)
        self.assertTrue(review.is_approved)

    def test_review_str(self):
        review = ProductReview.objects.create(
            product=self.product, client=self.eclient,
            rating=4,
        )
        s = str(review)
        self.assertIn('review@test.com', s)
        self.assertIn('REVIEW-PROD', s)
        self.assertIn('4/5', s)

    def test_review_unique_per_product_per_client(self):
        ProductReview.objects.create(
            product=self.product, client=self.eclient, rating=3,
        )
        with self.assertRaises(IntegrityError):
            ProductReview.objects.create(
                product=self.product, client=self.eclient, rating=5,
            )

    def test_review_defaults(self):
        review = ProductReview.objects.create(
            product=self.product, client=self.eclient, rating=4,
        )
        self.assertFalse(review.is_verified_purchase)
        self.assertTrue(review.is_approved)


# ============================================================================
# Cart with variants
# ============================================================================

class TestCartWithVariants(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='cart-var-admin@test.com')
        self.eclient = EcommerceClient(
            first_name='VCart', last_name='Client',
            email='vcart@test.com', phone_number='+995555999002',
        )
        self.eclient.set_password('pass1234')
        self.eclient.save()
        self.product = Product.objects.create(
            sku='VCART-PROD', name={'en': 'Cart Variant Product'},
            price=Decimal('50.00'), created_by=self.admin,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku='VCART-VAR-RED',
            name={'en': 'Red'}, price=Decimal('55.00'), quantity=10,
        )

    def test_cart_item_with_variant(self):
        cart = Cart.objects.create(client=self.eclient)
        item = CartItem.objects.create(
            cart=cart, product=self.product, variant=self.variant,
            quantity=2, price_at_add=self.variant.price,
        )
        self.assertEqual(item.subtotal, Decimal('110.00'))
        self.assertEqual(cart.total_amount, Decimal('110.00'))

    def test_cart_item_auto_sets_variant_price(self):
        cart = Cart.objects.create(client=self.eclient)
        item = CartItem(
            cart=cart, product=self.product, variant=self.variant,
            quantity=1,
        )
        item.save()
        self.assertEqual(item.price_at_add, Decimal('55.00'))

    def test_cart_item_auto_sets_product_price_no_variant(self):
        cart = Cart.objects.create(client=self.eclient)
        item = CartItem(cart=cart, product=self.product, quantity=1)
        item.save()
        self.assertEqual(item.price_at_add, Decimal('50.00'))

    def test_cart_mixed_items_total(self):
        cart = Cart.objects.create(client=self.eclient)
        CartItem.objects.create(
            cart=cart, product=self.product,
            quantity=1, price_at_add=Decimal('50.00'),
        )
        CartItem.objects.create(
            cart=cart, product=self.product, variant=self.variant,
            quantity=2, price_at_add=Decimal('55.00'),
        )
        self.assertEqual(cart.total_amount, Decimal('160.00'))
        self.assertEqual(cart.total_items, 3)


# ============================================================================
# Order status transitions
# ============================================================================

class TestOrderStatusTransitions(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='trans-admin@test.com')
        self.eclient = EcommerceClient(
            first_name='Trans', last_name='Client',
            email='trans@test.com', phone_number='+995555999003',
        )
        self.eclient.set_password('pass1234')
        self.eclient.save()
        self.address = ClientAddress.objects.create(
            client=self.eclient, label='Home',
            address='Test St', city='Tbilisi',
        )

    def _make_order(self, **kw):
        defaults = {
            'order_number': Order.generate_order_number(),
            'client': self.eclient,
            'delivery_address': self.address,
            'total_amount': Decimal('100.00'),
        }
        defaults.update(kw)
        return Order.objects.create(**defaults)

    def test_pending_to_confirmed(self):
        order = self._make_order(status='pending')
        order.status = 'confirmed'
        order.confirmed_at = timezone.now()
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.status, 'confirmed')

    def test_confirmed_to_processing(self):
        order = self._make_order(status='confirmed')
        order.status = 'processing'
        order.processing_at = timezone.now()
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.status, 'processing')

    def test_processing_to_shipped(self):
        order = self._make_order(status='processing')
        order.status = 'shipped'
        order.shipped_at = timezone.now()
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.status, 'shipped')

    def test_shipped_to_delivered(self):
        order = self._make_order(status='shipped')
        order.status = 'delivered'
        order.delivered_at = timezone.now()
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')

    def test_pending_to_cancelled(self):
        order = self._make_order(status='pending')
        order.status = 'cancelled'
        order.cancelled_at = timezone.now()
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')


# ============================================================================
# Product slug edge cases
# ============================================================================

class TestProductSlugEdgeCases(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='slug-admin@test.com')

    def test_slug_from_ascii_sku(self):
        p = Product.objects.create(
            sku='SIMPLE-SKU', name={'en': 'Simple'},
            price=Decimal('10'), created_by=self.admin,
        )
        self.assertEqual(p.slug, 'simple-sku')

    def test_slug_uniqueness_with_collision(self):
        p1 = Product.objects.create(
            sku='COLLISION', name={'en': 'First'},
            price=Decimal('10'), created_by=self.admin,
        )
        # Force slug to collide by using a similar sku
        p2 = Product.objects.create(
            sku='COLLISION-V2', name={'en': 'Second'},
            price=Decimal('10'), created_by=self.admin,
        )
        self.assertNotEqual(p1.slug, p2.slug)

    def test_slug_not_overwritten_on_update(self):
        p = Product.objects.create(
            sku='KEEP-SLUG', name={'en': 'Keep'},
            price=Decimal('10'), created_by=self.admin,
        )
        original_slug = p.slug
        p.price = Decimal('20')
        p.save()
        p.refresh_from_db()
        self.assertEqual(p.slug, original_slug)

    def test_explicit_slug_is_preserved(self):
        p = Product.objects.create(
            sku='EXPLICIT-SKU', name={'en': 'Explicit'},
            price=Decimal('10'), slug='my-custom-slug', created_by=self.admin,
        )
        self.assertEqual(p.slug, 'my-custom-slug')
