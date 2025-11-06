from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from tenant_schemas.models import TenantMixin

# Import feature models
from .feature_models import (
    Feature, FeaturePermission,
    PackageFeature, TenantFeature, TenantPermission,
    FeatureCategory
)
from django.contrib.auth.models import Permission


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
    max_whatsapp_messages = models.IntegerField(null=True, blank=True, help_text="WhatsApp messages per month (deprecated)")
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
    is_custom = models.BooleanField(default=False, help_text="Custom package created for specific tenant")
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
        """Return list of enabled features (legacy + dynamic)"""
        features = []

        # Legacy boolean features (for backward compatibility)
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

        # Dynamic features from PackageFeature model
        for pf in self.package_features.select_related('feature').filter(feature__is_active=True):
            features.append(pf.feature.name)

        # Add limits info
        if self.max_users:
            features.insert(0, f"Up to {self.max_users} Users")
        if self.max_whatsapp_messages:
            features.append(f"Up to {self.max_whatsapp_messages:,} WhatsApp messages/month")
        features.append(f"{self.max_storage_gb}GB Storage")

        return features

    def get_dynamic_features(self):
        """Get all dynamic features for this package"""
        return self.package_features.select_related('feature').filter(feature__is_active=True)

    def has_feature(self, feature_key):
        """Check if package has a specific feature by key"""
        return self.package_features.filter(feature__key=feature_key, feature__is_active=True).exists()

    def calculate_custom_price(self, user_count=None):
        """
        Calculate price for custom package based on selected features

        For agent-based (per-user): sum of (feature.price_per_user_gel * user_count)
        For CRM-based (unlimited): sum of feature.price_unlimited_gel

        Args:
            user_count: Number of users for agent-based pricing (overrides max_users)
        """
        if not self.is_custom:
            return self.price_gel

        total = 0
        package_features = self.package_features.filter(feature__is_active=True).select_related('feature')

        for pf in package_features:
            feature = pf.feature

            # Agent-based: per-user pricing
            if self.pricing_model == PricingModel.AGENT_BASED:
                users = user_count if user_count is not None else (self.max_users or 1)
                total += feature.price_per_user_gel * users

            # CRM-based: unlimited pricing
            else:
                total += feature.price_unlimited_gel

        return total


class Tenant(TenantMixin):
    """
    Tenant model for multi-tenancy support.
    Each tenant represents a separate organization/company.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # Owner/admin contact information
    admin_email = models.EmailField()
    admin_name = models.CharField(max_length=100)
    
    # Legacy plan field (kept for backward compatibility)
    plan = models.CharField(
        max_length=50, 
        default='basic',
        choices=[
            ('basic', 'Basic'),
            ('premium', 'Premium'),
            ('enterprise', 'Enterprise'),
        ]
    )
    
    # Legacy limits (kept for backward compatibility)
    max_users = models.IntegerField(default=10)
    max_storage = models.BigIntegerField(default=1073741824)  # 1GB in bytes
    
    # Language preference for tenant dashboard
    preferred_language = models.CharField(
        max_length=10,
        default='en',
        choices=[
            ('en', 'English'),
            ('ru', 'Russian'),
            ('ka', 'Georgian'),
        ],
        help_text='Preferred language for the frontend dashboard'
    )

    # Branding
    logo = models.ImageField(upload_to='tenant_logos/', blank=True, null=True, help_text="Company logo")

    # Ticket settings
    min_users_per_ticket = models.IntegerField(
        default=0,
        help_text="Minimum number of users required on a ticket after initial assignment. 0 = no minimum. Only superadmins can reduce below this number."
    )
    only_superadmin_can_delete_tickets = models.BooleanField(
        default=False,
        help_text="If True, only superadmins can delete tickets. If False, both ticket owners and superadmins can delete tickets."
    )

    # Frontend deployment fields
    frontend_url = models.URLField(blank=True, null=True, help_text="URL of the deployed frontend")
    deployment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('deploying', 'Deploying'),
            ('deployed', 'Deployed'),
            ('failed', 'Failed'),
        ],
        default='pending',
        help_text="Status of the frontend deployment"
    )
    
    # Auto-created schema name is available as self.schema_name
    # domain_url inherited from TenantMixin
    
    auto_create_schema = True
    auto_drop_schema = False
    
    class Meta:
        db_table = 'tenants_tenant'
    
    def __str__(self):
        return f"{self.name} ({self.schema_name})"
    
    @property
    def is_public_schema(self):
        """Check if this is the public schema"""
        return self.schema_name == 'public'
    
    @property
    def current_package(self):
        """Get current package from subscription"""
        try:
            return self.subscription.package
        except:
            return None
    
    @property
    def current_subscription(self):
        """Get current subscription"""
        try:
            return self.subscription
        except:
            return None


class TenantSubscription(models.Model):
    """
    Tracks tenant's current subscription and usage
    """
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='subscription')
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    
    # Subscription status
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Agent-based pricing info
    agent_count = models.IntegerField(default=1, help_text="Number of agents for agent-based pricing")
    
    # Usage tracking
    current_users = models.IntegerField(default=0)
    whatsapp_messages_used = models.IntegerField(default=0)
    storage_used_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Billing
    last_billed_at = models.DateTimeField(null=True, blank=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)

    # Trial information
    is_trial = models.BooleanField(default=False, help_text='Whether this is a trial subscription')
    trial_ends_at = models.DateTimeField(null=True, blank=True, help_text='When the trial period ends')
    trial_converted = models.BooleanField(default=False, help_text='Whether trial was converted to paid subscription')

    # Saved card for recurring payments
    parent_order_id = models.CharField(max_length=100, blank=True, null=True, help_text='BOG order ID with saved card')

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenants_tenant_subscription'
    
    def __str__(self):
        return f"{self.tenant.name} - {self.package.display_name}"
    
    @property
    def monthly_cost(self):
        """Calculate monthly cost based on package and agent count"""
        if self.package.pricing_model == PricingModel.AGENT_BASED:
            return self.package.price_gel * self.agent_count
        return self.package.price_gel
    
    @property
    def is_over_user_limit(self):
        """Check if tenant is over user limit"""
        if not self.package.max_users:
            return False
        return self.current_users > self.package.max_users
    
    @property
    def is_over_whatsapp_limit(self):
        """Check if tenant is over WhatsApp message limit"""
        if not self.package.max_whatsapp_messages:
            return False  # No limit set
        return self.whatsapp_messages_used > self.package.max_whatsapp_messages
    
    @property
    def is_over_storage_limit(self):
        """Check if tenant is over storage limit"""
        return self.storage_used_gb > self.package.max_storage_gb
    
    def can_add_user(self):
        """Check if tenant can add another user"""
        if not self.package.max_users:
            return True
        return self.current_users < self.package.max_users
    
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


class SavedCard(models.Model):
    """
    Store saved payment card details from Bank of Georgia for recurring payments
    """
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='saved_cards',
        help_text='Tenant that owns this saved card'
    )

    # BOG order ID for recurring charges
    parent_order_id = models.CharField(
        max_length=100,
        unique=True,
        help_text='BOG parent order ID used for recurring payments'
    )

    # Card details (masked/safe to store)
    card_type = models.CharField(
        max_length=20,
        blank=True,
        help_text='Card type (e.g., mc, visa)'
    )
    masked_card_number = models.CharField(
        max_length=20,
        blank=True,
        help_text='Masked card number (e.g., 531125***1450)'
    )
    card_expiry = models.CharField(
        max_length=7,
        blank=True,
        help_text='Card expiry date (MM/YY format)'
    )

    # Payment metadata
    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='Initial transaction ID'
    )
    saved_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When the card was saved'
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this card is active for recurring payments'
    )
    is_default = models.BooleanField(
        default=False,
        help_text='Whether this is the default card for automatic payments'
    )

    class Meta:
        db_table = 'tenants_saved_card'
        verbose_name = 'Saved Card'
        verbose_name_plural = 'Saved Cards'
        ordering = ['-is_default', '-saved_at']

    def __str__(self):
        card_display = f"{self.card_type.upper()} {self.masked_card_number}" if self.masked_card_number else "Card"
        default_indicator = " (Default)" if self.is_default else ""
        return f"{self.tenant.name} - {card_display}{default_indicator}"

    def save(self, *args, **kwargs):
        # If this card is being set as default, unset other default cards for this tenant
        if self.is_default:
            SavedCard.objects.filter(tenant=self.tenant, is_default=True).exclude(id=self.id).update(is_default=False)

        # If this is the first active card for the tenant, make it default
        if self.is_active and not SavedCard.objects.filter(tenant=self.tenant, is_active=True).exclude(id=self.id).exists():
            self.is_default = True

        super().save(*args, **kwargs)


class PaymentOrder(models.Model):
    """
    Track payment orders and metadata for subscription payments
    """
    order_id = models.CharField(max_length=100, unique=True, db_index=True)
    bog_order_id = models.CharField(max_length=100, blank=True, null=True, help_text='BOG internal order ID for saved card charging')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True)
    package = models.ForeignKey(Package, on_delete=models.CASCADE, null=True, blank=True, help_text='Package for subscription payments. Null for card-only payments.')

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='GEL')
    agent_count = models.IntegerField(default=1)

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending'
    )

    payment_url = models.URLField(max_length=500, blank=True)
    card_saved = models.BooleanField(default=False, help_text='Whether card was saved for recurring payments')
    is_trial_payment = models.BooleanField(default=False, help_text='Whether this is a 0 GEL trial payment')
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'tenants_payment_order'
        ordering = ['-created_at']

    def __str__(self):
        tenant_name = self.tenant.name if self.tenant else "Registration"
        return f"{self.order_id} - {tenant_name} - {self.status}"


class Invoice(models.Model):
    """
    Invoice generated for successful payments
    """
    invoice_number = models.CharField(max_length=100, unique=True, db_index=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    payment_order = models.OneToOneField(PaymentOrder, on_delete=models.CASCADE, related_name='invoice')

    # Invoice details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='GEL')

    # What was invoiced for
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    agent_count = models.IntegerField(default=1)

    # Dates
    invoice_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    paid_date = models.DateTimeField(null=True, blank=True)

    # PDF generation
    pdf_generated = models.BooleanField(default=False)
    pdf_url = models.URLField(max_length=500, blank=True)

    # Additional data
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'tenants_invoice'
        ordering = ['-invoice_date']

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.tenant.name} - {self.amount} {self.currency}"

    def generate_invoice_number(self):
        """Generate a unique invoice number"""
        from datetime import datetime
        date_str = datetime.now().strftime('%Y%m')
        # Find the last invoice for this month
        last_invoice = Invoice.objects.filter(
            invoice_number__startswith=f'INV-{date_str}'
        ).order_by('-invoice_number').first()

        if last_invoice:
            # Extract the sequence number and increment
            try:
                last_seq = int(last_invoice.invoice_number.split('-')[-1])
                new_seq = last_seq + 1
            except (ValueError, IndexError):
                new_seq = 1
        else:
            new_seq = 1

        return f'INV-{date_str}-{new_seq:04d}'

    def save(self, *args, **kwargs):
        # Auto-generate invoice number if not set
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        super().save(*args, **kwargs)


class PendingRegistration(models.Model):
    """
    Stores tenant registration data temporarily until payment is completed
    """
    schema_name = models.CharField(max_length=63, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    admin_email = models.EmailField()
    admin_password = models.CharField(max_length=255)  # Will be hashed
    admin_first_name = models.CharField(max_length=100)
    admin_last_name = models.CharField(max_length=100)

    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    agent_count = models.IntegerField(default=1)
    order_id = models.CharField(max_length=100, unique=True, db_index=True, blank=True, default='')

    # Status tracking
    is_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'tenants_pending_registration'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.schema_name} - {self.name} - {'Processed' if self.is_processed else 'Pending'}"

    def save(self, *args, **kwargs):
        # Set expiration to 1 hour from now if not set
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if registration has expired"""
        return timezone.now() > self.expires_at

    def can_process(self):
        """Check if this registration can be processed"""
        return not self.is_processed and not self.is_expired
