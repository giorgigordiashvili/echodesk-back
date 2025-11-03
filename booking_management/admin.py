from django.contrib import admin
from .models import (
    BookingClient, ServiceCategory, Service, BookingStaff,
    StaffAvailability, StaffException, Booking, RecurringBooking,
    BookingSettings
)


@admin.register(BookingClient)
class BookingClientAdmin(admin.ModelAdmin):
    list_display = ['email', 'first_name', 'last_name', 'phone_number', 'is_verified', 'created_at']
    list_filter = ['is_verified', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ['get_name', 'display_order', 'is_active']
    list_filter = ['is_active']
    ordering = ['display_order']

    def get_name(self, obj):
        return obj.name.get('en', 'N/A') if isinstance(obj.name, dict) else obj.name
    get_name.short_description = 'Name'


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['get_name', 'category', 'base_price', 'duration_minutes', 'booking_type', 'status']
    list_filter = ['status', 'booking_type', 'category']
    search_fields = ['name']
    filter_horizontal = ['staff_members']

    def get_name(self, obj):
        return obj.name.get('en', 'N/A') if isinstance(obj.name, dict) else obj.name
    get_name.short_description = 'Name'


@admin.register(BookingStaff)
class BookingStaffAdmin(admin.ModelAdmin):
    list_display = ['user', 'average_rating', 'total_ratings', 'is_active_for_bookings']
    list_filter = ['is_active_for_bookings']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']


@admin.register(StaffAvailability)
class StaffAvailabilityAdmin(admin.ModelAdmin):
    list_display = ['staff', 'day_of_week', 'start_time', 'end_time', 'is_available']
    list_filter = ['day_of_week', 'is_available']
    search_fields = ['staff__user__email']


@admin.register(StaffException)
class StaffExceptionAdmin(admin.ModelAdmin):
    list_display = ['staff', 'date', 'start_time', 'end_time', 'reason']
    list_filter = ['date']
    search_fields = ['staff__user__email', 'reason']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['booking_number', 'client', 'service', 'staff', 'date', 'start_time', 'status', 'payment_status']
    list_filter = ['status', 'payment_status', 'date']
    search_fields = ['booking_number', 'client__email', 'service__name']
    readonly_fields = ['booking_number', 'created_at', 'updated_at', 'confirmed_at', 'completed_at', 'cancelled_at']


@admin.register(RecurringBooking)
class RecurringBookingAdmin(admin.ModelAdmin):
    list_display = ['client', 'service', 'frequency', 'preferred_day_of_week', 'status', 'next_booking_date']
    list_filter = ['frequency', 'status', 'preferred_day_of_week']
    search_fields = ['client__email', 'service__name']


@admin.register(BookingSettings)
class BookingSettingsAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'require_deposit', 'allow_cash_payment', 'allow_card_payment', 'cancellation_hours_before']
    readonly_fields = ['tenant']
