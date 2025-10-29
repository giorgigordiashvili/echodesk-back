from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from django import forms
from tenant_schemas.utils import get_public_schema_name
from .models import (
    Tenant, Package, TenantSubscription, UsageLog, PaymentOrder, PendingRegistration,
    Feature, Permission, FeaturePermission, PackageFeature,
    TenantFeature, TenantPermission
)


class PackageFeatureInline(admin.TabularInline):
    """Inline for managing package features"""
    model = PackageFeature
    extra = 1
    autocomplete_fields = ['feature']
    fields = ['feature', 'is_highlighted', 'sort_order', 'custom_value']

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Customize JSON field display"""
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'custom_value':
            field.help_text = 'JSON format: {"max_limit": 1000, "custom_setting": true}'
        return field


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    """Admin interface for Package model"""
    list_display = [
        'display_name', 'pricing_model', 'price_gel', 'max_users',
        'max_whatsapp_messages', 'feature_count', 'is_highlighted', 'is_active', 'sort_order'
    ]
    list_filter = ['pricing_model', 'is_active', 'is_highlighted', 'is_custom']
    search_fields = ['name', 'display_name', 'description']
    ordering = ['pricing_model', 'sort_order', 'price_gel']

    def get_fieldsets(self, request, obj=None):
        """Dynamic fieldsets to include features field"""
        return (
            ('Basic Information', {
                'fields': ('name', 'display_name', 'description', 'pricing_model', 'is_custom')
            }),
            ('Features', {
                'fields': ('package_features_list',),
                'description': 'Select features that this package includes'
            }),
            ('Pricing', {
                'fields': ('price_gel', 'billing_period')
            }),
            ('Limits', {
                'fields': ('max_users', 'max_whatsapp_messages', 'max_storage_gb')
            }),
            ('Legacy Features (deprecated - use Dynamic Features above)', {
                'fields': (
                    'ticket_management', 'email_integration', 'sip_calling',
                    'facebook_integration', 'instagram_integration', 'whatsapp_integration',
                    'advanced_analytics', 'api_access', 'custom_integrations',
                    'priority_support', 'dedicated_account_manager'
                ),
                'classes': ['collapse'],
                'description': 'Legacy boolean features - use Dynamic Features system instead'
            }),
            ('Display Settings', {
                'fields': ('is_highlighted', 'is_active', 'sort_order')
            })
        )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related()

    @admin.display(description='Features')
    def feature_count(self, obj):
        """Display count of features"""
        count = obj.package_features.count()
        return f"{count} feature{'s' if count != 1 else ''}"

    def save_model(self, request, obj, form, change):
        """Save the package and update features"""
        super().save_model(request, obj, form, change)

        # Get the selected features from the form
        if 'package_features_list' in form.cleaned_data:
            selected_features = form.cleaned_data['package_features_list']

            # Remove existing PackageFeature links
            obj.package_features.all().delete()

            # Create new PackageFeature links
            for feature in selected_features:
                PackageFeature.objects.create(
                    package=obj,
                    feature=feature,
                    is_highlighted=False,
                    sort_order=feature.sort_order
                )

    def get_form(self, request, obj=None, **kwargs):
        """Customize the form"""
        # Prepare the fields list - exclude package_features_list since we'll add it manually
        if 'fields' not in kwargs:
            kwargs['fields'] = None

        # Get the form
        form = super().get_form(request, obj, **kwargs)

        # Add a custom field for features AFTER form is created
        initial_features = []
        if obj:
            # Get currently linked features
            initial_features = list(Feature.objects.filter(
                package_features__package=obj
            ).values_list('id', flat=True))

        # Add the field to the form
        form.base_fields['package_features_list'] = forms.ModelMultipleChoiceField(
            queryset=Feature.objects.filter(is_active=True).order_by('category', 'sort_order', 'name'),
            required=False,
            initial=initial_features,
            widget=admin.widgets.FilteredSelectMultiple('Features', False),
            help_text='Select features that this package will include'
        )

        return form


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

        html = '<table style="width: 100%; border-collapse: collapse; margin-bottom: 10px;">'
        html += '<tr style="background-color: #f0f0f0;"><th>Resource</th><th>Current</th><th>Limit</th><th>Status</th></tr>'

        # Subscription Info (Agents)
        if package.pricing_model == 'Agent-based':
            html += f'<tr style="background-color: #e8f4f8;"><td><strong>Agents (Paid For)</strong></td><td colspan="3"><strong>{obj.agent_count} agents</strong> @ {package.price_gel}₾/agent/month</td></tr>'

        # Users (Actual)
        if package.max_users:
            users_pct = (obj.current_users / package.max_users * 100) if package.max_users else 0
            users_color = 'red' if obj.is_over_user_limit else ('orange' if users_pct > 80 else 'green')
            html += f'<tr><td>Active Users</td><td>{obj.current_users}</td><td>{package.max_users}</td><td style="color: {users_color};">{users_pct:.0f}%</td></tr>'
        else:
            html += f'<tr><td>Active Users</td><td>{obj.current_users}</td><td>Unlimited</td><td style="color: green;">✓</td></tr>'

        # WhatsApp
        wa_pct = (obj.whatsapp_messages_used / package.max_whatsapp_messages * 100) if package.max_whatsapp_messages else 0
        wa_color = 'red' if obj.is_over_whatsapp_limit else ('orange' if wa_pct > 80 else 'green')
        html += f'<tr><td>WhatsApp</td><td>{obj.whatsapp_messages_used:,}</td><td>{package.max_whatsapp_messages:,}</td><td style="color: {wa_color};">{wa_pct:.0f}%</td></tr>'

        # Storage
        storage_pct = (float(obj.storage_used_gb) / package.max_storage_gb * 100) if package.max_storage_gb else 0
        storage_color = 'red' if obj.is_over_storage_limit else ('orange' if storage_pct > 80 else 'green')
        html += f'<tr><td>Storage (Manual)</td><td>{obj.storage_used_gb} GB</td><td>{package.max_storage_gb} GB</td><td style="color: {storage_color};">{storage_pct:.0f}%</td></tr>'

        html += '</table>'

        # Add explanation
        html += '<div style="padding: 8px; background-color: #f9f9f9; border-left: 3px solid #2196F3; margin-top: 10px;">'
        html += '<small><strong>💡 Note:</strong></small><br>'
        html += '<small>• <strong>Agents (Paid For)</strong>: Number of agents in subscription plan (billing basis)</small><br>'
        html += '<small>• <strong>Active Users</strong>: Actual users created in the system</small><br>'
        html += '<small>• <strong>Storage</strong>: Must be manually updated (not auto-calculated)</small>'
        html += '</div>'

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


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    """Admin interface for PaymentOrder model"""
    list_display = [
        'order_id', 'tenant', 'package', 'amount', 'currency',
        'status_badge', 'created_at', 'paid_at'
    ]
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['order_id', 'tenant__name', 'tenant__schema_name']
    ordering = ['-created_at']
    readonly_fields = ['order_id', 'created_at', 'updated_at', 'paid_at']

    fieldsets = (
        ('Order Information', {
            'fields': ('order_id', 'tenant', 'package', 'status')
        }),
        ('Payment Details', {
            'fields': ('amount', 'currency', 'agent_count', 'payment_url')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'paid_at'),
            'classes': ['collapse']
        })
    )

    @admin.display(description='Status')
    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            'pending': 'orange',
            'paid': 'green',
            'failed': 'red',
            'cancelled': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant', 'package')


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


@admin.register(PendingRegistration)
class PendingRegistrationAdmin(admin.ModelAdmin):
    """Admin interface for PendingRegistration model"""
    list_display = [
        'schema_name', 'name', 'admin_email', 'package',
        'agent_count', 'status_badge', 'created_at', 'expires_at'
    ]
    list_filter = ['is_processed', 'package', 'created_at']
    search_fields = ['schema_name', 'name', 'admin_email', 'order_id']
    readonly_fields = ['created_at', 'expires_at', 'admin_password']
    ordering = ['-created_at']

    @admin.display(description='Status')
    def status_badge(self, obj):
        """Display status with color badge"""
        if obj.is_processed:
            color = 'green'
            status = 'Processed'
        elif obj.is_expired:
            color = 'red'
            status = 'Expired'
        else:
            color = 'orange'
            status = 'Pending'

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            status
        )

    def get_readonly_fields(self, request, obj=None):
        """Make all fields readonly for processed registrations"""
        if obj and obj.is_processed:
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields


# Only register if we're in the public schema context
admin.site.register(Tenant, TenantAdmin)


# =============================================================================
# Feature & Permission System Admin
# =============================================================================

class FeaturePermissionInline(admin.TabularInline):
    """Inline for managing feature permissions"""
    model = FeaturePermission
    extra = 1
    autocomplete_fields = ['permission']


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    """Admin interface for Feature model"""
    list_display = [
        'name', 'key', 'category', 'price_per_user_gel', 'price_unlimited_gel',
        'icon_display', 'permission_count', 'sort_order', 'is_active', 'created_at'
    ]
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['key', 'name', 'description']
    ordering = ['category', 'sort_order', 'name']
    inlines = [FeaturePermissionInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('key', 'name', 'description')
        }),
        ('Pricing for Custom Packages', {
            'fields': ('price_per_user_gel', 'price_unlimited_gel'),
            'description': 'Agent-based uses per-user price, CRM-based uses unlimited price (with 10% discount)'
        }),
        ('Categorization & Display', {
            'fields': ('category', 'icon', 'sort_order')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        })
    )

    readonly_fields = ['created_at', 'updated_at']

    @admin.display(description='Icon')
    def icon_display(self, obj):
        """Display the icon"""
        if obj.icon:
            return format_html('{} {}', obj.icon, obj.icon)
        return '-'

    @admin.display(description='Permissions')
    def permission_count(self, obj):
        """Display count of permissions"""
        count = obj.permissions.count()
        return f"{count} permission{'s' if count != 1 else ''}"


class FeaturePermissionInlineForPermission(admin.TabularInline):
    """Inline for viewing which features use this permission"""
    model = FeaturePermission
    extra = 0
    autocomplete_fields = ['feature']


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """Admin interface for Permission model"""
    list_display = [
        'name', 'key', 'module', 'is_active', 'created_at'
    ]
    list_filter = ['module', 'is_active', 'created_at']
    search_fields = ['key', 'name', 'description', 'module']
    ordering = ['module', 'key']
    inlines = [FeaturePermissionInlineForPermission]

    fieldsets = (
        ('Basic Information', {
            'fields': ('key', 'name', 'description')
        }),
        ('Grouping', {
            'fields': ('module',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        })
    )

    readonly_fields = ['created_at', 'updated_at']


@admin.register(FeaturePermission)
class FeaturePermissionAdmin(admin.ModelAdmin):
    """Admin interface for FeaturePermission model"""
    list_display = ['feature', 'permission', 'is_required']
    list_filter = ['is_required', 'feature__category']
    search_fields = ['feature__name', 'permission__name']
    autocomplete_fields = ['feature', 'permission']

    fieldsets = (
        ('Relationship', {
            'fields': ('feature', 'permission')
        }),
        ('Configuration', {
            'fields': ('is_required',)
        })
    )


@admin.register(PackageFeature)
class PackageFeatureAdmin(admin.ModelAdmin):
    """Admin interface for PackageFeature model"""
    list_display = [
        'package', 'feature', 'is_highlighted', 'sort_order', 'has_custom_value'
    ]
    list_filter = ['is_highlighted', 'package', 'feature__category']
    search_fields = ['package__display_name', 'feature__name']
    autocomplete_fields = ['package', 'feature']

    fieldsets = (
        ('Relationship', {
            'fields': ('package', 'feature')
        }),
        ('Display Settings', {
            'fields': ('is_highlighted', 'sort_order')
        }),
        ('Custom Configuration', {
            'fields': ('custom_value',),
            'description': 'Optional JSON configuration for package-specific limits or settings'
        })
    )

    @admin.display(description='Custom Config', boolean=True)
    def has_custom_value(self, obj):
        """Show if custom value is set"""
        return bool(obj.custom_value)


@admin.register(TenantFeature)
class TenantFeatureAdmin(admin.ModelAdmin):
    """Admin interface for TenantFeature model"""
    list_display = [
        'tenant', 'feature', 'is_active', 'enabled_at', 'disabled_at'
    ]
    list_filter = ['is_active', 'feature__category', 'enabled_at']
    search_fields = ['tenant__name', 'tenant__schema_name', 'feature__name']
    autocomplete_fields = ['tenant', 'feature']
    readonly_fields = ['enabled_at']

    fieldsets = (
        ('Relationship', {
            'fields': ('tenant', 'feature')
        }),
        ('Status', {
            'fields': ('is_active', 'enabled_at', 'disabled_at')
        }),
        ('Custom Configuration', {
            'fields': ('custom_value',),
            'description': 'Optional tenant-specific overrides',
            'classes': ['collapse']
        })
    )

    actions = ['enable_features', 'disable_features']

    @admin.action(description='Enable selected features')
    def enable_features(self, request, queryset):
        """Enable selected tenant features"""
        count = queryset.update(is_active=True, disabled_at=None)
        self.message_user(request, f'{count} feature(s) enabled successfully.', messages.SUCCESS)

    @admin.action(description='Disable selected features')
    def disable_features(self, request, queryset):
        """Disable selected tenant features"""
        count = queryset.update(is_active=False, disabled_at=timezone.now())
        self.message_user(request, f'{count} feature(s) disabled successfully.', messages.SUCCESS)


@admin.register(TenantPermission)
class TenantPermissionAdmin(admin.ModelAdmin):
    """Admin interface for TenantPermission model"""
    list_display = [
        'tenant', 'permission', 'granted_by_feature', 'is_active', 'granted_at'
    ]
    list_filter = ['is_active', 'permission__module', 'granted_at']
    search_fields = ['tenant__name', 'tenant__schema_name', 'permission__name']
    autocomplete_fields = ['tenant', 'permission', 'granted_by_feature']
    readonly_fields = ['granted_at']

    fieldsets = (
        ('Relationship', {
            'fields': ('tenant', 'permission')
        }),
        ('Source', {
            'fields': ('granted_by_feature',)
        }),
        ('Status', {
            'fields': ('is_active', 'granted_at', 'revoked_at')
        })
    )

    actions = ['activate_permissions', 'revoke_permissions']

    @admin.action(description='Activate selected permissions')
    def activate_permissions(self, request, queryset):
        """Activate selected permissions"""
        count = queryset.update(is_active=True, revoked_at=None)
        self.message_user(request, f'{count} permission(s) activated successfully.', messages.SUCCESS)

    @admin.action(description='Revoke selected permissions')
    def revoke_permissions(self, request, queryset):
        """Revoke selected permissions"""
        count = queryset.update(is_active=False, revoked_at=timezone.now())
        self.message_user(request, f'{count} permission(s) revoked successfully.', messages.SUCCESS)


# UserPermission admin removed - tenant admins manage user permissions
# via the existing User model fields (can_view_all_tickets, can_manage_users, etc.)
# TenantPermission shows which permissions are available to the tenant based on their package
