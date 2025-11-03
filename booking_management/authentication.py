from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import exceptions
from .models import BookingClient
import logging

logger = logging.getLogger(__name__)


class BookingClientJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication for booking clients
    Similar to EcommerceClientJWTAuthentication but for booking system
    """

    def get_user(self, validated_token):
        """
        Attempts to find and return a BookingClient using the given validated token.
        """
        try:
            booking_client_id = validated_token.get('booking_client_id')

            if not booking_client_id:
                raise exceptions.AuthenticationFailed('Token does not contain booking_client_id')

            try:
                booking_client = BookingClient.objects.get(id=booking_client_id)
            except BookingClient.DoesNotExist:
                raise exceptions.AuthenticationFailed('Booking client not found')

            # Check if client is verified
            if not booking_client.is_verified:
                raise exceptions.AuthenticationFailed('Email not verified')

            return booking_client

        except KeyError:
            logger.error('booking_client_id not found in token payload')
            raise exceptions.AuthenticationFailed('Invalid token payload')
        except Exception as e:
            logger.error(f'Error in BookingClientJWTAuthentication: {str(e)}')
            raise exceptions.AuthenticationFailed('Authentication failed')
