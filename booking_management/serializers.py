from rest_framework import serializers
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from .models import (
    BookingClient, ServiceCategory, Service, BookingStaff,
    StaffAvailability, StaffException, Booking, RecurringBooking,
    BookingSettings
)
from users.models import User


# ============================================================================
# BOOKING CLIENT SERIALIZERS
# ============================================================================

class BookingClientSerializer(serializers.ModelSerializer):
    """Serializer for BookingClient (read)"""
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = BookingClient
        fields = ['id', 'email', 'phone_number', 'first_name', 'last_name', 'full_name', 'is_verified', 'created_at']
        read_only_fields = ['id', 'is_verified', 'created_at']


class BookingClientRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for client registration"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = BookingClient
        fields = ['email', 'phone_number', 'first_name', 'last_name', 'password', 'password_confirm']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')

        client = BookingClient.objects.create(**validated_data)
        client.set_password(password)
        client.generate_verification_token()
        client.save()

        return client


class BookingClientLoginSerializer(serializers.Serializer):
    """Serializer for client login"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        try:
            client = BookingClient.objects.get(email=email)
        except BookingClient.DoesNotExist:
            raise serializers.ValidationError('Invalid email or password')

        if not client.check_password(password):
            raise serializers.ValidationError('Invalid email or password')

        if not client.is_verified:
            raise serializers.ValidationError('Email not verified. Please check your email.')

        # Update last login
        client.last_login = timezone.now()
        client.save(update_fields=['last_login'])

        # Generate JWT token with booking_client_id claim
        refresh = RefreshToken()
        refresh['booking_client_id'] = client.id
        refresh['email'] = client.email

        attrs['client'] = client
        attrs['access'] = str(refresh.access_token)
        attrs['refresh'] = str(refresh)

        return attrs


# ============================================================================
# SERVICE CATEGORY SERIALIZERS
# ============================================================================

class ServiceCategorySerializer(serializers.ModelSerializer):
    """Serializer for ServiceCategory"""
    name_display = serializers.SerializerMethodField()
    description_display = serializers.SerializerMethodField()

    class Meta:
        model = ServiceCategory
        fields = ['id', 'name', 'description', 'icon', 'display_order', 'is_active', 'name_display', 'description_display']
        read_only_fields = ['id']

    def get_name_display(self, obj):
        """Get name in requested language"""
        language = self.context.get('language', 'en')
        if isinstance(obj.name, dict):
            return obj.name.get(language, obj.name.get('en', ''))
        return obj.name

    def get_description_display(self, obj):
        """Get description in requested language"""
        language = self.context.get('language', 'en')
        if isinstance(obj.description, dict):
            return obj.description.get(language, obj.description.get('en', ''))
        return obj.description if obj.description else ''


# ============================================================================
# STAFF SERIALIZERS
# ============================================================================

class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal User serializer for staff display"""
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = fields


class BookingStaffSerializer(serializers.ModelSerializer):
    """Serializer for BookingStaff (read)"""
    user = UserMinimalSerializer(read_only=True)

    class Meta:
        model = BookingStaff
        fields = ['id', 'user', 'bio', 'profile_image', 'average_rating', 'total_ratings', 'is_active_for_bookings']
        read_only_fields = ['id', 'average_rating', 'total_ratings']


class BookingStaffCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating BookingStaff"""
    user_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = BookingStaff
        fields = ['user_id', 'bio', 'profile_image', 'is_active_for_bookings']

    def validate_user_id(self, value):
        """Validate that user exists and is in a booking_staff enabled group"""
        try:
            user = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

        # Check if user is in a group with is_booking_staff=True
        if not user.tenant_groups.filter(is_booking_staff=True).exists():
            raise serializers.ValidationError("User must be in a group enabled for booking staff")

        # Check if user is already a booking staff
        if hasattr(user, 'booking_staff'):
            raise serializers.ValidationError("User is already assigned as booking staff")

        return value

    def create(self, validated_data):
        user_id = validated_data.pop('user_id')
        user = User.objects.get(id=user_id)
        return BookingStaff.objects.create(user=user, **validated_data)


class StaffAvailabilitySerializer(serializers.ModelSerializer):
    """Serializer for StaffAvailability"""
    day_name = serializers.SerializerMethodField()

    class Meta:
        model = StaffAvailability
        fields = ['id', 'staff', 'day_of_week', 'day_name', 'start_time', 'end_time', 'is_available', 'break_start', 'break_end']
        read_only_fields = ['id']

    def get_day_name(self, obj):
        return obj.get_day_of_week_display()


class StaffExceptionSerializer(serializers.ModelSerializer):
    """Serializer for StaffException"""
    class Meta:
        model = StaffException
        fields = ['id', 'staff', 'date', 'start_time', 'end_time', 'is_available', 'reason']
        read_only_fields = ['id']


# ============================================================================
# SERVICE SERIALIZERS
# ============================================================================

class ServiceListSerializer(serializers.ModelSerializer):
    """Serializer for Service list view"""
    category = ServiceCategorySerializer(read_only=True)
    staff_members = BookingStaffSerializer(many=True, read_only=True)
    name_display = serializers.SerializerMethodField()
    description_display = serializers.SerializerMethodField()
    deposit_amount = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = [
            'id', 'name', 'description', 'category', 'base_price', 'deposit_percentage',
            'duration_minutes', 'buffer_time_minutes', 'booking_type', 'available_time_slots',
            'staff_members', 'status', 'image', 'name_display', 'description_display', 'deposit_amount'
        ]
        read_only_fields = ['id']

    def get_name_display(self, obj):
        language = self.context.get('language', 'en')
        if isinstance(obj.name, dict):
            return obj.name.get(language, obj.name.get('en', ''))
        return obj.name

    def get_description_display(self, obj):
        language = self.context.get('language', 'en')
        if isinstance(obj.description, dict):
            return obj.description.get(language, obj.description.get('en', ''))
        return obj.description if obj.description else ''

    def get_deposit_amount(self, obj):
        return float(obj.calculate_deposit_amount())


class ServiceDetailSerializer(ServiceListSerializer):
    """Detailed service serializer including staff members"""
    staff_members = BookingStaffSerializer(many=True, read_only=True)

    class Meta(ServiceListSerializer.Meta):
        fields = ServiceListSerializer.Meta.fields + ['staff_members']


class ServiceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating Service"""
    category_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    staff_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)

    class Meta:
        model = Service
        fields = [
            'name', 'description', 'category_id', 'base_price', 'deposit_percentage',
            'duration_minutes', 'buffer_time_minutes', 'booking_type', 'available_time_slots',
            'staff_ids', 'status', 'image'
        ]

    def create(self, validated_data):
        category_id = validated_data.pop('category_id', None)
        staff_ids = validated_data.pop('staff_ids', [])

        if category_id:
            validated_data['category_id'] = category_id

        service = Service.objects.create(**validated_data)

        if staff_ids:
            staff_members = BookingStaff.objects.filter(id__in=staff_ids)
            service.staff_members.set(staff_members)

        return service

    def update(self, instance, validated_data):
        category_id = validated_data.pop('category_id', None)
        staff_ids = validated_data.pop('staff_ids', None)

        if category_id is not None:
            instance.category_id = category_id

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if staff_ids is not None:
            staff_members = BookingStaff.objects.filter(id__in=staff_ids)
            instance.staff_members.set(staff_members)

        return instance


# ============================================================================
# BOOKING SERIALIZERS
# ============================================================================

class BookingListSerializer(serializers.ModelSerializer):
    """Serializer for Booking list view"""
    client = BookingClientSerializer(read_only=True)
    service = ServiceListSerializer(read_only=True)
    staff = BookingStaffSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'booking_number', 'client', 'service', 'staff', 'date', 'start_time', 'end_time',
            'status', 'payment_status', 'total_amount', 'deposit_amount', 'paid_amount',
            'client_notes', 'created_at'
        ]
        read_only_fields = ['id', 'booking_number']


class BookingDetailSerializer(serializers.ModelSerializer):
    """Serializer for Booking detail view"""
    client = BookingClientSerializer(read_only=True)
    service = ServiceListSerializer(read_only=True)
    staff = BookingStaffSerializer(read_only=True)
    remaining_amount = serializers.ReadOnlyField()

    class Meta:
        model = Booking
        fields = [
            'id', 'booking_number', 'client', 'service', 'staff', 'date', 'start_time', 'end_time',
            'status', 'payment_status', 'total_amount', 'deposit_amount', 'paid_amount', 'remaining_amount',
            'bog_order_id', 'payment_url', 'client_notes', 'staff_notes',
            'cancelled_at', 'cancelled_by', 'cancellation_reason',
            'created_at', 'updated_at', 'confirmed_at', 'completed_at'
        ]
        read_only_fields = ['id', 'booking_number', 'remaining_amount']


class BookingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Booking"""
    service_id = serializers.IntegerField(write_only=True)
    staff_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    payment_type = serializers.ChoiceField(choices=['full', 'deposit'], write_only=True, default='full')

    class Meta:
        model = Booking
        fields = ['service_id', 'staff_id', 'date', 'start_time', 'client_notes', 'payment_type']

    def validate(self, attrs):
        """Validate booking availability"""
        service_id = attrs.get('service_id')
        staff_id = attrs.get('staff_id')
        date = attrs.get('date')
        start_time = attrs.get('start_time')

        # Import here to avoid circular imports
        from .utils import validate_booking_availability

        try:
            service = Service.objects.get(id=service_id)
        except Service.DoesNotExist:
            raise serializers.ValidationError({"service_id": "Service not found"})

        staff = None
        if staff_id:
            try:
                staff = BookingStaff.objects.get(id=staff_id)
            except BookingStaff.DoesNotExist:
                raise serializers.ValidationError({"staff_id": "Staff not found"})

        # Validate availability
        is_available, error_message = validate_booking_availability(service, staff, date, start_time)
        if not is_available:
            raise serializers.ValidationError(error_message)

        attrs['service'] = service
        attrs['staff'] = staff
        return attrs

    def create(self, validated_data):
        payment_type = validated_data.pop('payment_type')
        service = validated_data.pop('service')
        staff = validated_data.pop('staff', None)
        validated_data.pop('service_id')
        validated_data.pop('staff_id', None)

        # Calculate end time
        from datetime import datetime, timedelta
        start_datetime = datetime.combine(validated_data['date'], validated_data['start_time'])
        end_datetime = start_datetime + timedelta(minutes=service.duration_minutes)
        validated_data['end_time'] = end_datetime.time()

        # Set pricing
        validated_data['service'] = service
        validated_data['staff'] = staff
        validated_data['total_amount'] = service.base_price

        if payment_type == 'deposit':
            validated_data['deposit_amount'] = service.calculate_deposit_amount()
        else:
            validated_data['deposit_amount'] = service.base_price

        # Client will be set from request.user in view
        booking = Booking.objects.create(**validated_data)

        return booking


class BookingUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Booking (admin only)"""
    staff_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Booking
        fields = ['staff_id', 'status', 'payment_status', 'staff_notes']

    def update(self, instance, validated_data):
        staff_id = validated_data.pop('staff_id', None)

        if staff_id:
            try:
                staff = BookingStaff.objects.get(id=staff_id)
                instance.staff = staff
            except BookingStaff.DoesNotExist:
                raise serializers.ValidationError({"staff_id": "Staff not found"})

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Auto-set timestamps based on status
        if instance.status == 'confirmed' and not instance.confirmed_at:
            instance.confirmed_at = timezone.now()
        elif instance.status == 'completed' and not instance.completed_at:
            instance.completed_at = timezone.now()

        instance.save()
        return instance


# ============================================================================
# RECURRING BOOKING SERIALIZERS
# ============================================================================

class RecurringBookingSerializer(serializers.ModelSerializer):
    """Serializer for RecurringBooking"""
    client = BookingClientSerializer(read_only=True)
    service = ServiceListSerializer(read_only=True)
    staff = BookingStaffSerializer(read_only=True)
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)
    day_name = serializers.CharField(source='get_preferred_day_of_week_display', read_only=True)

    class Meta:
        model = RecurringBooking
        fields = [
            'id', 'client', 'service', 'staff', 'frequency', 'frequency_display',
            'preferred_day_of_week', 'day_name', 'preferred_time', 'status',
            'next_booking_date', 'end_date', 'max_occurrences', 'current_occurrences'
        ]
        read_only_fields = ['id', 'current_occurrences']


class RecurringBookingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating RecurringBooking"""
    service_id = serializers.IntegerField(write_only=True)
    staff_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = RecurringBooking
        fields = [
            'service_id', 'staff_id', 'frequency', 'preferred_day_of_week',
            'preferred_time', 'end_date', 'max_occurrences'
        ]

    def create(self, validated_data):
        service_id = validated_data.pop('service_id')
        staff_id = validated_data.pop('staff_id', None)

        try:
            service = Service.objects.get(id=service_id)
        except Service.DoesNotExist:
            raise serializers.ValidationError({"service_id": "Service not found"})

        validated_data['service'] = service

        if staff_id:
            try:
                staff = BookingStaff.objects.get(id=staff_id)
                validated_data['staff'] = staff
            except BookingStaff.DoesNotExist:
                raise serializers.ValidationError({"staff_id": "Staff not found"})

        # Calculate next_booking_date
        from datetime import timedelta
        today = timezone.now().date()
        preferred_day = validated_data['preferred_day_of_week']

        # Find next occurrence of preferred day
        days_ahead = preferred_day - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        validated_data['next_booking_date'] = today + timedelta(days=days_ahead)

        # Client will be set from request.user in view
        return RecurringBooking.objects.create(**validated_data)


# ============================================================================
# BOOKING SETTINGS SERIALIZERS
# ============================================================================

class BookingSettingsSerializer(serializers.ModelSerializer):
    """Serializer for BookingSettings"""
    bog_client_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = BookingSettings
        fields = [
            'id', 'require_deposit', 'allow_cash_payment', 'allow_card_payment',
            'bog_client_id', 'bog_client_secret', 'bog_use_production',
            'cancellation_hours_before', 'refund_policy',
            'auto_confirm_on_deposit', 'auto_confirm_on_full_payment',
            'min_hours_before_booking', 'max_days_advance_booking'
        ]
        read_only_fields = ['id']

    def update(self, instance, validated_data):
        bog_client_secret = validated_data.pop('bog_client_secret', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if bog_client_secret is not None:
            instance.bog_client_secret = bog_client_secret

        instance.save()
        return instance
