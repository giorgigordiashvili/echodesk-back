"""
Client-facing ecommerce API endpoints

These ViewSets are designed for ecommerce clients (customers) to access their own data.
Uses EcommerceClientJWTAuthentication for client-specific access control.
"""
from rest_framework import viewsets, filters, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django_filters.rest_framework import DjangoFilterBackend
from .authentication import EcommerceClientJWTAuthentication
from .models import (
    Product,
    ClientAddress,
    FavoriteProduct,
    Cart,
    CartItem,
    Order,
)
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    FavoriteProductSerializer,
    FavoriteProductCreateSerializer,
    CartSerializer,
    CartItemSerializer,
    CartItemCreateSerializer,
    OrderSerializer,
    OrderCreateSerializer,
)


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


class ClientProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Client-facing product browsing (read-only)
    Clients can view published products only
    """
    queryset = Product.objects.filter(status='published')
    authentication_classes = [EcommerceClientJWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_featured']
    search_fields = ['sku', 'slug']
    ordering_fields = ['price', 'created_at']
    ordering = ['-created_at']

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
        tags=['Client - Products'],
        summary='List products',
        description='Browse published products'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Products'],
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
        tags=['Client - Addresses'],
        summary='List my addresses',
        description='Get all delivery addresses for authenticated client'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Addresses'],
        summary='Get address details',
        description='View details of a specific address'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Addresses'],
        summary='Create new address',
        description='Add a new delivery address (client auto-set from token)'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Addresses'],
        summary='Update address'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Addresses'],
        summary='Partially update address'
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Addresses'],
        summary='Delete address'
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Addresses'],
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
        return FavoriteProduct.objects.filter(client=self.request.user)

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
        tags=['Client - Favorites'],
        summary='List my favorites',
        description='Get all favorite products for authenticated client'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Favorites'],
        summary='Add to favorites'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Favorites'],
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
        return Cart.objects.filter(client=self.request.user)

    @extend_schema(
        tags=['Client - Cart'],
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

    @extend_schema(
        tags=['Client - Cart'],
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
        return CartItem.objects.filter(cart__client=self.request.user)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CartItemCreateSerializer
        return CartItemSerializer

    @extend_schema(
        tags=['Client - Cart Items'],
        summary='List cart items',
        description='Get items in authenticated client\'s carts'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Cart Items'],
        summary='Add item to cart'
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Cart Items'],
        summary='Update cart item quantity'
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Cart Items'],
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
        return Order.objects.filter(client=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    @extend_schema(
        tags=['Client - Orders'],
        summary='List my orders',
        description='Get all orders for authenticated client'
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Orders'],
        summary='Get order details',
        description='View detailed order information'
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Client - Orders'],
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

        # Get BOG credentials
        try:
            from .models import EcommerceSettings
            ecommerce_settings = EcommerceSettings.objects.get(tenant=request.tenant)

            if ecommerce_settings.has_bog_credentials:
                client_id = ecommerce_settings.bog_client_id
                client_secret = ecommerce_settings.get_bog_secret()
                use_production = ecommerce_settings.bog_use_production
            else:
                client_id = settings.BOG_CLIENT_ID
                client_secret = settings.BOG_CLIENT_SECRET
                use_production = not settings.BOG_API_BASE_URL.endswith('-test.bog.ge/payments/v1')
        except:
            client_id = settings.BOG_CLIENT_ID
            client_secret = settings.BOG_CLIENT_SECRET
            use_production = not settings.BOG_API_BASE_URL.endswith('-test.bog.ge/payments/v1')

        # Create BOG payment
        try:
            callback_url = f"{request.scheme}://{request.get_host()}/api/ecommerce/payment-webhook/"
            return_url_success = request.data.get('return_url_success', '')
            return_url_fail = request.data.get('return_url_fail', '')

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
            output_serializer = OrderSerializer(order)
            response_data = output_serializer.data
            response_data['payment_error'] = str(e)
            response_data['message'] = 'Order created but payment initialization failed'
            return Response(response_data, status=status.HTTP_201_CREATED)
