from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from tenant_schemas.utils import get_public_schema_name
from .models import Tenant, Package, TenantSubscription, UsageLog


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    """Admin interface for Package model"""
    list_display = [
        'display_name', 'pricing_model', 'price_gel', 'max_users', 
        'max_whatsapp_messages', 'is_highlighted', 'is_active', 'sort_order'
    ]
    list_filter = ['pricing_model', 'is_active', 'is_highlighted']
    search_fields = ['name', 'display_name', 'description']
    ordering = ['pricing_model', 'sort_order', 'price_gel']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'pricing_model')
        }),
        ('Pricing', {
            'fields': ('price_gel', 'billing_period')
        }),
        ('Limits', {
            'fields': ('max_users', 'max_whatsapp_messages', 'max_storage_gb')
        }),
        ('Features', {
            'fields': (
                'ticket_management', 'email_integration', 'sip_calling',
                'facebook_integration', 'instagram_integration', 'whatsapp_integration',
                'advanced_analytics', 'api_access', 'custom_integrations',
                'priority_support', 'dedicated_account_manager'
            ),
            'classes': ['collapse']
        }),
        ('Display Settings', {
            'fields': ('is_highlighted', 'is_active', 'sort_order')
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for TenantSubscription model"""
    list_display = [
        'tenant', 'package', 'status_badge', 'agent_count', 'monthly_cost',
        'current_users', 'usage_status', 'starts_at', 'expires_at'
    ]
    list_filter = ['is_active', 'package__pricing_model', 'package']
    search_fields = ['tenant__name', 'tenant__admin_email', 'package__display_name']
    ordering = ['-created_at']
    readonly_fields = [
        'monthly_cost', 'created_at', 'updated_at',
        'usage_summary', 'feature_summary'
    ]
    actions = [
        'activate_subscriptions',
        'deactivate_subscriptions',
        'reset_usage',
        'extend_subscription_30_days'
    ]

    fieldsets = (
        ('Subscription Details', {
            'fields': ('tenant', 'package', 'is_active', 'starts_at', 'expires_at')
        }),
        ('Pricing', {
            'fields': ('agent_count', 'monthly_cost')
        }),
        ('Usage Tracking', {
            'fields': ('current_users', 'whatsapp_messages_used', 'storage_used_gb', 'usage_summary')
        }),
        ('Features', {
            'fields': ('feature_summary',),
            'classes': ['collapse']
        }),
        ('Billing', {
            'fields': ('last_billed_at', 'next_billing_date')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant', 'package')

    @admin.display(description='Status')
    def status_badge(self, obj):
        """Display status with color badge"""
        if obj.is_active:
            color = 'green'
            text = 'Active'
        else:
            color = 'red'
            text = 'Inactive'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, text
        )

    @admin.display(description='Usage Status')
    def usage_status(self, obj):
        """Display usage status indicators"""
        indicators = []

        if obj.is_over_user_limit:
            indicators.append('<span style="color: red;">👥 Over user limit</span>')

        if obj.is_over_whatsapp_limit:
            indicators.append('<span style="color: red;">💬 Over WhatsApp limit</span>')

        if obj.is_over_storage_limit:
            indicators.append('<span style="color: red;">💾 Over storage limit</span>')

        if not indicators:
            return format_html('<span style="color: green;">✓ Within limits</span>')

        return format_html('<br>'.join(indicators))

    @admin.display(description='Usage Summary')
    def usage_summary(self, obj):
        """Display detailed usage summary"""
        package = obj.package

        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background-color: #f0f0f0;"><th>Resource</th><th>Used</th><th>Limit</th><th>%</th></tr>'

        # Users
        if package.max_users:
            users_pct = (obj.current_users / package.max_users * 100) if package.max_users else 0
            users_color = 'red' if obj.is_over_user_limit else ('orange' if users_pct > 80 else 'green')
            html += f'<tr><td>Users</td><td>{obj.current_users}</td><td>{package.max_users}</td><td style="color: {users_color};">{users_pct:.0f}%</td></tr>'
        else:
            html += f'<tr><td>Users</td><td>{obj.current_users}</td><td>Unlimited</td><td>-</td></tr>'

        # WhatsApp
        wa_pct = (obj.whatsapp_messages_used / package.max_whatsapp_messages * 100) if package.max_whatsapp_messages else 0
        wa_color = 'red' if obj.is_over_whatsapp_limit else ('orange' if wa_pct > 80 else 'green')
        html += f'<tr><td>WhatsApp</td><td>{obj.whatsapp_messages_used:,}</td><td>{package.max_whatsapp_messages:,}</td><td style="color: {wa_color};">{wa_pct:.0f}%</td></tr>'

        # Storage
        storage_pct = (float(obj.storage_used_gb) / package.max_storage_gb * 100) if package.max_storage_gb else 0
        storage_color = 'red' if obj.is_over_storage_limit else ('orange' if storage_pct > 80 else 'green')
        html += f'<tr><td>Storage</td><td>{obj.storage_used_gb} GB</td><td>{package.max_storage_gb} GB</td><td style="color: {storage_color};">{storage_pct:.0f}%</td></tr>'

        html += '</table>'

        return format_html(html)

    @admin.display(description='Features')
    def feature_summary(self, obj):
        """Display enabled features"""
        package = obj.package
        features = []

        if package.ticket_management:
            features.append('✓ Ticket Management')
        if package.email_integration:
            features.append('✓ Email Integration')
        if package.sip_calling:
            features.append('✓ SIP Calling')
        if package.facebook_integration:
            features.append('✓ Facebook')
        if package.instagram_integration:
            features.append('✓ Instagram')
        if package.whatsapp_integration:
            features.append('✓ WhatsApp')
        if package.advanced_analytics:
            features.append('✓ Advanced Analytics')
        if package.api_access:
            features.append('✓ API Access')
        if package.custom_integrations:
            features.append('✓ Custom Integrations')
        if package.priority_support:
            features.append('✓ Priority Support')
        if package.dedicated_account_manager:
            features.append('✓ Dedicated Account Manager')

        return format_html('<br>'.join(features))

    # Admin Actions

    @admin.action(description='Activate selected subscriptions')
    def activate_subscriptions(self, request, queryset):
        """Activate selected subscriptions"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} subscription(s) activated successfully.', messages.SUCCESS)

    @admin.action(description='Deactivate selected subscriptions')
    def deactivate_subscriptions(self, request, queryset):
        """Deactivate selected subscriptions"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} subscription(s) deactivated successfully.', messages.SUCCESS)

    @admin.action(description='Reset usage counters')
    def reset_usage(self, request, queryset):
        """Reset usage counters for selected subscriptions"""
        count = queryset.update(
            whatsapp_messages_used=0,
            storage_used_gb=0
        )
        self.message_user(request, f'Usage reset for {count} subscription(s).', messages.SUCCESS)

    @admin.action(description='Extend subscription by 30 days')
    def extend_subscription_30_days(self, request, queryset):
        """Extend subscription expiry by 30 days"""
        from datetime import timedelta

        for subscription in queryset:
            if subscription.expires_at:
                subscription.expires_at += timedelta(days=30)
            else:
                subscription.expires_at = timezone.now() + timedelta(days=30)
            subscription.save()

        self.message_user(
            request,
            f'{queryset.count()} subscription(s) extended by 30 days.',
            messages.SUCCESS
        )


@admin.register(UsageLog)
class UsageLogAdmin(admin.ModelAdmin):
    """Admin interface for UsageLog model"""
    list_display = ['subscription', 'event_type', 'quantity', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['subscription__tenant__name', 'event_type']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('subscription__tenant')


# Inline admin for better UX
class TenantSubscriptionInline(admin.StackedInline):
    """Inline admin for TenantSubscription"""
    model = TenantSubscription
    extra = 0
    readonly_fields = ['monthly_cost', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Subscription', {
            'fields': ('package', 'is_active', 'starts_at', 'expires_at', 'agent_count')
        }),
        ('Usage', {
            'fields': ('current_users', 'whatsapp_messages_used', 'storage_used_gb'),
            'classes': ['collapse']
        }),
    )


class TenantAdmin(admin.ModelAdmin):
    """Admin interface for Tenant model"""
    list_display = [
        'name', 'schema_name', 'admin_email', 'current_package_name',
        'subscription_status', 'is_active', 'deployment_status', 'created_on'
    ]
    list_filter = ['is_active', 'deployment_status', 'preferred_language', 'plan']
    search_fields = ['name', 'admin_email', 'schema_name', 'domain_url']
    ordering = ['-created_on']
    readonly_fields = ['schema_name', 'created_on', 'current_package_name', 'subscription_details']
    inlines = [TenantSubscriptionInline]
    actions = ['create_basic_subscription', 'activate_tenants', 'deactivate_tenants']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'schema_name', 'domain_url')
        }),
        ('Admin Contact', {
            'fields': ('admin_email', 'admin_name')
        }),
        ('Current Package', {
            'fields': ('current_package_name', 'subscription_details'),
            'description': 'Current package information (manage via inline below or Tenant Subscriptions)'
        }),
        ('Legacy Settings', {
            'fields': ('plan', 'max_users', 'max_storage'),
            'classes': ['collapse'],
            'description': 'Legacy fields kept for backward compatibility'
        }),
        ('Preferences', {
            'fields': ('preferred_language',)
        }),
        ('Deployment', {
            'fields': ('frontend_url', 'deployment_status')
        }),
        ('Status', {
            'fields': ('is_active', 'created_on')
        })
    )

    @admin.display(description='Current Package')
    def current_package_name(self, obj):
        """Display current package name"""
        if obj.current_package:
            return f"{obj.current_package.display_name} ({obj.current_package.get_pricing_model_display()})"
        return format_html('<span style="color: red;">⚠ No package assigned</span>')

    @admin.display(description='Subscription')
    def subscription_status(self, obj):
        """Display subscription status badge"""
        subscription = obj.current_subscription
        if not subscription:
            return format_html('<span style="background-color: red; color: white; padding: 3px 10px; border-radius: 3px;">No Subscription</span>')

        if subscription.is_active:
            return format_html('<span style="background-color: green; color: white; padding: 3px 10px; border-radius: 3px;">Active</span>')
        else:
            return format_html('<span style="background-color: gray; color: white; padding: 3px 10px; border-radius: 3px;">Inactive</span>')

    @admin.display(description='Subscription Details')
    def subscription_details(self, obj):
        """Display detailed subscription information"""
        subscription = obj.current_subscription

        if not subscription:
            return format_html('<p style="color: red;">No active subscription found. Create one using the inline form below.</p>')

        package = subscription.package

        html = '<div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px;">'
        html += f'<h3 style="margin-top: 0;">{package.display_name}</h3>'
        html += f'<p><strong>Pricing:</strong> {subscription.monthly_cost}₾/month ({package.get_pricing_model_display()})</p>'

        if package.pricing_model == 'agent':
            html += f'<p><strong>Agent Count:</strong> {subscription.agent_count}</p>'

        html += f'<p><strong>Status:</strong> {"Active" if subscription.is_active else "Inactive"}</p>'
        html += f'<p><strong>Period:</strong> {subscription.starts_at.strftime("%Y-%m-%d")} to {subscription.expires_at.strftime("%Y-%m-%d") if subscription.expires_at else "No expiry"}</p>'

        # View subscription link
        url = reverse('admin:tenants_tenantsubscription_change', args=[subscription.id])
        html += f'<p><a href="{url}" style="color: #447e9b;">View/Edit Subscription →</a></p>'

        html += '</div>'

        return format_html(html)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('subscription__package')

    def has_module_permission(self, request):
        # Only allow access in public schema
        if hasattr(request, 'tenant') and request.tenant.schema_name != get_public_schema_name():
            return False
        return super().has_module_permission(request)

    # Admin Actions

    @admin.action(description='Create basic subscription for selected tenants')
    def create_basic_subscription(self, request, queryset):
        """Create a basic subscription for tenants without one"""
        from datetime import timedelta

        # Get the first available package (or create a default one)
        try:
            basic_package = Package.objects.filter(is_active=True).first()
            if not basic_package:
                self.message_user(request, 'No active packages found. Please create a package first.', messages.ERROR)
                return
        except Package.DoesNotExist:
            self.message_user(request, 'No packages available. Please create a package first.', messages.ERROR)
            return

        created_count = 0
        skipped_count = 0

        for tenant in queryset:
            # Skip if already has subscription
            if hasattr(tenant, 'subscription'):
                skipped_count += 1
                continue

            # Create subscription
            TenantSubscription.objects.create(
                tenant=tenant,
                package=basic_package,
                is_active=True,
                starts_at=timezone.now(),
                expires_at=timezone.now() + timedelta(days=30),
                agent_count=1
            )
            created_count += 1

        self.message_user(
            request,
            f'Created {created_count} subscription(s). Skipped {skipped_count} tenant(s) with existing subscriptions.',
            messages.SUCCESS
        )

    @admin.action(description='Activate selected tenants')
    def activate_tenants(self, request, queryset):
        """Activate selected tenants"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} tenant(s) activated successfully.', messages.SUCCESS)

    @admin.action(description='Deactivate selected tenants')
    def deactivate_tenants(self, request, queryset):
        """Deactivate selected tenants"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} tenant(s) deactivated successfully.', messages.SUCCESS)


# Only register if we're in the public schema context
admin.site.register(Tenant, TenantAdmin)
