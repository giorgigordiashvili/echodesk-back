"""
Bank of Georgia (BOG) Payment Gateway Integration for EchoDesk

Official BOG Payment API integration for processing subscription payments.
Documentation: https://api.bog.ge/docs/en/payments/introduction
"""

import requests
import hashlib
import base64
import logging
from django.conf import settings
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BOGPaymentService:
    """
    Service for integrating with Bank of Georgia payment gateway

    Configuration in settings.py:
    BOG_CLIENT_ID = 'your-client-id'
    BOG_CLIENT_SECRET = 'your-client-secret'
    BOG_AUTH_URL = 'https://oauth2.bog.ge/auth/realms/bog/protocol/openid-connect/token'
    BOG_API_BASE_URL = 'https://api.bog.ge/payments/v1'
    """

    def __init__(self):
        self.client_id = getattr(settings, 'BOG_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'BOG_CLIENT_SECRET', '')
        self.auth_url = getattr(settings, 'BOG_AUTH_URL',
                               'https://oauth2.bog.ge/auth/realms/bog/protocol/openid-connect/token')
        self.base_url = getattr(settings, 'BOG_API_BASE_URL',
                               'https://api.bog.ge/payments/v1')

        self._access_token = None
        self._token_expires_at = None

        if not all([self.client_id, self.client_secret]):
            logger.warning('BOG payment gateway not fully configured. Payment processing will be disabled.')

    def is_configured(self) -> bool:
        """Check if BOG is properly configured"""
        return bool(self.client_id and self.client_secret)

    def _get_access_token(self) -> str:
        """
        Get OAuth 2.0 access token using client credentials grant
        Caches token until it expires

        Returns:
            Access token string
        """
        # Return cached token if still valid
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at:
                return self._access_token

        try:
            # Create Basic Auth header
            credentials = f"{self.client_id}:{self.client_secret}"
            b64_credentials = base64.b64encode(credentials.encode()).decode()

            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {b64_credentials}'
            }

            data = {
                'grant_type': 'client_credentials'
            }

            response = requests.post(
                self.auth_url,
                headers=headers,
                data=data,
                timeout=30
            )

            if response.status_code == 200:
                token_data = response.json()
                self._access_token = token_data['access_token']

                # Cache token with 5 minute buffer before expiration
                expires_in = token_data.get('expires_in', 3600)
                self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)

                logger.info('Successfully obtained BOG access token')
                return self._access_token
            else:
                logger.error(f'Failed to get BOG access token: {response.status_code} - {response.text}')
                raise ValueError(f'Authentication failed: {response.status_code}')

        except requests.RequestException as e:
            logger.error(f'Error getting BOG access token: {e}')
            raise ValueError(f'Authentication error: {str(e)}')

    def create_payment(
        self,
        amount: float,
        currency: str = 'GEL',
        description: str = '',
        customer_email: str = '',
        customer_name: str = '',
        customer_phone: str = '',
        return_url_success: str = '',
        return_url_fail: str = '',
        callback_url: str = '',
        external_order_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Create a payment order with BOG

        Args:
            amount: Payment amount
            currency: Currency code (GEL, USD, EUR, GBP)
            description: Payment description
            customer_email: Customer email (masked automatically by BOG)
            customer_name: Customer full name
            customer_phone: Customer phone (masked automatically by BOG)
            return_url_success: URL to redirect after successful payment
            return_url_fail: URL to redirect after failed payment
            callback_url: Webhook URL for payment status updates
            external_order_id: Optional custom order ID
            metadata: Additional metadata (stored separately, not sent to BOG)

        Returns:
            Dict containing order_id, payment_url, and other details
        """
        if not self.is_configured():
            raise ValueError('BOG payment gateway is not configured')

        # Get access token
        access_token = self._get_access_token()

        # Format amount to 2 decimal places
        amount = round(float(amount), 2)

        # Build request payload
        payload = {
            'callback_url': callback_url,
            'purchase_units': {
                'currency': currency,
                'total_amount': amount,
                'basket': [
                    {
                        'product_id': external_order_id or 'subscription',
                        'description': description[:255] if description else 'EchoDesk Subscription',
                        'quantity': 1,
                        'unit_price': amount
                    }
                ]
            },
            'redirect_urls': {
                'success': return_url_success,
                'fail': return_url_fail
            },
            'payment_method': ['card']  # Enable card payment method
        }

        # Add optional fields
        if external_order_id:
            payload['external_order_id'] = external_order_id

        if customer_name or customer_email or customer_phone:
            payload['buyer'] = {}
            if customer_name:
                payload['buyer']['full_name'] = customer_name
            if customer_email:
                payload['buyer']['masked_email'] = customer_email
            if customer_phone:
                payload['buyer']['masked_phone'] = customer_phone

        # Make API request
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {access_token}',
                'Accept-Language': 'en'
            }

            response = requests.post(
                f'{self.base_url}/ecommerce/orders',
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                order_id = data['id']
                payment_url = data['_links']['redirect']['href']

                logger.info(f'BOG payment created: order_id={order_id}, amount={amount}{currency}')

                return {
                    'order_id': order_id,
                    'payment_id': order_id,
                    'payment_url': payment_url,
                    'amount': amount,
                    'currency': currency,
                    'status': 'pending',
                    'metadata': metadata,
                    'details_url': data['_links']['details']['href']
                }
            else:
                error_msg = f'BOG payment creation failed: {response.status_code} - {response.text}'
                logger.error(error_msg)
                raise ValueError(error_msg)

        except requests.RequestException as e:
            logger.error(f'Error creating BOG payment: {e}')
            raise ValueError(f'Payment creation error: {str(e)}')

    def check_payment_status(self, order_id: str) -> Dict:
        """
        Check the status of a payment

        Args:
            order_id: BOG order ID

        Returns:
            Dict containing payment status and details
        """
        if not self.is_configured():
            raise ValueError('BOG payment gateway is not configured')

        try:
            access_token = self._get_access_token()

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept-Language': 'en'
            }

            response = requests.get(
                f'{self.base_url}/receipt/{order_id}',
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                # Extract key status information
                order_status = data.get('order_status', {})
                status_key = order_status.get('key', 'unknown')

                # Map BOG status to our internal status
                status_mapping = {
                    'created': 'pending',
                    'processing': 'processing',
                    'completed': 'paid',
                    'rejected': 'failed',
                    'refund_requested': 'refund_requested',
                    'refunded': 'refunded',
                    'refunded_partially': 'refunded_partially',
                    'blocked': 'blocked'
                }

                internal_status = status_mapping.get(status_key, 'unknown')

                return {
                    'order_id': order_id,
                    'status': internal_status,
                    'bog_status': status_key,
                    'transaction_id': data.get('transaction_id'),
                    'amount': data.get('transfer_amount'),
                    'currency': data.get('currency'),
                    'transfer_method': data.get('transfer_method'),
                    'response_code': data.get('code'),
                    'raw_data': data
                }
            else:
                logger.warning(f'BOG status check failed: {response.status_code} - {response.text}')
                return {
                    'order_id': order_id,
                    'status': 'unknown',
                    'error': f'Status check failed: {response.status_code}'
                }

        except requests.RequestException as e:
            logger.error(f'Failed to check payment status: {e}')
            return {
                'order_id': order_id,
                'status': 'error',
                'error': str(e)
            }

    def verify_webhook_signature(self, payload: str, signature: str, public_key: str = None) -> bool:
        """
        Verify webhook signature from BOG callback

        Note: BOG uses SHA256withRSA signature verification with a public key.
        This is optional but recommended for production.

        Args:
            payload: Raw request body as string
            signature: Signature from Callback-Signature header
            public_key: Public key provided by BOG

        Returns:
            True if signature is valid or if signature verification is not configured
        """
        if not signature or not public_key:
            logger.warning('Webhook signature verification skipped (no signature or public key)')
            return True

        try:
            # TODO: Implement RSA signature verification when public key is available
            # This requires cryptography library and proper RSA verification
            logger.warning('Webhook signature verification not implemented yet')
            return True

        except Exception as e:
            logger.error(f'Webhook signature verification error: {e}')
            return False

    def create_subscription_payment(
        self,
        tenant,
        package,
        agent_count: int = 1,
        return_url_success: str = '',
        return_url_fail: str = '',
        callback_url: str = '',
        external_order_id: str = None
    ) -> Dict:
        """
        Create a subscription payment for a tenant

        Args:
            tenant: Tenant instance
            package: Package instance
            agent_count: Number of agents (for agent-based pricing)
            return_url_success: URL to redirect after successful payment
            return_url_fail: URL to redirect after failed payment
            callback_url: Webhook URL for payment updates
            external_order_id: Optional custom order ID

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
            return_url_success=return_url_success,
            return_url_fail=return_url_fail,
            callback_url=callback_url,
            external_order_id=external_order_id,
            metadata={
                'tenant_id': tenant.id,
                'tenant_schema': tenant.schema_name,
                'package_id': package.id,
                'package_name': package.name,
                'agent_count': agent_count,
                'subscription_type': 'new' if not hasattr(tenant, 'subscription') else 'upgrade'
            }
        )


# Convenience instance
bog_service = BOGPaymentService()
