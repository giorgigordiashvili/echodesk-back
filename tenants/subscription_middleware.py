"""
Subscription middleware for EchoDesk

This middleware adds subscription information to every request,
making it easy to check features and limits throughout the application.

Usage:
    # In your views, you can access:
    request.subscription  # TenantSubscription object
    request.subscription_features  # Dict of all features (legacy + dynamic)
    request.has_feature(feature_name)  # Helper method for legacy features
    request.tenant_has_feature(feature_key)  # Check if tenant has dynamic feature enabled
    request.tenant_has_permission_available(key)  # Check if permission is available to grant

    # User permissions are checked via user.has_permission() method (existing system)
"""

from tenant_schemas.utils import get_public_schema_name
from .models import TenantSubscription
from .subscription_service import SubscriptionService


class SubscriptionMiddleware:
    """
    Middleware to attach subscription information to requests

    Adds the following attributes to request:
    - request.subscription: TenantSubscription object or None
    - request.subscription_features: Dict of feature flags
    - request.has_feature(name): Helper method to check features
    - request.subscription_package: Package object or None
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Attach subscription info before processing the request
        self._attach_subscription_info(request)

        response = self.get_response(request)

        return response

    def _attach_subscription_info(self, request):
        """Attach subscription information to the request"""
        import logging
        logger = logging.getLogger(__name__)

        # Default values
        request.subscription = None
        request.subscription_package = None
        request.subscription_features = {}

        # Skip if no tenant or if public schema
        if not hasattr(request, 'tenant'):
            if '/admin/tenants/feature/' in request.path:
                logger.info(f"🔍 SubscriptionMiddleware: No tenant attribute on request for {request.path}")
            return

        schema_name = request.tenant.schema_name
        public_schema = get_public_schema_name()

        if '/admin/tenants/feature/' in request.path:
            logger.info(f"🔍 SubscriptionMiddleware: Schema={schema_name}, Public={public_schema}, Path={request.path}")

        # Skip for public schema - especially important for admin paths
        if schema_name == public_schema:
            if '/admin/tenants/feature/' in request.path or request.path.startswith('/admin/'):
                logger.info(f"🔍 SubscriptionMiddleware: Skipping (public schema) for path: {request.path}")
            return

        # Try to get active subscription
        try:
            subscription = TenantSubscription.objects.prefetch_related('selected_features').get(
                tenant=request.tenant,
                is_active=True
            )

            request.subscription = subscription
            request.subscription_package = None  # Package system removed

            # Initialize features dict
            request.subscription_features = {}

            # Add features from selected_features (single source of truth)
            for feature in subscription.selected_features.filter(is_active=True):
                request.subscription_features[feature.key] = True

        except TenantSubscription.DoesNotExist:
            pass
        except Exception as e:
            # Log error but don't break the request
            import logging
            from django.db import connection
            logger = logging.getLogger(__name__)
            logger.error(f"Error loading subscription for tenant {request.tenant.schema_name}: {e}")

            # If the transaction is poisoned, roll it back
            if connection.connection:
                status = connection.connection.get_transaction_status()
                if status == 3:  # IN_ERROR
                    logger.warning(f"Transaction poisoned in subscription middleware, rolling back")
                    connection.rollback()

        # Add helper methods to request
        request.has_feature = lambda feature_name: request.subscription_features.get(feature_name, False)

        # Check dynamic feature by key
        request.tenant_has_feature = lambda feature_key: (
            SubscriptionService.check_tenant_feature(request.tenant, feature_key)
            if hasattr(request, 'tenant') else False
        )

        # Check if tenant has a permission available (for admin UI to show/hide permission toggles)
        request.tenant_has_permission_available = lambda permission_key: (
            SubscriptionService.check_tenant_has_permission_available(request.tenant, permission_key)
            if hasattr(request, 'tenant') else False
        )
