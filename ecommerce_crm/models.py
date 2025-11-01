from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.contrib.auth.hashers import make_password, check_password
from decimal import Decimal
import uuid


class ProductCategory(models.Model):
    """Product category for organization"""
    name = models.JSONField(
        help_text="Category name in different languages: {'en': 'Electronics', 'ka': 'ელექტრონიკა', 'ru': 'Электроника'}"
    )
    description = models.JSONField(
        blank=True,
        default=dict,
        help_text="Category description in different languages"
    )
    slug = models.SlugField(max_length=100, unique=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subcategories'
    )
    image = models.ImageField(upload_to='product_categories/', blank=True, null=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_categories'
    )

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Product Category'
        verbose_name_plural = 'Product Categories'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'sort_order']),
        ]

    def __str__(self):
        # Return English name or first available language
        if isinstance(self.name, dict):
            return self.name.get('en', self.name.get(list(self.name.keys())[0], 'Unnamed'))
        return str(self.name)

    def get_name(self, language='en'):
        """Get category name in specific language"""
        if isinstance(self.name, dict):
            return self.name.get(language, self.name.get('en', ''))
        return str(self.name)


class ProductType(models.Model):
    """
    Product types define different kinds of products with their own attribute sets
    (e.g., 'Electronics', 'Clothing', 'Books')
    Similar to Directus collections - each type can have its own fields/attributes
    """
    name = models.JSONField(
        help_text="Type name in different languages: {'en': 'Electronics', 'ka': 'ელექტრონიკა', 'ru': 'Электроника'}"
    )
    key = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique key for code reference (e.g., 'electronics', 'clothing')"
    )
    description = models.JSONField(
        blank=True,
        default=dict,
        help_text="Type description in different languages"
    )
    icon = models.CharField(max_length=50, blank=True, help_text="Icon name or emoji")
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Product Type'
        verbose_name_plural = 'Product Types'
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['is_active', 'sort_order']),
        ]

    def __str__(self):
        if isinstance(self.name, dict):
            return self.name.get('en', self.name.get(list(self.name.keys())[0], self.key))
        return str(self.name)

    def get_name(self, language='en'):
        """Get type name in specific language"""
        if isinstance(self.name, dict):
            return self.name.get(language, self.name.get('en', self.key))
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


class ProductTypeAttribute(models.Model):
    """
    Link product types to their specific attributes
    Defines which attributes are available for each product type
    """
    product_type = models.ForeignKey(
        ProductType,
        on_delete=models.CASCADE,
        related_name='type_attributes'
    )
    attribute = models.ForeignKey(
        AttributeDefinition,
        on_delete=models.CASCADE,
        related_name='product_types'
    )
    is_required = models.BooleanField(
        default=False,
        help_text="Override the attribute's default is_required setting for this product type"
    )
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['product_type', 'attribute']
        ordering = ['sort_order', 'id']
        verbose_name = 'Product Type Attribute'
        verbose_name_plural = 'Product Type Attributes'

    def __str__(self):
        return f"{self.product_type} - {self.attribute.key}"


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

    # Product Type (defines which attributes are available)
    product_type = models.ForeignKey(
        ProductType,
        on_delete=models.PROTECT,
        related_name='products',
        help_text="Product type determines available attributes"
    )

    # Categorization
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )

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
    image = models.ImageField(upload_to='products/', blank=True, null=True, help_text="Main product image")

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
            models.Index(fields=['category', 'status']),
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
    image = models.ImageField(upload_to='products/gallery/')
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
    image = models.ImageField(upload_to='products/variants/', blank=True, null=True)

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

    def update_last_login(self):
        """Update the last_login timestamp"""
        from django.utils import timezone
        self.last_login = timezone.now()
        self.save(update_fields=['last_login'])
