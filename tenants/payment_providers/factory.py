"""
Payment provider factory.

Returns the appropriate payment provider instance based on tenant configuration
or explicit provider name.
"""
import logging
from typing import Optional

from .base import PaymentProvider
from .bog import BOGPaymentProvider
from .paddle import PaddlePaymentProvider
from .tbc import TBCPaymentProvider
from .flitt import FlittPaymentProvider

logger = logging.getLogger(__name__)

# Cached provider instances (singletons)
_providers = {}


def _get_provider_instance(provider_name: str) -> PaymentProvider:
    """Get or create a cached provider instance."""
    if provider_name not in _providers:
        if provider_name == 'bog':
            _providers[provider_name] = BOGPaymentProvider()
        elif provider_name == 'paddle':
            _providers[provider_name] = PaddlePaymentProvider()
        elif provider_name == 'tbc':
            _providers[provider_name] = TBCPaymentProvider()
        elif provider_name == 'flitt':
            _providers[provider_name] = FlittPaymentProvider()
        else:
            raise ValueError(f"Unknown payment provider: {provider_name}")
    return _providers[provider_name]


def get_payment_provider(
    tenant=None,
    provider_name: Optional[str] = None,
) -> PaymentProvider:
    """
    Get the payment provider for a tenant or by explicit name.

    Priority:
    1. Explicit provider_name if given
    2. tenant.payment_provider field
    3. Default: 'bog'
    """
    if provider_name:
        return _get_provider_instance(provider_name)

    if tenant and hasattr(tenant, 'payment_provider'):
        return _get_provider_instance(tenant.payment_provider)

    return _get_provider_instance('bog')


def get_ecommerce_payment_provider(tenant) -> PaymentProvider:
    """
    Get the payment provider for a tenant's ecommerce store.

    Uses ecommerce_settings.ecommerce_payment_provider if available,
    otherwise falls back to tenant.payment_provider.
    """
    try:
        ecommerce_settings = tenant.ecommerce_settings
        if hasattr(ecommerce_settings, 'ecommerce_payment_provider'):
            return _get_provider_instance(ecommerce_settings.ecommerce_payment_provider)
    except Exception:
        pass

    return get_payment_provider(tenant=tenant)
