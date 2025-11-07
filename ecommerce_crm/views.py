from rest_framework import viewsets, filters, status, serializers
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter, inline_serializer
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
    OrderItem,
    EcommerceSettings
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
    OrderCreateSerializer,
    EcommerceSettingsSerializer
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
        tags=['Ecommerce Admin - Languages'],
        summary='List all languages'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Languages'],
        summary='Get language details'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Languages'],
        summary='Create new language'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Languages'],
        summary='Update language'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Languages'],
        summary='Partially update language'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Languages'],
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
        tags=['Ecommerce Admin - Attributes'],
        summary='List all product attributes'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Attributes'],
        summary='Get attribute details'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Attributes'],
        summary='Create new attribute'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Attributes'],
        summary='Update attribute'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Attributes'],
        summary='Partially update attribute'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Attributes'],
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
    ViewSet for products with advanced filtering and sorting (Admin only)
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
        tags=['Ecommerce Admin - Products'],
        summary='List all products',
        description='Get a list of products with advanced filtering by price, category, status, and stock levels'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Products'],
        summary='Get product details',
        description='Retrieve detailed information about a specific product including variants and attributes'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Products'],
        summary='Create new product',
        description='Create a new product with multilingual support'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Products'],
        summary='Update product',
        description='Update all fields of an existing product'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Products'],
        summary='Partially update product',
        description='Update specific fields of an existing product'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Products'],
        summary='Delete product'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Products'],
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
        tags=['Ecommerce Admin - Products'],
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
        tags=['Ecommerce Admin - Products'],
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
        tags=['Ecommerce Admin - Products'],
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
        tags=['Ecommerce Admin - Products'],
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
    """ViewSet for product images (Admin only)"""
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['sort_order', 'id']


class ProductVariantViewSet(viewsets.ModelViewSet):
    """ViewSet for product variants (Admin only)"""
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
    """ViewSet for managing ecommerce clients (Admin only)"""
    queryset = EcommerceClient.objects.all()
    serializer_class = EcommerceClientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'email', 'phone_number']
    filterset_fields = ['is_active', 'is_verified']
    ordering_fields = ['created_at', 'last_login', 'first_name', 'last_name']
    ordering = ['-created_at']

    @extend_schema(
        tags=['Ecommerce Admin - Clients'],
        summary='List all ecommerce clients'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Clients'],
        summary='Get client details'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Clients'],
        summary='Update client'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Clients'],
        summary='Partially update client'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Clients'],
        summary='Delete client'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


@extend_schema(
    operation_id='register_client',
    summary='Register a new ecommerce client',
    description='Create a new ecommerce client account. Returns a verification token that should be used with the verification code sent via email.',
    request=ClientRegistrationSerializer,
    responses={
        201: OpenApiResponse(
            description='Client registered successfully. Verification code sent to email.',
            response=inline_serializer(
                'ClientRegistrationResponse',
                fields={
                    'client': EcommerceClientSerializer(),
                    'verification_token': serializers.CharField(help_text='Token to use for email verification'),
                    'message': serializers.CharField(),
                }
            )
        ),
        400: OpenApiResponse(description='Validation error')
    },
    tags=['Ecommerce - Client Auth']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def register_client(request):
    """Register a new ecommerce client and send verification code"""
    import random
    import secrets
    from datetime import timedelta
    from django.utils import timezone
    from .email_utils import send_verification_code_email
    from .models import ClientVerificationCode

    serializer = ClientRegistrationSerializer(data=request.data)

    if serializer.is_valid():
        client = serializer.save()

        # Generate 6-digit verification code
        verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

        # Generate unique verification token
        verification_token = secrets.token_urlsafe(32)

        # Set expiration time (15 minutes from now)
        expires_at = timezone.now() + timedelta(minutes=15)

        # Store verification code
        ClientVerificationCode.objects.create(
            email=client.email,
            code=verification_code,
            token=verification_token,
            expires_at=expires_at
        )

        # Send verification code email
        send_verification_code_email(
            email=client.email,
            code=verification_code,
            client_name=client.first_name
        )

        response_serializer = EcommerceClientSerializer(client)
        return Response({
            'client': response_serializer.data,
            'verification_token': verification_token,
            'message': 'Registration successful. Please check your email for verification code.'
        }, status=status.HTTP_201_CREATED)

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
    operation_id='refresh_client_token',
    summary='Refresh client access token',
    description='Use refresh token to get a new access token',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'refresh': {'type': 'string', 'description': 'Refresh token'}
            },
            'required': ['refresh']
        }
    },
    responses={
        200: {
            'type': 'object',
            'properties': {
                'access': {'type': 'string', 'description': 'New access token'},
                'refresh': {'type': 'string', 'description': 'New refresh token'}
            }
        },
        401: {'description': 'Invalid or expired refresh token'}
    },
    tags=['Ecommerce - Auth']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_client_token(request):
    """Refresh client access token using refresh token"""
    from rest_framework_simplejwt.tokens import RefreshToken
    from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

    refresh_token = request.data.get('refresh')

    if not refresh_token:
        return Response({
            'error': 'Refresh token is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Validate the refresh token
        refresh = RefreshToken(refresh_token)

        # Check if it contains client_id (ecommerce client token)
        client_id = refresh.get('client_id')
        if not client_id:
            return Response({
                'error': 'Invalid token type'
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Verify client still exists and is active
        try:
            from .models import EcommerceClient
            client = EcommerceClient.objects.get(id=client_id, is_active=True)
        except EcommerceClient.DoesNotExist:
            return Response({
                'error': 'Client not found or inactive'
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Generate new tokens
        new_refresh = RefreshToken()
        new_refresh['client_id'] = client.id
        new_refresh['email'] = client.email

        return Response({
            'access': str(new_refresh.access_token),
            'refresh': str(new_refresh)
        }, status=status.HTTP_200_OK)

    except (TokenError, InvalidToken) as e:
        return Response({
            'error': 'Invalid or expired refresh token'
        }, status=status.HTTP_401_UNAUTHORIZED)


@extend_schema(
    operation_id='verify_email',
    summary='Verify email with code',
    description='Verify client email using the verification token and code sent via email. Returns JWT tokens upon successful verification.',
    request=inline_serializer(
        'EmailVerificationRequest',
        fields={
            'verification_token': serializers.CharField(help_text='Token received during registration'),
            'code': serializers.CharField(help_text='6-digit code received via email'),
        }
    ),
    responses={
        200: OpenApiResponse(
            description='Email verified successfully',
            response=inline_serializer(
                'EmailVerificationResponse',
                fields={
                    'message': serializers.CharField(),
                    'client': EcommerceClientSerializer(),
                    'access': serializers.CharField(help_text='JWT access token'),
                    'refresh': serializers.CharField(help_text='JWT refresh token'),
                }
            )
        ),
        400: OpenApiResponse(description='Invalid or expired code')
    },
    tags=['Ecommerce - Client Auth']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    """Verify client email with verification code"""
    from .models import ClientVerificationCode, EcommerceClient
    from django.utils import timezone
    from rest_framework_simplejwt.tokens import RefreshToken

    verification_token = request.data.get('verification_token')
    code = request.data.get('code')

    if not verification_token or not code:
        return Response({
            'error': 'Both verification_token and code are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Find verification code record
        verification = ClientVerificationCode.objects.get(
            token=verification_token,
            code=code
        )

        # Check if code is valid
        if not verification.is_valid():
            return Response({
                'error': 'Verification code is invalid or has expired'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Mark code as used
        verification.is_used = True
        verification.save()

        # Get the client and mark as verified
        try:
            client = EcommerceClient.objects.get(email=verification.email)
            client.is_verified = True
            client.save()

            # Generate JWT tokens
            refresh = RefreshToken()
            refresh['client_id'] = client.id
            refresh['email'] = client.email

            response_serializer = EcommerceClientSerializer(client)
            return Response({
                'message': 'Email verified successfully',
                'client': response_serializer.data,
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }, status=status.HTTP_200_OK)

        except EcommerceClient.DoesNotExist:
            return Response({
                'error': 'Client not found'
            }, status=status.HTTP_404_NOT_FOUND)

    except ClientVerificationCode.DoesNotExist:
        return Response({
            'error': 'Invalid verification token or code'
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='resend_verification_code',
    summary='Resend verification code',
    description='Resend verification code to client email. Use this if the client did not receive the initial verification email.',
    request=inline_serializer(
        'ResendVerificationCodeRequest',
        fields={
            'email': serializers.EmailField(help_text='Email address used during registration'),
        }
    ),
    responses={
        200: OpenApiResponse(
            description='Verification code resent successfully',
            response=inline_serializer(
                'ResendVerificationCodeResponse',
                fields={
                    'verification_token': serializers.CharField(help_text='New verification token to use'),
                    'message': serializers.CharField(),
                }
            )
        ),
        400: OpenApiResponse(description='Email already verified or client not found'),
        429: OpenApiResponse(description='Too many requests - please wait before requesting another code')
    },
    tags=['Ecommerce - Client Auth']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification_code(request):
    """Resend verification code to client email"""
    import random
    import secrets
    from datetime import timedelta
    from django.utils import timezone
    from .email_utils import send_verification_code_email
    from .models import ClientVerificationCode, EcommerceClient

    email = request.data.get('email')

    if not email:
        return Response({
            'error': 'Email is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Check if client exists
        client = EcommerceClient.objects.get(email=email)

        # Check if already verified
        if client.is_verified:
            return Response({
                'error': 'Email is already verified'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Rate limiting: Check if a code was sent recently (within last 1 minute)
        recent_code = ClientVerificationCode.objects.filter(
            email=email,
            created_at__gte=timezone.now() - timedelta(minutes=1)
        ).order_by('-created_at').first()

        if recent_code:
            return Response({
                'error': 'A verification code was recently sent. Please wait before requesting another one.',
                'retry_after': 60  # seconds
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Generate new 6-digit verification code
        verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

        # Generate unique verification token
        verification_token = secrets.token_urlsafe(32)

        # Set expiration time (15 minutes from now)
        expires_at = timezone.now() + timedelta(minutes=15)

        # Store verification code
        ClientVerificationCode.objects.create(
            email=client.email,
            code=verification_code,
            token=verification_token,
            expires_at=expires_at
        )

        # Send verification code email
        send_verification_code_email(
            email=client.email,
            code=verification_code,
            client_name=client.first_name
        )

        return Response({
            'verification_token': verification_token,
            'message': 'Verification code has been resent. Please check your email.'
        }, status=status.HTTP_200_OK)

    except EcommerceClient.DoesNotExist:
        return Response({
            'error': 'No account found with this email address'
        }, status=status.HTTP_404_NOT_FOUND)


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

        # Generate 6-digit verification code
        code = PasswordResetToken.generate_code()
        expires_at = timezone.now() + timedelta(hours=1)  # Code expires in 1 hour

        # Invalidate any existing unused codes for this client
        PasswordResetToken.objects.filter(
            client=client,
            is_used=False
        ).update(is_used=True)

        # Create password reset token with code
        reset_token = PasswordResetToken.objects.create(
            client=client,
            token=code,
            expires_at=expires_at
        )

        # Send password reset email with code
        send_password_reset_email(client, code)

        return Response({
            'message': 'Verification code sent to your email. Please check your inbox.'
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='password_reset_confirm',
    summary='Confirm password reset',
    description='Reset password using the 6-digit verification code received via email',
    request=PasswordResetConfirmSerializer,
    responses={
        200: OpenApiResponse(description='Password reset successful'),
        400: OpenApiResponse(description='Invalid code or validation error')
    },
    tags=['Ecommerce - Client Auth']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def confirm_password_reset(request):
    """Confirm password reset with verification code"""
    serializer = PasswordResetConfirmSerializer(data=request.data)

    if serializer.is_valid():
        reset_token = serializer.validated_data['reset_token']
        new_password = serializer.validated_data['new_password']

        # Update client password
        client = reset_token.client
        client.set_password(new_password)
        client.save()

        # Mark code as used
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
@authentication_classes([])  # Bypass global authentication
@permission_classes([AllowAny])
def get_current_client(request):
    """Get current authenticated client profile"""
    from rest_framework_simplejwt.tokens import AccessToken
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
    from .models import EcommerceClient

    # Extract token from Authorization header
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return Response(
            {'error': 'Authentication credentials were not provided.'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    token_string = auth_header.split(' ')[1]

    try:
        # Decode the JWT token
        token = AccessToken(token_string)

        # Extract client_id from token
        client_id = token.get('client_id')
        if not client_id:
            return Response(
                {'error': 'Token does not contain client_id.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get the client
        try:
            client = EcommerceClient.objects.get(id=client_id)
            serializer = EcommerceClientSerializer(client)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except EcommerceClient.DoesNotExist:
            return Response(
                {'error': 'Client not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

    except (InvalidToken, TokenError) as e:
        return Response(
            {'error': f'Invalid token: {str(e)}'},
            status=status.HTTP_401_UNAUTHORIZED
        )


class ClientAddressViewSet(viewsets.ModelViewSet):
    """ViewSet for managing client addresses (Admin only)"""
    queryset = ClientAddress.objects.all()
    serializer_class = ClientAddressSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['is_default', 'client']
    ordering_fields = ['created_at', 'is_default']
    ordering = ['-is_default', '-created_at']

    @extend_schema(
        tags=['Ecommerce Admin - Client Addresses'],
        summary='List client addresses',
        description='Get all delivery addresses (admin only)'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Client Addresses'],
        summary='Get address details',
        description='Retrieve detailed information about a specific address'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Client Addresses'],
        summary='Create new address',
        description='Add a new delivery address (admin only, client ID required)'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Client Addresses'],
        summary='Update address',
        description='Update all fields of an existing address'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Client Addresses'],
        summary='Partially update address',
        description='Update specific fields of an existing address'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Client Addresses'],
        summary='Delete address',
        description='Remove an address from a client'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Client Addresses'],
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
    """ViewSet for managing client favorite products/wishlist (Admin only)"""
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
        tags=['Ecommerce Admin - Favorites'],
        summary='List favorite products',
        description='Get all favorite products with optional filtering by client or product'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Favorites'],
        summary='Get favorite details',
        description='Retrieve details of a specific favorite item'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Favorites'],
        summary='Add product to favorites',
        description='Add a product to client\'s favorites/wishlist'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Favorites'],
        summary='Remove from favorites',
        description='Remove a product from favorites/wishlist'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Favorites'],
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
        tags=['Ecommerce Admin - Favorites'],
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
    """ViewSet for managing shopping carts (Admin only)"""
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['client', 'status']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at']

    @extend_schema(
        tags=['Ecommerce Admin - Cart'],
        summary='List all carts',
        description='Get all shopping carts with optional filtering'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Cart'],
        summary='Get cart details',
        description='Retrieve cart with all items and totals'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Cart'],
        summary='Create new cart'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Cart'],
        summary='Update cart',
        description='Update cart details (e.g., delivery address, notes)'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Cart'],
        summary='Delete cart'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Cart'],
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
        tags=['Ecommerce Admin - Cart'],
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
    """ViewSet for managing cart items (Admin only)"""
    queryset = CartItem.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['cart', 'product']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CartItemCreateSerializer
        return CartItemSerializer

    @extend_schema(
        tags=['Ecommerce Admin - Cart Items'],
        summary='List cart items'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Cart Items'],
        summary='Add item to cart',
        description='Add a product to shopping cart'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Cart Items'],
        summary='Update cart item',
        description='Update quantity or variant'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Cart Items'],
        summary='Remove item from cart'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing orders (Admin only)"""
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
        tags=['Ecommerce Admin - Orders'],
        summary='List all orders',
        description='Get all orders with filtering and search'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Orders'],
        summary='Get order details',
        description='Retrieve order with all items and client info'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Orders'],
        summary='Create order from cart',
        description='Submit cart and create order with automatic BOG payment URL generation'
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
                # User provided their own credentials - use production URLs
                client_id = ecommerce_settings.bog_client_id
                client_secret = ecommerce_settings.get_bog_secret()
                auth_url = 'https://oauth2.bog.ge/auth/realms/bog/protocol/openid-connect/token'
                api_base_url = 'https://api.bog.ge/payments/v1'
            else:
                # No credentials provided - use test environment with credentials from env
                client_id = settings.BOG_CLIENT_ID
                client_secret = settings.BOG_CLIENT_SECRET
                auth_url = 'https://oauth2.bog.ge/auth/realms/bog/protocol/openid-connect/token'
                api_base_url = 'https://api.bog.ge/payments/v1'
        except:
            # Fallback to test environment with credentials from env
            client_id = settings.BOG_CLIENT_ID
            client_secret = settings.BOG_CLIENT_SECRET
            auth_url = 'https://oauth2.bog.ge/auth/realms/bog/protocol/openid-connect/token'
            api_base_url = 'https://api.bog.ge/payments/v1'

        # Create BOG service instance with the appropriate credentials
        from tenants.bog_payment import BOGPaymentService
        bog_service_instance = BOGPaymentService()
        bog_service_instance.client_id = client_id
        bog_service_instance.client_secret = client_secret
        bog_service_instance.auth_url = auth_url
        bog_service_instance.base_url = api_base_url

        # Create BOG payment
        try:
            callback_url = f"{request.scheme}://{request.get_host()}/api/ecommerce/payment-webhook/"
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
            # User can try to initiate payment later
            output_serializer = OrderSerializer(order)
            response_data = output_serializer.data
            response_data['payment_error'] = str(e)
            response_data['message'] = 'Order created but payment initialization failed'
            return Response(response_data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=['Ecommerce Admin - Orders'],
        summary='Update order',
        description='Update order status, notes, etc.'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Orders'],
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

    @extend_schema(
        tags=['Ecommerce Admin - Orders'],
        summary='Initiate payment for order',
        description='Create BOG payment session for an order'
    )
    @action(detail=True, methods=['post'])
    def initiate_payment(self, request, pk=None):
        """
        Initiate payment for an order
        Creates a BOG payment session and returns payment URL
        """
        from tenants.bog_payment import bog_service
        import uuid

        order = self.get_object()

        # Check if order is already paid
        if order.payment_status == 'paid':
            return Response(
                {'error': 'Order is already paid'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if payment is pending
        if order.payment_url and order.payment_status == 'pending':
            return Response({
                'payment_url': order.payment_url,
                'bog_order_id': order.bog_order_id,
                'status': 'pending'
            })

        # Get tenant's ecommerce settings for BOG credentials
        try:
            from .models import EcommerceSettings
            ecommerce_settings = EcommerceSettings.objects.get(tenant=request.tenant)

            # Use tenant-specific credentials if available
            if ecommerce_settings.has_bog_credentials:
                client_id = ecommerce_settings.bog_client_id
                client_secret = ecommerce_settings.get_bog_secret()
                use_production = ecommerce_settings.bog_use_production
            else:
                # Fall back to default credentials from settings
                from django.conf import settings
                client_id = settings.BOG_CLIENT_ID
                client_secret = settings.BOG_CLIENT_SECRET
                use_production = not settings.BOG_API_BASE_URL.endswith('-test.bog.ge/payments/v1')
        except EcommerceSettings.DoesNotExist:
            # Use default credentials
            from django.conf import settings
            client_id = settings.BOG_CLIENT_ID
            client_secret = settings.BOG_CLIENT_SECRET
            use_production = not settings.BOG_API_BASE_URL.endswith('-test.bog.ge/payments/v1')

        # Check payment method
        payment_method = request.data.get('payment_method', 'card')

        if payment_method == 'cash_on_delivery':
            # No BOG payment needed, just mark as COD
            order.payment_method = 'cash_on_delivery'
            order.payment_status = 'pending'
            order.save()
            return Response({
                'payment_method': 'cash_on_delivery',
                'message': 'Order will be paid on delivery'
            })

        # Create BOG payment
        try:
            # Generate callback URL
            callback_url = f"{request.scheme}://{request.get_host()}/api/ecommerce/payment-webhook/"
            return_url_success = request.data.get('return_url_success', '')
            return_url_fail = request.data.get('return_url_fail', '')

            # Create payment with tenant-specific or default credentials
            payment_result = bog_service.create_payment(
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

            return Response({
                'payment_url': payment_result['payment_url'],
                'bog_order_id': payment_result['order_id'],
                'amount': payment_result['amount'],
                'currency': payment_result['currency'],
                'status': 'pending'
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to create payment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    operation_id='ecommerce_payment_webhook',
    summary='BOG Payment Webhook for Ecommerce Orders',
    description='Webhook endpoint for receiving payment status updates from Bank of Georgia for ecommerce orders',
    responses={
        200: OpenApiResponse(description='Webhook processed successfully'),
        400: OpenApiResponse(description='Invalid payload')
    },
    tags=['Ecommerce Admin - Orders']
)
@api_view(['POST'])
@permission_classes([AllowAny])  # Webhook from BOG, no auth
def ecommerce_payment_webhook(request):
    """
    Handle webhook notifications from Bank of Georgia payment gateway for ecommerce orders
    
    BOG Callback format:
    {
        "event": "order_payment",
        "zoned_request_time": "2024-01-01T12:00:00.000000Z",
        "body": {
            "order_id": "...",
            "order_status": {"key": "completed", ...},
            "external_order_id": "ORD-20250211-XYZ789",
            ...
        }
    }
    """
    import logging
    from django.utils import timezone
    
    logger = logging.getLogger(__name__)
    
    # Process payment event
    event_type = request.data.get('event')
    body = request.data.get('body', {})
    
    if event_type != 'order_payment':
        logger.warning(f'Unexpected webhook event type: {event_type}')
        return Response({'error': 'Unexpected event type'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Extract payment details
    bog_order_id = body.get('order_id') or body.get('id')
    external_order_id = body.get('external_order_id')  # This is our order_number
    order_status_obj = body.get('order_status', {})
    bog_status = order_status_obj.get('key', '')
    
    # Get response code from payment_detail
    payment_detail = body.get('payment_detail', {})
    response_code = payment_detail.get('code', '')
    transaction_id = payment_detail.get('transaction_id', '')
    
    logger.info(f'Ecommerce payment webhook: bog_order_id={bog_order_id}, order_number={external_order_id}, status={bog_status}, code={response_code}')
    
    # Handle successful payment (BOG status: 'completed' with response code '100')
    if bog_status == 'completed' and response_code == '100':
        try:
            # Find order by order_number (external_order_id)
            if not external_order_id:
                logger.error('Missing external_order_id in webhook payload')
                return Response({'error': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if this is a card validation transaction (order_id starts with 'card_')
            if external_order_id.startswith('card_'):
                # Extract client ID from order_id format: card_{client_id}_{random}
                try:
                    parts = external_order_id.split('_')
                    client_id = int(parts[1])

                    from .models import EcommerceClient, ClientCard
                    client = EcommerceClient.objects.get(id=client_id)

                    # Extract card details from payment_detail
                    payment_detail = body.get('payment_detail', {})
                    payer_identifier = payment_detail.get('payer_identifier', '')  # e.g., "531125***1450"
                    card_type = payment_detail.get('card_type', '')  # e.g., "mc" or "visa"
                    card_expiry = payment_detail.get('card_expiry_date', '')  # e.g., "05/27"

                    # Format card type for display
                    card_type_display = {
                        'mc': 'Mastercard',
                        'visa': 'Visa',
                        'amex': 'American Express'
                    }.get(card_type.lower(), card_type.upper())

                    # Create or update saved card
                    card, created = ClientCard.objects.update_or_create(
                        parent_order_id=bog_order_id,
                        defaults={
                            'client': client,
                            'card_type': card_type_display,
                            'masked_card_number': payer_identifier,
                            'card_expiry': card_expiry,
                            'is_active': True,
                            'is_default': not ClientCard.objects.filter(client=client, is_active=True).exists()  # First card is default
                        }
                    )

                    action = 'created' if created else 'updated'
                    logger.info(f'Card {action} for client {client_id}: {payer_identifier} ({card_type_display})')

                    return Response({
                        'status': 'success',
                        'action': f'card_{action}',
                        'card_id': card.id
                    })

                except (IndexError, ValueError, EcommerceClient.DoesNotExist) as e:
                    logger.error(f'Error processing card validation: {e}')
                    return Response({'error': 'Invalid card validation order'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                order = Order.objects.get(order_number=external_order_id)
            except Order.DoesNotExist:
                logger.error(f'Order not found: {external_order_id}')
                return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
            
            # Check if already processed (idempotency)
            if order.payment_status == 'paid' and order.paid_at:
                logger.info(f'Webhook already processed for order: {external_order_id}')
                return Response({
                    'status': 'success',
                    'message': 'Payment already processed'
                }, status=status.HTTP_200_OK)
            
            # Update order payment status
            order.payment_status = 'paid'
            order.paid_at = timezone.now()
            order.status = 'confirmed'  # Auto-confirm order when paid
            order.confirmed_at = timezone.now()
            order.payment_metadata.update({
                'bog_order_id': bog_order_id,
                'transaction_id': transaction_id,
                'response_code': response_code,
                'paid_at': timezone.now().isoformat()
            })
            order.save()
            
            logger.info(f'Payment completed for order: {external_order_id}')
            
            # TODO: Send order confirmation email to client
            # TODO: Notify admin of new paid order
            
            return Response({
                'status': 'success',
                'action': 'payment_completed',
                'order_number': order.order_number
            })
        
        except Exception as e:
            logger.error(f'Error processing webhook: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Handle failed payment (BOG status: 'rejected')
    elif bog_status == 'rejected':
        logger.warning(f'Payment failed: order_number={external_order_id}, code={response_code}')
        
        # Update order status if exists
        try:
            order = Order.objects.get(order_number=external_order_id)
            order.payment_status = 'failed'
            order.payment_metadata.update({
                'bog_status': bog_status,
                'response_code': response_code,
                'failed_at': timezone.now().isoformat()
            })
            order.save()
        except Order.DoesNotExist:
            logger.error(f'Order not found for failed payment: {external_order_id}')
    
    # Handle other statuses
    else:
        logger.info(f'Webhook received with status: {bog_status}, code: {response_code}')

    return Response({'status': 'received'})


class EcommerceSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for managing ecommerce settings including BOG payment configuration"""
    serializer_class = EcommerceSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return settings for the current tenant only"""
        return EcommerceSettings.objects.filter(tenant=self.request.tenant)

    def perform_create(self, serializer):
        """Automatically set tenant when creating settings"""
        serializer.save(tenant=self.request.tenant)

    @extend_schema(
        tags=['Ecommerce Admin - Settings'],
        summary='Get ecommerce settings',
        description='Retrieve ecommerce settings for current tenant including BOG configuration'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Settings'],
        summary='Get settings detail',
        description='Retrieve detailed ecommerce settings'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Settings'],
        summary='Create ecommerce settings',
        description='Create ecommerce settings for tenant including BOG credentials and return URLs'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Settings'],
        summary='Update ecommerce settings',
        description='Update ecommerce settings including BOG configuration'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Ecommerce Admin - Settings'],
        summary='Partial update settings',
        description='Partially update ecommerce settings'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
