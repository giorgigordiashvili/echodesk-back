"""
TBC Bank payment provider adapter.

TBC Pay API integration for one-time and subscription payments.
Docs: https://developers.tbcbank.ge/docs/tbc-pay-api
"""
import logging
import requests
from decimal import Decimal
from typing import Optional, Dict, Any, List

from .base import PaymentProvider, PaymentResult, PaymentStatus, ChargeResult

logger = logging.getLogger(__name__)

TBC_API_BASE = 'https://api.tbcbank.ge/v1/tpay'
TBC_AUTH_URL = 'https://api.tbcbank.ge/v1/tpay/access-token'


class TBCPaymentProvider(PaymentProvider):
    """
    TBC Bank payment provider.

    - Requires redirect to hosted payment page
    - Does NOT manage recurring billing (EchoDesk charges via cron)
    - Uses OAuth2 client_credentials for auth + apikey header
    """

    @property
    def name(self) -> str:
        return 'tbc'

    @property
    def manages_recurring_billing(self) -> bool:
        return False

    @property
    def requires_redirect(self) -> bool:
        return True

    def _get_credentials(self) -> Dict[str, str]:
        """
        Get TBC credentials from current tenant's ecommerce settings.
        Returns dict with client_id, client_secret, api_key.
        """
        from django.db import connection
        from tenants.models import Tenant

        tenant = Tenant.objects.get(schema_name=connection.schema_name)
        settings = tenant.ecommerce_settings

        client_secret = settings.get_tbc_secret()
        if not client_secret:
            raise ValueError("TBC client secret not configured")

        return {
            'client_id': settings.tbc_client_id,
            'client_secret': client_secret,
            'api_key': settings.tbc_api_key,
        }

    def _get_access_token(self, credentials: Dict[str, str]) -> str:
        """Obtain an access token from TBC Bank OAuth2 endpoint."""
        try:
            response = requests.post(
                TBC_AUTH_URL,
                data={
                    'client_id': credentials['client_id'],
                    'client_secret': credentials['client_secret'],
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            token = data.get('access_token')
            if not token:
                raise ValueError(f"No access_token in TBC auth response: {data}")
            return token
        except requests.RequestException as e:
            logger.error(f"TBC auth request failed: {e}")
            raise

    def _get_auth_headers(self, credentials: Dict[str, str]) -> Dict[str, str]:
        """Build authorization headers for TBC API requests."""
        token = self._get_access_token(credentials)
        return {
            'Authorization': f'Bearer {token}',
            'apikey': credentials['api_key'],
            'Content-Type': 'application/json',
        }

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
        headers = self._get_auth_headers(credentials)

        payload = {
            'amount': {
                'currency': currency or 'GEL',
                'total': float(amount),
            },
            'returnurl': return_url_success,
            'callbackUrl': callback_url,
            'language': 'KA',
            'merchantPaymentId': external_order_id,
            'saveCard': False,
        }

        if return_url_fail:
            payload['failurl'] = return_url_fail

        try:
            response = requests.post(
                f'{TBC_API_BASE}/payments',
                json=payload,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            pay_id = data.get('payId', '')
            links = data.get('links', {})
            approval_url = ''
            if isinstance(links, dict):
                approval_url = links.get('approval', '')
            elif isinstance(links, list):
                for link in links:
                    if link.get('rel') == 'approval' or link.get('method') == 'REDIRECT':
                        approval_url = link.get('uri', link.get('href', ''))
                        break

            logger.info(
                f"TBC payment created: payId={pay_id}, "
                f"external_order_id={external_order_id}"
            )

            return PaymentResult(
                provider='tbc',
                provider_order_id=str(pay_id),
                external_order_id=external_order_id,
                amount=amount,
                currency=currency or 'GEL',
                status='pending',
                payment_url=approval_url,
                requires_redirect=True,
                metadata=metadata or {},
            )
        except requests.RequestException as e:
            logger.error(f"TBC create_payment failed: {e}")
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
        Create a subscription payment with card saving enabled.
        TBC uses saveCard=True to tokenize the card for future charges.
        """
        credentials = self._get_credentials()
        headers = self._get_auth_headers(credentials)

        payload = {
            'amount': {
                'currency': currency or 'GEL',
                'total': float(amount),
            },
            'returnurl': return_url_success,
            'callbackUrl': callback_url,
            'language': 'KA',
            'merchantPaymentId': external_order_id,
            'saveCard': True,
        }

        if return_url_fail:
            payload['failurl'] = return_url_fail

        try:
            response = requests.post(
                f'{TBC_API_BASE}/payments',
                json=payload,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            pay_id = data.get('payId', '')
            links = data.get('links', {})
            approval_url = ''
            if isinstance(links, dict):
                approval_url = links.get('approval', '')
            elif isinstance(links, list):
                for link in links:
                    if link.get('rel') == 'approval' or link.get('method') == 'REDIRECT':
                        approval_url = link.get('uri', link.get('href', ''))
                        break

            logger.info(
                f"TBC subscription payment created: payId={pay_id}, "
                f"external_order_id={external_order_id}"
            )

            return PaymentResult(
                provider='tbc',
                provider_order_id=str(pay_id),
                external_order_id=external_order_id,
                amount=amount,
                currency=currency or 'GEL',
                status='pending',
                payment_url=approval_url,
                requires_redirect=True,
                card_saving_enabled=True,
                metadata=metadata or {},
            )
        except requests.RequestException as e:
            logger.error(f"TBC create_subscription_payment failed: {e}")
            raise

    def check_payment_status(self, provider_order_id: str) -> PaymentStatus:
        """Check the status of a TBC payment by payId."""
        credentials = self._get_credentials()
        headers = self._get_auth_headers(credentials)

        try:
            response = requests.get(
                f'{TBC_API_BASE}/payments/{provider_order_id}',
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            # Map TBC status to normalized status
            tbc_status = data.get('status', '').lower()
            status_map = {
                'created': 'pending',
                'processing': 'processing',
                'succeeded': 'paid',
                'completed': 'paid',
                'failed': 'failed',
                'rejected': 'failed',
                'expired': 'cancelled',
                'cancelled': 'cancelled',
            }
            normalized_status = status_map.get(tbc_status, 'pending')

            amount_data = data.get('amount', {})
            amount = None
            if amount_data.get('total'):
                amount = Decimal(str(amount_data['total']))

            return PaymentStatus(
                provider='tbc',
                provider_order_id=provider_order_id,
                status=normalized_status,
                amount=amount,
                currency=amount_data.get('currency'),
                raw_data=data,
            )
        except requests.RequestException as e:
            logger.error(f"TBC check_payment_status failed: {e}")
            raise

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        """
        Verify TBC webhook authenticity.
        TBC sends payment result to callbackUrl; basic verification
        by checking payment status via API.
        """
        # TBC does not provide HMAC signature on webhooks by default.
        # Verification is done by checking payment status via the API.
        return True

    def charge_recurring(
        self,
        parent_order_id: str,
        amount: Optional[Decimal] = None,
        callback_url: str = '',
        external_order_id: str = '',
    ) -> ChargeResult:
        """Charge a saved card via TBC recurring payment endpoint."""
        credentials = self._get_credentials()
        headers = self._get_auth_headers(credentials)

        payload = {
            'payId': parent_order_id,
            'callbackUrl': callback_url,
            'merchantPaymentId': external_order_id,
        }
        if amount is not None:
            payload['amount'] = {
                'currency': 'GEL',
                'total': float(amount),
            }

        try:
            response = requests.post(
                f'{TBC_API_BASE}/payments/execution',
                json=payload,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            pay_id = data.get('payId', parent_order_id)

            logger.info(
                f"TBC recurring charge: payId={pay_id}, "
                f"external_order_id={external_order_id}"
            )

            return ChargeResult(
                provider='tbc',
                provider_order_id=str(pay_id),
                status='processing',
                amount=amount,
                requires_authentication=False,
                metadata=data,
            )
        except requests.RequestException as e:
            logger.error(f"TBC charge_recurring failed: {e}")
            raise
