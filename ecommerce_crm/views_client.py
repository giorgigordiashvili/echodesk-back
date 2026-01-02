"""
Client-facing ecommerce API endpoints

These ViewSets are designed for ecommerce clients (customers) to access their own data.
Uses EcommerceClientJWTAuthentication for client-specific access control.
"""
import requests
from rest_framework import viewsets, filters, status, serializers
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter, OpenApiExample, extend_schema_view
from drf_spectacular.openapi import AutoSchema
from django_filters.rest_framework import DjangoFilterBackend
from django.views.decorators.cache import cache_page
from .authentication import EcommerceClientJWTAuthentication
from .models import (
    EcommerceClient,
    Product,
    ProductAttributeValue,
    AttributeDefinition,
    ClientAddress,
    FavoriteProduct,
    Cart,
    CartItem,
    Order,
    ClientCard,
    EcommerceSettings,
    Language,
)
from tickets.models import ItemList, ListItem
from .serializers import (
    EcommerceClientSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    AttributeDefinitionSerializer,
    FavoriteProductSerializer,
    FavoriteProductCreateSerializer,
    CartSerializer,
    CartItemSerializer,
    CartItemCreateSerializer,
    OrderSerializer,
    OrderCreateSerializer,
    ClientCardSerializer,
    ItemListMinimalSerializer,
    ItemListDetailSerializer,
    ListItemSerializer,
    LanguageSerializer,
    HomepageSectionPublicSerializer,
)
from .models import HomepageSection


class ClientAddressSerializer(serializers.ModelSerializer):
    """Serializer for client addresses (client-facing, auto-sets client from token)"""
    client = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ClientAddress
        fields = [
            'id', 'client', 'label', 'address', 'city',
            'extra_instructions', 'latitude', 'longitude',
            'is_default', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'client', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Ensure coordinates are both set or both unset"""
        latitude = attrs.get('latitude')
        longitude = attrs.get('longitude')

        if (latitude is not None and longitude is None) or (latitude is None and longitude is not None):
            raise serializers.ValidationError(
                "Both latitude and longitude must be provided together"
            )

        return attrs


class ClientProfileViewSet(viewsets.GenericViewSet):
    """
    Client profile management
    Authenticated clients can view and update their own profile
    """
    serializer_class = EcommerceClientSerializer
    authentication_classes = [EcommerceClientJWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Ecommerce Client - Profile'],
        summary='Get authenticated client profile',
        description='Get the profile information of the authenticated client'
    )
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get authenticated client's profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @extend_schema(
        tags=['Ecommerce Client - Profile'],
        summary='Update authenticated client profile',
        description='Update the profile information of the authenticated client'
    )
    @action(detail=False, methods=['patch'])
    def update_profile(self, request):
        """Update authenticated client's profile"""
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ClientAttributeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Client-facing attribute browsing (read-only, public access)
    Returns only filterable attributes for product filtering
    """
    queryset = AttributeDefinition.objects.filter(is_active=True, is_filterable=True)
    serializer_class = AttributeDefinitionSerializer
    authentication_classes = []
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['attribute_type', 'is_variant_attribute']
    ordering_fields = ['sort_order', 'key']
    ordering = ['sort_order', 'id']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        language = self.request.query_params.get('language', 'en')
        context['language'] = language
        return context

    @extend_schema(
        tags=['Ecommerce Client - Attributes'],
        summary='List filterable attributes',
        description='Get all filterable attributes for product filtering'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Attributes'],
        summary='Get attribute details',
        description='View detailed attribute information including options'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Attributes'],
        summary='Get faceted search data',
        description='''Get attribute filter options with product counts.
        Returns available filter values and their product counts for each attribute.
        Supports existing filter selections to show refined counts.'''
    )
    @action(detail=False, methods=['get'])
    def facets(self, request):
        """
        Get faceted search data for all filterable attributes
        Returns option values with product counts
        """
        from django.db.models import Count, Q, Min, Max

        # Get query parameters for existing filters
        existing_filters = {}
        for key, value in request.GET.items():
            if key.startswith('attr_'):
                attr_key = key[5:]  # Remove 'attr_' prefix
                existing_filters[attr_key] = value.split(',')  # Support multiple values

        # Base product queryset (only active products)
        products_qs = Product.objects.filter(status='active')

        # Apply existing filters to narrow down products
        for attr_key, values in existing_filters.items():
            try:
                attribute = AttributeDefinition.objects.get(key=attr_key, is_filterable=True)
                q_filter = Q()
                for value in values:
                    if attribute.attribute_type == 'select':
                        q_filter |= Q(
                            attribute_values__attribute=attribute,
                            attribute_values__value_text=value
                        )
                    elif attribute.attribute_type == 'multiselect':
                        q_filter |= Q(
                            attribute_values__attribute=attribute,
                            attribute_values__value_json__contains=value
                        )
                    elif attribute.attribute_type == 'boolean':
                        q_filter |= Q(
                            attribute_values__attribute=attribute,
                            attribute_values__value_boolean=(value.lower() == 'true')
                        )
                    elif attribute.attribute_type == 'number':
                        # Support range: min-max format
                        if '-' in value:
                            min_val, max_val = value.split('-')
                            q_filter |= Q(
                                attribute_values__attribute=attribute,
                                attribute_values__value_number__gte=float(min_val),
                                attribute_values__value_number__lte=float(max_val)
                            )
                products_qs = products_qs.filter(q_filter).distinct()
            except AttributeDefinition.DoesNotExist:
                continue

        # Get all filterable attributes
        attributes = AttributeDefinition.objects.filter(is_active=True, is_filterable=True).order_by('sort_order')

        facet_data = []
        language = request.query_params.get('language', 'en')

        for attribute in attributes:
            facet = {
                'attribute_key': attribute.key,
                'attribute_name': attribute.get_name(language),
                'attribute_type': attribute.attribute_type,
                'options': []
            }

            if attribute.attribute_type in ['select', 'multiselect']:
                # For select types, count products per option value
                for option in attribute.options:
                    value = option.get('value', '')
                    label = option.get(language, option.get('en', value))

                    # Count products with this option value
                    count = products_qs.filter(
                        attribute_values__attribute=attribute,
                        attribute_values__value_text=value
                    ).distinct().count()

                    if count > 0:  # Only include options that have products
                        facet['options'].append({
                            'value': value,
                            'label': label,
                            'count': count
                        })

            elif attribute.attribute_type == 'number':
                # For number types, return min and max range
                value_range = products_qs.filter(
                    attribute_values__attribute=attribute
                ).aggregate(
                    min_value=Min('attribute_values__value_number'),
                    max_value=Max('attribute_values__value_number')
                )

                if value_range['min_value'] is not None:
                    facet['range'] = {
                        'min': float(value_range['min_value']),
                        'max': float(value_range['max_value']),
                        'unit': attribute.unit
                    }

            elif attribute.attribute_type == 'boolean':
                # For boolean types, count true/false
                true_count = products_qs.filter(
                    attribute_values__attribute=attribute,
                    attribute_values__value_boolean=True
                ).distinct().count()

                false_count = products_qs.filter(
                    attribute_values__attribute=attribute,
                    attribute_values__value_boolean=False
                ).distinct().count()

                if true_count > 0 or false_count > 0:
                    facet['options'] = [
                        {'value': 'true', 'label': 'Yes', 'count': true_count},
                        {'value': 'false', 'label': 'No', 'count': false_count}
                    ]

            # Only include facets that have data
            if facet.get('options') or facet.get('range'):
                facet_data.append(facet)

        return Response({
            'facets': facet_data,
            'total_products': products_qs.distinct().count()
        })


class ClientProductAutoSchema(AutoSchema):
    """Custom schema for ClientProductViewSet that dynamically generates attribute filter parameters"""

    def get_override_parameters(self):
        """Add dynamic attribute filter parameters to the schema"""
        import logging
        from django.db import connection
        from tenant_schemas.utils import schema_context, get_public_schema_name
        from tenants.models import Tenant

        logger = logging.getLogger(__name__)
        parameters = super().get_override_parameters()

        # Only add dynamic parameters for the list action
        if self.method.lower() != 'get' or self.path.endswith('{id}/'):
            return parameters

        # Collect unique attributes from all tenants
        all_attributes = {}

        try:
            # Get all active tenants
            with schema_context(get_public_schema_name()):
                tenants = Tenant.objects.all()

            # Query attributes from each tenant schema
            for tenant in tenants:
                try:
                    with schema_context(tenant.schema_name):
                        # Use 'name' field (JSONField) instead of 'label'
                        attrs = AttributeDefinition.objects.filter(is_filterable=True).values('key', 'name', 'attribute_type')

                        for attr in attrs:
                            attr_key = attr['key']
                            # Store unique attributes by key (avoid duplicates across tenants)
                            if attr_key not in all_attributes:
                                # Extract label from JSONField 'name' (multilingual)
                                attr_name = attr['name']
                                if isinstance(attr_name, dict):
                                    # Try to get English name, fallback to first available or key
                                    attr_label = attr_name.get('en', next(iter(attr_name.values()), attr_key.title()))
                                else:
                                    attr_label = attr_key.title()

                                all_attributes[attr_key] = {
                                    'key': attr_key,
                                    'label': attr_label,
                                    'type': attr['attribute_type']
                                }
                except Exception as e:
                    # Log the error but continue with other tenants
                    logger.warning(f"Error querying attributes for tenant {tenant.schema_name}: {e}")
                    continue

            # Generate parameters for all unique attributes
            for attr_key, attr_data in all_attributes.items():
                attr_label = attr_data['label']
                attr_type = attr_data['type']

                # Create description based on attribute type
                if attr_type == 'select':
                    description = f'Filter by {attr_label}. Supports multiple values separated by comma (OR logic). Example: ?attr_{attr_key}=value1,value2'
                elif attr_type == 'multiselect':
                    description = f'Filter by {attr_label}. Supports multiple values separated by comma. Example: ?attr_{attr_key}=value1,value2'
                elif attr_type == 'boolean':
                    description = f'Filter by {attr_label}. Use true or false. Example: ?attr_{attr_key}=true'
                elif attr_type == 'number':
                    description = f'Filter by {attr_label}. Supports ranges with hyphen (min-max) or exact values. Example: ?attr_{attr_key}=10-20'
                elif attr_type == 'text':
                    description = f'Filter by {attr_label}. Supports partial text matching. Example: ?attr_{attr_key}=search_term'
                else:
                    description = f'Filter by {attr_label}. Example: ?attr_{attr_key}=value'

                parameters.append(
                    OpenApiParameter(
                        name=f'attr_{attr_key}',
                        type=str,
                        location=OpenApiParameter.QUERY,
                        description=description,
                        required=False,
                    )
                )

            logger.info(f"Generated {len(all_attributes)} dynamic attribute parameters for OpenAPI schema")

        except Exception as e:
            # Log the error for debugging
            logger.error(f"Failed to generate dynamic attribute parameters: {e}")
            pass

        return parameters


class ClientProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Client-facing product browsing (read-only, public access)
    Anyone can view active products without authentication
    """
    queryset = Product.objects.filter(status='active').select_related(
        'created_by',
        'updated_by'
    ).prefetch_related(
        'images',
        'attribute_values__attribute',
        'variants__attribute_values__attribute'
    )
    authentication_classes = []
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_featured']
    search_fields = ['sku', 'slug']
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['-created_at']
    schema = ClientProductAutoSchema()

    def get_queryset(self):
        """
        Filter products by attributes using query params like: ?attr_color=red,blue&attr_size=large
        Also supports price range: ?min_price=10&max_price=100
        And on_sale filter: ?on_sale=true
        """
        from django.db.models import Q, F

        queryset = super().get_queryset()

        # Price range filtering
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        # On sale filter - products where compare_at_price > price
        on_sale = self.request.query_params.get('on_sale')
        if on_sale and on_sale.lower() == 'true':
            queryset = queryset.filter(
                compare_at_price__isnull=False,
                compare_at_price__gt=F('price')
            )

        # Attribute-based filtering
        for key, value in self.request.GET.items():
            if key.startswith('attr_'):
                attr_key = key[5:]  # Remove 'attr_' prefix
                values = value.split(',')  # Support multiple values (OR logic)

                try:
                    attribute = AttributeDefinition.objects.get(key=attr_key, is_filterable=True)
                    q_filter = Q()

                    for val in values:
                        if attribute.attribute_type == 'select':
                            q_filter |= Q(
                                attribute_values__attribute=attribute,
                                attribute_values__value_text=val
                            )
                        elif attribute.attribute_type == 'multiselect':
                            q_filter |= Q(
                                attribute_values__attribute=attribute,
                                attribute_values__value_json__contains=val
                            )
                        elif attribute.attribute_type == 'boolean':
                            q_filter |= Q(
                                attribute_values__attribute=attribute,
                                attribute_values__value_boolean=(val.lower() == 'true')
                            )
                        elif attribute.attribute_type == 'number':
                            # Support range: min-max format
                            if '-' in val:
                                min_val, max_val = val.split('-')
                                q_filter |= Q(
                                    attribute_values__attribute=attribute,
                                    attribute_values__value_number__gte=float(min_val),
                                    attribute_values__value_number__lte=float(max_val)
                                )
                            else:
                                q_filter |= Q(
                                    attribute_values__attribute=attribute,
                                    attribute_values__value_number=float(val)
                                )
                        elif attribute.attribute_type == 'text':
                            q_filter |= Q(
                                attribute_values__attribute=attribute,
                                attribute_values__value_text__icontains=val
                            )

                    if q_filter:
                        queryset = queryset.filter(q_filter).distinct()

                except AttributeDefinition.DoesNotExist:
                    continue

        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        language = self.request.query_params.get('language', 'en')
        context['language'] = language
        return context

    @extend_schema(
        tags=['Ecommerce Client - Products'],
        summary='List products',
        description='''Browse active products with filtering options.

        **Dynamic Attribute Filters:**
        Filter by any product attribute using the pattern `attr_{attribute_key}`.
        The available attribute filters are dynamically generated based on your attribute definitions.

        Examples:
        - `?attr_color=red` - Single value
        - `?attr_color=red,blue,green` - Multiple values (OR logic)
        - `?attr_size=large&attr_color=red` - Multiple attributes (AND logic)
        - `?attr_width=10-20` - Number ranges
        - `?attr_waterproof=true` - Boolean values

        **Ordering Options:**
        - `?ordering=price` - Sort by price ascending
        - `?ordering=-price` - Sort by price descending
        - `?ordering=created_at` - Sort by creation date ascending (oldest first)
        - `?ordering=-created_at` - Sort by creation date descending (newest first)
        - `?ordering=name` - Sort by name ascending
        - `?ordering=-name` - Sort by name descending

        **Pagination:**
        - `?page=2` - Get specific page
        - `?page_size=50` - Items per page (default: 20, max: 100)

        **Other Filters:**
        - Basic: `?is_featured=true`
        - On Sale: `?on_sale=true`
        - Search: `?search=laptop`
        - Price: `?min_price=100&max_price=500`
        - Language: `?language=ka`''',
        parameters=[
            OpenApiParameter(
                name='min_price',
                type=float,
                location=OpenApiParameter.QUERY,
                description='Minimum price filter',
                required=False,
                examples=[
                    OpenApiExample('Example', value=10.00)
                ]
            ),
            OpenApiParameter(
                name='max_price',
                type=float,
                location=OpenApiParameter.QUERY,
                description='Maximum price filter',
                required=False,
                examples=[
                    OpenApiExample('Example', value=500.00)
                ]
            ),
            OpenApiParameter(
                name='on_sale',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='Filter to show only products on sale (compare_at_price > price)',
                required=False,
                examples=[
                    OpenApiExample('On Sale Only', value=True),
                ]
            ),
            OpenApiParameter(
                name='ordering',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Sort products by field. Available options: price, -price, created_at, -created_at, name, -name. Prefix with - for descending order.',
                required=False,
                examples=[
                    OpenApiExample('Price Low to High', value='price'),
                    OpenApiExample('Price High to Low', value='-price'),
                    OpenApiExample('Newest First', value='-created_at'),
                    OpenApiExample('Oldest First', value='created_at'),
                    OpenApiExample('Name A-Z', value='name'),
                    OpenApiExample('Name Z-A', value='-name'),
                ]
            ),
            OpenApiParameter(
                name='language',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Language code for multilingual content (e.g., en, ka, ru)',
                required=False,
                examples=[
                    OpenApiExample('English', value='en'),
                    OpenApiExample('Georgian', value='ka'),
                ]
            ),
            OpenApiParameter(
                name='page',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Page number for pagination',
                required=False,
                examples=[
                    OpenApiExample('First page', value=1),
                    OpenApiExample('Second page', value=2),
                ]
            ),
            OpenApiParameter(
                name='page_size',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Number of items per page (default: 20, max: 100)',
                required=False,
                examples=[
                    OpenApiExample('Default (20)', value=20),
                    OpenApiExample('50 items', value=50),
                    OpenApiExample('Maximum (100)', value=100),
                ]
            ),
            # Dynamic attribute parameters are added via ClientProductAutoSchema
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Products'],
        summary='Get product details',
        description='View detailed product information'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class ClientAddressViewSet(viewsets.ModelViewSet):
    """
    Client-facing address management
    Clients can only access their own addresses
    """
    serializer_class = ClientAddressSerializer
    authentication_classes = [EcommerceClientJWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['is_default']
    ordering_fields = ['created_at', 'is_default']
    ordering = ['-is_default', '-created_at']

    def get_queryset(self):
        """Return only addresses belonging to the authenticated client"""
        return ClientAddress.objects.filter(client=self.request.user)

    def perform_create(self, serializer):
        """Automatically set client from authenticated user"""
        serializer.save(client=self.request.user)

    @extend_schema(
        tags=['Ecommerce Client - Addresses'],
        summary='List my addresses',
        description='Get all delivery addresses for authenticated client'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Addresses'],
        summary='Get address details',
        description='View details of a specific address'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Addresses'],
        summary='Create new address',
        description='Add a new delivery address (client auto-set from token)'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Addresses'],
        summary='Update address'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Addresses'],
        summary='Partially update address'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Addresses'],
        summary='Delete address'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Addresses'],
        summary='Set address as default'
    )
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set an address as the default for the client"""
        address = self.get_object()
        address.is_default = True
        address.save()
        serializer = self.get_serializer(address)
        return Response(serializer.data)


class ClientFavoriteViewSet(viewsets.ModelViewSet):
    """
    Client-facing favorites/wishlist management
    Clients can only access their own favorites
    """
    authentication_classes = [EcommerceClientJWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """Return only favorites belonging to the authenticated client"""
        return FavoriteProduct.objects.filter(client=self.request.user).select_related('product', 'client')

    def get_serializer_class(self):
        if self.action == 'create':
            return FavoriteProductCreateSerializer
        return FavoriteProductSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        language = self.request.query_params.get('language', 'en')
        context['language'] = language
        return context

    def perform_create(self, serializer):
        """Automatically set client from authenticated user"""
        serializer.save(client=self.request.user)

    @extend_schema(
        tags=['Ecommerce Client - Favorites'],
        summary='List my favorites',
        description='Get all favorite products for authenticated client'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Favorites'],
        summary='Add to favorites'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Favorites'],
        summary='Remove from favorites'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class ClientCartViewSet(viewsets.ModelViewSet):
    """
    Client-facing shopping cart management
    Clients can only access their own carts
    """
    serializer_class = CartSerializer
    authentication_classes = [EcommerceClientJWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at']

    def get_queryset(self):
        """Return only carts belonging to the authenticated client"""
        return Cart.objects.filter(client=self.request.user).select_related('client').prefetch_related('items', 'items__product')

    @extend_schema(
        tags=['Ecommerce Client - Cart'],
        summary='Get or create active cart',
        description='Get authenticated client\'s active cart or create new one'
    )
    @action(detail=False, methods=['get'])
    def get_or_create(self, request):
        """Get or create active cart for authenticated client"""
        client = request.user

        cart, created = Cart.objects.get_or_create(
            client=client,
            status='active',
            defaults={'status': 'active'}
        )
        serializer = self.get_serializer(cart)
        return Response({
            'cart': serializer.data,
            'created': created
        })


class ClientCartItemViewSet(viewsets.ModelViewSet):
    """
    Client-facing cart item management
    Clients can only access items in their own carts
    """
    authentication_classes = [EcommerceClientJWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['cart', 'product']

    def get_queryset(self):
        """Return only cart items belonging to the authenticated client's carts"""
        return CartItem.objects.filter(cart__client=self.request.user).select_related('cart', 'product', 'cart__client')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CartItemCreateSerializer
        return CartItemSerializer

    @extend_schema(
        tags=['Ecommerce Client - Cart Items'],
        summary='List cart items',
        description='Get items in authenticated client\'s carts'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Cart Items'],
        summary='Add item to cart'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Cart Items'],
        summary='Update cart item quantity'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Cart Items'],
        summary='Remove item from cart'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class ClientOrderViewSet(viewsets.ModelViewSet):
    """
    Client-facing order management
    Clients can only access their own orders
    """
    authentication_classes = [EcommerceClientJWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['created_at', 'total_amount']
    ordering = ['-created_at']

    def get_queryset(self):
        """Return only orders belonging to the authenticated client"""
        return Order.objects.filter(client=self.request.user).select_related('client').prefetch_related('items', 'items__product')

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    @extend_schema(
        tags=['Ecommerce Client - Orders'],
        summary='List my orders',
        description='Get all orders for authenticated client'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Orders'],
        summary='Get order details',
        description='View detailed order information'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Orders'],
        summary='Create order from cart',
        description='''Submit cart and create order.
        - If card_id is provided: Charges the saved card directly
        - If card_id is null/not provided: Returns a BOG payment URL for new payment
        - If payment_method is "cash_on_delivery": Creates order without payment processing'''
    )
    def create(self, request, *args, **kwargs):
        from tenants.bog_payment import bog_service
        from django.conf import settings

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Automatically generate payment URL
        payment_method = request.data.get('payment_method', 'card')

        if payment_method == 'cash_on_delivery':
            # No BOG payment needed, just mark as COD
            order.payment_method = 'cash_on_delivery'
            order.payment_status = 'pending'
            order.save()

            output_serializer = OrderSerializer(order)
            response_data = output_serializer.data
            response_data['payment_method'] = 'cash_on_delivery'
            response_data['message'] = 'Order will be paid on delivery'
            return Response(response_data, status=status.HTTP_201_CREATED)

        # Get BOG credentials and configure service
        try:
            from .models import EcommerceSettings
            from tenants.bog_payment import BOGPaymentService

            ecommerce_settings = EcommerceSettings.objects.get(tenant=request.tenant)

            if ecommerce_settings.has_bog_credentials:
                # Tenant provided their own credentials
                client_id = ecommerce_settings.bog_client_id
                client_secret = ecommerce_settings.get_bog_secret()
                auth_url = settings.BOG_AUTH_URL
                api_base_url = settings.BOG_API_BASE_URL
            else:
                # Use credentials from environment variables
                client_id = settings.BOG_CLIENT_ID
                client_secret = settings.BOG_CLIENT_SECRET
                auth_url = settings.BOG_AUTH_URL
                api_base_url = settings.BOG_API_BASE_URL
        except:
            # Fallback to environment variables
            client_id = settings.BOG_CLIENT_ID
            client_secret = settings.BOG_CLIENT_SECRET
            auth_url = settings.BOG_AUTH_URL
            api_base_url = settings.BOG_API_BASE_URL

        # Create BOG service instance with the appropriate credentials
        from tenants.bog_payment import BOGPaymentService
        bog_service_instance = BOGPaymentService()
        bog_service_instance.client_id = client_id
        bog_service_instance.client_secret = client_secret
        bog_service_instance.auth_url = auth_url
        bog_service_instance.base_url = api_base_url

        # Check if a card_id was provided in the request for charging
        card_id = request.data.get('card_id')
        if card_id:
            # Use provided saved card to charge
            try:
                card = ClientCard.objects.get(id=card_id, client=request.user, is_active=True)
                callback_url = f"https://{request.get_host()}/api/ecommerce/payment-webhook/"

                payment_result = bog_service_instance.charge_saved_card(
                    parent_order_id=card.parent_order_id,
                    amount=float(order.total_amount),
                    currency='GEL',
                    callback_url=callback_url,
                    external_order_id=order.order_number
                )

                # Update order with payment info
                order.bog_order_id = payment_result['order_id']
                order.payment_status = 'processing'
                order.payment_method = 'saved_card'
                order.payment_metadata = payment_result
                order.save()

                # Return order data with payment info
                output_serializer = OrderSerializer(order)
                response_data = output_serializer.data
                response_data['payment_method'] = 'saved_card'
                response_data['bog_order_id'] = payment_result['order_id']

                # Check if user authentication is required (3D Secure)
                if payment_result.get('requires_authentication'):
                    response_data['payment_url'] = payment_result['payment_url']
                    response_data['message'] = 'Please complete payment authentication'
                else:
                    response_data['message'] = 'Order charged to saved card'

                return Response(response_data, status=status.HTTP_201_CREATED)

            except ClientCard.DoesNotExist:
                # Card not found, return error
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Card {card_id} not found for order {order.order_number}')
                return Response({
                    'error': 'Card not found or inactive'
                }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                # If saved card charge fails, return error instead of falling back
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Saved card charge failed for order {order.order_number}: {str(e)}')
                return Response({
                    'error': 'Failed to charge saved card',
                    'details': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)

        # Create BOG payment (new payment or fallback from failed saved card charge)
        try:
            callback_url = f"https://{request.get_host()}/api/ecommerce/payment-webhook/"

            # Use return URLs from EcommerceSettings if configured, otherwise from request
            try:
                ecommerce_settings = EcommerceSettings.objects.get(tenant=request.tenant)
                return_url_success = ecommerce_settings.bog_return_url_success or request.data.get('return_url_success', '')
                return_url_fail = ecommerce_settings.bog_return_url_fail or request.data.get('return_url_fail', '')
            except EcommerceSettings.DoesNotExist:
                return_url_success = request.data.get('return_url_success', '')
                return_url_fail = request.data.get('return_url_fail', '')

            payment_result = bog_service_instance.create_payment(
                amount=float(order.total_amount),
                currency='GEL',
                description=f"Order {order.order_number}",
                customer_email=order.client.email,
                customer_name=order.client.full_name,
                customer_phone=order.client.phone_number or '',
                return_url_success=return_url_success,
                return_url_fail=return_url_fail,
                callback_url=callback_url,
                external_order_id=order.order_number,
                metadata={
                    'order_id': order.id,
                    'order_number': order.order_number,
                    'tenant_id': request.tenant.id
                }
            )

            # Update order with payment info
            order.bog_order_id = payment_result['order_id']
            order.payment_url = payment_result['payment_url']
            order.payment_status = 'pending'
            order.payment_method = 'card'
            order.payment_metadata = payment_result
            order.save()

            # Return order data with payment info
            output_serializer = OrderSerializer(order)
            response_data = output_serializer.data
            response_data['payment_url'] = payment_result['payment_url']
            response_data['bog_order_id'] = payment_result['order_id']
            response_data['payment_amount'] = payment_result['amount']
            response_data['payment_currency'] = payment_result['currency']
            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            # If payment creation fails, return order without payment URL
            import logging
            import requests
            logger = logging.getLogger(__name__)

            # Try to get server's public IP for debugging
            try:
                server_ip = requests.get('https://api.ipify.org', timeout=5).text
                logger.error(f'BOG payment failed. Server IP: {server_ip}. Error: {str(e)}')
            except:
                logger.error(f'BOG payment failed. Error: {str(e)}')

            output_serializer = OrderSerializer(order)
            response_data = output_serializer.data
            response_data['payment_error'] = str(e)
            response_data['message'] = 'Order created but payment initialization failed'
            return Response(response_data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Ecommerce Client - Cards'],
    summary='Add new payment card',
    description='Initiate 0 GEL card validation payment to save a new card for future orders'
)
@api_view(['POST'])
@authentication_classes([EcommerceClientJWTAuthentication])
@permission_classes([IsAuthenticated])
def add_client_card(request):
    """
    Initiate 0 GEL payment to validate and save a new card for the client
    """
    from django.conf import settings
    from tenants.bog_payment import BOGPaymentService
    import uuid
    import logging

    logger = logging.getLogger(__name__)
    client = request.user

    try:
        # Try to get ecommerce settings
        try:
            ecommerce_settings = EcommerceSettings.objects.get(tenant=request.tenant)
            logger.info(f'Ecommerce settings found for tenant {request.tenant.schema_name}')
        except EcommerceSettings.DoesNotExist:
            ecommerce_settings = None
            logger.info(f'No ecommerce settings for tenant {request.tenant.schema_name}, will use environment credentials')

        # Configure BOG service with tenant or environment credentials
        bog_service = BOGPaymentService()

        if ecommerce_settings and ecommerce_settings.has_bog_credentials:
            # Use tenant's own BOG credentials
            logger.info(f'Using tenant BOG credentials for {request.tenant.schema_name}')
            bog_service.client_id = ecommerce_settings.bog_client_id
            bog_service.client_secret = ecommerce_settings.get_bog_secret()
            bog_service.auth_url = settings.BOG_AUTH_URL
            bog_service.base_url = settings.BOG_API_BASE_URL
        else:
            # Use credentials from environment variables
            logger.info(f'Using environment BOG credentials for {request.tenant.schema_name}')
            bog_service.client_id = settings.BOG_CLIENT_ID
            bog_service.client_secret = settings.BOG_CLIENT_SECRET
            bog_service.auth_url = settings.BOG_AUTH_URL
            bog_service.base_url = settings.BOG_API_BASE_URL

        if not bog_service.is_configured():
            logger.error(f'BOG service not configured properly. client_id: {bool(bog_service.client_id)}, client_secret: {bool(bog_service.client_secret)}')
            return Response({
                'error': 'Payment gateway not configured - missing BOG credentials'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Generate unique order ID for card validation
        order_id = f'card_{client.id}_{uuid.uuid4().hex[:12]}'

        # Get callback and return URLs
        callback_url = f"https://{request.get_host()}/api/ecommerce/payment-webhook/"
        return_url = ecommerce_settings.bog_return_url_success if (ecommerce_settings and ecommerce_settings.bog_return_url_success) else f'https://{request.tenant.schema_name}.echodesk.ge/payment/success'

        # Create 0 GEL payment for card validation
        try:
            # Get OAuth token first
            access_token = bog_service._get_access_token()

            # Prepare payment data for recurring payment (NOT subscription)
            payment_data = {
                'callback_url': callback_url,
                'purchase_units': {
                    'currency': 'GEL',
                    'total_amount': 0.01,  # Minimum 0.01 GEL for card validation (BOG requirement)
                    'basket': [{
                        'quantity': 1,
                        'unit_price': 0.01,
                        'product_id': 'card_validation',
                        'description': 'Card validation'
                    }]
                },
                'redirect_urls': {
                    'success': return_url,
                    'fail': return_url
                },
                'external_order_id': order_id,
                'payment_method': ['card'],
                'industry': 'ecommerce',
                'capture': 'automatic'
            }

            # Make API request with Bearer token
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {access_token}',
                'Accept-Language': 'en'
            }

            response = requests.post(
                f'{bog_service.base_url}/ecommerce/orders',
                json=payment_data,
                headers=headers,
                timeout=30
            )

            if response.status_code in [200, 201]:
                bog_response = response.json()
                bog_order_id = bog_response['id']
                payment_url = bog_response['_links']['redirect']['href']

                # Enable card saving for this order
                enable_result = bog_service.enable_card_saving(bog_order_id)
                if not enable_result:
                    logger.warning(f'Failed to enable card saving for order {bog_order_id}')

                logger.info(f'Card validation initiated for client {client.id}: {order_id}, bog_order_id: {bog_order_id}, card_saving_enabled: {enable_result}')

                return Response({
                    'order_id': order_id,
                    'payment_url': payment_url,
                    'message': 'Please complete card validation'
                }, status=status.HTTP_200_OK)
            else:
                error_details = response.text
                logger.error(f'BOG API error for card validation: {response.status_code} - {error_details}')
                return Response({
                    'error': 'Failed to initiate card validation',
                    'details': error_details
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f'Card validation request failed for client {client.id}: {str(e)}')
            return Response({
                'error': 'Failed to initiate card validation',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.error(f'Unexpected error in add_client_card for client {client.id}: {str(e)}')
        return Response({
            'error': 'An unexpected error occurred',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['Ecommerce Client - Cards'],
    summary='List saved payment cards',
    description='Get all saved payment cards for the authenticated client'
)
@api_view(['GET'])
@authentication_classes([EcommerceClientJWTAuthentication])
@permission_classes([IsAuthenticated])
def list_client_cards(request):
    """
    List all saved payment cards for the authenticated client
    """
    client = request.user

    cards = ClientCard.objects.filter(client=client, is_active=True)
    serializer = ClientCardSerializer(cards, many=True)

    return Response(serializer.data)


@extend_schema(
    tags=['Ecommerce Client - Cards'],
    summary='Delete payment card',
    description='Soft-delete a saved payment card'
)
@api_view(['DELETE'])
@authentication_classes([EcommerceClientJWTAuthentication])
@permission_classes([IsAuthenticated])
def delete_client_card(request, card_id):
    """
    Delete a saved payment card
    """
    client = request.user

    try:
        card = ClientCard.objects.get(id=card_id, client=client)
        card.is_active = False
        card.save()

        return Response({
            'message': 'Card deleted successfully'
        }, status=status.HTTP_200_OK)

    except ClientCard.DoesNotExist:
        return Response({
            'error': 'Card not found'
        }, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    tags=['Ecommerce Client - Cards'],
    summary='Set default payment card',
    description='Set a card as the default payment method for the authenticated client'
)
@api_view(['POST'])
@authentication_classes([EcommerceClientJWTAuthentication])
@permission_classes([IsAuthenticated])
def set_default_client_card(request, card_id):
    """
    Set a card as the default payment method
    """
    client = request.user

    try:
        card = ClientCard.objects.get(id=card_id, client=client, is_active=True)

        # Set this card as default (the model's save method handles unsetting others)
        card.is_default = True
        card.save()

        return Response({
            'message': 'Default card updated successfully'
        }, status=status.HTTP_200_OK)

    except ClientCard.DoesNotExist:
        return Response({
            'error': 'Card not found'
        }, status=status.HTTP_404_NOT_FOUND)



class ClientItemListViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Ecommerce clients can access public item lists
    These are the same item lists used in tickets, but filtered to show only public ones
    No authentication required - public access
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'created_at']
    ordering = ['title']

    def get_queryset(self):
        """Return only public and active item lists with their items"""
        return ItemList.objects.filter(
            is_public=True,
            is_active=True
        ).prefetch_related('items', 'items__children')

    def get_serializer_class(self):
        """Use detailed serializer for retrieve, minimal for list"""
        if self.action == 'retrieve':
            return ItemListDetailSerializer
        return ItemListMinimalSerializer

    @extend_schema(
        tags=['Ecommerce Client - Item Lists'],
        summary='List public item lists',
        description='Get all public item lists that are marked as accessible to clients'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Item Lists'],
        summary='Get item list with all items',
        description='Get detailed item list including all items in the list (hierarchical structure)'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Client - Item Lists'],
        summary='Get specific item from item list',
        description='Get a specific item by its ID from within an item list',
        responses={200: ListItemSerializer}
    )
    @action(detail=True, methods=['get'], url_path='items/(?P<item_id>[^/.]+)')
    def get_item(self, request, pk=None, item_id=None):
        """
        Get a specific item from an item list
        GET /api/ecommerce/client/item-lists/{id}/items/{item_id}/
        """
        # Get the item list first (ensures it's public and active)
        item_list = self.get_object()

        # Try to get the specific item
        try:
            item = ListItem.objects.get(
                id=item_id,
                item_list=item_list,
                is_active=True
            )
            serializer = ListItemSerializer(item)
            return Response(serializer.data)
        except ListItem.DoesNotExist:
            return Response(
                {'error': 'Item not found in this list'},
                status=status.HTTP_404_NOT_FOUND
            )


@extend_schema_view(
    list=extend_schema(
        tags=['Ecommerce Client - Languages'],
        summary='List available languages',
        description='Get all active languages available for the storefront'
    ),
    retrieve=extend_schema(
        tags=['Ecommerce Client - Languages'],
        summary='Get language details',
        description='Get details of a specific language'
    )
)
class ClientLanguageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Client-facing language endpoint for storefronts.
    Returns active languages that can be used for UI localization.
    No authentication required - public access.
    """
    serializer_class = LanguageSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['sort_order', 'code', 'name']
    ordering = ['sort_order']

    def get_queryset(self):
        """Return only active languages ordered by sort_order"""
        return Language.objects.filter(is_active=True).order_by('sort_order')


@extend_schema(
    tags=['Ecommerce Client - Homepage'],
    summary='Get homepage configuration',
    description='''Get the complete homepage configuration with resolved section data.
    Returns all active sections ordered by position, with data from linked ItemLists resolved.
    This endpoint is public and does not require authentication.''',
    responses={200: HomepageSectionPublicSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 10)  # Cache for 10 minutes
def get_homepage_config(request):
    """
    Get the homepage configuration for the storefront.
    Returns all active sections with their resolved data from ItemLists.

    GET /api/ecommerce/client/homepage/
    """
    from django.db.models import Prefetch
    from tickets.models import ListItem

    sections = HomepageSection.objects.filter(
        is_active=True
    ).select_related('item_list').prefetch_related(
        Prefetch(
            'item_list__items',
            queryset=ListItem.objects.filter(
                is_active=True,
                parent__isnull=True
            ).prefetch_related('children').order_by('position'),
            to_attr='prefetched_root_items'
        )
    ).order_by('position')

    serializer = HomepageSectionPublicSerializer(sections, many=True)

    return Response({
        'sections': serializer.data
    })


@extend_schema(
    operation_id='get_store_theme',
    summary='Get store theme configuration',
    description='Get the theme configuration (colors, border radius) for the storefront. This endpoint is public and does not require authentication.',
    responses={
        200: OpenApiResponse(
            description='Theme configuration',
            examples=[
                OpenApiExample(
                    'Theme Response',
                    value={
                        'preset': 'default',
                        'colors': {
                            'primary': '221 83% 53%',
                            'secondary': '215 16% 47%',
                            'accent': '221 83% 53%',
                            'background': '0 0% 100%',
                            'foreground': '0 0% 9%',
                            'muted': '0 0% 96%',
                            'muted_foreground': '0 0% 45%',
                            'destructive': '0 84.2% 60.2%',
                            'border': '0 0% 90%',
                            'card': '0 0% 100%',
                            'card_foreground': '0 0% 9%',
                        },
                        'radius': '0.5rem',
                        'store_name': 'My Store',
                    }
                )
            ]
        ),
        404: OpenApiResponse(description='Settings not found')
    },
    tags=['Store']
)
@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def get_store_theme(request):
    """
    Get the theme configuration for the storefront.
    Returns theme colors, border radius, and preset information.

    GET /api/ecommerce/client/theme/
    """
    try:
        settings = EcommerceSettings.objects.first()
        if not settings:
            # Return defaults if no settings exist
            return Response({
                'preset': 'default',
                'colors': {
                    'primary': '221 83% 53%',
                    'secondary': '215 16% 47%',
                    'accent': '221 83% 53%',
                    'background': '0 0% 100%',
                    'foreground': '0 0% 9%',
                    'muted': '0 0% 96%',
                    'muted_foreground': '0 0% 45%',
                    'destructive': '0 84.2% 60.2%',
                    'border': '0 0% 90%',
                    'card': '0 0% 100%',
                    'card_foreground': '0 0% 9%',
                },
                'radius': '0.5rem',
                'store_name': '',
            })

        return Response({
            'preset': settings.theme_preset,
            'colors': {
                'primary': settings.theme_primary_color,
                'secondary': settings.theme_secondary_color,
                'accent': settings.theme_accent_color,
                'background': settings.theme_background_color,
                'foreground': settings.theme_foreground_color,
                'muted': settings.theme_muted_color,
                'muted_foreground': settings.theme_muted_foreground_color,
                'destructive': settings.theme_destructive_color,
                'border': settings.theme_border_color,
                'card': settings.theme_card_color,
                'card_foreground': settings.theme_card_foreground_color,
            },
            'radius': settings.theme_border_radius,
            'store_name': settings.store_name,
        })
    except Exception as e:
        return Response(
            {'error': f'Failed to fetch theme: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

