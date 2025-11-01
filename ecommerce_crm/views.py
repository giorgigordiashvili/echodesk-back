from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter, BooleanFilter
from django.db.models import Q, F
from .models import (
    ProductCategory,
    ProductType,
    AttributeDefinition,
    Product,
    ProductImage,
    ProductVariant,
    ProductAttributeValue
)
from .serializers import (
    ProductCategorySerializer,
    ProductTypeSerializer,
    AttributeDefinitionSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCreateUpdateSerializer,
    ProductImageSerializer,
    ProductVariantSerializer
)


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

    @action(detail=True, methods=['post'])
    def add_image(self, request, pk=None):
        """Add an image to a product"""
        product = self.get_object()
        serializer = ProductImageSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(product=product)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
