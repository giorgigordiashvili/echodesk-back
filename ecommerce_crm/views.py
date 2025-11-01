from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter, BooleanFilter
from django.db.models import Q, F
from .models import (
    Language,
    ProductCategory,
    ProductType,
    AttributeDefinition,
    Product,
    ProductImage,
    ProductVariant,
    ProductAttributeValue,
    EcommerceClient,
    ClientAddress
)
from .serializers import (
    LanguageSerializer,
    ProductCategorySerializer,
    ProductTypeSerializer,
    AttributeDefinitionSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCreateUpdateSerializer,
    ProductImageSerializer,
    ProductVariantSerializer,
    EcommerceClientSerializer,
    ClientRegistrationSerializer,
    ClientLoginSerializer,
    ClientAddressSerializer
)


class LanguageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing available languages
    """
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['sort_order', 'code']
    ordering = ['sort_order', 'code']

    @extend_schema(
        tags=['Ecommerce - Languages'],
        summary='List all languages'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Languages'],
        summary='Get language details'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Languages'],
        summary='Create new language'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Languages'],
        summary='Update language'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Languages'],
        summary='Partially update language'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Languages'],
        summary='Delete language'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class ProductCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for product categories
    """
    queryset = ProductCategory.objects.filter(is_active=True)
    serializer_class = ProductCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['slug']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['sort_order', 'id']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        language = self.request.query_params.get('language', 'en')
        context['language'] = language
        return context

    @extend_schema(
        tags=['Ecommerce - Categories'],
        summary='List all product categories'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Categories'],
        summary='Get category details'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Categories'],
        summary='Create new category'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Categories'],
        summary='Update category'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Categories'],
        summary='Partially update category'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Categories'],
        summary='Delete category'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Categories'],
        summary='Get category tree',
        description='Retrieve hierarchical category tree structure'
    )
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get category tree"""
        root_categories = self.queryset.filter(parent=None)
        serializer = self.get_serializer(root_categories, many=True)
        return Response(serializer.data)


class ProductTypeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for product types
    """
    queryset = ProductType.objects.filter(is_active=True)
    serializer_class = ProductTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['key']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['sort_order', 'id']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        language = self.request.query_params.get('language', 'en')
        context['language'] = language
        return context

    @extend_schema(
        tags=['Ecommerce - Product Types'],
        summary='List all product types'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Product Types'],
        summary='Get product type details'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Product Types'],
        summary='Create new product type'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Product Types'],
        summary='Update product type'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Product Types'],
        summary='Partially update product type'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Product Types'],
        summary='Delete product type'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class AttributeDefinitionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for attribute definitions
    """
    queryset = AttributeDefinition.objects.filter(is_active=True)
    serializer_class = AttributeDefinitionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['key']
    filterset_fields = ['attribute_type', 'is_variant_attribute', 'is_filterable']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['sort_order', 'id']

    @extend_schema(
        tags=['Ecommerce - Attributes'],
        summary='List all product attributes'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Attributes'],
        summary='Get attribute details'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Attributes'],
        summary='Create new attribute'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Attributes'],
        summary='Update attribute'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Attributes'],
        summary='Partially update attribute'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Attributes'],
        summary='Delete attribute'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class ProductFilter(FilterSet):
    """Custom filter for products"""
    min_price = NumberFilter(field_name='price', lookup_expr='gte')
    max_price = NumberFilter(field_name='price', lookup_expr='lte')
    search = CharFilter(method='search_filter')
    category_slug = CharFilter(field_name='category__slug')
    product_type_key = CharFilter(field_name='product_type__key')
    in_stock = BooleanFilter(method='filter_in_stock')
    low_stock = BooleanFilter(method='filter_low_stock')

    class Meta:
        model = Product
        fields = ['status', 'is_featured', 'product_type', 'category']

    def search_filter(self, queryset, name, value):
        """Search across multiple fields"""
        return queryset.filter(
            Q(sku__icontains=value) |
            Q(slug__icontains=value)
        )

    def filter_in_stock(self, queryset, name, value):
        """Filter products that are in stock"""
        if value:
            return queryset.filter(
                Q(track_inventory=False) | Q(quantity__gt=0)
            )
        return queryset.filter(track_inventory=True, quantity=0)

    def filter_low_stock(self, queryset, name, value):
        """Filter products with low stock"""
        if value:
            return queryset.filter(
                track_inventory=True,
                quantity__lte=F('low_stock_threshold'),
                quantity__gt=0
            )
        return queryset


class ProductViewSet(viewsets.ModelViewSet):
    """
    ViewSet for products with advanced filtering and sorting
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['sku', 'slug']
    ordering_fields = ['price', 'quantity', 'created_at', 'updated_at', 'sku']
    ordering = ['-created_at']

    def get_queryset(self):
        """Optimize queryset with prefetch_related"""
        queryset = Product.objects.select_related(
            'product_type',
            'category',
            'created_by',
            'updated_by'
        ).prefetch_related(
            'images',
            'attribute_values__attribute',
            'variants__attribute_values__attribute'
        )

        if self.action == 'list':
            status_filter = self.request.query_params.get('status')
            if not status_filter:
                queryset = queryset.filter(status='active')

        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return ProductListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        language = self.request.query_params.get('language', 'en')
        context['language'] = language
        return context

    @extend_schema(
        tags=['Ecommerce - Products'],
        summary='List all products',
        description='Get a list of products with advanced filtering by price, category, status, and stock levels'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Products'],
        summary='Get product details',
        description='Retrieve detailed information about a specific product including variants and attributes'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Products'],
        summary='Create new product',
        description='Create a new product with multilingual support'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Products'],
        summary='Update product',
        description='Update all fields of an existing product'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Products'],
        summary='Partially update product',
        description='Update specific fields of an existing product'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Products'],
        summary='Delete product'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Products'],
        summary='Get featured products',
        description='Retrieve all products marked as featured'
    )
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured products"""
        products = self.get_queryset().filter(is_featured=True, status='active')
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductListSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)
        serializer = ProductListSerializer(products, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @extend_schema(
        tags=['Ecommerce - Products'],
        summary='Get low stock products',
        description='Retrieve all products with stock levels at or below their low stock threshold'
    )
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get products with low stock"""
        products = self.get_queryset().filter(
            track_inventory=True,
            quantity__lte=F('low_stock_threshold'),
            quantity__gt=0
        )
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductListSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)
        serializer = ProductListSerializer(products, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @extend_schema(
        tags=['Ecommerce - Products'],
        summary='Add image to product',
        description='Upload and attach an image to a specific product'
    )
    @action(detail=True, methods=['post'])
    def add_image(self, request, pk=None):
        """Add an image to a product"""
        product = self.get_object()
        serializer = ProductImageSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(product=product)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=['Ecommerce - Products'],
        summary='Remove image from product',
        description='Delete a specific image from a product'
    )
    @action(detail=True, methods=['delete'], url_path='remove_image/(?P<image_id>[^/.]+)')
    def remove_image(self, request, pk=None, image_id=None):
        """Remove an image from a product"""
        product = self.get_object()
        try:
            image = product.images.get(id=image_id)
            image.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProductImage.DoesNotExist:
            return Response(
                {'error': 'Image not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        tags=['Ecommerce - Products'],
        summary='Update product attributes',
        description='Update all attributes for a specific product'
    )
    @action(detail=True, methods=['post'])
    def update_attributes(self, request, pk=None):
        """Update product attributes"""
        product = self.get_object()
        attributes_data = request.data.get('attributes', [])

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

        # Return updated product detail
        serializer = ProductDetailSerializer(product, context=self.get_serializer_context())
        return Response(serializer.data)


class ProductImageViewSet(viewsets.ModelViewSet):
    """ViewSet for product images"""
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['sort_order', 'id']


class ProductVariantViewSet(viewsets.ModelViewSet):
    """ViewSet for product variants"""
    queryset = ProductVariant.objects.filter(is_active=True)
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'is_active']
    search_fields = ['sku']
    ordering_fields = ['sort_order', 'price', 'quantity', 'created_at']
    ordering = ['sort_order', 'id']

    def get_queryset(self):
        return super().get_queryset().select_related('product').prefetch_related(
            'attribute_values__attribute'
        )


class EcommerceClientViewSet(viewsets.ModelViewSet):
    """ViewSet for managing ecommerce clients"""
    queryset = EcommerceClient.objects.all()
    serializer_class = EcommerceClientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'email', 'phone_number']
    filterset_fields = ['is_active', 'is_verified']
    ordering_fields = ['created_at', 'last_login', 'first_name', 'last_name']
    ordering = ['-created_at']

    @extend_schema(
        tags=['Ecommerce - Clients'],
        summary='List all ecommerce clients'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Clients'],
        summary='Get client details'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Clients'],
        summary='Update client'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Clients'],
        summary='Partially update client'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Clients'],
        summary='Delete client'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


@extend_schema(
    operation_id='register_client',
    summary='Register a new ecommerce client',
    description='Create a new ecommerce client account. Supports registration with email and phone number.',
    request=ClientRegistrationSerializer,
    responses={
        201: OpenApiResponse(
            description='Client registered successfully',
            response=EcommerceClientSerializer
        ),
        400: OpenApiResponse(description='Validation error')
    },
    tags=['Ecommerce - Client Auth']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def register_client(request):
    """Register a new ecommerce client"""
    serializer = ClientRegistrationSerializer(data=request.data)

    if serializer.is_valid():
        client = serializer.save()
        response_serializer = EcommerceClientSerializer(client)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='login_client',
    summary='Login ecommerce client',
    description='Authenticate a client using email or phone number with password. Returns client details on successful authentication.',
    request=ClientLoginSerializer,
    responses={
        200: OpenApiResponse(
            description='Login successful',
            response=EcommerceClientSerializer
        ),
        400: OpenApiResponse(description='Invalid credentials or validation error')
    },
    tags=['Ecommerce - Client Auth']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_client(request):
    """Login ecommerce client with email or phone"""
    serializer = ClientLoginSerializer(data=request.data)

    if serializer.is_valid():
        client = serializer.validated_data['client']
        response_serializer = EcommerceClientSerializer(client)
        return Response({
            'message': 'Login successful',
            'client': response_serializer.data
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClientAddressViewSet(viewsets.ModelViewSet):
    """ViewSet for managing client addresses"""
    queryset = ClientAddress.objects.all()
    serializer_class = ClientAddressSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['client', 'is_default']
    ordering_fields = ['created_at', 'is_default']
    ordering = ['-is_default', '-created_at']

    @extend_schema(
        tags=['Ecommerce - Client Addresses'],
        summary='List all client addresses',
        description='Get all delivery addresses with optional filtering by client'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Client Addresses'],
        summary='Get address details',
        description='Retrieve detailed information about a specific address'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Client Addresses'],
        summary='Create new address',
        description='Add a new delivery address for a client with Google Maps coordinates'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Client Addresses'],
        summary='Update address',
        description='Update all fields of an existing address'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Client Addresses'],
        summary='Partially update address',
        description='Update specific fields of an existing address'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Client Addresses'],
        summary='Delete address',
        description='Remove an address from a client'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Client Addresses'],
        summary='Set address as default',
        description='Mark a specific address as the default delivery address for the client'
    )
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set an address as the default for the client"""
        address = self.get_object()
        address.is_default = True
        address.save()
        serializer = self.get_serializer(address)
        return Response(serializer.data)
