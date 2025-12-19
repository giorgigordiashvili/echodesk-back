from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from tenant_schemas.utils import get_public_schema_name, schema_context
from tenants.models import Tenant
from .models import (
    Language,
    AttributeDefinition,
    Product,
    ProductImage,
    ProductAttributeValue,
    ProductVariant,
    ProductVariantAttributeValue,
    EcommerceClient,
    ClientVerificationCode,
    PasswordResetToken,
    EcommerceSettings
)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['code', '__str__', 'is_default', 'is_active', 'sort_order', 'created_at']
    list_filter = ['is_default', 'is_active']
    search_fields = ['code']
    ordering = ['sort_order', 'code']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Language Information', {
            'fields': ('code', 'name', 'sort_order')
        }),
        ('Settings', {
            'fields': ('is_default', 'is_active')
        }),
        ('System', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AttributeDefinition)
class AttributeDefinitionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'key', 'attribute_type', 'is_required', 'is_variant_attribute', 'is_filterable', 'is_active']
    list_filter = ['attribute_type', 'is_required', 'is_variant_attribute', 'is_filterable', 'is_active']
    search_fields = ['key']
    ordering = ['sort_order', 'id']


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ['image', 'alt_text', 'sort_order']


class ProductAttributeValueInline(admin.TabularInline):
    model = ProductAttributeValue
    extra = 0
    fields = ['attribute', 'value_text', 'value_number', 'value_boolean', 'value_date', 'value_json']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['sku', '__str__', 'price', 'quantity', 'status', 'is_featured', 'created_at']
    list_filter = ['status', 'is_featured', 'track_inventory']
    search_fields = ['sku', 'slug']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    inlines = [ProductImageInline, ProductAttributeValueInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('sku', 'slug', 'name', 'description', 'short_description')
        }),
        ('Pricing', {
            'fields': ('price', 'compare_at_price', 'cost_price')
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('Inventory', {
            'fields': ('track_inventory', 'quantity', 'low_stock_threshold')
        }),
        ('Status & Metadata', {
            'fields': ('status', 'is_featured', 'weight', 'dimensions')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('System', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['sku', '__str__', 'product', 'price', 'quantity', 'is_active', 'created_at']
    list_filter = ['is_active', 'product']
    search_fields = ['sku', 'product__sku']
    ordering = ['product', 'sort_order']


@admin.register(EcommerceClient)
class EcommerceClientAdmin(admin.ModelAdmin):
    list_display = ['email', 'full_name', 'phone_number', 'is_active', 'is_verified', 'last_login', 'created_at']
    list_filter = ['is_active', 'is_verified', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'phone_number']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'last_login']

    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone_number', 'date_of_birth')
        }),
        ('Authentication', {
            'fields': ('password',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_verified', 'last_login')
        }),
        ('System', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ['client', 'token', 'created_at', 'expires_at', 'is_used', 'used_at']
    list_filter = ['is_used', 'created_at', 'expires_at']
    search_fields = ['client__email', 'token']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'used_at']

    fieldsets = (
        ('Token Information', {
            'fields': ('client', 'token', 'created_at', 'expires_at')
        }),
        ('Status', {
            'fields': ('is_used', 'used_at')
        }),
    )


@admin.register(ClientVerificationCode)
class ClientVerificationCodeAdmin(admin.ModelAdmin):
    list_display = ['email', 'code', 'token', 'created_at', 'expires_at', 'is_used']
    list_filter = ['is_used', 'created_at', 'expires_at']
    search_fields = ['email', 'code', 'token']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

    fieldsets = (
        ('Verification Information', {
            'fields': ('email', 'code', 'token', 'created_at', 'expires_at')
        }),
        ('Status', {
            'fields': ('is_used',)
        }),
    )


@admin.register(EcommerceSettings)
class EcommerceSettingsAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'store_name', 'get_deployment_status_display', 'frontend_url_link', 'deploy_button']
    readonly_fields = ['tenant', 'get_deployment_status_display', 'frontend_url_link', 'get_vercel_project_id', 'deploy_button']

    fieldsets = (
        ('Store Information', {
            'fields': ('tenant', 'store_name', 'store_email', 'store_phone')
        }),
        ('Payment Settings', {
            'fields': ('bog_client_id', 'bog_return_url_success', 'bog_return_url_fail', 'enable_cash_on_delivery', 'enable_card_payment')
        }),
        ('Frontend Deployment', {
            'fields': ('get_deployment_status_display', 'get_vercel_project_id', 'frontend_url_link', 'deploy_button'),
            'classes': ('wide',)
        }),
    )

    def get_deployment_status_display(self, obj):
        """Display deployment status with color coding"""
        status = obj.deployment_status
        colors = {
            'pending': '#ffc107',
            'deploying': '#17a2b8',
            'deployed': '#28a745',
            'failed': '#dc3545'
        }
        color = colors.get(status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            status.upper()
        )
    get_deployment_status_display.short_description = 'Deployment Status'

    def frontend_url_link(self, obj):
        """Show frontend URL as clickable link"""
        if obj.ecommerce_frontend_url:
            return format_html(
                '<a href="{}" target="_blank" style="color: #007bff;">{}</a>',
                obj.ecommerce_frontend_url,
                obj.ecommerce_frontend_url
            )
        return 'Not deployed'
    frontend_url_link.short_description = 'E-commerce Frontend URL'

    def get_vercel_project_id(self, obj):
        """Get Vercel project ID"""
        if obj.vercel_project_id:
            return obj.vercel_project_id
        return '-'
    get_vercel_project_id.short_description = 'Vercel Project ID'

    def deploy_button(self, obj):
        """Render deploy/redeploy button"""
        if obj.pk:
            if obj.ecommerce_frontend_url:
                # Already deployed - show redeploy button
                return format_html(
                    '<a class="button" href="{}" style="background-color: #17a2b8; color: white; padding: 5px 15px; text-decoration: none; border-radius: 3px;">Redeploy Frontend</a>',
                    reverse('admin:ecommerce_crm_ecommercesettings_deploy', args=[obj.pk])
                )
            else:
                # Not deployed - show deploy button
                return format_html(
                    '<a class="button" href="{}" style="background-color: #28a745; color: white; padding: 5px 15px; text-decoration: none; border-radius: 3px;">Deploy Frontend</a>',
                    reverse('admin:ecommerce_crm_ecommercesettings_deploy', args=[obj.pk])
                )
        return '-'
    deploy_button.short_description = 'Actions'

    def get_urls(self):
        """Add custom URL for deploy action"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:settings_id>/deploy/',
                self.admin_site.admin_view(self.deploy_view),
                name='ecommerce_crm_ecommercesettings_deploy'
            ),
        ]
        return custom_urls + urls

    def deploy_view(self, request, settings_id):
        """Handle deploy button click (Multi-Tenant)

        Adds tenant's subdomain to the shared multi-tenant Vercel project.
        """
        from .services.vercel_deployment import deploy_tenant_frontend

        try:
            settings = EcommerceSettings.objects.get(pk=settings_id)
            tenant = settings.tenant

            if not tenant:
                messages.error(request, "No tenant associated with these settings")
                return HttpResponseRedirect(reverse('admin:ecommerce_crm_ecommercesettings_change', args=[settings_id]))

            # Check if already deployed
            if settings.deployment_status == 'deployed' and settings.ecommerce_frontend_url:
                messages.info(
                    request,
                    f"Frontend is already deployed at {settings.ecommerce_frontend_url}. Code updates propagate automatically."
                )
                return HttpResponseRedirect(reverse('admin:ecommerce_crm_ecommercesettings_change', args=[settings_id]))

            # Update status to deploying
            settings.deployment_status = 'deploying'
            settings.save(update_fields=['deployment_status'])

            # Add subdomain to shared Vercel project
            with schema_context(get_public_schema_name()):
                tenant_obj = Tenant.objects.get(id=tenant.id)
                result = deploy_tenant_frontend(tenant_obj)

            if result.get('success'):
                # Update settings with deployment info
                settings.ecommerce_frontend_url = result.get('url')
                settings.vercel_project_id = result.get('project_id')
                settings.deployment_status = 'deployed'
                settings.save(update_fields=['ecommerce_frontend_url', 'vercel_project_id', 'deployment_status'])

                messages.success(
                    request,
                    f"Frontend deployed successfully! URL: {result.get('url')}"
                )
            else:
                # Update status to failed
                settings.deployment_status = 'failed'
                settings.save(update_fields=['deployment_status'])

                messages.error(
                    request,
                    f"Deployment failed: {result.get('error', 'Unknown error')}"
                )
        except EcommerceSettings.DoesNotExist:
            messages.error(request, "Settings not found")
        except Exception as e:
            messages.error(request, f"Error during deployment: {str(e)}")

        return HttpResponseRedirect(reverse('admin:ecommerce_crm_ecommercesettings_change', args=[settings_id]))
