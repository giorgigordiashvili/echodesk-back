"""
Django signals for automatic feature and permission synchronization

Automatically syncs tenant features and permissions when:
- A new subscription is created
- A subscription package is changed
- A subscription is activated/deactivated
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TenantSubscription
from .subscription_service import SubscriptionService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TenantSubscription)
def sync_subscription_features(sender, instance, created, **kwargs):
    """
    Automatically sync tenant features and permissions when subscription changes

    Triggered on:
    - New subscription creation
    - Subscription package change
    - Subscription activation/deactivation
    """
    try:
        # Only sync if subscription is active
        if instance.is_active:
            logger.info(f"Syncing features for subscription: {instance}")
            result = SubscriptionService.sync_tenant_features(instance)
            logger.info(
                f"Feature sync completed for {instance.tenant.schema_name}: "
                f"{result['enabled_features'].__len__()} enabled, "
                f"{result['disabled_features'].__len__()} disabled, "
                f"{result['permissions_granted']} permissions granted"
            )
        else:
            logger.info(f"Subscription {instance} is inactive, skipping feature sync")

    except Exception as e:
        # Handle case where tenant schema migrations haven't completed yet
        error_msg = str(e).lower()
        if 'does not exist' in error_msg or 'relation' in error_msg:
            logger.warning(
                f"Tenant schema tables not ready yet for {instance.tenant.schema_name}, "
                f"skipping feature sync. This is normal during initial tenant creation."
            )
        else:
            logger.error(f"Error syncing features for subscription {instance}: {e}", exc_info=True)
