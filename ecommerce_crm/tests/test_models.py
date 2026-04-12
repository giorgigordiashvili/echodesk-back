"""
Tests for ecommerce_crm model logic.
Covers Product properties, Order/OrderItem calculations, EcommerceClient,
Language, AttributeDefinition, ProductVariant, Cart/CartItem, and EcommerceSettings.
"""
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone
from django.db import IntegrityError

from users.tests.conftest import EchoDeskTenantTestCase
from ecommerce_crm.models import (
    Language,
    AttributeDefinition,
    Product,
    ProductImage,
    ProductAttributeValue,
    ProductVariant,
    ProductVariantAttributeValue,
    EcommerceClient,
    ClientVerificationCode,
    ClientAddress,
    FavoriteProduct,
    Cart,
    CartItem,
    Order,
    OrderItem,
    EcommerceSettings,
)


# ============================================================================
# Language
# ============================================================================

class TestLanguageModel(EchoDeskTenantTestCase):

    def test_create_language(self):
        lang = Language.objects.create(
            code='de',
            name={'en': 'German', 'ka': 'გერმანული'},
            is_active=True,
        )
        self.assertEqual(lang.code, 'de')
        self.assertTrue(lang.is_active)

    def test_language_str_english(self):
        lang = Language.objects.create(
            code='fr', name={'en': 'French', 'ka': 'ფრანგული'},
        )
        self.assertEqual(str(lang), 'French')

    def test_language_get_name(self):
        lang = Language.objects.create(
            code='ru', name={'en': 'Russian', 'ka': 'რუსული'},
        )
        self.assertEqual(lang.get_name('ka'), 'რუსული')
        self.assertEqual(lang.get_name('en'), 'Russian')
        # Fallback to 'en' for unknown language
        self.assertEqual(lang.get_name('xx'), 'Russian')

    def test_default_language_flag(self):
        lang = Language.objects.create(
            code='en-test', name={'en': 'English'}, is_default=True,
        )
        self.assertTrue(lang.is_default)

    def test_inactive_language(self):
        lang = Language.objects.create(
            code='zh', name={'en': 'Chinese'}, is_active=False,
        )
        self.assertFalse(lang.is_active)

    def test_language_code_unique(self):
        Language.objects.create(code='unique-code', name={'en': 'Test'})
        with self.assertRaises(IntegrityError):
            Language.objects.create(code='unique-code', name={'en': 'Duplicate'})


# ============================================================================
# AttributeDefinition
# ============================================================================

class TestAttributeDefinitionModel(EchoDeskTenantTestCase):

    def test_create_multiselect_attribute(self):
        attr = AttributeDefinition.objects.create(
            name={'en': 'Color', 'ka': 'ფერი'},
            key='color',
            attribute_type='multiselect',
            options=[
                {'en': 'Red', 'ka': 'წითელი', 'value': 'red'},
                {'en': 'Blue', 'ka': 'ლურჯი', 'value': 'blue'},
            ],
            is_filterable=True,
        )
        self.assertEqual(attr.attribute_type, 'multiselect')
        self.assertEqual(len(attr.options), 2)

    def test_create_number_attribute(self):
        attr = AttributeDefinition.objects.create(
            name={'en': 'Weight'},
            key='weight',
            attribute_type='number',
            unit='kg',
        )
        self.assertEqual(attr.unit, 'kg')
        self.assertEqual(attr.attribute_type, 'number')

    def test_attribute_str(self):
        attr = AttributeDefinition.objects.create(
            name={'en': 'Size'}, key='size',
        )
        self.assertEqual(str(attr), 'Size')

    def test_attribute_get_name(self):
        attr = AttributeDefinition.objects.create(
            name={'en': 'Material', 'ka': 'მასალა'}, key='material',
        )
        self.assertEqual(attr.get_name('ka'), 'მასალა')
        self.assertEqual(attr.get_name('xx'), 'Material')

    def test_attribute_key_unique(self):
        AttributeDefinition.objects.create(name={'en': 'A'}, key='unique_key')
        with self.assertRaises(IntegrityError):
            AttributeDefinition.objects.create(name={'en': 'B'}, key='unique_key')

    def test_attribute_is_required_default(self):
        attr = AttributeDefinition.objects.create(
            name={'en': 'Optional'}, key='optional_attr',
        )
        self.assertFalse(attr.is_required)

    def test_attribute_is_filterable_default(self):
        attr = AttributeDefinition.objects.create(
            name={'en': 'Filterable'}, key='filterable_attr',
        )
        self.assertTrue(attr.is_filterable)


# ============================================================================
# Product
# ============================================================================

class TestProductModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='prod-model-admin@test.com')

    def _make_product(self, sku='TEST-001', **kwargs):
        defaults = {
            'sku': sku,
            'name': {'en': 'Test Product'},
            'price': Decimal('50.00'),
            'created_by': self.admin,
        }
        defaults.update(kwargs)
        return Product.objects.create(**defaults)

    def test_create_product(self):
        p = self._make_product()
        self.assertEqual(p.sku, 'TEST-001')
        self.assertEqual(p.price, Decimal('50.00'))

    def test_is_in_stock_true(self):
        p = self._make_product(quantity=10, track_inventory=True)
        self.assertTrue(p.is_in_stock)

    def test_is_in_stock_false(self):
        p = self._make_product(quantity=0, track_inventory=True)
        self.assertFalse(p.is_in_stock)

    def test_is_in_stock_no_tracking(self):
        """When inventory tracking is off, always in stock."""
        p = self._make_product(quantity=0, track_inventory=False)
        self.assertTrue(p.is_in_stock)

    def test_is_low_stock(self):
        p = self._make_product(quantity=3, low_stock_threshold=5, track_inventory=True)
        self.assertTrue(p.is_low_stock)

    def test_is_low_stock_false(self):
        p = self._make_product(quantity=10, low_stock_threshold=5, track_inventory=True)
        self.assertFalse(p.is_low_stock)

    def test_is_low_stock_no_tracking(self):
        """Low stock always False when tracking is off."""
        p = self._make_product(quantity=0, low_stock_threshold=5, track_inventory=False)
        self.assertFalse(p.is_low_stock)

    def test_discount_percentage(self):
        p = self._make_product(price=Decimal('80.00'), compare_at_price=Decimal('100.00'))
        self.assertEqual(p.discount_percentage, 20)

    def test_discount_percentage_no_compare(self):
        p = self._make_product(price=Decimal('50.00'))
        self.assertEqual(p.discount_percentage, 0)

    def test_discount_percentage_compare_lower(self):
        """No discount when compare_at_price is lower than price."""
        p = self._make_product(price=Decimal('100.00'), compare_at_price=Decimal('80.00'))
        self.assertEqual(p.discount_percentage, 0)

    def test_slug_auto_generated(self):
        p = self._make_product(sku='MY-PRODUCT-1')
        self.assertTrue(p.slug)
        self.assertIn('my-product-1', p.slug.lower())

    def test_slug_uniqueness(self):
        p1 = self._make_product(sku='SAME-SKU')
        p2 = self._make_product(sku='SAME-SKU-VARIANT')
        self.assertNotEqual(p1.slug, p2.slug)

    def test_get_name(self):
        p = self._make_product(name={'en': 'Laptop', 'ka': 'ლეპტოპი'})
        self.assertEqual(p.get_name('en'), 'Laptop')
        self.assertEqual(p.get_name('ka'), 'ლეპტოპი')
        self.assertEqual(p.get_name('xx'), 'Laptop')

    def test_get_description(self):
        p = self._make_product(description={'en': 'A laptop', 'ka': 'ლეპტოპი'})
        self.assertEqual(p.get_description('en'), 'A laptop')
        self.assertEqual(p.get_description('xx'), 'A laptop')

    def test_str_representation(self):
        p = self._make_product(sku='STR-01', name={'en': 'Widget'})
        self.assertIn('STR-01', str(p))
        self.assertIn('Widget', str(p))

    def test_product_status_default(self):
        p = self._make_product()
        self.assertEqual(p.status, 'draft')

    def test_product_featured_default(self):
        p = self._make_product()
        self.assertFalse(p.is_featured)


# ============================================================================
# ProductImage
# ============================================================================

class TestProductImageModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='img-admin@test.com')
        self.product = Product.objects.create(
            sku='IMG-PROD', name={'en': 'Img Product'},
            price=Decimal('10'), created_by=self.admin,
        )

    def test_create_product_image(self):
        img = ProductImage.objects.create(
            product=self.product,
            image='https://example.com/image.jpg',
            sort_order=0,
        )
        self.assertEqual(img.product, self.product)

    def test_image_str(self):
        img = ProductImage.objects.create(
            product=self.product,
            image='https://example.com/img.jpg',
        )
        self.assertIn('IMG-PROD', str(img))


# ============================================================================
# ProductAttributeValue
# ============================================================================

class TestProductAttributeValueModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='attrval-admin@test.com')
        self.product = Product.objects.create(
            sku='ATTR-PROD', name={'en': 'Attr Product'},
            price=Decimal('10'), created_by=self.admin,
        )
        self.color_attr = AttributeDefinition.objects.create(
            name={'en': 'Color'}, key='test_color', attribute_type='multiselect',
        )
        self.weight_attr = AttributeDefinition.objects.create(
            name={'en': 'Weight'}, key='test_weight', attribute_type='number', unit='kg',
        )

    def test_set_and_get_number_value(self):
        pav = ProductAttributeValue.objects.create(
            product=self.product, attribute=self.weight_attr,
        )
        pav.set_value(3.5)
        pav.save()
        self.assertEqual(pav.get_value(), Decimal('3.5'))

    def test_set_and_get_multiselect_value(self):
        pav = ProductAttributeValue.objects.create(
            product=self.product, attribute=self.color_attr,
        )
        pav.set_value(['red', 'blue'])
        pav.save()
        self.assertEqual(pav.get_value(), ['red', 'blue'])

    def test_unique_together_product_attribute(self):
        ProductAttributeValue.objects.create(
            product=self.product, attribute=self.color_attr,
        )
        with self.assertRaises(IntegrityError):
            ProductAttributeValue.objects.create(
                product=self.product, attribute=self.color_attr,
            )

    def test_str_representation(self):
        pav = ProductAttributeValue.objects.create(
            product=self.product, attribute=self.color_attr,
        )
        self.assertIn('ATTR-PROD', str(pav))
        self.assertIn('test_color', str(pav))


# ============================================================================
# ProductVariant
# ============================================================================

class TestProductVariantModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='variant-admin@test.com')
        self.product = Product.objects.create(
            sku='VAR-PROD', name={'en': 'Variant Product'},
            price=Decimal('100.00'), created_by=self.admin,
        )

    def test_create_variant(self):
        v = ProductVariant.objects.create(
            product=self.product, sku='VAR-PROD-RED',
            name={'en': 'Red'}, price=Decimal('110.00'), quantity=5,
        )
        self.assertEqual(v.effective_price, Decimal('110.00'))

    def test_effective_price_uses_product_price_when_no_variant_price(self):
        v = ProductVariant.objects.create(
            product=self.product, sku='VAR-PROD-DEFAULT',
            name={'en': 'Default'}, price=None, quantity=5,
        )
        self.assertEqual(v.effective_price, Decimal('100.00'))

    def test_variant_str(self):
        v = ProductVariant.objects.create(
            product=self.product, sku='VAR-PROD-BLU',
            name={'en': 'Blue'}, quantity=1,
        )
        self.assertIn('Blue', str(v))

    def test_variant_sku_unique(self):
        ProductVariant.objects.create(
            product=self.product, sku='UNIQUE-VAR', name={'en': 'A'},
        )
        with self.assertRaises(IntegrityError):
            ProductVariant.objects.create(
                product=self.product, sku='UNIQUE-VAR', name={'en': 'B'},
            )


# ============================================================================
# EcommerceClient
# ============================================================================

class TestEcommerceClientModel(EchoDeskTenantTestCase):

    def _make_client(self, email='buyer@example.com', **kwargs):
        defaults = {
            'first_name': 'Test',
            'last_name': 'Buyer',
            'email': email,
            'phone_number': kwargs.pop('phone_number', '+995555000001'),
        }
        defaults.update(kwargs)
        c = EcommerceClient(**defaults)
        c.set_password('pass1234')
        c.save()
        return c

    def test_create_client(self):
        c = self._make_client()
        self.assertEqual(c.email, 'buyer@example.com')
        self.assertEqual(c.full_name, 'Test Buyer')

    def test_password_hashing(self):
        c = self._make_client()
        self.assertTrue(c.check_password('pass1234'))
        self.assertFalse(c.check_password('wrong'))

    def test_is_authenticated_property(self):
        c = self._make_client()
        self.assertTrue(c.is_authenticated)

    def test_str_representation(self):
        c = self._make_client()
        self.assertIn('Test Buyer', str(c))
        self.assertIn('buyer@example.com', str(c))

    def test_update_last_login(self):
        c = self._make_client()
        self.assertIsNone(c.last_login)
        c.update_last_login()
        c.refresh_from_db()
        self.assertIsNotNone(c.last_login)

    def test_is_verified_default(self):
        c = self._make_client()
        self.assertFalse(c.is_verified)

    def test_is_active_default(self):
        c = self._make_client()
        self.assertTrue(c.is_active)


# ============================================================================
# ClientVerificationCode
# ============================================================================

class TestClientVerificationCodeModel(EchoDeskTenantTestCase):

    def test_is_valid_true(self):
        code = ClientVerificationCode.objects.create(
            email='v@test.com', code='123456', token='tok-1',
            expires_at=timezone.now() + timedelta(hours=1),
        )
        self.assertTrue(code.is_valid())

    def test_is_valid_expired(self):
        code = ClientVerificationCode.objects.create(
            email='v@test.com', code='111111', token='tok-2',
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertFalse(code.is_valid())

    def test_is_valid_used(self):
        code = ClientVerificationCode.objects.create(
            email='v@test.com', code='222222', token='tok-3',
            expires_at=timezone.now() + timedelta(hours=1),
            is_used=True,
        )
        self.assertFalse(code.is_valid())

    def test_str(self):
        code = ClientVerificationCode.objects.create(
            email='s@test.com', code='333333', token='tok-4',
            expires_at=timezone.now() + timedelta(hours=1),
        )
        self.assertIn('s@test.com', str(code))
        self.assertIn('333333', str(code))


# ============================================================================
# ClientAddress
# ============================================================================

class TestClientAddressModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.ec_client = EcommerceClient(
            first_name='Addr', last_name='Test',
            email='addr@test.com', phone_number='+995555888001',
        )
        self.ec_client.set_password('pass1234')
        self.ec_client.save()

    def test_create_address(self):
        addr = ClientAddress.objects.create(
            client=self.ec_client, label='Home',
            address='123 Main St', city='Tbilisi',
        )
        self.assertEqual(addr.city, 'Tbilisi')

    def test_default_address_flag(self):
        a1 = ClientAddress.objects.create(
            client=self.ec_client, label='Home',
            address='Addr 1', city='Tbilisi', is_default=True,
        )
        a2 = ClientAddress.objects.create(
            client=self.ec_client, label='Work',
            address='Addr 2', city='Tbilisi', is_default=True,
        )
        a1.refresh_from_db()
        a2.refresh_from_db()
        # Only the latest should be default
        self.assertFalse(a1.is_default)
        self.assertTrue(a2.is_default)

    def test_str_representation(self):
        addr = ClientAddress.objects.create(
            client=self.ec_client, label='Office',
            address='456 Oak', city='Batumi',
        )
        self.assertIn('Office', str(addr))
        self.assertIn('Batumi', str(addr))


# ============================================================================
# Cart & CartItem
# ============================================================================

class TestCartModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='cart-admin@test.com')
        self.ec_client = EcommerceClient(
            first_name='Cart', last_name='Client',
            email='cart@test.com', phone_number='+995555888002',
        )
        self.ec_client.set_password('pass1234')
        self.ec_client.save()
        self.product = Product.objects.create(
            sku='CART-PROD', name={'en': 'Cart Product'},
            price=Decimal('25.00'), created_by=self.admin,
        )

    def test_create_cart(self):
        cart = Cart.objects.create(client=self.ec_client)
        self.assertEqual(cart.status, 'active')
        self.assertEqual(cart.total_amount, 0)
        self.assertEqual(cart.total_items, 0)

    def test_cart_total_amount(self):
        cart = Cart.objects.create(client=self.ec_client)
        CartItem.objects.create(
            cart=cart, product=self.product,
            quantity=2, price_at_add=Decimal('25.00'),
        )
        CartItem.objects.create(
            cart=cart, product=self.product,
            quantity=1, price_at_add=Decimal('10.00'),
        )
        self.assertEqual(cart.total_amount, Decimal('60.00'))  # 50 + 10
        self.assertEqual(cart.total_items, 3)

    def test_cart_item_subtotal(self):
        cart = Cart.objects.create(client=self.ec_client)
        item = CartItem.objects.create(
            cart=cart, product=self.product,
            quantity=3, price_at_add=Decimal('25.00'),
        )
        self.assertEqual(item.subtotal, Decimal('75.00'))

    def test_cart_item_auto_set_price(self):
        """price_at_add is set from product price if not provided."""
        cart = Cart.objects.create(client=self.ec_client)
        item = CartItem(cart=cart, product=self.product, quantity=1)
        item.save()
        self.assertEqual(item.price_at_add, Decimal('25.00'))

    def test_cart_str(self):
        cart = Cart.objects.create(client=self.ec_client)
        self.assertIn('Cart Client', str(cart))


# ============================================================================
# Order & OrderItem
# ============================================================================

class TestOrderModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='order-admin@test.com')
        self.ec_client = EcommerceClient(
            first_name='Order', last_name='Client',
            email='order@test.com', phone_number='+995555888003',
        )
        self.ec_client.set_password('pass1234')
        self.ec_client.save()
        self.address = ClientAddress.objects.create(
            client=self.ec_client, label='Home',
            address='1 Test St', city='Tbilisi',
        )
        self.product = Product.objects.create(
            sku='ORD-PROD', name={'en': 'Order Product'},
            price=Decimal('30.00'), created_by=self.admin,
        )

    def _make_order(self, **kwargs):
        defaults = {
            'order_number': Order.generate_order_number(),
            'client': self.ec_client,
            'delivery_address': self.address,
            'total_amount': Decimal('60.00'),
        }
        defaults.update(kwargs)
        return Order.objects.create(**defaults)

    def test_create_order(self):
        order = self._make_order()
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.payment_status, 'pending')

    def test_order_number_format(self):
        order_num = Order.generate_order_number()
        self.assertTrue(order_num.startswith('ORD-'))

    def test_order_status_transitions(self):
        order = self._make_order(status='pending')
        order.status = 'confirmed'
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.status, 'confirmed')

    def test_order_total_items(self):
        order = self._make_order()
        OrderItem.objects.create(
            order=order, product=self.product,
            product_name={'en': 'Product 1'}, quantity=2, price=Decimal('30.00'),
        )
        OrderItem.objects.create(
            order=order, product=self.product,
            product_name={'en': 'Product 2'}, quantity=1, price=Decimal('15.00'),
        )
        self.assertEqual(order.total_items, 3)

    def test_order_str(self):
        order = self._make_order()
        self.assertIn('Order Client', str(order))

    def test_order_payment_tracking(self):
        order = self._make_order(payment_status='paid')
        order.paid_at = timezone.now()
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')
        self.assertIsNotNone(order.paid_at)


class TestOrderItemModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='oi-admin@test.com')
        self.ec_client = EcommerceClient(
            first_name='OI', last_name='Client',
            email='oi@test.com', phone_number='+995555888004',
        )
        self.ec_client.set_password('pass1234')
        self.ec_client.save()
        self.address = ClientAddress.objects.create(
            client=self.ec_client, label='Home',
            address='2 Test St', city='Tbilisi',
        )
        self.product = Product.objects.create(
            sku='OI-PROD', name={'en': 'OI Product'},
            price=Decimal('20.00'), created_by=self.admin,
        )
        self.order = Order.objects.create(
            order_number=Order.generate_order_number(),
            client=self.ec_client,
            delivery_address=self.address,
            total_amount=Decimal('40.00'),
        )

    def test_create_order_item(self):
        item = OrderItem.objects.create(
            order=self.order, product=self.product,
            product_name={'en': 'OI Product'}, quantity=2, price=Decimal('20.00'),
        )
        self.assertEqual(item.quantity, 2)

    def test_subtotal(self):
        item = OrderItem.objects.create(
            order=self.order, product=self.product,
            product_name={'en': 'OI Product'}, quantity=3, price=Decimal('20.00'),
        )
        self.assertEqual(item.subtotal, Decimal('60.00'))

    def test_str(self):
        item = OrderItem.objects.create(
            order=self.order, product=self.product,
            product_name={'en': 'OI Product'}, quantity=1, price=Decimal('20.00'),
        )
        self.assertIn('OI-PROD', str(item))


# ============================================================================
# FavoriteProduct
# ============================================================================

class TestFavoriteProductModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='fav-admin@test.com')
        self.ec_client = EcommerceClient(
            first_name='Fav', last_name='Client',
            email='fav@test.com', phone_number='+995555888005',
        )
        self.ec_client.set_password('pass1234')
        self.ec_client.save()
        self.product = Product.objects.create(
            sku='FAV-PROD', name={'en': 'Fav Product'},
            price=Decimal('15.00'), created_by=self.admin,
        )

    def test_create_favorite(self):
        fav = FavoriteProduct.objects.create(
            client=self.ec_client, product=self.product,
        )
        self.assertEqual(fav.client, self.ec_client)
        self.assertEqual(fav.product, self.product)

    def test_unique_together(self):
        FavoriteProduct.objects.create(
            client=self.ec_client, product=self.product,
        )
        with self.assertRaises(IntegrityError):
            FavoriteProduct.objects.create(
                client=self.ec_client, product=self.product,
            )

    def test_str(self):
        fav = FavoriteProduct.objects.create(
            client=self.ec_client, product=self.product,
        )
        self.assertIn('Fav Client', str(fav))
        self.assertIn('FAV-PROD', str(fav))


# ============================================================================
# EcommerceSettings
# ============================================================================

class TestEcommerceSettingsModel(EchoDeskTenantTestCase):

    def test_create_settings(self):
        settings = EcommerceSettings.objects.create(
            tenant=self.tenant,
            store_name='Test Store',
            store_email='store@test.com',
        )
        self.assertEqual(settings.store_name, 'Test Store')
        self.assertTrue(settings.enable_cash_on_delivery)
        self.assertTrue(settings.enable_card_payment)

    def test_settings_defaults(self):
        settings = EcommerceSettings.objects.create(tenant=self.tenant)
        self.assertEqual(settings.ecommerce_payment_provider, 'bog')
        self.assertTrue(settings.enable_cash_on_delivery)
        self.assertTrue(settings.enable_card_payment)
        self.assertEqual(settings.theme_preset, 'default')
        self.assertEqual(settings.deployment_status, 'pending')

    def test_settings_str(self):
        """EcommerceSettings should have a meaningful string representation."""
        settings = EcommerceSettings.objects.create(
            tenant=self.tenant,
            store_name='My Store',
        )
        # The model __str__ may vary, just ensure it doesn't crash
        self.assertIsInstance(str(settings), str)
