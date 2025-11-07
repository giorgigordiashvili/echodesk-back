"""
Client-facing ecommerce API endpoints

These ViewSets are designed for ecommerce clients (customers) to access their own data.
Uses EcommerceClientJWTAuthentication for client-specific access control.
"""
import requests
from rest_framework import viewsets, filters, status, serializers
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django_filters.rest_framework import DjangoFilterBackend
from .authentication import EcommerceClientJWTAuthentication
from .models import (
    EcommerceClient,
    Product,
    ClientAddress,
    FavoriteProduct,
    Cart,
    CartItem,
    Order,
    ClientCard,
    EcommerceSettings,
)
from .serializers import (
    EcommerceClientSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    FavoriteProductSerializer,
    FavoriteProductCreateSerializer,
    CartSerializer,
    CartItemSerializer,
    CartItemCreateSerializer,
    OrderSerializer,
    OrderCreateSerializer,
    ClientCardSerializer,
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


class ClientProfileViewSet(viewsets.GenericViewSet):
    """
    Client profile management
    Authenticated clients can view and update their own profile
    """
    serializer_class = EcommerceClientSerializer
    authentication_classes = [EcommerceClientJWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Client - Profile'],
        summary='Get authenticated client profile',
        description='Get the profile information of the authenticated client'
    )
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get authenticated client's profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @extend_schema(
        tags=['Client - Profile'],
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


class ClientProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Client-facing product browsing (read-only)
    Clients can view active products only
    """
    queryset = Product.objects.filter(status='active')
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
        description='Browse active products'
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
        description='Set or update delivery address for authenticated client\'s active cart'
    )
    @action(detail=False, methods=['post'])
    def set_address(self, request):
        """Set delivery address for authenticated client's active cart"""
        client = request.user
        address_id = request.data.get('address_id')

        if not address_id:
            return Response({'error': 'Address ID required'}, status=status.HTTP_400_BAD_REQUEST)

        # Get or create active cart
        cart, created = Cart.objects.get_or_create(
            client=client,
            status='active',
            defaults={'status': 'active'}
        )

        try:
            address = ClientAddress.objects.get(id=address_id, client=client)
            cart.delivery_address = address
            cart.save()
            serializer = self.get_serializer(cart)
            return Response(serializer.data)
        except ClientAddress.DoesNotExist:
            return Response({'error': 'Address not found'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        tags=['Client - Cart'],
        summary='Set payment card',
        description='Set or update payment card for authenticated client\'s active cart'
    )
    @action(detail=False, methods=['post'])
    def set_card(self, request):
        """Set payment card for authenticated client's active cart"""
        client = request.user
        card_id = request.data.get('card_id')

        if not card_id:
            return Response({'error': 'Card ID required'}, status=status.HTTP_400_BAD_REQUEST)

        # Get or create active cart
        cart, created = Cart.objects.get_or_create(
            client=client,
            status='active',
            defaults={'status': 'active'}
        )

        try:
            card = ClientCard.objects.get(id=card_id, client=client, is_active=True)
            cart.selected_card = card
            cart.save()
            serializer = self.get_serializer(cart)
            return Response(serializer.data)
        except ClientCard.DoesNotExist:
            return Response({'error': 'Card not found'}, status=status.HTTP_404_NOT_FOUND)


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
        description='Submit cart and create order with automatic BOG payment URL generation or saved card charge'
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

        # Check if cart has a selected card for charging
        cart = order.cart
        if cart and cart.selected_card and cart.selected_card.is_active:
            # Use saved card to charge
            try:
                callback_url = f"https://{request.get_host()}/api/ecommerce/payment-webhook/"

                payment_result = bog_service_instance.charge_saved_card(
                    parent_order_id=cart.selected_card.parent_order_id,
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
                response_data['message'] = 'Order charged to saved card'
                return Response(response_data, status=status.HTTP_201_CREATED)

            except Exception as e:
                # If saved card charge fails, fall back to creating new payment
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Saved card charge failed for order {order.order_number}: {str(e)}')
                # Continue to create regular payment below

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
    tags=['Client - Cards'],
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
    client = request.user

    try:
        # Get ecommerce settings
        ecommerce_settings = EcommerceSettings.objects.get(tenant=request.tenant)

        # Generate unique order ID for card validation
        import uuid
        order_id = f'card_{client.id}_{uuid.uuid4().hex[:12]}'

        # Prepare BOG payment request for 0 GEL (card validation)
        bog_api_url = 'https://api.bog.ge/payments/v1/ecommerce/orders'

        # Use return URL from ecommerce settings
        callback_url = ecommerce_settings.payment_return_url or f'https://{request.tenant.schema_name}.echodesk.ge/payment/success'

        payment_data = {
            'callback_url': callback_url,
            'purchase_units': {
                'currency': 'GEL',
                'total_amount': 0.00,  # 0 GEL for card validation
                'basket': [{
                    'quantity': 1,
                    'unit_price': 0.00,
                    'product_id': 'card_validation'
                }]
            },
            'redirect_url': callback_url,
            'shop_order_id': order_id,
            'locale': 'ka',
            'save_card': True,  # Important: save card for future use
            'show_shop_order_id_on_extract': False
        }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {ecommerce_settings.get_decrypted_bog_secret_key()}'
        }

        response = requests.post(
            bog_api_url,
            json=payment_data,
            headers=headers,
            timeout=30
        )

        if response.status_code in [200, 201]:
            bog_response = response.json()

            return Response({
                'order_id': order_id,
                'payment_url': bog_response.get('redirect_url') or bog_response.get('_links', {}).get('redirect', {}).get('href'),
                'message': 'Please complete card validation'
            })
        else:
            return Response({
                'error': 'Failed to initiate card validation',
                'details': response.json()
            }, status=status.HTTP_400_BAD_REQUEST)

    except EcommerceSettings.DoesNotExist:
        return Response({
            'error': 'Payment gateway not configured'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Card validation failed for client {client.id}: {str(e)}')

        return Response({
            'error': 'Failed to initiate card validation',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['Client - Cards'],
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
    tags=['Client - Cards'],
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
    tags=['Client - Cards'],
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
