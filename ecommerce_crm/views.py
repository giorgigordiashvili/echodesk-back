from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter, BooleanFilter
from django.db.models import Q, F
from .models import (
    Language,
    AttributeDefinition,
    Product,
    ProductImage,
    ProductVariant,
    ProductAttributeValue,
    EcommerceClient,
    ClientAddress,
    FavoriteProduct,
    Cart,
    CartItem,
    Order,
    OrderItem
)
from .serializers import (
    LanguageSerializer,
    AttributeDefinitionSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCreateUpdateSerializer,
    ProductImageSerializer,
    ProductVariantSerializer,
    EcommerceClientSerializer,
    ClientRegistrationSerializer,
    ClientLoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    ClientAddressSerializer,
    FavoriteProductSerializer,
    FavoriteProductCreateSerializer,
    CartSerializer,
    CartItemSerializer,
    CartItemCreateSerializer,
    OrderSerializer,
    OrderCreateSerializer
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
    in_stock = BooleanFilter(method='filter_in_stock')
    low_stock = BooleanFilter(method='filter_low_stock')

    class Meta:
        model = Product
        fields = ['status', 'is_featured']

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
    from .email_utils import send_welcome_email

    serializer = ClientRegistrationSerializer(data=request.data)

    if serializer.is_valid():
        client = serializer.save()

        # Send welcome email
        send_welcome_email(client)

        response_serializer = EcommerceClientSerializer(client)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='login_client',
    summary='Login ecommerce client',
    description='Authenticate a client using email or phone number with password. Returns JWT access and refresh tokens.',
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
    from rest_framework_simplejwt.tokens import RefreshToken

    serializer = ClientLoginSerializer(data=request.data)

    if serializer.is_valid():
        client = serializer.validated_data['client']

        # Generate JWT tokens
        refresh = RefreshToken()
        refresh['client_id'] = client.id
        refresh['email'] = client.email

        response_serializer = EcommerceClientSerializer(client)
        return Response({
            'message': 'Login successful',
            'client': response_serializer.data,
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='password_reset_request',
    summary='Request password reset',
    description='Send a password reset email to the client',
    request=PasswordResetRequestSerializer,
    responses={
        200: OpenApiResponse(description='Password reset email sent'),
        400: OpenApiResponse(description='Validation error')
    },
    tags=['Ecommerce - Client Auth']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """Request password reset for ecommerce client"""
    from .email_utils import send_password_reset_email
    from .models import PasswordResetToken
    from django.utils import timezone
    from datetime import timedelta

    serializer = PasswordResetRequestSerializer(data=request.data)

    if serializer.is_valid():
        client = serializer.context.get('client')

        # Generate reset token
        token = PasswordResetToken.generate_token()
        expires_at = timezone.now() + timedelta(hours=24)

        # Create password reset token
        reset_token = PasswordResetToken.objects.create(
            client=client,
            token=token,
            expires_at=expires_at
        )

        # Send password reset email
        send_password_reset_email(client, token)

        return Response({
            'message': 'Password reset email sent. Please check your inbox.'
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='password_reset_confirm',
    summary='Confirm password reset',
    description='Reset password using the token received via email',
    request=PasswordResetConfirmSerializer,
    responses={
        200: OpenApiResponse(description='Password reset successful'),
        400: OpenApiResponse(description='Invalid token or validation error')
    },
    tags=['Ecommerce - Client Auth']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def confirm_password_reset(request):
    """Confirm password reset with token"""
    serializer = PasswordResetConfirmSerializer(data=request.data)

    if serializer.is_valid():
        reset_token = serializer.validated_data['reset_token']
        new_password = serializer.validated_data['new_password']

        # Update client password
        client = reset_token.client
        client.set_password(new_password)
        client.save()

        # Mark token as used
        reset_token.mark_as_used()

        return Response({
            'message': 'Password has been reset successfully. You can now login with your new password.'
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='get_current_client',
    summary='Get current client profile',
    description='Retrieve the authenticated client\'s profile information',
    responses={
        200: OpenApiResponse(
            description='Client profile',
            response=EcommerceClientSerializer
        ),
        401: OpenApiResponse(description='Not authenticated')
    },
    tags=['Ecommerce - Client Auth']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def get_current_client(request):
    """Get current authenticated client profile"""
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from .models import EcommerceClient

    # Try to authenticate using JWT
    jwt_auth = JWTAuthentication()
    try:
        auth_result = jwt_auth.authenticate(request)
        if auth_result is not None:
            user, token = auth_result
            # Extract client_id from token
            client_id = token.get('client_id')
            if client_id:
                try:
                    client = EcommerceClient.objects.get(id=client_id)
                    serializer = EcommerceClientSerializer(client)
                    return Response(serializer.data, status=status.HTTP_200_OK)
                except EcommerceClient.DoesNotExist:
                    pass
    except Exception:
        pass

    return Response(
        {'error': 'Authentication credentials were not provided or are invalid.'},
        status=status.HTTP_401_UNAUTHORIZED
    )


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


class FavoriteProductViewSet(viewsets.ModelViewSet):
    """ViewSet for managing client favorite products (wishlist)"""
    queryset = FavoriteProduct.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['client', 'product']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action in ['create']:
            return FavoriteProductCreateSerializer
        return FavoriteProductSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        language = self.request.query_params.get('language', 'en')
        context['language'] = language
        return context

    @extend_schema(
        tags=['Ecommerce - Favorites'],
        summary='List favorite products',
        description='Get all favorite products with optional filtering by client or product'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Favorites'],
        summary='Get favorite details',
        description='Retrieve details of a specific favorite item'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Favorites'],
        summary='Add product to favorites',
        description='Add a product to client\'s favorites/wishlist'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Favorites'],
        summary='Remove from favorites',
        description='Remove a product from favorites/wishlist'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Favorites'],
        summary='Check if product is favorited',
        description='Check if a specific product is in client\'s favorites',
        parameters=[
            OpenApiParameter(name='client', type=int, required=True),
            OpenApiParameter(name='product', type=int, required=True),
        ]
    )
    @action(detail=False, methods=['get'])
    def is_favorited(self, request):
        """Check if a product is in client's favorites"""
        client_id = request.query_params.get('client')
        product_id = request.query_params.get('product')

        if not client_id or not product_id:
            return Response(
                {'error': 'Both client and product IDs are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_favorited = FavoriteProduct.objects.filter(
            client_id=client_id,
            product_id=product_id
        ).exists()

        return Response({'is_favorited': is_favorited})

    @extend_schema(
        tags=['Ecommerce - Favorites'],
        summary='Toggle favorite',
        description='Add or remove a product from favorites',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'client': {'type': 'integer'},
                    'product': {'type': 'integer'},
                }
            }
        }
    )
    @action(detail=False, methods=['post'])
    def toggle(self, request):
        """Toggle product in favorites (add if not exists, remove if exists)"""
        client_id = request.data.get('client')
        product_id = request.data.get('product')

        if not client_id or not product_id:
            return Response(
                {'error': 'Both client and product IDs are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        favorite, created = FavoriteProduct.objects.get_or_create(
            client_id=client_id,
            product_id=product_id
        )

        if not created:
            # Already exists, so remove it
            favorite.delete()
            return Response({
                'message': 'Removed from favorites',
                'is_favorited': False
            })
        else:
            # Newly created
            serializer = self.get_serializer(favorite)
            return Response({
                'message': 'Added to favorites',
                'is_favorited': True,
                'favorite': serializer.data
            }, status=status.HTTP_201_CREATED)


class CartViewSet(viewsets.ModelViewSet):
    """ViewSet for managing shopping carts"""
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['client', 'status']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at']

    @extend_schema(
        tags=['Ecommerce - Cart'],
        summary='List all carts',
        description='Get all shopping carts with optional filtering'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Cart'],
        summary='Get cart details',
        description='Retrieve cart with all items and totals'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Cart'],
        summary='Create new cart'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Cart'],
        summary='Update cart',
        description='Update cart details (e.g., delivery address, notes)'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Cart'],
        summary='Delete cart'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Cart'],
        summary='Get or create active cart',
        description='Get client\'s active cart or create new one',
        parameters=[OpenApiParameter(name='client', type=int, required=True)]
    )
    @action(detail=False, methods=['get'])
    def get_or_create(self, request):
        """Get or create active cart for client"""
        client_id = request.query_params.get('client')
        if not client_id:
            return Response({'error': 'Client ID required'}, status=status.HTTP_400_BAD_REQUEST)

        cart, created = Cart.objects.get_or_create(
            client_id=client_id,
            status='active',
            defaults={'status': 'active'}
        )
        serializer = self.get_serializer(cart)
        return Response({
            'cart': serializer.data,
            'created': created
        })

    @extend_schema(
        tags=['Ecommerce - Cart'],
        summary='Set delivery address',
        description='Set or update delivery address for cart'
    )
    @action(detail=True, methods=['post'])
    def set_address(self, request, pk=None):
        """Set delivery address for cart"""
        cart = self.get_object()
        address_id = request.data.get('address_id')
        
        if not address_id:
            return Response({'error': 'Address ID required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            address = ClientAddress.objects.get(id=address_id, client=cart.client)
            cart.delivery_address = address
            cart.save()
            serializer = self.get_serializer(cart)
            return Response(serializer.data)
        except ClientAddress.DoesNotExist:
            return Response({'error': 'Address not found'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        tags=['Ecommerce - Cart'],
        summary='Clear cart',
        description='Remove all items from cart'
    )
    @action(detail=True, methods=['post'])
    def clear(self, request, pk=None):
        """Clear all items from cart"""
        cart = self.get_object()
        cart.items.all().delete()
        serializer = self.get_serializer(cart)
        return Response(serializer.data)


class CartItemViewSet(viewsets.ModelViewSet):
    """ViewSet for managing cart items"""
    queryset = CartItem.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['cart', 'product']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CartItemCreateSerializer
        return CartItemSerializer

    @extend_schema(
        tags=['Ecommerce - Cart Items'],
        summary='List cart items'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Cart Items'],
        summary='Add item to cart',
        description='Add a product to shopping cart'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Cart Items'],
        summary='Update cart item',
        description='Update quantity or variant'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Cart Items'],
        summary='Remove item from cart'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing orders"""
    queryset = Order.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['order_number', 'client__first_name', 'client__last_name', 'client__email']
    filterset_fields = ['client', 'status']
    ordering_fields = ['created_at', 'total_amount', 'status']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    @extend_schema(
        tags=['Ecommerce - Orders'],
        summary='List all orders',
        description='Get all orders with filtering and search'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Orders'],
        summary='Get order details',
        description='Retrieve order with all items and client info'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Orders'],
        summary='Create order from cart',
        description='Submit cart and create order'
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        output_serializer = OrderSerializer(order)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=['Ecommerce - Orders'],
        summary='Update order',
        description='Update order status, notes, etc.'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce - Orders'],
        summary='Update order status',
        description='Change order status (pending, confirmed, shipped, etc.)'
    )
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update order status"""
        from django.utils import timezone
        order = self.get_object()
        new_status = request.data.get('status')

        if not new_status:
            return Response({'error': 'Status required'}, status=status.HTTP_400_BAD_REQUEST)

        if new_status not in dict(Order.STATUS_CHOICES):
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

        order.status = new_status

        # Update timestamps based on status
        if new_status == 'confirmed' and not order.confirmed_at:
            order.confirmed_at = timezone.now()
        elif new_status == 'shipped' and not order.shipped_at:
            order.shipped_at = timezone.now()
        elif new_status == 'delivered' and not order.delivered_at:
            order.delivered_at = timezone.now()

        order.save()
        serializer = self.get_serializer(order)
        return Response(serializer.data)
