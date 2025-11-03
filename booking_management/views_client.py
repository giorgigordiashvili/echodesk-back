from rest_framework import viewsets, status, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.db.models import Q
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from .models import (
    BookingClient, Service, ServiceCategory, BookingStaff,
    Booking, RecurringBooking
)
from .serializers import (
    BookingClientSerializer, BookingClientRegistrationSerializer,
    BookingClientLoginSerializer, ServiceListSerializer,
    ServiceCategorySerializer, BookingStaffSerializer,
    BookingListSerializer, BookingDetailSerializer, BookingCreateSerializer,
    RecurringBookingSerializer, RecurringBookingCreateSerializer
)
from .authentication import BookingClientJWTAuthentication
from .permissions import IsAuthenticatedBookingClient, IsBookingOwner
from .utils import generate_available_slots, can_cancel_booking
from .payment_service import get_booking_payment_service


# ============================================================================
# PUBLIC AUTHENTICATION ENDPOINTS
# ============================================================================

@extend_schema(tags=['Booking Client - Authentication'])
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def client_register(request):
    """Register new booking client"""
    serializer = BookingClientRegistrationSerializer(data=request.data)

    if serializer.is_valid():
        client = serializer.save()

        # TODO: Send verification email
        # send_verification_email(client)

        return Response({
            'message': 'Registration successful. Please check your email to verify your account.',
            'client': BookingClientSerializer(client).data
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['Booking Client - Authentication'])
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def client_login(request):
    """Login booking client"""
    serializer = BookingClientLoginSerializer(data=request.data)

    if serializer.is_valid():
        return Response({
            'access': serializer.validated_data['access'],
            'refresh': serializer.validated_data['refresh'],
            'client': BookingClientSerializer(serializer.validated_data['client']).data
        })

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['Booking Client - Authentication'])
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def client_verify_email(request):
    """Verify client email"""
    token = request.data.get('token')

    if not token:
        return Response({'error': 'Token required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = BookingClient.objects.get(verification_token=token)

        if client.is_verified:
            return Response({'message': 'Email already verified'})

        client.is_verified = True
        client.verification_token = None
        client.save(update_fields=['is_verified', 'verification_token'])

        return Response({'message': 'Email verified successfully'})

    except BookingClient.DoesNotExist:
        return Response({'error': 'Invalid verification token'}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['Booking Client - Authentication'])
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def client_password_reset_request(request):
    """Request password reset"""
    email = request.data.get('email')

    if not email:
        return Response({'error': 'Email required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = BookingClient.objects.get(email=email)
        token = client.generate_reset_token()
        client.save(update_fields=['reset_token', 'reset_token_expires'])

        # TODO: Send reset email
        # send_password_reset_email(client, token)

        return Response({'message': 'Password reset link sent to your email'})

    except BookingClient.DoesNotExist:
        # Don't reveal if email exists
        return Response({'message': 'If email exists, reset link will be sent'})


@extend_schema(tags=['Booking Client - Authentication'])
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def client_password_reset_confirm(request):
    """Confirm password reset"""
    token = request.data.get('token')
    new_password = request.data.get('new_password')

    if not token or not new_password:
        return Response({'error': 'Token and new password required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = BookingClient.objects.get(reset_token=token)

        if not client.verify_reset_token(token):
            return Response({'error': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

        client.set_password(new_password)
        client.reset_token = None
        client.reset_token_expires = None
        client.save(update_fields=['password_hash', 'reset_token', 'reset_token_expires'])

        return Response({'message': 'Password reset successful'})

    except BookingClient.DoesNotExist:
        return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# CLIENT PROFILE
# ============================================================================

@extend_schema(tags=['Booking Client - Profile'])
@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticatedBookingClient])
def client_profile(request):
    """Get or update client profile"""
    client = request.user

    if request.method == 'GET':
        serializer = BookingClientSerializer(client)
        return Response(serializer.data)

    elif request.method == 'PATCH':
        # Allow updating only certain fields
        allowed_fields = ['first_name', 'last_name', 'phone_number']
        data = {k: v for k, v in request.data.items() if k in allowed_fields}

        serializer = BookingClientSerializer(client, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# CLIENT VIEWSETS
# ============================================================================

@extend_schema_view(
    list=extend_schema(tags=['Booking Client - Services']),
    retrieve=extend_schema(tags=['Booking Client - Services'])
)
class ClientServiceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """View service categories (public read-only)"""
    queryset = ServiceCategory.objects.filter(is_active=True)
    serializer_class = ServiceCategorySerializer
    permission_classes = [permissions.AllowAny]
    feature_required = 'booking_management'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Get language from Accept-Language header or query param
        context['language'] = self.request.query_params.get('lang', 'en')
        return context


@extend_schema_view(
    list=extend_schema(tags=['Booking Client - Services']),
    retrieve=extend_schema(tags=['Booking Client - Services']),
    slots=extend_schema(tags=['Booking Client - Services'])
)
class ClientServiceViewSet(viewsets.ReadOnlyModelViewSet):
    """View services (public read-only)"""
    queryset = Service.objects.filter(status='active')
    serializer_class = ServiceListSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ['category', 'booking_type']
    search_fields = ['name']
    feature_required = 'booking_management'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['language'] = self.request.query_params.get('lang', 'en')
        return context

    @action(detail=True, methods=['get'])
    def slots(self, request, pk=None):
        """Get available time slots for a service"""
        service = self.get_object()
        date_str = request.query_params.get('date')
        staff_id = request.query_params.get('staff_id')
        language = request.query_params.get('lang', 'en')

        if not date_str:
            return Response({'error': 'Date parameter required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        # Get staff if specified
        staff = None
        if staff_id:
            try:
                staff = BookingStaff.objects.get(id=staff_id)
            except BookingStaff.DoesNotExist:
                return Response({'error': 'Staff not found'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate available slots
        slots = generate_available_slots(service, date, staff, language)

        return Response({
            'date': date_str,
            'service': service.name if isinstance(service.name, str) else service.name.get(language, service.name.get('en', '')),
            'slots': slots
        })


@extend_schema_view(
    list=extend_schema(tags=['Booking Client - Staff']),
    retrieve=extend_schema(tags=['Booking Client - Staff'])
)
class ClientBookingStaffViewSet(viewsets.ReadOnlyModelViewSet):
    """View staff members (public read-only)"""
    queryset = BookingStaff.objects.filter(is_active_for_bookings=True)
    serializer_class = BookingStaffSerializer
    permission_classes = [permissions.AllowAny]
    feature_required = 'booking_management'


@extend_schema_view(
    list=extend_schema(tags=['Booking Client - Bookings']),
    retrieve=extend_schema(tags=['Booking Client - Bookings']),
    create=extend_schema(tags=['Booking Client - Bookings']),
    update=extend_schema(tags=['Booking Client - Bookings']),
    partial_update=extend_schema(tags=['Booking Client - Bookings']),
    cancel=extend_schema(tags=['Booking Client - Bookings'])
)
class ClientBookingViewSet(viewsets.ModelViewSet):
    """Manage client's own bookings"""
    serializer_class = BookingListSerializer
    authentication_classes = [BookingClientJWTAuthentication]
    permission_classes = [IsAuthenticatedBookingClient]
    feature_required = 'booking_management'

    def get_queryset(self):
        """Get only client's own bookings"""
        return Booking.objects.filter(client=self.request.user).order_by('-date', '-start_time')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BookingDetailSerializer
        elif self.action == 'create':
            return BookingCreateSerializer
        return BookingListSerializer

    def perform_create(self, serializer):
        """Create booking and generate payment"""
        booking = serializer.save(client=self.request.user)

        # Generate payment URL
        try:
            payment_service = get_booking_payment_service()
            callback_url = self.request.build_absolute_uri('/api/bookings/payment-webhook/')
            payment_result = payment_service.create_booking_payment(booking, callback_url)

            # Return booking with payment_url
            return booking

        except Exception as e:
            # If payment creation fails, still return booking
            # but client won't have payment_url
            import logging
            logging.error(f"Failed to create payment for booking {booking.booking_number}: {str(e)}")
            return booking

    def create(self, request, *args, **kwargs):
        """Override create to return payment info"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = self.perform_create(serializer)

        # Refresh from DB to get updated payment info
        booking.refresh_from_db()

        response_serializer = BookingDetailSerializer(booking)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel booking"""
        booking = self.get_object()

        # Check permissions
        if booking.client != request.user:
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        # Get settings
        from .models import BookingSettings
        try:
            settings = BookingSettings.objects.get(tenant=booking.service.id)  # TODO: Fix tenant reference
        except:
            # Use default settings if not found
            from .models import Tenant
            from django.db import connection
            tenant = Tenant.objects.get(schema_name=connection.schema_name)
            settings, _ = BookingSettings.objects.get_or_create(tenant=tenant)

        # Check if can cancel
        can_cancel, reason = can_cancel_booking(booking, settings)
        if not can_cancel:
            return Response({'error': reason}, status=status.HTTP_400_BAD_REQUEST)

        # Cancel booking
        cancellation_reason = request.data.get('reason', '')
        booking.cancel(cancelled_by='client', reason=cancellation_reason)

        # Initiate refund if applicable
        if booking.paid_amount > 0:
            try:
                payment_service = get_booking_payment_service()
                refund_result = payment_service.initiate_refund(booking)
            except Exception as e:
                import logging
                logging.error(f"Failed to initiate refund for {booking.booking_number}: {str(e)}")

        serializer = BookingDetailSerializer(booking)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(tags=['Booking Client - Recurring Bookings']),
    retrieve=extend_schema(tags=['Booking Client - Recurring Bookings']),
    create=extend_schema(tags=['Booking Client - Recurring Bookings']),
    update=extend_schema(tags=['Booking Client - Recurring Bookings']),
    partial_update=extend_schema(tags=['Booking Client - Recurring Bookings']),
    pause=extend_schema(tags=['Booking Client - Recurring Bookings']),
    resume=extend_schema(tags=['Booking Client - Recurring Bookings'])
)
class ClientRecurringBookingViewSet(viewsets.ModelViewSet):
    """Manage recurring bookings"""
    serializer_class = RecurringBookingSerializer
    authentication_classes = [BookingClientJWTAuthentication]
    permission_classes = [IsAuthenticatedBookingClient]
    feature_required = 'booking_management'

    def get_queryset(self):
        """Get only client's own recurring bookings"""
        return RecurringBooking.objects.filter(client=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return RecurringBookingCreateSerializer
        return RecurringBookingSerializer

    def perform_create(self, serializer):
        """Create recurring booking"""
        serializer.save(client=self.request.user)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause recurring booking"""
        recurring = self.get_object()
        recurring.status = 'paused'
        recurring.save(update_fields=['status'])
        return Response(RecurringBookingSerializer(recurring).data)

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume recurring booking"""
        recurring = self.get_object()
        recurring.status = 'active'
        recurring.save(update_fields=['status'])
        return Response(RecurringBookingSerializer(recurring).data)
