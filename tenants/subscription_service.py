"""
Subscription service for managing tenant features and permissions

Handles the automatic provisioning of features and permissions when
a tenant subscribes to a package or changes packages.
"""

from django.db import transaction
from django.utils import timezone
from .models import (
    TenantSubscription, TenantFeature, TenantPermission,
    PackageFeature, FeaturePermission
)
import logging

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing subscription features and permissions"""

    @staticmethod
    def sync_tenant_features(subscription):
        """
        Sync tenant features based on their subscription package

        This method:
        1. Gets all features from the package
        2. Creates/activates TenantFeature records
        3. Deactivates features not in the package
        4. Syncs permissions for each feature

        Args:
            subscription: TenantSubscription instance

        Returns:
            dict: Summary of changes made
        """
        with transaction.atomic():
            tenant = subscription.tenant
            package = subscription.package

            # Get all active package features
            package_features = PackageFeature.objects.filter(
                package=package,
                feature__is_active=True
            ).select_related('feature')

            enabled_features = []
            disabled_features = []
            permissions_granted = 0

            # Enable features from package
            for pf in package_features:
                feature = pf.feature

                # Get or create tenant feature
                tenant_feature, created = TenantFeature.objects.get_or_create(
                    tenant=tenant,
                    feature=feature,
                    defaults={
                        'is_active': True,
                        'custom_value': pf.custom_value
                    }
                )

                # Reactivate if it was disabled
                if not tenant_feature.is_active:
                    tenant_feature.is_active = True
                    tenant_feature.disabled_at = None
                    tenant_feature.save()
                    enabled_features.append(feature.name)

                # Update custom value if changed
                if tenant_feature.custom_value != pf.custom_value:
                    tenant_feature.custom_value = pf.custom_value
                    tenant_feature.save()

                if created:
                    enabled_features.append(feature.name)

                # Grant permissions for this feature
                permissions_granted += SubscriptionService._sync_feature_permissions(
                    tenant, feature
                )

            # Disable features not in package
            feature_ids = [pf.feature_id for pf in package_features]
            disabled_tenant_features = TenantFeature.objects.filter(
                tenant=tenant,
                is_active=True
            ).exclude(feature_id__in=feature_ids)

            for tf in disabled_tenant_features:
                tf.is_active = False
                tf.disabled_at = timezone.now()
                tf.save()
                disabled_features.append(tf.feature.name)

                # Revoke permissions for disabled features
                SubscriptionService._revoke_feature_permissions(tenant, tf.feature)

            logger.info(
                f"Synced features for tenant {tenant.schema_name}: "
                f"enabled={len(enabled_features)}, disabled={len(disabled_features)}, "
                f"permissions={permissions_granted}"
            )

            return {
                'enabled_features': enabled_features,
                'disabled_features': disabled_features,
                'permissions_granted': permissions_granted
            }

    @staticmethod
    def _sync_feature_permissions(tenant, feature):
        """
        Grant all permissions associated with a feature to a tenant

        Args:
            tenant: Tenant instance
            feature: Feature instance

        Returns:
            int: Number of permissions granted
        """
        # Get all permissions for this feature
        feature_permissions = FeaturePermission.objects.filter(
            feature=feature
        ).select_related('permission')

        granted_count = 0

        for fp in feature_permissions:
            permission = fp.permission

            # Get or create tenant permission
            tenant_perm, created = TenantPermission.objects.get_or_create(
                tenant=tenant,
                permission=permission,
                defaults={
                    'is_active': True,
                    'granted_by_feature': feature
                }
            )

            # Reactivate if it was revoked
            if not tenant_perm.is_active:
                tenant_perm.is_active = True
                tenant_perm.revoked_at = None
                tenant_perm.granted_by_feature = feature
                tenant_perm.save()
                granted_count += 1

            if created:
                granted_count += 1

        return granted_count

    @staticmethod
    def _revoke_feature_permissions(tenant, feature):
        """
        Revoke permissions that were granted by this feature

        Only revokes permissions that:
        1. Were granted by this specific feature
        2. Are not granted by any other active feature

        Args:
            tenant: Tenant instance
            feature: Feature instance
        """
        # Get all permissions granted by this feature
        feature_permission_ids = FeaturePermission.objects.filter(
            feature=feature
        ).values_list('permission_id', flat=True)

        # Get active features for tenant (excluding this one)
        other_active_features = TenantFeature.objects.filter(
            tenant=tenant,
            is_active=True
        ).exclude(feature=feature).values_list('feature_id', flat=True)

        # Get permissions granted by other active features
        protected_permission_ids = FeaturePermission.objects.filter(
            feature_id__in=other_active_features
        ).values_list('permission_id', flat=True)

        # Revoke only permissions not granted by other features
        revokable_permission_ids = set(feature_permission_ids) - set(protected_permission_ids)

        TenantPermission.objects.filter(
            tenant=tenant,
            permission_id__in=revokable_permission_ids,
            granted_by_feature=feature
        ).update(
            is_active=False,
            revoked_at=timezone.now()
        )

    @staticmethod
    def check_user_permission(user, permission_key):
        """
        Check if a user has a specific permission

        Checks:
        1. User's direct permissions (UserPermission)
        2. Tenant's available permissions (TenantPermission)

        Args:
            user: User instance
            permission_key: Permission key (e.g., 'tickets.create')

        Returns:
            bool: True if user has permission
        """
        from .models import UserPermission, TenantPermission, Permission

        try:
            # Get the permission object
            permission = Permission.objects.get(key=permission_key, is_active=True)

            # Check if user has direct permission
            has_user_permission = UserPermission.objects.filter(
                user=user,
                permission=permission,
                is_active=True
            ).exists()

            if has_user_permission:
                return True

            # Check if tenant has this permission available
            # (Assuming user has a tenant relationship)
            if hasattr(user, 'tenant'):
                has_tenant_permission = TenantPermission.objects.filter(
                    tenant=user.tenant,
                    permission=permission,
                    is_active=True
                ).exists()

                return has_tenant_permission

            return False

        except Permission.DoesNotExist:
            logger.warning(f"Permission '{permission_key}' not found")
            return False
        except Exception as e:
            logger.error(f"Error checking permission '{permission_key}' for user {user.id}: {e}")
            return False

    @staticmethod
    def check_tenant_feature(tenant, feature_key):
        """
        Check if a tenant has a specific feature enabled

        Args:
            tenant: Tenant instance
            feature_key: Feature key (e.g., 'whatsapp_integration')

        Returns:
            bool: True if feature is enabled
        """
        return TenantFeature.objects.filter(
            tenant=tenant,
            feature__key=feature_key,
            feature__is_active=True,
            is_active=True
        ).exists()
