from rest_framework import serializers
from .models import (
    Language,
    AttributeDefinition,
    Product,
    ProductImage,
    ProductAttributeValue,
    ProductVariant,
    ProductVariantAttributeValue,
    EcommerceClient,
    ClientAddress,
    FavoriteProduct,
    Cart,
    CartItem,
    Order,
    OrderItem
)


class LanguageSerializer(serializers.ModelSerializer):
    """Serializer for languages"""
    class Meta:
        model = Language
        fields = ['id', 'code', 'name', 'is_default', 'is_active', 'sort_order', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AttributeDefinitionSerializer(serializers.ModelSerializer):
    """Serializer for attribute definitions"""

    class Meta:
        model = AttributeDefinition
        fields = [
            'id', 'name', 'key', 'attribute_type', 'options', 'unit',
            'is_required', 'is_variant_attribute', 'is_filterable',
            'sort_order', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for product images"""

    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'sort_order', 'created_at']
        read_only_fields = ['created_at']


class ProductAttributeValueSerializer(serializers.ModelSerializer):
    """Serializer for product attribute values"""
    attribute = AttributeDefinitionSerializer(read_only=True)
    attribute_id = serializers.PrimaryKeyRelatedField(
        queryset=AttributeDefinition.objects.all(),
        source='attribute',
        write_only=True
    )
    value = serializers.SerializerMethodField()

    class Meta:
        model = ProductAttributeValue
        fields = [
            'id', 'attribute', 'attribute_id', 'value',
            'value_text', 'value_number', 'value_boolean', 'value_date', 'value_json',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_value(self, obj):
        """Get the appropriate value based on attribute type"""
        return obj.get_value()


class ProductVariantAttributeValueSerializer(serializers.ModelSerializer):
    """Serializer for product variant attribute values"""
    attribute = AttributeDefinitionSerializer(read_only=True)
    attribute_id = serializers.PrimaryKeyRelatedField(
        queryset=AttributeDefinition.objects.all(),
        source='attribute',
        write_only=True
    )

    class Meta:
        model = ProductVariantAttributeValue
        fields = ['id', 'attribute', 'attribute_id', 'value_json']


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for product variants"""
    attribute_values = ProductVariantAttributeValueSerializer(many=True, read_only=True)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'sku', 'name', 'price', 'effective_price', 'quantity',
            'image', 'is_active', 'sort_order', 'attribute_values',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for product listings"""
    discount_percentage = serializers.FloatField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'sku', 'slug', 'name', 'short_description',
            'price', 'compare_at_price', 'discount_percentage',
            'image', 'quantity', 'status', 'is_featured',
            'is_low_stock', 'is_in_stock', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for product with all related data"""
    images = ProductImageSerializer(many=True, read_only=True)
    attribute_values = ProductAttributeValueSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    discount_percentage = serializers.FloatField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'sku', 'slug', 'name', 'description', 'short_description',
            'price', 'compare_at_price', 'cost_price', 'discount_percentage',
            'image', 'images', 'track_inventory', 'quantity', 'low_stock_threshold',
            'is_low_stock', 'is_in_stock', 'status', 'is_featured',
            'weight', 'dimensions', 'meta_title', 'meta_description',
            'attribute_values', 'variants',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.email
        return None

    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return f"{obj.updated_by.first_name} {obj.updated_by.last_name}".strip() or obj.updated_by.email
        return None


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating products with attributes"""
    image = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="Image URL string")
    attributes = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of attribute values: [{'attribute_id': 1, 'value_text': 'Red'}, ...]"
    )
    images_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of additional images: [{'image': file, 'alt_text': {...}, 'sort_order': 0}, ...]"
    )

    class Meta:
        model = Product
        fields = [
            'id', 'sku', 'slug', 'name', 'description', 'short_description',
            'price', 'compare_at_price', 'cost_price',
            'image', 'track_inventory', 'quantity', 'low_stock_threshold',
            'status', 'is_featured', 'weight', 'dimensions',
            'meta_title', 'meta_description', 'attributes', 'images_data'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_sku(self, value):
        """Validate SKU length"""
        if len(value) > 100:
            raise serializers.ValidationError(
                f"SKU must be 100 characters or less. Current length: {len(value)}"
            )
        return value

    def validate_slug(self, value):
        """Validate slug length"""
        if len(value) > 200:
            raise serializers.ValidationError(
                f"Slug must be 200 characters or less. Current length: {len(value)}"
            )
        return value

    def validate_image(self, value):
        """Validate image URL length"""
        if value and len(value) > 2000:
            raise serializers.ValidationError(
                f"Image URL must be 2000 characters or less. Current length: {len(value)}. "
                f"Please use a shorter URL or filename."
            )
        return value

    def create(self, validated_data):
        # Extract nested data
        attributes_data = validated_data.pop('attributes', [])
        images_data = validated_data.pop('images_data', [])

        # Set created_by from request user
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
            validated_data['updated_by'] = request.user

        # Create product
        product = super().create(validated_data)

        # Create attribute values
        for attr_data in attributes_data:
            attribute_id = attr_data.get('attribute_id')
            if attribute_id:
                attr_value = ProductAttributeValue(
                    product=product,
                    attribute_id=attribute_id
                )
                # Set appropriate value field based on attribute type
                if 'value_text' in attr_data:
                    attr_value.value_text = attr_data['value_text']
                elif 'value_number' in attr_data:
                    attr_value.value_number = attr_data['value_number']
                elif 'value_boolean' in attr_data:
                    attr_value.value_boolean = attr_data['value_boolean']
                elif 'value_date' in attr_data:
                    attr_value.value_date = attr_data['value_date']
                elif 'value_json' in attr_data:
                    attr_value.value_json = attr_data['value_json']
                attr_value.save()

        # Create additional images
        for img_data in images_data:
            ProductImage.objects.create(
                product=product,
                **img_data
            )

        return product

    def update(self, instance, validated_data):
        # Extract nested data
        attributes_data = validated_data.pop('attributes', None)
        images_data = validated_data.pop('images_data', None)

        # Set updated_by from request user
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['updated_by'] = request.user

        # Update product
        product = super().update(instance, validated_data)

        # Update attributes if provided
        if attributes_data is not None:
            # Clear existing attributes
            product.attribute_values.all().delete()

            # Create new attribute values
            for attr_data in attributes_data:
                attribute_id = attr_data.get('attribute_id')
                if attribute_id:
                    attr_value = ProductAttributeValue(
                        product=product,
                        attribute_id=attribute_id
                    )
                    if 'value_text' in attr_data:
                        attr_value.value_text = attr_data['value_text']
                    elif 'value_number' in attr_data:
                        attr_value.value_number = attr_data['value_number']
                    elif 'value_boolean' in attr_data:
                        attr_value.value_boolean = attr_data['value_boolean']
                    elif 'value_date' in attr_data:
                        attr_value.value_date = attr_data['value_date']
                    elif 'value_json' in attr_data:
                        attr_value.value_json = attr_data['value_json']
                    attr_value.save()

        # Update images if provided
        if images_data is not None:
            # Note: This doesn't delete existing images, just adds new ones
            # You may want to implement a different strategy
            for img_data in images_data:
                ProductImage.objects.create(
                    product=product,
                    **img_data
                )

        return product


class ClientAddressSerializer(serializers.ModelSerializer):
    """Serializer for client addresses (Admin only)"""

    class Meta:
        model = ClientAddress
        fields = [
            'id', 'client', 'label', 'address', 'city',
            'extra_instructions', 'latitude', 'longitude',
            'is_default', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Ensure coordinates are both set or both unset"""
        latitude = attrs.get('latitude')
        longitude = attrs.get('longitude')

        if (latitude is not None and longitude is None) or (latitude is None and longitude is not None):
            raise serializers.ValidationError(
                "Both latitude and longitude must be provided together"
            )

        return attrs


class FavoriteProductSerializer(serializers.ModelSerializer):
    """Serializer for favorite products with nested product details"""
    product = serializers.SerializerMethodField()

    class Meta:
        model = FavoriteProduct
        fields = ['id', 'client', 'product', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_product(self, obj):
        """Return product details in the current language context"""
        from .serializers import ProductListSerializer
        language = self.context.get('language', 'en')
        return ProductListSerializer(obj.product, context={'language': language}).data


class FavoriteProductCreateSerializer(serializers.ModelSerializer):
    """Serializer for adding products to favorites"""

    class Meta:
        model = FavoriteProduct
        fields = ['id', 'client', 'product', 'created_at']
        read_only_fields = ['id', 'created_at']


class EcommerceClientSerializer(serializers.ModelSerializer):
    """Serializer for listing and viewing ecommerce clients"""
    full_name = serializers.CharField(read_only=True)
    addresses = ClientAddressSerializer(many=True, read_only=True)
    favorites = serializers.SerializerMethodField()

    class Meta:
        model = None  # Will be set dynamically
        fields = [
            'id', 'first_name', 'last_name', 'full_name', 'email',
            'phone_number', 'date_of_birth', 'is_active', 'is_verified',
            'last_login', 'created_at', 'updated_at', 'addresses', 'favorites'
        ]
        read_only_fields = ['id', 'is_verified', 'last_login', 'created_at', 'updated_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import EcommerceClient
        self.Meta.model = EcommerceClient

    def get_favorites(self, obj):
        """Return client's favorite products with product details"""
        from .serializers import FavoriteProductSerializer
        language = self.context.get('language', 'en')
        favorites = obj.favorites.all()
        return FavoriteProductSerializer(favorites, many=True, context={'language': language}).data


class ClientRegistrationSerializer(serializers.Serializer):
    """Serializer for client registration"""
    first_name = serializers.CharField(max_length=150, required=True)
    last_name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=True)
    phone_number = serializers.CharField(max_length=20, required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, required=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    def validate_email(self, value):
        """Validate that email is unique"""
        from .models import EcommerceClient
        if EcommerceClient.objects.filter(email=value).exists():
            raise serializers.ValidationError("A client with this email already exists.")
        return value

    def validate_phone_number(self, value):
        """Validate that phone number is unique"""
        from .models import EcommerceClient
        if EcommerceClient.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A client with this phone number already exists.")
        return value

    def validate(self, data):
        """Validate that passwords match"""
        if data.get('password') != data.get('password_confirm'):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return data

    def create(self, validated_data):
        """Create and return a new client"""
        from .models import EcommerceClient

        # Remove password_confirm from validated data
        validated_data.pop('password_confirm')

        # Extract password
        password = validated_data.pop('password')

        # Create client
        client = EcommerceClient(**validated_data)
        client.set_password(password)
        client.save()

        return client


class ClientLoginSerializer(serializers.Serializer):
    """Serializer for client login (supports email or phone)"""
    identifier = serializers.CharField(
        required=True,
        help_text="Email or phone number"
    )
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        """Authenticate the client"""
        from .models import EcommerceClient
        from django.db.models import Q

        identifier = data.get('identifier')
        password = data.get('password')

        # Try to find client by email or phone
        try:
            client = EcommerceClient.objects.get(
                Q(email=identifier) | Q(phone_number=identifier)
            )
        except EcommerceClient.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials.")

        # Check if client is active
        if not client.is_active:
            raise serializers.ValidationError("This account has been deactivated.")

        # Verify password
        if not client.check_password(password):
            raise serializers.ValidationError("Invalid credentials.")

        # Update last login
        client.update_last_login()

        # Add client to validated data
        data['client'] = client
        return data

class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for cart items with product details"""
    product = ProductListSerializer(read_only=True)
    variant = ProductVariantSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'cart', 'product', 'variant', 'quantity', 'price_at_add', 'subtotal', 'created_at', 'updated_at']
        read_only_fields = ['id', 'price_at_add', 'created_at', 'updated_at']


class CartSerializer(serializers.ModelSerializer):
    """Serializer for shopping cart with nested items"""
    items = CartItemSerializer(many=True, read_only=True)
    delivery_address = ClientAddressSerializer(read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'client', 'delivery_address', 'status', 'notes', 'items', 'total_amount', 'total_items', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class CartItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for adding items to cart"""
    
    class Meta:
        model = CartItem
        fields = ['id', 'cart', 'product', 'variant', 'quantity', 'price_at_add']
        read_only_fields = ['id', 'price_at_add']


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for order items"""
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'order', 'product', 'variant', 'product_name', 'quantity', 'price', 'subtotal', 'created_at']
        read_only_fields = ['id', 'created_at']


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for orders with nested items"""
    items = OrderItemSerializer(many=True, read_only=True)
    delivery_address = ClientAddressSerializer(read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    client_details = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'client', 'client_details', 'delivery_address',
            'status', 'total_amount', 'notes', 'admin_notes', 'items', 'total_items',
            # Payment fields
            'payment_status', 'payment_method', 'bog_order_id', 'payment_url',
            'payment_metadata',
            # Timestamps
            'created_at', 'updated_at', 'paid_at', 'confirmed_at', 'shipped_at', 'delivered_at'
        ]
        read_only_fields = [
            'id', 'order_number', 'created_at', 'updated_at', 'paid_at',
            'bog_order_id', 'payment_url', 'payment_metadata'
        ]

    def get_client_details(self, obj):
        """Return client basic info"""
        return {
            'id': obj.client.id,
            'full_name': obj.client.full_name,
            'email': obj.client.email,
            'phone_number': obj.client.phone_number
        }


class OrderCreateSerializer(serializers.Serializer):
    """Serializer for creating an order from cart"""
    cart_id = serializers.IntegerField(required=True)
    delivery_address_id = serializers.IntegerField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_cart_id(self, value):
        """Validate cart exists and has items"""
        try:
            cart = Cart.objects.get(id=value, status='active')
            if not cart.items.exists():
                raise serializers.ValidationError("Cart is empty")
            return value
        except Cart.DoesNotExist:
            raise serializers.ValidationError("Cart not found")

    def validate_delivery_address_id(self, value):
        """Validate delivery address exists"""
        try:
            ClientAddress.objects.get(id=value)
            return value
        except ClientAddress.DoesNotExist:
            raise serializers.ValidationError("Delivery address not found")

    def create(self, validated_data):
        """Create order from cart"""
        cart = Cart.objects.get(id=validated_data['cart_id'])
        delivery_address = ClientAddress.objects.get(id=validated_data['delivery_address_id'])

        # Generate unique order number
        order_number = Order.generate_order_number()

        # Create order
        order = Order.objects.create(
            order_number=order_number,
            client=cart.client,
            delivery_address=delivery_address,
            total_amount=cart.total_amount,
            notes=validated_data.get('notes', ''),
            status='pending'
        )

        # Create order items from cart items
        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                variant=cart_item.variant,
                product_name=cart_item.product.name,  # Snapshot of product name
                quantity=cart_item.quantity,
                price=cart_item.price_at_add
            )

        # Mark cart as converted
        cart.status = 'converted'
        cart.save()

        return order


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting password reset"""
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """Validate that email exists"""
        from .models import EcommerceClient
        try:
            client = EcommerceClient.objects.get(email=value, is_active=True)
            self.context['client'] = client
            return value
        except EcommerceClient.DoesNotExist:
            raise serializers.ValidationError("No active account found with this email address.")


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming password reset"""
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        """Validate token and passwords match"""
        from .models import PasswordResetToken

        # Validate passwords match
        if data.get('new_password') != data.get('new_password_confirm'):
            raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})

        # Validate token
        try:
            reset_token = PasswordResetToken.objects.get(token=data['token'])
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError({"token": "Invalid or expired reset token."})

        if not reset_token.is_valid():
            raise serializers.ValidationError({"token": "This reset token has expired or been used."})

        data['reset_token'] = reset_token
        return data
