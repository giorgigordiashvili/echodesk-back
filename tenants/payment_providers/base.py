"""
Abstract base class and data structures for payment providers.

All payment providers (BOG, Paddle, Flitt, etc.) must implement this interface
to ensure consistent behavior across the application.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict, Any, List


@dataclass
class PaymentResult:
    """Normalized result from creating a payment or subscription payment."""
    provider: str  # 'bog' or 'paddle'
    provider_order_id: str  # Provider's internal order/transaction ID
    external_order_id: str  # Our order ID
    amount: Decimal
    currency: str = 'GEL'
    status: str = 'pending'
    payment_url: Optional[str] = None  # BOG: redirect URL
    checkout_data: Optional[Dict[str, Any]] = None  # Paddle: {transaction_id, ...}
    requires_redirect: bool = False  # True for BOG, False for Paddle
    card_saving_enabled: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentStatus:
    """Normalized result from checking payment status."""
    provider: str
    provider_order_id: str
    status: str  # 'pending', 'paid', 'failed', 'cancelled', 'processing'
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class ChargeResult:
    """Normalized result from a recurring charge."""
    provider: str
    provider_order_id: str
    status: str  # 'processing', 'paid', 'failed'
    amount: Optional[Decimal] = None
    requires_authentication: bool = False
    payment_url: Optional[str] = None  # If 3DS required
    metadata: Dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    """
    Abstract payment provider interface.

    All payment providers must implement the required methods.
    Optional methods raise NotImplementedError by default.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g., 'bog', 'paddle')."""
        ...

    @property
    def manages_recurring_billing(self) -> bool:
        """
        Whether this provider manages recurring billing automatically.
        False for BOG (we charge via cron), True for Paddle.
        """
        return False

    @property
    def requires_redirect(self) -> bool:
        """
        Whether this provider requires redirecting the user to a hosted payment page.
        True for BOG, False for Paddle (overlay checkout).
        """
        return True

    @abstractmethod
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
        """Create a one-time payment."""
        ...

    @abstractmethod
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
        Create a subscription payment (first charge + card save / subscription creation).

        For BOG: creates payment + enables card saving for recurring charges.
        For Paddle: creates a transaction with subscription items.
        """
        ...

    @abstractmethod
    def check_payment_status(self, provider_order_id: str) -> PaymentStatus:
        """Check the status of a payment by the provider's order/transaction ID."""
        ...

    @abstractmethod
    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        """Verify webhook signature/authenticity."""
        ...

    def charge_recurring(
        self,
        parent_order_id: str,
        amount: Optional[Decimal] = None,
        callback_url: str = '',
        external_order_id: str = '',
    ) -> ChargeResult:
        """
        Charge a saved card for recurring payment (BOG only).
        Paddle manages this automatically — calling this on Paddle raises NotImplementedError.
        """
        raise NotImplementedError(
            f"{self.name} does not support manual recurring charges. "
            "This provider manages recurring billing automatically."
        )

    def cancel_subscription(self, provider_subscription_id: str) -> Dict[str, Any]:
        """Cancel a subscription (Paddle only)."""
        raise NotImplementedError(f"{self.name} does not support cancel_subscription")

    def update_subscription_items(
        self,
        provider_subscription_id: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Update subscription line items (Paddle only)."""
        raise NotImplementedError(f"{self.name} does not support update_subscription_items")

    def pause_subscription(self, provider_subscription_id: str) -> Dict[str, Any]:
        """Pause a subscription (Paddle only)."""
        raise NotImplementedError(f"{self.name} does not support pause_subscription")

    def resume_subscription(self, provider_subscription_id: str) -> Dict[str, Any]:
        """Resume a paused subscription (Paddle only)."""
        raise NotImplementedError(f"{self.name} does not support resume_subscription")

    def get_or_create_customer(self, email: str, name: str = '') -> Dict[str, Any]:
        """Get or create a customer record in the provider (Paddle only)."""
        raise NotImplementedError(f"{self.name} does not support customer management")
