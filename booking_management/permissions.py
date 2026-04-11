from rest_framework import permissions


class IsAuthenticatedBookingClient(permissions.BasePermission):
    """
    Permission check for authenticated booking clients.
    Uses the unified social_integrations.Client model (not deprecated BookingClient).
    """
    def has_permission(self, request, view):
        from social_integrations.models import Client
        if not request.user:
            return False
        if isinstance(request.user, Client):
            return getattr(request.user, 'is_booking_enabled', False)
        return False


class IsBookingOwner(permissions.BasePermission):
    """
    Object-level permission to only allow booking owners to view/edit their bookings.
    """
    def has_object_permission(self, request, view, obj):
        from social_integrations.models import Client
        if isinstance(request.user, Client):
            return obj.client == request.user
        return False


class HasBookingManagementFeature(permissions.BasePermission):
    """
    Check if tenant has booking_management feature enabled.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'has_feature'):
            return request.user.has_feature('booking_management')
        return False
