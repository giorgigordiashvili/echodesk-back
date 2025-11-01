from rest_framework import serializers
from .models import (
    Language,
    ProductCategory,
    ProductType,
    AttributeDefinition,
    ProductTypeAttribute,
    Product,
    ProductImage,
    ProductAttributeValue,
    ProductVariant,
    ProductVariantAttributeValue,
    ClientAddress,
    FavoriteProduct
)


class LanguageSerializer(serializers.ModelSerializer):
    """Serializer for languages"""
    class Meta:
        model = Language
        fields = ['id', 'code', 'name', 'is_default', 'is_active', 'sort_order', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductCategorySerializer(serializers.ModelSerializer):
    """Serializer for product categories with nested subcategories"""
    subcategories = serializers.SerializerMethodField()
    parent_name = serializers.SerializerMethodField()

    class Meta:
        model = ProductCategory
        fields = [
            'id', 'name', 'description', 'slug', 'parent', 'parent_name',
            'image', 'sort_order', 'is_active', 'created_at', 'updated_at',
            'subcategories'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']

    def get_subcategories(self, obj):
        # Return only active subcategories
        subcategories = obj.subcategories.filter(is_active=True)
        return ProductCategorySerializer(subcategories, many=True, context=self.context).data

    def get_parent_name(self, obj):
        if obj.parent:
            language = self.context.get('language', 'en')
            return obj.parent.get_name(language)
        return None


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


class ProductTypeAttributeSerializer(serializers.ModelSerializer):
    """Serializer for product type attributes linking"""
    attribute = AttributeDefinitionSerializer(read_only=True)
    attribute_id = serializers.PrimaryKeyRelatedField(
        queryset=AttributeDefinition.objects.all(),
        source='attribute',
        write_only=True
    )

    class Meta:
        model = ProductTypeAttribute
        fields = [
            'id', 'product_type', 'attribute', 'attribute_id',
            'is_required', 'sort_order', 'is_active'
        ]


class ProductTypeSerializer(serializers.ModelSerializer):
    """Serializer for product types with their attributes"""
    attributes = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductType
        fields = [
            'id', 'name', 'key', 'description', 'icon',
            'sort_order', 'is_active', 'created_at', 'updated_at',
            'attributes', 'product_count'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_attributes(self, obj):
        # Get all active attributes for this product type
        type_attrs = obj.type_attributes.filter(
            is_active=True,
            attribute__is_active=True
        ).select_related('attribute').order_by('sort_order')
        return ProductTypeAttributeSerializer(type_attrs, many=True, context=self.context).data

    def get_product_count(self, obj):
        return obj.products.filter(status='active').count()


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
    product_type_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    discount_percentage = serializers.FloatField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'sku', 'slug', 'name', 'short_description',
            'product_type', 'product_type_name', 'category', 'category_name',
            'price', 'compare_at_price', 'discount_percentage',
            'image', 'quantity', 'status', 'is_featured',
            'is_low_stock', 'is_in_stock', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_product_type_name(self, obj):
        language = self.context.get('language', 'en')
        return obj.product_type.get_name(language)

    def get_category_name(self, obj):
        if obj.category:
            language = self.context.get('language', 'en')
            return obj.category.get_name(language)
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for product with all related data"""
    product_type_detail = ProductTypeSerializer(source='product_type', read_only=True)
    category_detail = ProductCategorySerializer(source='category', read_only=True)
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
            'product_type', 'product_type_detail', 'category', 'category_detail',
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
            'product_type', 'category', 'price', 'compare_at_price', 'cost_price',
            'image', 'track_inventory', 'quantity', 'low_stock_threshold',
            'status', 'is_featured', 'weight', 'dimensions',
            'meta_title', 'meta_description', 'attributes', 'images_data'
        ]
        read_only_fields = ['created_at', 'updated_at']

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
    """Serializer for client addresses"""

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
