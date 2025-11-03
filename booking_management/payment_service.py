from tenants.bog_payment import BOGPaymentService
from .models import Booking, BookingSettings
from django.db import connection
from tenants.models import Tenant
import logging

logger = logging.getLogger(__name__)


class BookingPaymentService:
    """
    Payment service for booking management
    Wrapper around BOGPaymentService with booking-specific logic
    """

    def __init__(self, tenant=None):
        """
        Initialize payment service

        Args:
            tenant: Tenant instance (optional, will auto-detect from schema)
        """
        if tenant is None:
            try:
                tenant = Tenant.objects.get(schema_name=connection.schema_name)
            except Tenant.DoesNotExist:
                raise ValueError("Could not determine tenant")

        self.tenant = tenant

        # Get or create booking settings
        self.settings, created = BookingSettings.objects.get_or_create(tenant=tenant)

        # Initialize BOG service
        self.bog_service = self._init_bog_service()

    def _init_bog_service(self):
        """Initialize BOG payment service with booking settings"""
        # Check if tenant has configured BOG credentials
        if self.settings.bog_client_id and self.settings.bog_client_secret:
            # Use tenant's credentials
            client_id = self.settings.bog_client_id
            client_secret = self.settings.bog_client_secret
            use_production = self.settings.bog_use_production
        else:
            # Fall back to test credentials (for development/testing)
            from django.conf import settings
            client_id = getattr(settings, 'BOG_TEST_CLIENT_ID', '')
            client_secret = getattr(settings, 'BOG_TEST_CLIENT_SECRET', '')
            use_production = False

            logger.warning(f"Tenant {self.tenant.schema_name} has no BOG credentials configured. Using test credentials.")

        return BOGPaymentService(
            client_id=client_id,
            client_secret=client_secret,
            use_production=use_production
        )

    def create_booking_payment(self, booking, callback_url):
        """
        Create BOG payment for a booking

        Args:
            booking: Booking instance
            callback_url: Webhook URL for payment notifications

        Returns:
            dict: Payment result with order_id and payment_url
        """
        # Determine amount to charge (deposit or full)
        amount = float(booking.deposit_amount) if booking.deposit_amount > 0 else float(booking.total_amount)

        # Create payment description
        service_name = booking.service.name if isinstance(booking.service.name, str) else booking.service.name.get('en', 'Service')
        description = f"Booking {booking.booking_number} - {service_name}"

        # Create payment
        try:
            result = self.bog_service.create_payment(
                amount=amount,
                currency='GEL',
                description=description,
                customer_email=booking.client.email,
                customer_name=booking.client.full_name,
                callback_url=callback_url,
                external_order_id=booking.booking_number
            )

            # Update booking with payment details
            booking.bog_order_id = result['order_id']
            booking.payment_url = result['payment_url']
            booking.payment_metadata = result
            booking.save(update_fields=['bog_order_id', 'payment_url', 'payment_metadata'])

            return result

        except Exception as e:
            logger.error(f"Failed to create booking payment for {booking.booking_number}: {str(e)}")
            raise

    def process_webhook(self, webhook_data):
        """
        Process BOG webhook notification

        Args:
            webhook_data: Webhook payload from BOG

        Returns:
            Booking: Updated booking instance
        """
        try:
            # Extract payment info
            body = webhook_data.get('body', {})
            order_status = body.get('order_status', {})
            status_key = order_status.get('key', '')
            response_code = body.get('response_code', '')
            external_order_id = body.get('external_order_id', '')
            amount = body.get('amount', 0)

            # Find booking
            try:
                booking = Booking.objects.get(booking_number=external_order_id)
            except Booking.DoesNotExist:
                logger.error(f"Booking not found for webhook: {external_order_id}")
                raise ValueError(f"Booking not found: {external_order_id}")

            # Update payment metadata
            booking.payment_metadata = webhook_data

            # Process payment status
            if status_key == 'completed' and response_code == '100':
                # Payment successful
                booking.paid_amount += float(amount) / 100  # BOG sends amount in cents

                # Update payment status
                if booking.paid_amount >= booking.total_amount:
                    booking.payment_status = 'fully_paid'
                elif booking.paid_amount >= booking.deposit_amount:
                    booking.payment_status = 'deposit_paid'

                # Auto-confirm booking based on settings
                if booking.status == 'pending':
                    should_confirm = False

                    if booking.payment_status == 'fully_paid' and self.settings.auto_confirm_on_full_payment:
                        should_confirm = True
                    elif booking.payment_status == 'deposit_paid' and self.settings.auto_confirm_on_deposit:
                        should_confirm = True

                    if should_confirm:
                        booking.confirm()
                    else:
                        booking.save(update_fields=['paid_amount', 'payment_status', 'payment_metadata'])
                else:
                    booking.save(update_fields=['paid_amount', 'payment_status', 'payment_metadata'])

                logger.info(f"Booking {booking.booking_number} payment successful. Status: {booking.payment_status}")

            elif status_key in ['canceled', 'expired']:
                # Payment failed/cancelled
                booking.payment_status = 'failed'
                booking.save(update_fields=['payment_status', 'payment_metadata'])
                logger.warning(f"Booking {booking.booking_number} payment failed: {status_key}")

            return booking

        except Exception as e:
            logger.error(f"Error processing booking webhook: {str(e)}")
            raise

    def initiate_refund(self, booking):
        """
        Initiate refund for a booking

        Args:
            booking: Booking instance

        Returns:
            dict: Refund result
        """
        if not booking.bog_order_id or booking.paid_amount == 0:
            raise ValueError("No payment to refund")

        # Calculate refund amount based on policy
        from .utils import calculate_refund_amount
        refund_amount = calculate_refund_amount(booking, self.settings)

        if refund_amount == 0:
            logger.info(f"No refund for booking {booking.booking_number} due to policy")
            return {'status': 'no_refund', 'amount': 0}

        try:
            # Initiate refund via BOG
            # Note: BOG refund API may vary - adjust as needed
            result = self.bog_service.refund_payment(
                order_id=booking.bog_order_id,
                amount=float(refund_amount)
            )

            # Update booking
            booking.payment_status = 'refunded'
            booking.paid_amount -= refund_amount
            if booking.paid_amount < 0:
                booking.paid_amount = 0

            booking.save(update_fields=['payment_status', 'paid_amount'])

            logger.info(f"Refund initiated for booking {booking.booking_number}: {refund_amount} GEL")

            return result

        except Exception as e:
            logger.error(f"Failed to initiate refund for {booking.booking_number}: {str(e)}")
            raise

    def check_payment_status(self, booking):
        """
        Check payment status from BOG

        Args:
            booking: Booking instance

        Returns:
            dict: Payment status info
        """
        if not booking.bog_order_id:
            return {'status': 'no_payment'}

        try:
            status = self.bog_service.check_payment_status(booking.bog_order_id)
            return status
        except Exception as e:
            logger.error(f"Failed to check payment status for {booking.booking_number}: {str(e)}")
            raise


# Convenience function to get payment service
def get_booking_payment_service(tenant=None):
    """Get or create booking payment service instance"""
    return BookingPaymentService(tenant=tenant)
