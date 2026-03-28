"""
Paddle Billing payment provider.

Paddle Billing API v2 integration for subscription and one-time payments.
Paddle manages recurring billing automatically — no cron-based charging needed.

Docs: https://developer.paddle.com/api-reference/overview
"""
import hashlib
import hmac
import json
import logging
import requests
from decimal import Decimal
from typing import Optional, Dict, Any, List
from urllib.parse import quote

from django.conf import settings

from .base import PaymentProvider, PaymentResult, PaymentStatus, ChargeResult

logger = logging.getLogger(__name__)


class PaddlePaymentProvider(PaymentProvider):
    """
    Paddle Billing payment provider.

    - Uses JS overlay checkout (no redirect)
    - Manages recurring billing automatically
    - Bearer token auth via PADDLE_API_KEY
    """

    def __init__(self):
        self._api_key = getattr(settings, 'PADDLE_API_KEY', '')
        self._webhook_secret = getattr(settings, 'PADDLE_WEBHOOK_SECRET', '')
        environment = getattr(settings, 'PADDLE_ENVIRONMENT', 'sandbox')
        if environment == 'production':
            self._base_url = 'https://api.paddle.com'
        else:
            self._base_url = 'https://sandbox-api.paddle.com'

    @property
    def name(self) -> str:
        return 'paddle'

    @property
    def manages_recurring_billing(self) -> bool:
        return True

    @property
    def requires_redirect(self) -> bool:
        return False

    def _headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self._api_key}',
            'Content-Type': 'application/json',
        }

    def _request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict:
        """Make an authenticated request to Paddle API."""
        url = f'{self._base_url}{path}'
        try:
            response = requests.request(
                method,
                url,
                headers=self._headers(),
                json=data,
                timeout=30,
            )
            response_data = response.json()

            if response.status_code >= 400:
                error_detail = response_data.get('error', {})
                error_msg = error_detail.get('detail', response.text)
                error_code = error_detail.get('code', '')
                field_errors = error_detail.get('errors', [])
                logger.error(f'Paddle API error: {response.status_code} [{error_code}] {error_msg} | fields: {field_errors} | url: {url} | payload: {json.dumps(data) if data else "none"}')
                raise ValueError(f'Paddle API error: {error_msg} (code={error_code}, fields={field_errors})')

            return response_data.get('data', response_data)

        except requests.RequestException as e:
            logger.error(f'Paddle API request failed: {e}')
            raise ValueError(f'Paddle API request failed: {str(e)}')

    # ── Customer management ──────────────────────────────────────

    def get_or_create_customer(self, email: str, name: str = '') -> Dict[str, Any]:
        """
        Get existing Paddle customer by email, or create a new one.
        Returns dict with 'id', 'email', 'name'.
        """
        # Search for existing customer
        encoded_email = quote(email, safe='@.')
        customers = self._request('GET', f'/customers?email={encoded_email}')
        if isinstance(customers, list) and len(customers) > 0:
            return customers[0]

        # Create new customer
        payload = {'email': email}
        if name:
            payload['name'] = name

        return self._request('POST', '/customers', payload)

    # ── Payment creation ─────────────────────────────────────────

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
        """
        Create a one-time Paddle transaction.
        Returns checkout_data for the frontend to open Paddle.js overlay.
        """
        # Build transaction payload
        payload: Dict[str, Any] = {
            'items': [{
                'price': {
                    'description': description or 'EchoDesk Payment',
                    'unit_price': {
                        'amount': str(int(amount * 100)),  # Paddle uses lowest denomination
                        'currency_code': currency.upper(),
                    },
                    'product': {
                        'name': description or 'EchoDesk Payment',
                        'tax_category': 'standard',
                    },
                },
                'quantity': 1,
            }],
            'custom_data': {
                'external_order_id': external_order_id,
                **(metadata or {}),
            },
        }

        if customer_email:
            customer = self.get_or_create_customer(customer_email, customer_name)
            payload['customer_id'] = customer['id']

        if return_url_success:
            payload['checkout'] = {
                'url': return_url_success,
            }

        result = self._request('POST', '/transactions', payload)

        transaction_id = result.get('id', '')

        return PaymentResult(
            provider='paddle',
            provider_order_id=transaction_id,
            external_order_id=external_order_id,
            amount=amount,
            currency=currency,
            status='pending',
            payment_url=None,
            checkout_data={
                'transaction_id': transaction_id,
            },
            requires_redirect=False,
            metadata=metadata or {},
        )

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
        Create a Paddle subscription transaction.

        feature_items should be a list of dicts with 'paddle_price_id' and 'quantity'.
        If not provided, falls back to a single ad-hoc price item.
        """
        payload: Dict[str, Any] = {
            'custom_data': {
                'external_order_id': external_order_id,
                'company_name': company_name,
                **(metadata or {}),
            },
        }

        # Build items from feature price mappings or ad-hoc
        if feature_items:
            payload['items'] = [
                {
                    'price_id': item['paddle_price_id'],
                    'quantity': item.get('quantity', 1),
                }
                for item in feature_items
            ]
        else:
            # Ad-hoc price (for one-time or when no price mappings exist)
            payload['items'] = [{
                'price': {
                    'description': f'EchoDesk Subscription - {company_name}',
                    'unit_price': {
                        'amount': str(int(amount * 100)),
                        'currency_code': currency.upper(),
                    },
                    'product': {
                        'name': f'EchoDesk Subscription',
                        'tax_category': 'standard',
                    },
                    'billing_cycle': {
                        'interval': 'month',
                        'frequency': 1,
                    },
                },
                'quantity': 1,
            }]

        # Attach customer
        if customer_email:
            customer = self.get_or_create_customer(customer_email, customer_name)
            payload['customer_id'] = customer['id']

        if return_url_success:
            payload['checkout'] = {
                'url': return_url_success,
            }

        result = self._request('POST', '/transactions', payload)

        transaction_id = result.get('id', '')

        return PaymentResult(
            provider='paddle',
            provider_order_id=transaction_id,
            external_order_id=external_order_id,
            amount=amount,
            currency=currency,
            status='pending',
            payment_url=None,
            checkout_data={
                'transaction_id': transaction_id,
            },
            requires_redirect=False,
            card_saving_enabled=False,  # Paddle manages cards internally
            metadata=metadata or {},
        )

    # ── Status checking ──────────────────────────────────────────

    def check_payment_status(self, provider_order_id: str) -> PaymentStatus:
        """Check status of a Paddle transaction."""
        result = self._request('GET', f'/transactions/{provider_order_id}')

        # Map Paddle statuses to internal ones
        paddle_status = result.get('status', 'unknown')
        status_mapping = {
            'draft': 'pending',
            'ready': 'pending',
            'billed': 'processing',
            'completed': 'paid',
            'canceled': 'cancelled',
            'past_due': 'failed',
        }

        return PaymentStatus(
            provider='paddle',
            provider_order_id=provider_order_id,
            status=status_mapping.get(paddle_status, 'unknown'),
            amount=Decimal(str(result.get('details', {}).get('totals', {}).get('total', 0))) / 100
            if result.get('details', {}).get('totals', {}).get('total') else None,
            currency=result.get('currency_code'),
            raw_data=result,
        )

    # ── Webhook verification ─────────────────────────────────────

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        """
        Verify Paddle webhook via Paddle-Signature header (HMAC-SHA256).

        Paddle-Signature format: ts=<timestamp>;h1=<hash>
        """
        if not self._webhook_secret:
            logger.warning('PADDLE_WEBHOOK_SECRET not set, skipping webhook verification')
            return True

        signature_header = headers.get('Paddle-Signature', '')
        if not signature_header:
            logger.warning('Missing Paddle-Signature header')
            return False

        # Parse ts and h1 from the header
        parts = {}
        for part in signature_header.split(';'):
            key, _, value = part.partition('=')
            parts[key.strip()] = value.strip()

        ts = parts.get('ts', '')
        h1 = parts.get('h1', '')

        if not ts or not h1:
            logger.warning('Invalid Paddle-Signature format')
            return False

        # Build signed payload: ts:body
        signed_payload = f'{ts}:{body.decode("utf-8")}'
        expected = hmac.new(
            self._webhook_secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, h1):
            logger.warning('Paddle webhook signature mismatch')
            return False

        return True

    # ── Subscription management ──────────────────────────────────

    def cancel_subscription(self, provider_subscription_id: str) -> Dict[str, Any]:
        """Cancel a Paddle subscription. Effective at end of billing period by default."""
        return self._request(
            'POST',
            f'/subscriptions/{provider_subscription_id}/cancel',
            {'effective_from': 'next_billing_period'},
        )

    def update_subscription_items(
        self,
        provider_subscription_id: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update subscription line items (add/remove features).

        items: list of {'price_id': '...', 'quantity': N}
        """
        return self._request(
            'PATCH',
            f'/subscriptions/{provider_subscription_id}',
            {
                'items': items,
                'proration_billing_mode': 'prorated_immediately',
            },
        )

    def pause_subscription(self, provider_subscription_id: str) -> Dict[str, Any]:
        """Pause a Paddle subscription."""
        return self._request(
            'POST',
            f'/subscriptions/{provider_subscription_id}/pause',
            {'effective_from': 'next_billing_period'},
        )

    def resume_subscription(self, provider_subscription_id: str) -> Dict[str, Any]:
        """Resume a paused Paddle subscription."""
        return self._request(
            'POST',
            f'/subscriptions/{provider_subscription_id}/resume',
            {'effective_from': 'immediately'},
        )
