"""
Feature and Permission models for dynamic package features
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.contrib.auth.models import Permission as DjangoPermission


class FeatureCategory(models.TextChoices):
    """Feature categories for organization"""
    CORE = 'core', 'Core Features'
    INTEGRATION = 'integration', 'Integrations'
    ANALYTICS = 'analytics', 'Analytics & Reporting'
    COMMUNICATION = 'communication', 'Communication'
    SUPPORT = 'support', 'Support & Services'
    LIMITS = 'limits', 'Limits & Quotas'


class Feature(models.Model):
    """
    Dynamic feature definition

    Features can be enabled/disabled for packages and control what
    functionality tenants have access to.

    For custom packages, features have individual prices that are summed
    to calculate the total package price.
    """
    # Identification
    key = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique identifier for code (e.g., 'whatsapp_integration')"
    )
    name = models.CharField(
        max_length=100,
        help_text="Display name (e.g., 'WhatsApp Integration')"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of what this feature provides"
    )

    # Categorization
    category = models.CharField(
        max_length=20,
        choices=FeatureCategory.choices,
        default=FeatureCategory.CORE
    )

    # Pricing (for custom packages)
    price_per_user_gel = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Price per user in Georgian Lari (for per-user pricing)"
    )
    price_unlimited_gel = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Price for unlimited users in Georgian Lari (flat rate)"
    )

    # Display
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon name or emoji for UI display"
    )
    sort_order = models.IntegerField(
        default=0,
        help_text="Order for display in lists"
    )

    # Metadata
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this feature is currently available"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'sort_order', 'name']
        verbose_name = 'Feature'
        verbose_name_plural = 'Features'

    def __str__(self):
        return f"{self.name} ({self.key})"


# Using Django's built-in Permission model instead of custom Permission
# No need for a separate Permission model - we use django.contrib.auth.models.Permission


class FeaturePermission(models.Model):
    """
    Link features to Django's built-in permissions

    Defines which permissions are granted when a feature is enabled
    """
    feature = models.ForeignKey(
        Feature,
        on_delete=models.CASCADE,
        related_name='permissions'
    )
    permission = models.ForeignKey(
        DjangoPermission,
        on_delete=models.CASCADE,
        related_name='feature_permissions'
    )

    # Optional: permission can be required or optional within a feature
    is_required = models.BooleanField(
        default=True,
        help_text="If False, this permission can be selectively granted"
    )

    class Meta:
        unique_together = ['feature', 'permission']
        verbose_name = 'Feature Permission'
        verbose_name_plural = 'Feature Permissions'

    def __str__(self):
        return f"{self.feature.name} → {self.permission.name}"


class TenantFeature(models.Model):
    """
    Track which features are enabled for each tenant

    This is populated when a tenant subscribes to a package and
    can be used to check feature availability at runtime
    """
    tenant = models.ForeignKey(
        'Tenant',
        on_delete=models.CASCADE,
        related_name='tenant_features'
    )
    feature = models.ForeignKey(
        Feature,
        on_delete=models.CASCADE,
        related_name='tenant_features'
    )

    # Track when feature was enabled/disabled
    enabled_at = models.DateTimeField(auto_now_add=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Optional custom values for this tenant
    # (can override package defaults)
    custom_value = models.JSONField(
        null=True,
        blank=True,
        help_text="Tenant-specific feature configuration"
    )

    class Meta:
        unique_together = ['tenant', 'feature']
        verbose_name = 'Tenant Feature'
        verbose_name_plural = 'Tenant Features'

    def __str__(self):
        return f"{self.tenant.schema_name} → {self.feature.name}"


class TenantPermission(models.Model):
    """
    Track which permissions are AVAILABLE to a tenant for granting to users

    This model defines the "permission pool" that tenant admins can grant to users.
    Based on the tenant's selected features, certain permissions become available.

    Flow:
    1. EchoDesk admin creates Features with Django Permissions
    2. Tenant selects Features → Tenant gets TenantPermission records created
    3. Tenant admin can grant these permissions to users via User model fields
       (e.g., can_view_all_tickets, can_manage_users, etc.)

    Example:
    - If tenant has "Advanced Analytics" feature, they get TenantPermission for "view_reports"
    - Tenant admin can then enable user.can_view_reports = True for specific users
    - The User.has_permission() method checks the boolean fields
    """
    tenant = models.ForeignKey(
        'Tenant',
        on_delete=models.CASCADE,
        related_name='tenant_permissions'
    )
    permission = models.ForeignKey(
        DjangoPermission,
        on_delete=models.CASCADE,
        related_name='tenant_permissions'
    )

    # Track source of permission
    granted_by_feature = models.ForeignKey(
        Feature,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Which feature granted this permission"
    )

    # Track when permission was granted/revoked
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['tenant', 'permission']
        verbose_name = 'Tenant Permission'
        verbose_name_plural = 'Tenant Permissions'

    def __str__(self):
        return f"{self.tenant.schema_name} → {self.permission.name}"


# UserPermission removed - using existing User model boolean fields instead
# Tenant admins grant permissions to users via the User model's can_* fields
# TenantPermission controls which permissions are available to grant based on package features
