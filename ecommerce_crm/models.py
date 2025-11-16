from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.contrib.auth.hashers import make_password, check_password
from decimal import Decimal
import uuid
import base64


class Language(models.Model):
    """
    Available languages for multilanguage product content
    Default languages: English (en) and Georgian (ka)
    Users can add additional languages as needed
    """
    code = models.CharField(
        max_length=10,
        unique=True,
        help_text="Language code (e.g., 'en', 'ka', 'ru', 'de')"
    )
    name = models.JSONField(
        help_text="Language name in different languages: {'en': 'English', 'ka': 'ინგლისური'}"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is a default required language"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this language is active and available for use"
    )
    sort_order = models.IntegerField(default=0, help_text="Display order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'code']
        verbose_name = 'Language'
        verbose_name_plural = 'Languages'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active', 'sort_order']),
        ]

    def __str__(self):
        if isinstance(self.name, dict):
            return self.name.get('en', self.name.get(list(self.name.keys())[0], self.code))
        return str(self.name)

    def get_name(self, language='en'):
        """Get language name in specific language"""
        if isinstance(self.name, dict):
            return self.name.get(language, self.name.get('en', self.code))
        return str(self.name)


class AttributeDefinition(models.Model):
    """
    Define dynamic attributes that can be assigned to products
    (e.g., Color, Size, Material, etc.)
    """
    ATTRIBUTE_TYPES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('boolean', 'Boolean'),
        ('select', 'Single Select'),
        ('multiselect', 'Multi Select'),
        ('color', 'Color'),
        ('date', 'Date'),
    ]

    name = models.JSONField(
        help_text="Attribute name in different languages: {'en': 'Color', 'ka': 'ფერი', 'ru': 'Цвет'}"
    )
    key = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique key for code reference (e.g., 'color', 'size')"
    )
    attribute_type = models.CharField(max_length=20, choices=ATTRIBUTE_TYPES, default='text')
    options = models.JSONField(
        blank=True,
        default=list,
        help_text="For select/multiselect types: [{'en': 'Red', 'ka': 'წითელი', 'ru': 'Красный', 'value': 'red'}, ...]"
    )
    unit = models.CharField(
        max_length=50,
        blank=True,
        help_text="Unit of measurement (e.g., 'cm', 'kg', 'ml')"
    )
    is_required = models.BooleanField(default=False)
    is_variant_attribute = models.BooleanField(
        default=False,
        help_text="If True, this attribute can be used to create product variants (e.g., Size, Color)"
    )
    is_filterable = models.BooleanField(
        default=True,
        help_text="Whether this attribute can be used for filtering products"
    )
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Attribute Definition'
        verbose_name_plural = 'Attribute Definitions'
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['is_active', 'sort_order']),
        ]

    def __str__(self):
        if isinstance(self.name, dict):
            return self.name.get('en', self.name.get(list(self.name.keys())[0], self.key))
        return str(self.name)

    def get_name(self, language='en'):
        """Get attribute name in specific language"""
        if isinstance(self.name, dict):
            return self.name.get(language, self.name.get('en', self.key))
        return str(self.name)


class Product(models.Model):
    """Main product model"""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('out_of_stock', 'Out of Stock'),
    ]

    # Basic Information
    sku = models.CharField(max_length=100, unique=True, help_text="Stock Keeping Unit")
    name = models.JSONField(
        help_text="Product name in different languages: {'en': 'Laptop', 'ka': 'ლეპტოპი', 'ru': 'Ноутбук'}"
    )
    description = models.JSONField(
        blank=True,
        default=dict,
        help_text="Product description in different languages"
    )
    short_description = models.JSONField(
        blank=True,
        default=dict,
        help_text="Short product description in different languages"
    )

    # Using dynamic attributes instead of fixed product types and categories

    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Base price in GEL"
    )
    compare_at_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Original price for showing discounts"
    )
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Cost price for profit calculation"
    )

    # Media
    image = models.URLField(
        max_length=2000,
        blank=True,
        null=True,
        help_text="Main product image URL"
    )

    # Inventory
    track_inventory = models.BooleanField(default=True)
    quantity = models.IntegerField(default=0, help_text="Stock quantity")
    low_stock_threshold = models.IntegerField(
        default=10,
        help_text="Alert when stock falls below this level"
    )

    # Status and metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Weight in kg"
    )
    dimensions = models.JSONField(
        blank=True,
        default=dict,
        help_text="Dimensions: {'length': 10, 'width': 5, 'height': 3, 'unit': 'cm'}"
    )

    # SEO
    meta_title = models.JSONField(
        blank=True,
        default=dict,
        help_text="SEO title in different languages"
    )
    meta_description = models.JSONField(
        blank=True,
        default=dict,
        help_text="SEO description in different languages"
    )
    slug = models.SlugField(max_length=200, unique=True)

    # Timestamps and user tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_products'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_products'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['slug']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['is_featured', 'status']),
        ]

    def __str__(self):
        if isinstance(self.name, dict):
            name = self.name.get('en', self.name.get(list(self.name.keys())[0], 'Unnamed'))
        else:
            name = str(self.name)
        return f"{self.sku} - {name}"

    def get_name(self, language='en'):
        """Get product name in specific language"""
        if isinstance(self.name, dict):
            return self.name.get(language, self.name.get('en', ''))
        return str(self.name)

    def get_description(self, language='en'):
        """Get product description in specific language"""
        if isinstance(self.description, dict):
            return self.description.get(language, self.description.get('en', ''))
        return str(self.description)

    @property
    def is_low_stock(self):
        """Check if product is low on stock"""
        if not self.track_inventory:
            return False
        return self.quantity <= self.low_stock_threshold

    @property
    def is_in_stock(self):
        """Check if product is in stock"""
        if not self.track_inventory:
            return True
        return self.quantity > 0

    @property
    def discount_percentage(self):
        """Calculate discount percentage if compare_at_price is set"""
        if self.compare_at_price and self.compare_at_price > self.price:
            return round(((self.compare_at_price - self.price) / self.compare_at_price) * 100, 2)
        return 0


class ProductImage(models.Model):
    """Additional product images"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.URLField(max_length=2000, help_text="Product image URL")
    alt_text = models.JSONField(
        blank=True,
        default=dict,
        help_text="Alt text in different languages for SEO"
    )
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'

    def __str__(self):
        return f"Image for {self.product.sku}"


class ProductAttributeValue(models.Model):
    """
    Store attribute values for products
    Allows dynamic attributes without schema changes
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attribute_values')
    attribute = models.ForeignKey(AttributeDefinition, on_delete=models.CASCADE, related_name='product_values')

    # Store value based on attribute type
    value_text = models.TextField(blank=True)
    value_number = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)
    value_date = models.DateField(null=True, blank=True)
    value_json = models.JSONField(
        blank=True,
        default=dict,
        help_text="For complex values like multiselect or multilanguage text"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['product', 'attribute']
        verbose_name = 'Product Attribute Value'
        verbose_name_plural = 'Product Attribute Values'
        indexes = [
            models.Index(fields=['product', 'attribute']),
        ]

    def __str__(self):
        return f"{self.product.sku} - {self.attribute.key}"

    def get_value(self):
        """Get the appropriate value based on attribute type"""
        attribute_type = self.attribute.attribute_type

        if attribute_type == 'text':
            return self.value_text
        elif attribute_type == 'number':
            return self.value_number
        elif attribute_type == 'boolean':
            return self.value_boolean
        elif attribute_type == 'date':
            return self.value_date
        elif attribute_type in ['select', 'multiselect', 'color']:
            return self.value_json

        return None

    def set_value(self, value):
        """Set the appropriate value field based on attribute type"""
        attribute_type = self.attribute.attribute_type

        if attribute_type == 'text':
            self.value_text = str(value)
        elif attribute_type == 'number':
            self.value_number = Decimal(str(value))
        elif attribute_type == 'boolean':
            self.value_boolean = bool(value)
        elif attribute_type == 'date':
            self.value_date = value
        elif attribute_type in ['select', 'multiselect', 'color']:
            self.value_json = value


class ProductVariant(models.Model):
    """
    Product variants (e.g., different sizes or colors of the same product)
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=100, unique=True, help_text="Variant SKU")
    name = models.JSONField(
        help_text="Variant name in different languages: {'en': 'Blue - Large', 'ka': 'ლურჯი - დიდი'}"
    )

    # Pricing (can override parent product price)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Variant price (if different from base product)"
    )

    # Inventory
    quantity = models.IntegerField(default=0)
    image = models.URLField(
        max_length=2000,
        blank=True,
        null=True,
        help_text="Product variant image URL"
    )

    # Status
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'
        indexes = [
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['sku']),
        ]

    def __str__(self):
        if isinstance(self.name, dict):
            name = self.name.get('en', self.name.get(list(self.name.keys())[0], self.sku))
        else:
            name = str(self.name)
        return f"{self.product.sku} - {name}"

    @property
    def effective_price(self):
        """Get effective price (variant price or product price)"""
        return self.price if self.price else self.product.price


class ProductVariantAttributeValue(models.Model):
    """
    Store attribute values for product variants
    (e.g., Color=Blue, Size=Large for a specific variant)
    """
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='attribute_values')
    attribute = models.ForeignKey(AttributeDefinition, on_delete=models.CASCADE)
    value_json = models.JSONField(help_text="Attribute value for this variant")

    class Meta:
        unique_together = ['variant', 'attribute']
        verbose_name = 'Variant Attribute Value'
        verbose_name_plural = 'Variant Attribute Values'

    def __str__(self):
        return f"{self.variant.sku} - {self.attribute.key}"


class EcommerceClient(models.Model):
    """
    Ecommerce client/customer model for customer registration and authentication
    Separate from the main User model - these are customers of the ecommerce store
    """
    # Personal Information
    first_name = models.CharField(max_length=150, help_text="Client's first name")
    last_name = models.CharField(max_length=150, help_text="Client's last name")
    email = models.EmailField(unique=True, help_text="Client's email address (used for login)")
    phone_number = models.CharField(
        max_length=20,
        unique=True,
        help_text="Client's phone number (used for login)"
    )

    # Authentication
    password = models.CharField(max_length=128, help_text="Hashed password")

    # Additional Information
    date_of_birth = models.DateField(null=True, blank=True, help_text="Client's date of birth")

    # Status and Timestamps
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this client should be treated as active"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Email/phone verification status"
    )
    last_login = models.DateTimeField(null=True, blank=True, help_text="Last login timestamp")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Ecommerce Client'
        verbose_name_plural = 'Ecommerce Clients'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['is_active', '-created_at']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    def set_password(self, raw_password):
        """Hash and set the password"""
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Verify a password against the stored hash"""
        return check_password(raw_password, self.password)

    @property
    def full_name(self):
        """Return the client's full name"""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_authenticated(self):
        """
        Always return True for authenticated clients.
        This is required by DRF's IsAuthenticated permission class.
        """
        return True

    def update_last_login(self):
        """Update the last_login timestamp"""
        from django.utils import timezone
        self.last_login = timezone.now()
        self.save(update_fields=['last_login'])


class ClientVerificationCode(models.Model):
    """Model to store email verification codes for clients"""
    email = models.EmailField(help_text="Email address to verify")
    code = models.CharField(max_length=6, help_text="6-digit verification code")
    token = models.CharField(max_length=100, unique=True, help_text="Verification token")
    is_used = models.BooleanField(default=False, help_text="Whether code has been used")
    expires_at = models.DateTimeField(help_text="Expiration time for code")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Client Verification Code'
        verbose_name_plural = 'Client Verification Codes'
        indexes = [
            models.Index(fields=['email', 'token']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.email} - {self.code}"

    def is_valid(self):
        """Check if code is still valid (not used and not expired)"""
        from django.utils import timezone
        return not self.is_used and timezone.now() < self.expires_at


class ClientAddress(models.Model):
    """
    Delivery addresses for ecommerce clients
    Clients can have multiple addresses (home, work, etc.)
    """
    client = models.ForeignKey(
        EcommerceClient,
        on_delete=models.CASCADE,
        related_name='addresses',
        help_text="Client who owns this address"
    )
    label = models.CharField(
        max_length=50,
        help_text="Address label (e.g., 'Home', 'Work', 'Office')"
    )
    address = models.TextField(help_text="Full street address")
    city = models.CharField(max_length=100, help_text="City name")
    extra_instructions = models.TextField(
        blank=True,
        help_text="Special delivery instructions for courier"
    )

    # Geographic coordinates from Google Maps
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude coordinate from Google Maps"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude coordinate from Google Maps"
    )

    # Default address flag
    is_default = models.BooleanField(
        default=False,
        help_text="Mark this as the default delivery address"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-created_at']
        verbose_name = 'Client Address'
        verbose_name_plural = 'Client Addresses'
        indexes = [
            models.Index(fields=['client', '-is_default']),
            models.Index(fields=['client', '-created_at']),
        ]

    def __str__(self):
        return f"{self.client.full_name} - {self.label} ({self.city})"

    def save(self, *args, **kwargs):
        """Override save to ensure only one default address per client"""
        if self.is_default:
            # Set all other addresses for this client to non-default
            ClientAddress.objects.filter(
                client=self.client,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class FavoriteProduct(models.Model):
    """
    Client's favorite/wishlist products
    Many-to-many relationship between clients and products
    """
    client = models.ForeignKey(
        EcommerceClient,
        on_delete=models.CASCADE,
        related_name='favorites',
        help_text="Client who favorited the product"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='favorited_by',
        help_text="Product that was favorited"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['client', 'product']
        ordering = ['-created_at']
        verbose_name = 'Favorite Product'
        verbose_name_plural = 'Favorite Products'
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['product']),
        ]

    def __str__(self):
        return f"{self.client.full_name} - {self.product.sku}"


class Cart(models.Model):
    """
    Shopping cart for ecommerce clients
    Each client has one active cart at a time
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('abandoned', 'Abandoned'),
        ('converted', 'Converted to Order'),
    ]

    client = models.ForeignKey(
        EcommerceClient,
        on_delete=models.CASCADE,
        related_name='carts',
        help_text="Client who owns this cart"
    )
    delivery_address = models.ForeignKey(
        ClientAddress,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='carts',
        help_text="Selected delivery address for this cart"
    )
    selected_card = models.ForeignKey(
        'ClientCard',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='carts',
        help_text="Selected payment card for this cart"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Cart status"
    )
    notes = models.TextField(blank=True, help_text="Special instructions or notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Shopping Cart'
        verbose_name_plural = 'Shopping Carts'
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['status', '-updated_at']),
        ]

    def __str__(self):
        return f"Cart #{self.id} - {self.client.full_name} ({self.status})"

    @property
    def total_amount(self):
        """Calculate total cart amount"""
        return sum(item.subtotal for item in self.items.all())

    @property
    def total_items(self):
        """Get total number of items in cart"""
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    """
    Individual items in a shopping cart
    """
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="Cart this item belongs to"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='cart_items',
        help_text="Product in cart"
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart_items',
        help_text="Product variant (if applicable)"
    )
    quantity = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Quantity of this product"
    )
    price_at_add = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price when added to cart (to track price changes)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
        indexes = [
            models.Index(fields=['cart', 'product']),
        ]

    def __str__(self):
        return f"{self.product.sku} x{self.quantity} in Cart #{self.cart.id}"

    @property
    def subtotal(self):
        """Calculate subtotal for this cart item"""
        return self.price_at_add * self.quantity

    def save(self, *args, **kwargs):
        """Auto-set price_at_add if not provided"""
        if not self.price_at_add:
            if self.variant and self.variant.price:
                self.price_at_add = self.variant.price
            else:
                self.price_at_add = self.product.price
        super().save(*args, **kwargs)


class Order(models.Model):
    """
    Customer orders created from cart checkout
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid'),
        ('failed', 'Payment Failed'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    ]

    order_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique order number"
    )
    client = models.ForeignKey(
        EcommerceClient,
        on_delete=models.PROTECT,
        related_name='orders',
        help_text="Client who placed the order"
    )
    delivery_address = models.ForeignKey(
        ClientAddress,
        on_delete=models.PROTECT,
        related_name='orders',
        help_text="Delivery address for this order"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Order status"
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total order amount"
    )

    # Payment fields
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        help_text="Payment status"
    )
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        default='card',
        help_text="Payment method (card, cash_on_delivery, etc.)"
    )
    bog_order_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Bank of Georgia order ID"
    )
    payment_url = models.URLField(
        blank=True,
        null=True,
        help_text="BOG payment page URL"
    )
    payment_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Payment gateway response data"
    )

    notes = models.TextField(
        blank=True,
        help_text="Customer notes or special instructions"
    )
    admin_notes = models.TextField(
        blank=True,
        help_text="Internal admin notes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True, help_text="When payment was completed")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['payment_status', '-created_at']),
            models.Index(fields=['bog_order_id']),
        ]

    def __str__(self):
        return f"Order {self.order_number} - {self.client.full_name}"

    @property
    def total_items(self):
        """Get total number of items in order"""
        return sum(item.quantity for item in self.items.all())

    @staticmethod
    def generate_order_number():
        """Generate unique order number"""
        import random
        import string
        from django.utils import timezone

        timestamp = timezone.now().strftime('%Y%m%d')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"ORD-{timestamp}-{random_str}"


class OrderItem(models.Model):
    """
    Individual items in an order
    Snapshot of product details at time of order
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="Order this item belongs to"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='order_items',
        help_text="Product ordered"
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='order_items',
        help_text="Product variant (if applicable)"
    )
    product_name = models.JSONField(
        help_text="Product name at time of order (multilingual)"
    )
    quantity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Quantity ordered"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per item at time of order"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
        indexes = [
            models.Index(fields=['order', 'product']),
        ]

    def __str__(self):
        return f"{self.product.sku} x{self.quantity} in {self.order.order_number}"

    @property
    def subtotal(self):
        """Calculate subtotal for this order item"""
        return self.price * self.quantity


class EcommerceSettings(models.Model):
    """
    Per-tenant ecommerce settings including encrypted payment gateway credentials
    Each tenant can configure their own BOG API credentials
    """
    # OneToOne with Tenant (from tenants app)
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='ecommerce_settings',
        help_text="Tenant these settings belong to"
    )

    # BOG Payment Gateway Settings
    bog_client_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Bank of Georgia Client ID"
    )
    bog_client_secret_encrypted = models.BinaryField(
        blank=True,
        null=True,
        help_text="Encrypted Bank of Georgia Client Secret"
    )
    bog_use_production = models.BooleanField(
        default=False,
        help_text="Use production BOG API (unchecked = test environment)"
    )
    bog_return_url_success = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL to redirect after successful payment (e.g., https://yourstore.com/payment/success)"
    )
    bog_return_url_fail = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL to redirect after failed payment (e.g., https://yourstore.com/payment/fail)"
    )

    # Payment settings
    enable_cash_on_delivery = models.BooleanField(
        default=True,
        help_text="Allow cash on delivery payments"
    )
    enable_card_payment = models.BooleanField(
        default=True,
        help_text="Allow card payments via BOG"
    )

    # Store information
    store_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Store name for payment descriptions"
    )
    store_email = models.EmailField(
        blank=True,
        help_text="Store contact email"
    )
    store_phone = models.CharField(
        max_length=50,
        blank=True,
        help_text="Store contact phone"
    )

    # E-commerce Frontend Deployment
    ecommerce_frontend_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="URL of the deployed e-commerce storefront"
    )
    vercel_project_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Vercel project ID for the e-commerce frontend"
    )
    deployment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('deploying', 'Deploying'),
            ('deployed', 'Deployed'),
            ('failed', 'Failed'),
        ],
        default='pending',
        help_text="Current deployment status of the e-commerce frontend"
    )
    custom_domain = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Custom domain for the e-commerce storefront (e.g., shop.example.com)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ecommerce Settings'
        verbose_name_plural = 'Ecommerce Settings'

    def __str__(self):
        return f"Ecommerce Settings for {self.tenant.name}"

    def set_bog_secret(self, secret: str):
        """Encrypt and store BOG client secret"""
        from cryptography.fernet import Fernet
        from django.conf import settings

        # Use Django's SECRET_KEY for encryption
        key = settings.SECRET_KEY[:32].encode().ljust(32, b'0')
        fernet = Fernet(base64.urlsafe_b64encode(key))
        self.bog_client_secret_encrypted = fernet.encrypt(secret.encode())

    def get_bog_secret(self) -> str:
        """Decrypt and return BOG client secret"""
        if not self.bog_client_secret_encrypted:
            return ''

        from cryptography.fernet import Fernet
        from django.conf import settings

        key = settings.SECRET_KEY[:32].encode().ljust(32, b'0')
        fernet = Fernet(base64.urlsafe_b64encode(key))
        return fernet.decrypt(bytes(self.bog_client_secret_encrypted)).decode()

    @property
    def has_bog_credentials(self) -> bool:
        """Check if BOG credentials are configured"""
        return bool(self.bog_client_id and self.bog_client_secret_encrypted)


class PasswordResetToken(models.Model):
    """
    Password reset tokens for ecommerce clients
    Tokens expire after 24 hours
    """
    client = models.ForeignKey(
        EcommerceClient,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens'
    )
    token = models.CharField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Password Reset Token'
        verbose_name_plural = 'Password Reset Tokens'
        indexes = [
            models.Index(fields=['token', 'is_used']),
            models.Index(fields=['client', '-created_at']),
        ]

    def __str__(self):
        return f"Reset token for {self.client.email} - {'Used' if self.is_used else 'Active'}"

    @staticmethod
    def generate_token():
        """Generate a secure random token"""
        import secrets
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_code():
        """Generate a 6-digit verification code"""
        import random
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])

    def is_valid(self):
        """Check if token is still valid (not used and not expired)"""
        from django.utils import timezone
        return not self.is_used and self.expires_at > timezone.now()

    def mark_as_used(self):
        """Mark token as used"""
        from django.utils import timezone
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_at'])


class ClientCard(models.Model):
    """
    Store saved payment card details for ecommerce clients
    Cards are validated with 0 GEL transactions and saved for future purchases
    """
    client = models.ForeignKey(
        EcommerceClient,
        on_delete=models.CASCADE,
        related_name='saved_cards',
        help_text='Client who owns this saved card'
    )

    # BOG order ID for recurring charges
    parent_order_id = models.CharField(
        max_length=100,
        unique=True,
        help_text='BOG parent order ID used for charging this card'
    )

    # Card details (masked/safe to store)
    card_type = models.CharField(
        max_length=20,
        blank=True,
        help_text='Card type (e.g., mc, visa)'
    )
    masked_card_number = models.CharField(
        max_length=20,
        blank=True,
        help_text='Masked card number (e.g., 531125***1450)'
    )
    card_expiry = models.CharField(
        max_length=7,
        blank=True,
        help_text='Card expiry date (MM/YY format)'
    )

    # Default card flag
    is_default = models.BooleanField(
        default=False,
        help_text='Whether this is the default payment card for this client'
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this card can be used for payments'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-created_at']
        verbose_name = 'Client Payment Card'
        verbose_name_plural = 'Client Payment Cards'
        indexes = [
            models.Index(fields=['client', 'is_active']),
            models.Index(fields=['parent_order_id']),
        ]

    def __str__(self):
        return f"{self.client.email} - {self.masked_card_number}"

    def save(self, *args, **kwargs):
        # If this card is being set as default, unset other defaults for this client
        if self.is_default:
            ClientCard.objects.filter(
                client=self.client,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class HomepageSection(models.Model):
    """
    Configurable homepage section for ecommerce storefronts.
    Tenants can create, reorder, and configure sections to customize their homepage.
    """
    SECTION_TYPE_CHOICES = [
        ('hero_banner', 'Hero Banner/Slider'),
        ('featured_products', 'Featured Products'),
        ('category_grid', 'Category Grid'),
        ('product_by_attribute', 'Products by Attribute'),
        ('statistics', 'Statistics/Achievements'),
        ('branches', 'Store Branches/Locations'),
        ('custom_content', 'Custom ItemList Content'),
    ]

    DISPLAY_MODE_CHOICES = [
        ('slider', 'Slider/Carousel'),
        ('grid', 'Grid Layout'),
        ('single', 'Single Item'),
        ('list', 'Vertical List'),
    ]

    # Basic info
    title = models.JSONField(
        help_text='Section title in different languages: {"en": "Featured Products", "ka": "რჩეული პროდუქტები"}'
    )
    subtitle = models.JSONField(
        default=dict,
        blank=True,
        help_text='Optional subtitle in different languages'
    )
    section_type = models.CharField(
        max_length=30,
        choices=SECTION_TYPE_CHOICES,
        help_text='Type of content this section displays'
    )
    position = models.IntegerField(
        default=0,
        help_text='Order position on the homepage (lower numbers appear first)'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this section is visible on the homepage'
    )

    # Data source - link to ItemList for dynamic content
    item_list = models.ForeignKey(
        'tickets.ItemList',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='homepage_sections',
        help_text='ItemList to use as data source (for banners, categories, branches, etc.)'
    )

    # For product filtering by attribute
    attribute_key = models.CharField(
        max_length=100,
        blank=True,
        help_text='Attribute key to filter products (for product_by_attribute type)'
    )
    attribute_value = models.CharField(
        max_length=255,
        blank=True,
        help_text='Attribute value to filter products'
    )

    # Display configuration
    display_mode = models.CharField(
        max_length=20,
        choices=DISPLAY_MODE_CHOICES,
        default='grid',
        help_text='How to display items in this section'
    )
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional display settings: {"columns": 3, "autoSlide": true, "slideInterval": 5000, "itemsPerView": 4}'
    )

    # Styling
    background_color = models.CharField(
        max_length=20,
        blank=True,
        help_text='Background color (e.g., "#f5f5f5", "transparent")'
    )
    background_image_url = models.URLField(
        blank=True,
        help_text='Background image URL for this section'
    )
    text_color = models.CharField(
        max_length=20,
        blank=True,
        help_text='Text color for the section'
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'created_at']
        verbose_name = 'Homepage Section'
        verbose_name_plural = 'Homepage Sections'
        indexes = [
            models.Index(fields=['position']),
            models.Index(fields=['is_active', 'position']),
        ]

    def __str__(self):
        title_str = self.title.get('en', list(self.title.values())[0]) if isinstance(self.title, dict) else str(self.title)
        return f"{title_str} ({self.get_section_type_display()})"

    def get_title(self, language='en'):
        """Get title in specified language with fallback"""
        if isinstance(self.title, dict):
            return self.title.get(language, self.title.get('en', ''))
        return str(self.title)

    def get_subtitle(self, language='en'):
        """Get subtitle in specified language with fallback"""
        if isinstance(self.subtitle, dict):
            return self.subtitle.get(language, self.subtitle.get('en', ''))
        return str(self.subtitle) if self.subtitle else ''


