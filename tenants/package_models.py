from django.db import models
from django.core.exceptions import ValidationError


class PricingModel(models.TextChoices):
    """Pricing model choices"""
    AGENT_BASED = 'agent', 'Agent-based'
    CRM_BASED = 'crm', 'CRM-based'


class Package(models.Model):
    """
    Package/Plan definition model
    Defines available subscription packages
    """
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField()
    pricing_model = models.CharField(
        max_length=10,
        choices=PricingModel.choices,
        default=PricingModel.AGENT_BASED
    )
    
    # Pricing
    price_gel = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price in Georgian Lari")
    billing_period = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
        ],
        default='monthly'
    )
    
    # Limits
    max_users = models.IntegerField(null=True, blank=True, help_text="Maximum users (null = unlimited for agent-based)")
    max_whatsapp_messages = models.IntegerField(help_text="WhatsApp messages per month")
    max_storage_gb = models.IntegerField(default=5, help_text="Storage limit in GB")
    
    # Features
    ticket_management = models.BooleanField(default=True)
    email_integration = models.BooleanField(default=True)
    sip_calling = models.BooleanField(default=False)
    facebook_integration = models.BooleanField(default=False)
    instagram_integration = models.BooleanField(default=False)
    whatsapp_integration = models.BooleanField(default=False)
    advanced_analytics = models.BooleanField(default=False)
    api_access = models.BooleanField(default=False)
    custom_integrations = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    dedicated_account_manager = models.BooleanField(default=False)
    
    # Display settings
    is_highlighted = models.BooleanField(default=False, help_text="Show as featured/recommended")
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['pricing_model', 'sort_order', 'price_gel']
    
    def __str__(self):
        pricing_suffix = "/agent/month" if self.pricing_model == PricingModel.AGENT_BASED else "/month"
        return f"{self.display_name} - {self.price_gel}₾{pricing_suffix}"
    
    def clean(self):
        """Validate package configuration"""
        if self.pricing_model == PricingModel.CRM_BASED and not self.max_users:
            raise ValidationError("CRM-based packages must have a user limit")
        
        if self.pricing_model == PricingModel.AGENT_BASED and self.max_users:
            raise ValidationError("Agent-based packages should not have user limits")
    
    @property
    def features_list(self):
        """Return list of enabled features"""
        features = []
        if self.ticket_management:
            features.append("Complete Ticket Management System")
        if self.email_integration:
            features.append("Email Integration")
        if self.sip_calling:
            features.append("Integrated SIP Phone System")
        if self.facebook_integration:
            features.append("Facebook Messenger Integration")
        if self.instagram_integration:
            features.append("Instagram DM Integration")
        if self.whatsapp_integration:
            features.append("WhatsApp Business API")
        if self.advanced_analytics:
            features.append("Advanced Analytics Dashboard")
        if self.api_access:
            features.append("API Access")
        if self.custom_integrations:
            features.append("Custom Integrations")
        if self.priority_support:
            features.append("Priority Support")
        if self.dedicated_account_manager:
            features.append("Dedicated Account Manager")
        
        # Add limits info
        if self.max_users:
            features.insert(0, f"Up to {self.max_users} Users")
        features.append(f"Up to {self.max_whatsapp_messages:,} WhatsApp messages/month")
        features.append(f"{self.max_storage_gb}GB Storage")
        
        return features


class TenantSubscription(models.Model):
    """
    Tracks tenant's current subscription and usage
    """
    tenant = models.OneToOneField('Tenant', on_delete=models.CASCADE, related_name='subscription')
    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="DEPRECATED: Legacy package reference (kept for backward compatibility)"
    )

    # Feature-based subscription
    selected_features = models.ManyToManyField(
        'Feature',
        related_name='subscriptions',
        blank=True,
        help_text="Features selected for this subscription"
    )
    agent_count = models.IntegerField(
        default=10,
        help_text="Number of agents (in increments of 10: 10, 20, 30... 200)"
    )

    # Subscription status
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Usage tracking
    current_users = models.IntegerField(default=0)
    whatsapp_messages_used = models.IntegerField(default=0)
    storage_used_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Billing
    last_billed_at = models.DateTimeField(null=True, blank=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenants_tenant_subscription'
    
    def __str__(self):
        if self.package:
            return f"{self.tenant.name} - {self.package.display_name}"
        feature_count = self.selected_features.count()
        return f"{self.tenant.name} - {self.agent_count} agents, {feature_count} features"

    @property
    def monthly_cost(self):
        """Calculate monthly cost based on selected features and agent count"""
        # Import Feature model
        from .feature_models import Feature

        # New feature-based pricing model
        if self.selected_features.exists():
            total_cost_per_agent = sum(
                feature.price_per_user_gel
                for feature in self.selected_features.all()
            )
            return total_cost_per_agent * self.agent_count

        # Legacy package-based pricing (for backward compatibility)
        if self.package:
            if self.package.pricing_model == PricingModel.AGENT_BASED:
                return self.package.price_gel * self.agent_count
            return self.package.price_gel

        # No package and no features = free
        return 0
    
    @property
    def is_over_user_limit(self):
        """Check if tenant is over user limit"""
        # New model: check against agent_count
        if self.selected_features.exists():
            return self.current_users > self.agent_count

        # Legacy model: check against package max_users
        if self.package and self.package.max_users:
            return self.current_users > self.package.max_users

        return False
    
    @property
    def is_over_whatsapp_limit(self):
        """Check if tenant is over WhatsApp message limit"""
        # Feature-based subscriptions: default 10k limit
        if self.selected_features.exists():
            return self.whatsapp_messages_used > 10000

        # Package-based subscriptions
        if not self.package or not self.package.max_whatsapp_messages:
            return False  # No limit set
        return self.whatsapp_messages_used > self.package.max_whatsapp_messages

    @property
    def is_over_storage_limit(self):
        """Check if tenant is over storage limit"""
        # Feature-based subscriptions: default 100GB limit
        if self.selected_features.exists():
            return self.storage_used_gb > 100

        # Package-based subscriptions
        if not self.package:
            return False  # No limit set
        return self.storage_used_gb > self.package.max_storage_gb
    
    def can_add_user(self):
        """Check if tenant can add another user"""
        # New model: check against agent_count
        if self.selected_features.exists():
            return self.current_users < self.agent_count

        # Legacy model: check against package max_users
        if self.package and self.package.max_users:
            return self.current_users < self.package.max_users

        return True  # No limit
    
    def can_send_whatsapp_message(self):
        """Check if tenant can send WhatsApp message (deprecated - always returns True)"""
        return True  # WhatsApp limits removed


class UsageLog(models.Model):
    """
    Track usage events for billing and analytics
    """
    subscription = models.ForeignKey(TenantSubscription, on_delete=models.CASCADE, related_name='usage_logs')
    
    event_type = models.CharField(
        max_length=50,
        choices=[
            ('user_added', 'User Added'),
            ('user_removed', 'User Removed'),
            ('whatsapp_message', 'WhatsApp Message'),
            ('storage_usage', 'Storage Usage'),
            ('feature_used', 'Feature Used'),
        ]
    )
    
    quantity = models.IntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'tenants_usage_log'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.subscription.tenant.name} - {self.event_type} ({self.quantity})"
