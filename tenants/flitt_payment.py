"""
Flitt Payment Gateway Integration

This module handles payment processing through Flitt payment gateway for subscriptions.
"""

import requests
import hashlib
import hmac
import json
from django.conf import settings
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FlittPaymentService:
    """
    Service for integrating with Flitt payment gateway

    Configuration required in settings.py:
    FLITT_API_KEY = 'your-api-key'
    FLITT_SECRET_KEY = 'your-secret-key'
    FLITT_BASE_URL = 'https://api.flitt.com'  # Or appropriate Flitt API URL
    FLITT_MERCHANT_ID = 'your-merchant-id'
    """

    def __init__(self):
        self.api_key = getattr(settings, 'FLITT_API_KEY', '')
        self.secret_key = getattr(settings, 'FLITT_SECRET_KEY', '')
        self.base_url = getattr(settings, 'FLITT_BASE_URL', 'https://api.flitt.com')
        self.merchant_id = getattr(settings, 'FLITT_MERCHANT_ID', '')

        if not all([self.api_key, self.secret_key, self.merchant_id]):
            logger.warning('Flitt payment gateway not fully configured. Payment processing will be disabled.')

    def is_configured(self) -> bool:
        """Check if Flitt is properly configured"""
        return bool(self.api_key and self.secret_key and self.merchant_id)

    def _generate_signature(self, data: Dict) -> str:
        """
        Generate HMAC signature for request authentication

        NOTE: Update this method based on actual Flitt documentation
        """
        # Convert data to sorted string for consistent hashing
        sorted_data = json.dumps(data, sort_keys=True)
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            sorted_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def create_payment(
        self,
        amount: float,
        currency: str = 'GEL',
        description: str = '',
        customer_email: str = '',
        customer_name: str = '',
        return_url: str = '',
        callback_url: str = '',
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Create a payment session with Flitt

        Args:
            amount: Payment amount
            currency: Currency code (GEL, USD, EUR, etc.)
            description: Payment description
            customer_email: Customer email
            customer_name: Customer name
            return_url: URL to redirect after payment
            callback_url: Webhook URL for payment status updates
            metadata: Additional metadata (subscription_id, tenant_id, etc.)

        Returns:
            Dict containing payment_id, payment_url, and status
        """
        if not self.is_configured():
            raise ValueError('Flitt payment gateway is not configured')

        # Prepare payment data
        payment_data = {
            'merchant_id': self.merchant_id,
            'amount': amount,
            'currency': currency,
            'description': description,
            'customer_email': customer_email,
            'customer_name': customer_name,
            'return_url': return_url,
            'callback_url': callback_url,
            'metadata': metadata or {}
        }

        # Generate signature
        payment_data['signature'] = self._generate_signature(payment_data)

        # Make API request
        try:
            response = requests.post(
                f'{self.base_url}/api/v1/payments/create',  # Update with actual endpoint
                json=payment_data,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f'Payment created successfully: {result.get("payment_id")}')
            return result

        except requests.RequestException as e:
            logger.error(f'Failed to create Flitt payment: {e}')
            raise Exception(f'Payment creation failed: {str(e)}')

    def check_payment_status(self, payment_id: str) -> Dict:
        """
        Check the status of a payment

        Args:
            payment_id: Flitt payment ID

        Returns:
            Dict containing payment status and details
        """
        if not self.is_configured():
            raise ValueError('Flitt payment gateway is not configured')

        try:
            response = requests.get(
                f'{self.base_url}/api/v1/payments/{payment_id}',  # Update with actual endpoint
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            logger.error(f'Failed to check payment status: {e}')
            raise Exception(f'Payment status check failed: {str(e)}')

    def verify_webhook_signature(self, payload: Dict, received_signature: str) -> bool:
        """
        Verify webhook signature from Flitt

        Args:
            payload: Webhook payload
            received_signature: Signature from Flitt webhook headers

        Returns:
            True if signature is valid, False otherwise
        """
        calculated_signature = self._generate_signature(payload)
        return hmac.compare_digest(calculated_signature, received_signature)

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

        # Create payment
        return self.create_payment(
            amount=amount,
            currency='GEL',
            description=f'{package.display_name} Subscription - {tenant.name}',
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

    def refund_payment(self, payment_id: str, amount: Optional[float] = None, reason: str = '') -> Dict:
        """
        Refund a payment

        Args:
            payment_id: Flitt payment ID
            amount: Amount to refund (None for full refund)
            reason: Refund reason

        Returns:
            Dict with refund details
        """
        if not self.is_configured():
            raise ValueError('Flitt payment gateway is not configured')

        refund_data = {
            'payment_id': payment_id,
            'reason': reason
        }

        if amount is not None:
            refund_data['amount'] = amount

        try:
            response = requests.post(
                f'{self.base_url}/api/v1/payments/{payment_id}/refund',  # Update with actual endpoint
                json=refund_data,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            logger.error(f'Failed to refund payment: {e}')
            raise Exception(f'Refund failed: {str(e)}')


# Convenience instance
flitt_service = FlittPaymentService()
