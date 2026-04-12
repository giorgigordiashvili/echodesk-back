"""
Flitt (formerly Fondy) payment provider adapter.

Flitt payment API integration for one-time and subscription payments.
Docs: https://docs.flitt.com/
"""
import hashlib
import logging
import requests
from decimal import Decimal
from typing import Optional, Dict, Any, List

from .base import PaymentProvider, PaymentResult, PaymentStatus, ChargeResult

logger = logging.getLogger(__name__)

FLITT_API_BASE = 'https://pay.flitt.com/api'


def _compute_signature(password: str, params: Dict[str, Any]) -> str:
    """
    Compute Flitt HMAC-SHA1 signature.
    Signature = SHA1 of sorted non-empty param values joined with '|',
    prepended by the merchant password.
    """
    # Filter out empty values and the signature field itself
    filtered = {
        k: str(v) for k, v in params.items()
        if v not in (None, '', []) and k != 'signature'
    }
    # Sort by key, then join values with '|', password first
    sorted_values = [filtered[k] for k in sorted(filtered.keys())]
    params_str = '|'.join([password] + sorted_values)
    return hashlib.sha1(params_str.encode('utf-8')).hexdigest()


class FlittPaymentProvider(PaymentProvider):
    """
    Flitt (formerly Fondy) payment provider.

    - Requires redirect to hosted payment page
    - Does NOT manage recurring billing
    - Amounts are in cents (100.00 GEL = 10000)
    """

    @property
    def name(self) -> str:
        return 'flitt'

    @property
    def manages_recurring_billing(self) -> bool:
        return False

    @property
    def requires_redirect(self) -> bool:
        return True

    def _get_credentials(self) -> Dict[str, str]:
        """
        Get Flitt credentials from current tenant's ecommerce settings.
        Returns dict with merchant_id and password.
        """
        from django.db import connection
        from tenants.models import Tenant

        tenant = Tenant.objects.get(schema_name=connection.schema_name)
        settings = tenant.ecommerce_settings

        password = settings.get_flitt_password()
        if not password:
            raise ValueError("Flitt password not configured")

        return {
            'merchant_id': settings.flitt_merchant_id,
            'password': password,
        }

    @staticmethod
    def _to_cents(amount: Decimal) -> int:
        """Convert decimal amount to cents (integer)."""
        return int(amount * 100)

    @staticmethod
    def _from_cents(cents: int) -> Decimal:
        """Convert cents to decimal amount."""
        return Decimal(str(cents)) / Decimal('100')

    def create_payment(
        self,
        amount: Decimal,
        currency: str,
        external_order_id: str,
        description: str = '',
        customer_email: str = '',
        customer_name: str = '',
        return_url_success: str = '',
        return_url_fail: str = '',
        callback_url: str = '',
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentResult:
        credentials = self._get_credentials()

        params = {
            'merchant_id': credentials['merchant_id'],
            'order_id': external_order_id,
            'order_desc': description or f'Order {external_order_id}',
            'amount': self._to_cents(amount),
            'currency': currency or 'GEL',
        }

        if callback_url:
            params['server_callback_url'] = callback_url
        if return_url_success:
            params['response_url'] = return_url_success
        if customer_email:
            params['sender_email'] = customer_email

        # Compute signature
        params['signature'] = _compute_signature(credentials['password'], params)

        try:
            response = requests.post(
                f'{FLITT_API_BASE}/checkout/url',
                json={'request': params},
                headers={'Content-Type': 'application/json'},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            response_data = data.get('response', {})
            checkout_url = response_data.get('checkout_url', '')
            payment_id = response_data.get('payment_id', '')

            if response_data.get('response_status') == 'failure':
                error_msg = response_data.get('error_message', 'Unknown Flitt error')
                error_code = response_data.get('error_code', '')
                logger.error(
                    f"Flitt create_payment error: {error_code} - {error_msg}"
                )
                raise ValueError(f"Flitt payment creation failed: {error_msg}")

            logger.info(
                f"Flitt payment created: payment_id={payment_id}, "
                f"external_order_id={external_order_id}"
            )

            return PaymentResult(
                provider='flitt',
                provider_order_id=str(payment_id) if payment_id else external_order_id,
                external_order_id=external_order_id,
                amount=amount,
                currency=currency or 'GEL',
                status='pending',
                payment_url=checkout_url,
                requires_redirect=True,
                metadata=metadata or {},
            )
        except requests.RequestException as e:
            logger.error(f"Flitt create_payment failed: {e}")
            raise

    def create_subscription_payment(
        self,
        amount: Decimal,
        currency: str,
        external_order_id: str,
        customer_email: str = '',
        customer_name: str = '',
        company_name: str = '',
        return_url_success: str = '',
        return_url_fail: str = '',
        callback_url: str = '',
        feature_items: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentResult:
        """
        Create a subscription payment with card tokenization.
        Flitt uses recurring_data to enable card saving for future charges.
        """
        credentials = self._get_credentials()

        params = {
            'merchant_id': credentials['merchant_id'],
            'order_id': external_order_id,
            'order_desc': f'Subscription {external_order_id}',
            'amount': self._to_cents(amount),
            'currency': currency or 'GEL',
            'required_rectoken': 'Y',  # Request recurring token
        }

        if callback_url:
            params['server_callback_url'] = callback_url
        if return_url_success:
            params['response_url'] = return_url_success
        if customer_email:
            params['sender_email'] = customer_email

        params['signature'] = _compute_signature(credentials['password'], params)

        try:
            response = requests.post(
                f'{FLITT_API_BASE}/checkout/url',
                json={'request': params},
                headers={'Content-Type': 'application/json'},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            response_data = data.get('response', {})
            checkout_url = response_data.get('checkout_url', '')
            payment_id = response_data.get('payment_id', '')

            if response_data.get('response_status') == 'failure':
                error_msg = response_data.get('error_message', 'Unknown Flitt error')
                logger.error(f"Flitt create_subscription_payment error: {error_msg}")
                raise ValueError(f"Flitt subscription payment failed: {error_msg}")

            logger.info(
                f"Flitt subscription payment created: payment_id={payment_id}, "
                f"external_order_id={external_order_id}"
            )

            return PaymentResult(
                provider='flitt',
                provider_order_id=str(payment_id) if payment_id else external_order_id,
                external_order_id=external_order_id,
                amount=amount,
                currency=currency or 'GEL',
                status='pending',
                payment_url=checkout_url,
                requires_redirect=True,
                card_saving_enabled=True,
                metadata=metadata or {},
            )
        except requests.RequestException as e:
            logger.error(f"Flitt create_subscription_payment failed: {e}")
            raise

    def check_payment_status(self, provider_order_id: str) -> PaymentStatus:
        """Check the status of a Flitt payment by order_id."""
        credentials = self._get_credentials()

        params = {
            'merchant_id': credentials['merchant_id'],
            'order_id': provider_order_id,
        }
        params['signature'] = _compute_signature(credentials['password'], params)

        try:
            response = requests.post(
                f'{FLITT_API_BASE}/status/order_id',
                json={'request': params},
                headers={'Content-Type': 'application/json'},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            response_data = data.get('response', {})
            order_status = response_data.get('order_status', '').lower()

            # Map Flitt status to normalized status
            status_map = {
                'created': 'pending',
                'processing': 'processing',
                'approved': 'paid',
                'declined': 'failed',
                'reversed': 'cancelled',
                'expired': 'cancelled',
            }
            normalized_status = status_map.get(order_status, 'pending')

            amount_cents = response_data.get('amount')
            amount = None
            if amount_cents:
                amount = self._from_cents(int(amount_cents))

            return PaymentStatus(
                provider='flitt',
                provider_order_id=provider_order_id,
                status=normalized_status,
                amount=amount,
                currency=response_data.get('currency'),
                raw_data=response_data,
            )
        except requests.RequestException as e:
            logger.error(f"Flitt check_payment_status failed: {e}")
            raise

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        """
        Verify Flitt webhook signature.
        The callback POST data includes a 'signature' field that must match
        our computed signature from the other fields.
        """
        import json as json_module

        try:
            credentials = self._get_credentials()

            # Parse callback data
            try:
                data = json_module.loads(body)
            except (json_module.JSONDecodeError, TypeError):
                # Try form-encoded data
                from urllib.parse import parse_qs
                parsed = parse_qs(body.decode('utf-8'))
                data = {k: v[0] for k, v in parsed.items()}

            received_signature = data.get('signature', '')
            if not received_signature:
                logger.warning("Flitt webhook missing signature")
                return False

            expected_signature = _compute_signature(credentials['password'], data)
            return received_signature == expected_signature

        except Exception as e:
            logger.error(f"Flitt webhook verification failed: {e}")
            return False

    def charge_recurring(
        self,
        parent_order_id: str,
        amount: Optional[Decimal] = None,
        callback_url: str = '',
        external_order_id: str = '',
    ) -> ChargeResult:
        """Charge a saved card via Flitt recurring token."""
        credentials = self._get_credentials()

        params = {
            'merchant_id': credentials['merchant_id'],
            'order_id': external_order_id or parent_order_id,
            'order_desc': f'Recurring charge for {external_order_id or parent_order_id}',
            'currency': 'GEL',
            'rectoken': parent_order_id,  # The recurring token from initial payment
        }

        if amount is not None:
            params['amount'] = self._to_cents(amount)

        if callback_url:
            params['server_callback_url'] = callback_url

        params['signature'] = _compute_signature(credentials['password'], params)

        try:
            response = requests.post(
                f'{FLITT_API_BASE}/recurring',
                json={'request': params},
                headers={'Content-Type': 'application/json'},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            response_data = data.get('response', {})
            payment_id = response_data.get('payment_id', '')
            order_status = response_data.get('order_status', '').lower()

            if response_data.get('response_status') == 'failure':
                error_msg = response_data.get('error_message', 'Unknown error')
                logger.error(f"Flitt recurring charge error: {error_msg}")
                raise ValueError(f"Flitt recurring charge failed: {error_msg}")

            # Map status
            status_map = {
                'approved': 'paid',
                'processing': 'processing',
                'declined': 'failed',
            }
            normalized_status = status_map.get(order_status, 'processing')

            logger.info(
                f"Flitt recurring charge: payment_id={payment_id}, "
                f"status={order_status}"
            )

            return ChargeResult(
                provider='flitt',
                provider_order_id=str(payment_id) if payment_id else parent_order_id,
                status=normalized_status,
                amount=amount,
                requires_authentication=False,
                metadata=response_data,
            )
        except requests.RequestException as e:
            logger.error(f"Flitt charge_recurring failed: {e}")
            raise
