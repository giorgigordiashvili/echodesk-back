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
from .models import TenantSubscription, TenantFeature
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

        # Default values
        request.subscription = None
        request.subscription_package = None
        request.subscription_features = {}

        # Skip if no tenant or if public schema
        if not hasattr(request, 'tenant'):
            return

        if request.tenant.schema_name == get_public_schema_name():
            return

        # Try to get active subscription
        try:
            subscription = TenantSubscription.objects.select_related('package').get(
                tenant=request.tenant,
                is_active=True
            )

            request.subscription = subscription
            request.subscription_package = subscription.package

            # Create features dict for easy access (legacy features)
            package = subscription.package
            request.subscription_features = {
                'ticket_management': package.ticket_management,
                'email_integration': package.email_integration,
                'sip_calling': package.sip_calling,
                'facebook_integration': package.facebook_integration,
                'instagram_integration': package.instagram_integration,
                'whatsapp_integration': package.whatsapp_integration,
                'advanced_analytics': package.advanced_analytics,
                'api_access': package.api_access,
                'custom_integrations': package.custom_integrations,
                'priority_support': package.priority_support,
                'dedicated_account_manager': package.dedicated_account_manager,
            }

            # Add dynamic features to the dict
            tenant_features = TenantFeature.objects.filter(
                tenant=request.tenant,
                is_active=True,
                feature__is_active=True
            ).select_related('feature')

            for tf in tenant_features:
                # Use feature key as dict key
                request.subscription_features[tf.feature.key] = True

        except TenantSubscription.DoesNotExist:
            pass
        except Exception as e:
            # Log error but don't break the request
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error loading subscription for tenant {request.tenant.schema_name}: {e}")

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
