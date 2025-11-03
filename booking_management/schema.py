"""
OpenAPI schema extensions for booking_management authentication
"""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class BookingClientJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    OpenAPI extension to properly document BookingClientJWTAuthentication
    as a Bearer token authentication scheme.
    """
    target_class = 'booking_management.authentication.BookingClientJWTAuthentication'
    name = 'bookingJwtAuth'  # Unique name for booking JWT auth

    def get_security_definition(self, auto_schema):
        """
        Return the security definition for this authentication class.
        Uses the same Bearer JWT scheme as rest_framework_simplejwt.
        """
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
            'description': 'Booking Client JWT Authentication - Use the access token obtained from /api/bookings/clients/login/'
        }
