"""
Flitt Payment Gateway Integration for EchoDesk

Official Flitt integration for processing subscription payments.
"""

import requests
import hashlib
import hmac
import json
import uuid
from django.conf import settings
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FlittPaymentService:
    """
    Service for integrating with Flitt payment gateway (https://flitt.ge)

    Configuration in settings.py:
    FLITT_MERCHANT_URL = 'https://echodesk.ge'
    FLITT_MERCHANT_ID = '4054989'
    FLITT_PAYMENT_KEY = 'MkyBxXTxV3SARPNgdl2k5dAbr3qFZd9s'
    FLITT_CREDIT_PRIVATE_KEY = 'pu5NWw4W4jJfQduz7SKKEmWfis0SsUvW'
    FLITT_BASE_URL = 'https://api.flitt.ge'
    """

    def __init__(self):
        self.merchant_url = getattr(settings, 'FLITT_MERCHANT_URL', 'https://echodesk.ge')
        self.merchant_id = getattr(settings, 'FLITT_MERCHANT_ID', '')
        self.payment_key = getattr(settings, 'FLITT_PAYMENT_KEY', '')
        self.credit_key = getattr(settings, 'FLITT_CREDIT_PRIVATE_KEY', '')
        self.base_url = getattr(settings, 'FLITT_BASE_URL', 'https://api.flitt.ge')

        if not all([self.merchant_id, self.payment_key]):
            logger.warning('Flitt payment gateway not fully configured. Payment processing will be disabled.')

    def is_configured(self) -> bool:
        """Check if Flitt is properly configured"""
        return bool(self.merchant_id and self.payment_key)

    def _generate_signature(self, order_id: str, amount: float, currency: str = 'GEL') -> str:
        """
        Generate signature for Flitt payment request

        Flitt signature format: MD5(merchant_id:order_id:amount:currency:payment_key)
        """
        # Format amount to 2 decimal places
        amount_str = f"{amount:.2f}"

        # Create signature string
        signature_string = f"{self.merchant_id}:{order_id}:{amount_str}:{currency}:{self.payment_key}"

        # Generate MD5 hash
        signature = hashlib.md5(signature_string.encode('utf-8')).hexdigest()

        logger.debug(f'Generated signature for order {order_id}')
        return signature

    def _verify_signature(self, order_id: str, amount: float, currency: str, received_signature: str) -> bool:
        """
        Verify signature from Flitt callback

        Args:
            order_id: Order ID
            amount: Payment amount
            currency: Currency code
            received_signature: Signature from Flitt

        Returns:
            True if signature is valid
        """
        expected_signature = self._generate_signature(order_id, amount, currency)
        return hmac.compare_digest(expected_signature, received_signature)

    def create_payment(
        self,
        amount: float,
        currency: str = 'GEL',
        description: str = '',
        customer_email: str = '',
        customer_name: str = '',
        return_url: str = '',
        callback_url: str = '',
        metadata: Optional[Dict] = None,
        order_id: Optional[str] = None
    ) -> Dict:
        """
        Create a payment session with Flitt

        Creates a redirect URL for the customer to complete payment.

        Args:
            amount: Payment amount
            currency: Currency code (GEL default)
            description: Payment description
            customer_email: Customer email
            customer_name: Customer name
            return_url: URL to redirect after payment
            callback_url: Webhook URL for payment status updates
            metadata: Additional metadata (subscription_id, tenant_id, etc.)
            order_id: Optional custom order ID (generated if not provided)

        Returns:
            Dict containing order_id, payment_url, and other details
        """
        if not self.is_configured():
            raise ValueError('Flitt payment gateway is not configured')

        # Generate unique order ID if not provided
        if not order_id:
            order_id = str(uuid.uuid4())[:32]  # Flitt order IDs should be unique

        # Format amount
        amount = round(float(amount), 2)

        # Generate signature
        signature = self._generate_signature(order_id, amount, currency)

        # Build payment URL with query parameters (Flitt redirect method)
        payment_url = f"{self.base_url}/en/merchant/redirect"

        params = {
            'merchant_id': self.merchant_id,
            'order_id': order_id,
            'amount': f"{amount:.2f}",
            'currency': currency,
            'description': description[:255],  # Limit description length
            'return_url': return_url,
            'callback_url': callback_url,
            'signature': signature,
        }

        # Add optional parameters
        if customer_email:
            params['customer_email'] = customer_email
        if customer_name:
            params['customer_name'] = customer_name

        # Store metadata separately (Flitt doesn't support custom metadata in URL)
        # You may want to store this in your database linked to order_id

        # Build full payment URL
        query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        full_payment_url = f"{payment_url}?{query_string}"

        logger.info(f'Payment created: order_id={order_id}, amount={amount}{currency}')

        return {
            'order_id': order_id,
            'payment_id': order_id,  # Flitt uses order_id as payment identifier
            'payment_url': full_payment_url,
            'amount': amount,
            'currency': currency,
            'status': 'pending',
            'metadata': metadata
        }

    def check_payment_status(self, order_id: str) -> Dict:
        """
        Check the status of a payment

        Note: Flitt typically notifies status via webhook.
        This method might require additional API access.

        Args:
            order_id: Flitt order ID

        Returns:
            Dict containing payment status
        """
        if not self.is_configured():
            raise ValueError('Flitt payment gateway is not configured')

        # Flitt status check endpoint (if available)
        try:
            response = requests.get(
                f'{self.base_url}/api/order/status',
                params={
                    'merchant_id': self.merchant_id,
                    'order_id': order_id
                },
                headers={
                    'Authorization': f'Bearer {self.payment_key}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f'Flitt status check failed: {response.status_code}')
                return {
                    'order_id': order_id,
                    'status': 'unknown',
                    'error': 'Status check failed'
                }

        except requests.RequestException as e:
            logger.error(f'Failed to check payment status: {e}')
            return {
                'order_id': order_id,
                'status': 'error',
                'error': str(e)
            }

    def verify_webhook_signature(self, payload: Dict, received_signature: str) -> bool:
        """
        Verify webhook signature from Flitt callback

        Args:
            payload: Webhook payload containing order_id, amount, currency, status
            received_signature: Signature from Flitt

        Returns:
            True if signature is valid
        """
        order_id = payload.get('order_id', '')
        amount = float(payload.get('amount', 0))
        currency = payload.get('currency', 'GEL')

        return self._verify_signature(order_id, amount, currency, received_signature)

    def create_subscription_payment(
        self,
        tenant,
        package,
        agent_count: int = 1,
        return_url: str = '',
        callback_url: str = ''
    ) -> Dict:
        """
        Create a subscription payment for a tenant

        Args:
            tenant: Tenant instance
            package: Package instance
            agent_count: Number of agents (for agent-based pricing)
            return_url: URL to redirect after payment
            callback_url: Webhook URL for payment updates

        Returns:
            Dict with payment details including payment_url
        """
        from .models import PricingModel

        # Calculate amount
        if package.pricing_model == PricingModel.AGENT_BASED:
            amount = float(package.price_gel) * agent_count
        else:
            amount = float(package.price_gel)

        # Format description
        description = f"EchoDesk {package.display_name} - {tenant.name}"

        # Create payment
        return self.create_payment(
            amount=amount,
            currency='GEL',
            description=description,
            customer_email=tenant.admin_email,
            customer_name=tenant.admin_name,
            return_url=return_url,
            callback_url=callback_url,
            metadata={
                'tenant_id': tenant.id,
                'tenant_schema': tenant.schema_name,
                'package_id': package.id,
                'package_name': package.name,
                'agent_count': agent_count,
                'subscription_type': 'new' if not hasattr(tenant, 'subscription') else 'upgrade'
            }
        )

    def refund_payment(self, order_id: str, amount: Optional[float] = None, reason: str = '') -> Dict:
        """
        Request a refund for a payment

        Note: Refunds typically need to be processed through Flitt dashboard
        or require special API access.

        Args:
            order_id: Flitt order ID
            amount: Amount to refund (None for full refund)
            reason: Refund reason

        Returns:
            Dict with refund details
        """
        logger.info(f'Refund requested for order {order_id}: {reason}')

        # Flitt refunds might need manual processing
        return {
            'order_id': order_id,
            'status': 'refund_requested',
            'message': 'Refund request submitted. Please process through Flitt dashboard.',
            'reason': reason
        }


# Convenience instance
flitt_service = FlittPaymentService()
