from rest_framework import permissions


class IsAuthenticatedBookingClient(permissions.BasePermission):
    """
    Permission check for authenticated booking clients
    """
    def has_permission(self, request, view):
        from .models import BookingClient
        return bool(request.user and isinstance(request.user, BookingClient))


class IsBookingOwner(permissions.BasePermission):
    """
    Object-level permission to only allow booking owners to view/edit their bookings
    """
    def has_object_permission(self, request, view, obj):
        from .models import BookingClient
        # Check if user is a BookingClient and owns this booking
        if isinstance(request.user, BookingClient):
            return obj.client == request.user
        return False


class HasBookingManagementFeature(permissions.BasePermission):
    """
    Check if tenant has booking_management feature enabled
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin users should have has_feature method
        if hasattr(request.user, 'has_feature'):
            return request.user.has_feature('booking_management')

        return False
