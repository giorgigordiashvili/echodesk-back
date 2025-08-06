from django.contrib import admin
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
        'tenant', 'package', 'is_active', 'agent_count', 'monthly_cost',
        'current_users', 'starts_at', 'expires_at'
    ]
    list_filter = ['is_active', 'package__pricing_model', 'package']
    search_fields = ['tenant__name', 'tenant__admin_email', 'package__display_name']
    ordering = ['-created_at']
    readonly_fields = ['monthly_cost', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Subscription Details', {
            'fields': ('tenant', 'package', 'is_active', 'starts_at', 'expires_at')
        }),
        ('Pricing', {
            'fields': ('agent_count', 'monthly_cost')
        }),
        ('Usage Tracking', {
            'fields': ('current_users', 'whatsapp_messages_used', 'storage_used_gb')
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
        'is_active', 'deployment_status', 'created_on'
    ]
    list_filter = ['is_active', 'deployment_status', 'preferred_language', 'plan']
    search_fields = ['name', 'admin_email', 'schema_name', 'domain_url']
    ordering = ['-created_on']
    readonly_fields = ['schema_name', 'created_on', 'current_package_name']
    inlines = [TenantSubscriptionInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'schema_name', 'domain_url')
        }),
        ('Admin Contact', {
            'fields': ('admin_email', 'admin_name')
        }),
        ('Current Package', {
            'fields': ('current_package_name',),
            'description': 'Current package information (read-only, manage via Tenant Subscriptions)'
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
    
    def current_package_name(self, obj):
        """Display current package name"""
        if obj.current_package:
            return f"{obj.current_package.display_name} ({obj.current_package.get_pricing_model_display()})"
        return "No package assigned"
    current_package_name.short_description = "Current Package"
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('subscription__package')
    
    def has_module_permission(self, request):
        # Only allow access in public schema
        if hasattr(request, 'tenant') and request.tenant.schema_name != get_public_schema_name():
            return False
        return super().has_module_permission(request)


# Only register if we're in the public schema context
admin.site.register(Tenant, TenantAdmin)
