from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from django import forms
from django.contrib.auth.models import Permission
from tenant_schemas.utils import get_public_schema_name
import logging
from .models import (
    Tenant, TenantSubscription, UsageLog, PaymentOrder, PendingRegistration,
    SavedCard, Feature, FeaturePermission,
    TenantFeature, TenantPermission, PaymentAttempt, SubscriptionEvent,
    PaymentRetrySchedule, PlatformMetrics
)
from .subscription_utils import get_subscription_health, get_failed_payments_summary

logger = logging.getLogger(__name__)


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for TenantSubscription model"""
    list_display = [
        'tenant', 'status_badge', 'payment_health_display',
        'agent_count', 'monthly_cost', 'current_users',
        'next_billing_date', 'failed_payment_count'
    ]
    list_filter = [
        'is_active',
        'payment_status',
        'is_trial',
        'selected_features',
    ]
    search_fields = ['tenant__name', 'tenant__admin_email']
    ordering = ['-created_at']
    readonly_fields = [
        'monthly_cost', 'created_at', 'updated_at',
        'usage_summary', 'feature_summary', 'payment_health_status',
        'days_until_next_billing', 'view_payment_attempts', 'view_events'
    ]
    filter_horizontal = ['selected_features']
    actions = [
        'activate_subscriptions',
        'deactivate_subscriptions',
        'reset_usage',
        'extend_subscription_30_days',
        'retry_failed_payments',
        'sync_tenant_features',
    ]

    fieldsets = (
        ('Subscription Details', {
            'fields': ('tenant', 'is_active', 'is_trial', 'trial_ends_at', 'starts_at', 'expires_at')
        }),
        ('Payment Health', {
            'fields': (
                'payment_status',
                'payment_health_status',
                'parent_order_id',
                'failed_payment_count',
                'last_payment_failure',
                'view_payment_attempts',
                'view_events',
            ),
            'classes': ['wide']
        }),
        ('Pricing', {
            'fields': ('agent_count', 'monthly_cost')
        }),
        ('Usage Tracking', {
            'fields': ('current_users', 'whatsapp_messages_used', 'storage_used_gb', 'usage_summary')
        }),
        ('Feature Management', {
            'fields': ('selected_features', 'feature_summary'),
            'description': 'Add or remove features for this tenant. After changing features, use the "Sync tenant features" action to apply changes.',
        }),
        ('Billing', {
            'fields': ('last_billed_at', 'next_billing_date', 'days_until_next_billing')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant').prefetch_related('selected_features')

    def save_related(self, request, form, formsets, change):
        """Auto-sync TenantFeature records after saving selected_features"""
        super().save_related(request, form, formsets, change)

        # Auto-sync features after M2M save
        subscription = form.instance
        if subscription.pk:
            self._sync_single_subscription(subscription)
            self.message_user(request, 'Features synced automatically.', messages.INFO)

    def _sync_single_subscription(self, subscription):
        """Helper to sync features for a single subscription"""
        from tenants.feature_models import TenantFeature

        tenant = subscription.tenant
        selected_feature_ids = set(subscription.selected_features.values_list('id', flat=True))

        # Get existing TenantFeature records
        existing_feature_ids = set(
            TenantFeature.objects.filter(tenant=tenant).values_list('feature_id', flat=True)
        )

        # Create missing TenantFeature records
        for feature_id in selected_feature_ids:
            if feature_id not in existing_feature_ids:
                TenantFeature.objects.create(
                    tenant=tenant,
                    feature_id=feature_id,
                    is_active=True
                )

        # Activate features that should be active
        TenantFeature.objects.filter(
            tenant=tenant,
            feature_id__in=selected_feature_ids
        ).update(is_active=True, disabled_at=None)

        # Deactivate features that are no longer selected
        TenantFeature.objects.filter(
            tenant=tenant
        ).exclude(
            feature_id__in=selected_feature_ids
        ).update(is_active=False, disabled_at=timezone.now())

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
        html = '<table style="width: 100%; border-collapse: collapse; margin-bottom: 10px;">'
        html += '<tr style="background-color: #f0f0f0;"><th>Resource</th><th>Current</th><th>Limit</th><th>Status</th></tr>'

        # Subscription Info (Agents)
        html += f'<tr style="background-color: #e8f4f8;"><td><strong>Agents (Paid For)</strong></td><td colspan="3"><strong>{obj.agent_count} agents</strong> @ {obj.monthly_cost}₾/month</td></tr>'

        # Users (Actual) - compare against agent_count
        users_pct = (obj.current_users / obj.agent_count * 100) if obj.agent_count else 0
        users_color = 'red' if obj.is_over_user_limit else ('orange' if users_pct > 80 else 'green')
        html += f'<tr><td>Active Users</td><td>{obj.current_users}</td><td>{obj.agent_count}</td><td style="color: {users_color};">{users_pct:.0f}%</td></tr>'

        # WhatsApp - default 10k limit
        wa_limit = 10000
        wa_pct = (obj.whatsapp_messages_used / wa_limit * 100) if wa_limit else 0
        wa_color = 'red' if obj.is_over_whatsapp_limit else ('orange' if wa_pct > 80 else 'green')
        html += f'<tr><td>WhatsApp</td><td>{obj.whatsapp_messages_used:,}</td><td>{wa_limit:,}</td><td style="color: {wa_color};">{wa_pct:.0f}%</td></tr>'

        # Storage - default 100GB limit
        storage_limit = 100
        storage_pct = (float(obj.storage_used_gb) / storage_limit * 100) if storage_limit else 0
        storage_color = 'red' if obj.is_over_storage_limit else ('orange' if storage_pct > 80 else 'green')
        html += f'<tr><td>Storage (Manual)</td><td>{obj.storage_used_gb} GB</td><td>{storage_limit} GB</td><td style="color: {storage_color};">{storage_pct:.0f}%</td></tr>'

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
        selected_features = obj.selected_features.filter(is_active=True)

        if not selected_features.exists():
            return format_html('<span style="color: red;">No features selected</span>')

        features = []
        for feature in selected_features:
            features.append(f'✓ {feature.name}')

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

    @admin.action(description='Sync tenant features (create TenantFeature records)')
    def sync_tenant_features(self, request, queryset):
        """Sync TenantFeature records based on selected_features"""
        synced_count = 0
        for subscription in queryset:
            self._sync_single_subscription(subscription)
            synced_count += 1

        self.message_user(
            request,
            f'Synced features for {synced_count} subscription(s).',
            messages.SUCCESS
        )

    @admin.action(description='Retry failed payments for selected subscriptions')
    def retry_failed_payments(self, request, queryset):
        """Manually retry failed payments for selected subscriptions"""
        from tenants.subscription_utils import execute_retry
        from tenants.models import PaymentRetrySchedule

        retry_count = 0
        error_count = 0

        for subscription in queryset:
            # Only retry if subscription has failed payment status and has saved card
            if subscription.payment_status in ['overdue', 'retrying', 'failed'] and subscription.parent_order_id:
                # Find pending retries
                pending_retries = PaymentRetrySchedule.objects.filter(
                    subscription=subscription,
                    status='pending'
                ).order_by('scheduled_for')

                if pending_retries.exists():
                    # Execute the first pending retry
                    retry_schedule = pending_retries.first()
                    try:
                        execute_retry(retry_schedule)
                        retry_count += 1
                    except Exception as e:
                        error_count += 1
                        logger.error(f'Manual retry failed for subscription {subscription.id}: {e}')
                else:
                    # No retries scheduled - subscription might have exhausted all retries
                    error_count += 1

        if retry_count > 0:
            self.message_user(
                request,
                f'Successfully initiated {retry_count} payment retry/retries.',
                messages.SUCCESS
            )
        if error_count > 0:
            self.message_user(
                request,
                f'{error_count} subscription(s) could not be retried (no pending retries or no saved card).',
                messages.WARNING
            )

    # Display methods for payment health

    @admin.display(description='Payment Health')
    def payment_health_display(self, obj):
        """Display payment health status with colored badge"""
        status_config = {
            'current': {'color': '#4CAF50', 'text': '✓ Current'},
            'overdue': {'color': '#FF9800', 'text': '⚠ Overdue'},
            'retrying': {'color': '#FFC107', 'text': '🔄 Retrying'},
            'failed': {'color': '#F44336', 'text': '✗ Failed'},
            'no_card': {'color': '#9E9E9E', 'text': '⊘ No Card'},
        }

        config = status_config.get(obj.payment_status, {'color': '#9E9E9E', 'text': obj.payment_status})

        html = f'<span style="background-color: {config["color"]}; color: white; padding: 3px 10px; border-radius: 3px; display: inline-block;">{config["text"]}</span>'

        # Add failed count if > 0
        if obj.failed_payment_count > 0:
            html += f'<br><small style="color: #F44336;">Failed: {obj.failed_payment_count}x</small>'

        return format_html(html)

    @admin.display(description='Payment Attempts')
    def view_payment_attempts(self, obj):
        """Link to view all payment attempts for this subscription"""
        from django.urls import reverse
        from django.utils.http import urlencode

        count = obj.payment_attempts.count()
        if count == 0:
            return format_html('<span style="color: #999;">No attempts</span>')

        url = reverse('admin:tenants_paymentattempt_changelist')
        filter_params = urlencode({'subscription__id__exact': obj.id})
        link_url = f'{url}?{filter_params}'

        # Color code based on recent failures
        recent_failures = obj.payment_attempts.filter(status='failed').count()
        color = '#F44336' if recent_failures > 0 else '#4CAF50'

        return format_html(
            '<a href="{}" style="color: {}; text-decoration: none;">📋 {} attempts ({} failed)</a>',
            link_url, color, count, recent_failures
        )

    @admin.display(description='Subscription Events')
    def view_events(self, obj):
        """Link to view all events for this subscription"""
        from django.urls import reverse
        from django.utils.http import urlencode

        count = obj.events.count()
        if count == 0:
            return format_html('<span style="color: #999;">No events</span>')

        url = reverse('admin:tenants_subscriptionevent_changelist')
        filter_params = urlencode({'subscription__id__exact': obj.id})
        link_url = f'{url}?{filter_params}'

        return format_html(
            '<a href="{}" style="color: #2196F3; text-decoration: none;">📅 {} events</a>',
            link_url, count
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


@admin.register(SavedCard)
class SavedCardAdmin(admin.ModelAdmin):
    """Admin interface for SavedCard model"""
    list_display = [
        'tenant', 'card_display', 'card_expiry', 'saved_at', 'is_active'
    ]
    list_filter = ['is_active', 'card_type', 'saved_at']
    search_fields = ['tenant__name', 'tenant__schema_name', 'masked_card_number']
    ordering = ['-saved_at']
    readonly_fields = ['parent_order_id', 'card_type', 'masked_card_number', 'card_expiry', 'transaction_id', 'saved_at']

    fieldsets = (
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Card Details (Masked)', {
            'fields': ('card_type', 'masked_card_number', 'card_expiry')
        }),
        ('Payment Reference', {
            'fields': ('parent_order_id', 'transaction_id'),
            'description': 'BOG parent_order_id used for recurring payments'
        }),
        ('Status', {
            'fields': ('is_active', 'saved_at')
        })
    )

    @admin.display(description='Card')
    def card_display(self, obj):
        """Display card type and masked number"""
        if obj.card_type and obj.masked_card_number:
            return f"{obj.card_type.upper()} {obj.masked_card_number}"
        return '-'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    """Admin interface for PaymentOrder model"""
    list_display = [
        'order_id', 'tenant', 'amount', 'currency',
        'status_badge', 'created_at', 'paid_at'
    ]
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['order_id', 'tenant__name', 'tenant__schema_name']
    ordering = ['-created_at']
    readonly_fields = ['order_id', 'created_at', 'updated_at', 'paid_at']

    fieldsets = (
        ('Order Information', {
            'fields': ('order_id', 'tenant', 'status')
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
        return super().get_queryset(request).select_related('tenant')


# Inline admin for better UX
class TenantSubscriptionInline(admin.StackedInline):
    """Inline admin for TenantSubscription"""
    model = TenantSubscription
    extra = 0
    readonly_fields = ['monthly_cost', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Subscription', {
            'fields': ('is_active', 'starts_at', 'expires_at', 'agent_count')
        }),
        ('Usage', {
            'fields': ('current_users', 'whatsapp_messages_used', 'storage_used_gb'),
            'classes': ['collapse']
        }),
    )


class TenantAdmin(admin.ModelAdmin):
    """Admin interface for Tenant model"""
    list_display = [
        'name', 'schema_name', 'admin_email',
        'subscription_status', 'is_active', 'deployment_status', 'created_on'
    ]
    list_filter = ['is_active', 'deployment_status', 'preferred_language', 'plan']
    search_fields = ['name', 'admin_email', 'schema_name', 'domain_url']
    ordering = ['-created_on']
    readonly_fields = ['schema_name', 'created_on', 'subscription_details']
    inlines = [TenantSubscriptionInline]
    actions = ['activate_tenants', 'deactivate_tenants']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'schema_name', 'domain_url')
        }),
        ('Admin Contact', {
            'fields': ('admin_email', 'admin_name')
        }),
        ('Subscription', {
            'fields': ('subscription_details',),
            'description': 'Current subscription information (manage via inline below or Tenant Subscriptions)'
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

        html = '<div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px;">'
        html += f'<h3 style="margin-top: 0;">Feature-based Subscription</h3>'
        html += f'<p><strong>Monthly Cost:</strong> {subscription.monthly_cost}₾/month</p>'
        html += f'<p><strong>Agent Count:</strong> {subscription.agent_count}</p>'

        # Show selected features
        selected_features = subscription.selected_features.filter(is_active=True)
        if selected_features.exists():
            html += '<p><strong>Features:</strong></p><ul style="margin: 5px 0;">'
            for feature in selected_features:
                html += f'<li>{feature.name} ({feature.price_per_user_gel}₾/agent)</li>'
            html += '</ul>'

        html += f'<p><strong>Status:</strong> {"Active" if subscription.is_active else "Inactive"}</p>'
        html += f'<p><strong>Period:</strong> {subscription.starts_at.strftime("%Y-%m-%d")} to {subscription.expires_at.strftime("%Y-%m-%d") if subscription.expires_at else "No expiry"}</p>'

        # View subscription link
        url = reverse('admin:tenants_tenantsubscription_change', args=[subscription.id])
        html += f'<p><a href="{url}" style="color: #447e9b;">View/Edit Subscription →</a></p>'

        html += '</div>'

        return format_html(html)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('subscription__selected_features')

    def has_module_permission(self, request):
        # Only allow access in public schema
        if hasattr(request, 'tenant') and request.tenant.schema_name != get_public_schema_name():
            return False
        return super().has_module_permission(request)

    # Admin Actions removed - create_basic_subscription removed as packages no longer exist

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
        'schema_name', 'name', 'admin_email',
        'agent_count', 'status_badge', 'created_at', 'expires_at'
    ]
    list_filter = ['is_processed', 'created_at']
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


class FeatureAdminForm(forms.ModelForm):
    """Custom form for Feature admin with permissions selector"""
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(),  # Will be set in __init__
        required=False,
        widget=admin.widgets.FilteredSelectMultiple('Permissions', False),
        help_text='Select Django permissions that this feature will grant'
    )

    class Meta:
        model = Feature
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        import logging
        from django.db import connection
        logger = logging.getLogger(__name__)

        logger.info("FeatureAdminForm.__init__ called")

        # Check if we're in a bad transaction state before doing anything
        if connection.connection and connection.connection.get_transaction_status() == 3:  # STATUS_IN_ERROR
            logger.error("Transaction is already in error state before form init!")
            connection.rollback()

        super().__init__(*args, **kwargs)

        # Set the permissions queryset - do this safely to avoid transaction errors
        try:
            logger.info("Loading permissions queryset...")
            # Don't use select_related - it might cause issues with orphaned records
            self.fields['permissions'].queryset = Permission.objects.all().order_by('codename')
            logger.info(f"✅ Permissions queryset loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load permissions queryset: {e}", exc_info=True)
            self.fields['permissions'].queryset = Permission.objects.none()

        if self.instance.pk:
            # Load existing permissions for this feature using the reverse relationship
            try:
                logger.info(f"Loading existing permissions for feature {self.instance.key}...")
                # Get Permission objects from FeaturePermission junction table
                # related_name='permissions' gives us FeaturePermission queryset
                permission_ids = []
                for fp in self.instance.permissions.all():
                    try:
                        permission_ids.append(fp.permission_id)
                    except Exception as e:
                        logger.warning(f"Skipping invalid FeaturePermission: {e}")
                        # Skip FeaturePermissions with invalid permission_id
                        pass
                # Now get the actual Permission objects
                self.initial['permissions'] = Permission.objects.filter(id__in=permission_ids)
                logger.info(f"✅ Loaded {len(permission_ids)} permissions for feature")
            except Exception as e:
                logger.error(f"❌ Failed to load permissions for feature {self.instance.key}: {e}", exc_info=True)
                self.initial['permissions'] = Permission.objects.none()

    def save(self, commit=True):
        feature = super().save(commit=False)
        if commit:
            feature.save()
        if feature.pk:
            # Clear existing permissions
            FeaturePermission.objects.filter(feature=feature).delete()
            # Add new permissions
            for permission in self.cleaned_data['permissions']:
                FeaturePermission.objects.create(feature=feature, permission=permission)
        return feature


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    """Admin interface for Feature model"""
    # Temporarily disabled custom form to debug transaction errors
    # form = FeatureAdminForm
    list_display = [
        'name', 'key', 'category', 'price_per_user_gel', 'price_unlimited_gel',
        'icon_display', 'permission_count', 'sort_order', 'is_active', 'created_at'
    ]
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['key', 'name', 'description']
    ordering = ['category', 'sort_order', 'name']

    fieldsets = (
        ('Basic Information', {
            'fields': ('key', 'name', 'description')
        }),
        # Permissions fieldset removed - only available with custom form
        ('Pricing', {
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
        try:
            count = obj.permissions.count()
            return f"{count} permission{'s' if count != 1 else ''}"
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to count permissions for feature {obj.key}: {e}")
            return "Error"


# Using Django's built-in Permission admin instead of custom Permission model
# Permissions are managed through Django Admin -> Authentication and Authorization -> Permissions


@admin.register(FeaturePermission)
class FeaturePermissionAdmin(admin.ModelAdmin):
    """Admin interface for FeaturePermission model"""
    list_display = ['feature', 'permission', 'is_required']
    list_filter = ['is_required', 'feature__category']
    search_fields = ['feature__name', 'permission__name', 'permission__codename']
    autocomplete_fields = ['feature']
    raw_id_fields = ['permission']

    fieldsets = (
        ('Relationship', {
            'fields': ('feature', 'permission')
        }),
        ('Configuration', {
            'fields': ('is_required',)
        })
    )


# TenantFeatureAdmin removed - feature management should be done through
# TenantSubscription.selected_features (via TenantSubscriptionAdmin).
# Direct TenantFeature manipulation can cause inconsistency.
# TenantFeature model is kept for historical data only.


@admin.register(TenantPermission)
class TenantPermissionAdmin(admin.ModelAdmin):
    """Admin interface for TenantPermission model"""
    list_display = [
        'tenant', 'permission', 'granted_by_feature', 'is_active', 'granted_at'
    ]
    list_filter = ['is_active', 'permission__content_type__app_label', 'granted_at']
    search_fields = ['tenant__name', 'tenant__schema_name', 'permission__name', 'permission__codename']
    autocomplete_fields = ['tenant', 'granted_by_feature']
    raw_id_fields = ['permission']
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
# TenantPermission shows which permissions are available to the tenant based on their selected features


# ====================================================================================
# SUBSCRIPTION MANAGEMENT ADMIN CLASSES
# ====================================================================================

@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    """Admin interface for payment attempts"""
    list_display = [
        'id',
        'tenant_link',
        'amount_display',
        'status_badge',
        'attempt_number',
        'is_retry',
        'attempted_at',
        'duration_display',
    ]
    list_filter = [
        'status',
        'is_retry',
        ('attempted_at', admin.DateFieldListFilter),
    ]
    search_fields = [
        'tenant__name',
        'tenant__schema_name',
        'bog_order_id',
        'payment_order__order_id',
    ]
    readonly_fields = [
        'payment_order',
        'subscription',
        'tenant',
        'attempt_number',
        'status',
        'bog_order_id',
        'amount',
        'attempted_at',
        'completed_at',
        'failed_reason',
        'bog_error_code',
        'bog_response_display',
        'is_retry',
        'parent_attempt',
        'duration_display',
    ]
    date_hierarchy = 'attempted_at'
    ordering = ['-attempted_at']

    def tenant_link(self, obj):
        if obj.tenant:
            url = reverse('admin:tenants_tenant_change', args=[obj.tenant.pk])
            return format_html('<a href="{}">{}</a>', url, obj.tenant.name)
        return '-'
    tenant_link.short_description = 'Tenant'

    def amount_display(self, obj):
        return f'{obj.amount} GEL'
    amount_display.short_description = 'Amount'

    def status_badge(self, obj):
        colors = {
            'pending': '#FFA500',
            'success': '#28A745',
            'failed': '#DC3545',
            'cancelled': '#6C757D',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.status.upper()
        )
    status_badge.short_description = 'Status'

    def duration_display(self, obj):
        if obj.duration:
            return f'{obj.duration:.2f}s'
        return '-'
    duration_display.short_description = 'Duration'

    def bog_response_display(self, obj):
        import json
        return format_html('<pre>{}</pre>', json.dumps(obj.bog_response, indent=2))
    bog_response_display.short_description = 'BOG Response'


@admin.register(SubscriptionEvent)
class SubscriptionEventAdmin(admin.ModelAdmin):
    """Admin interface for subscription events"""
    list_display = [
        'id',
        'tenant_link',
        'event_type_badge',
        'description_short',
        'created_at',
        'created_by',
    ]
    list_filter = [
        'event_type',
        ('created_at', admin.DateFieldListFilter),
    ]
    search_fields = [
        'tenant__name',
        'tenant__schema_name',
        'description',
    ]
    readonly_fields = [
        'subscription',
        'tenant',
        'event_type',
        'payment_order',
        'payment_attempt',
        'old_value',
        'new_value',
        'metadata',
        'description',
        'created_at',
        'created_by',
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    def tenant_link(self, obj):
        url = reverse('admin:tenants_tenant_change', args=[obj.tenant.pk])
        return format_html('<a href="{}">{}</a>', url, obj.tenant.name)
    tenant_link.short_description = 'Tenant'

    def event_type_badge(self, obj):
        colors = {
            'created': '#17A2B8',
            'payment_success': '#28A745',
            'payment_failed': '#DC3545',
            'retry_success': '#FFC107',
            'suspended': '#6C757D',
            'cancelled': '#343A40',
        }
        color = colors.get(obj.event_type, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_event_type_display()
        )
    event_type_badge.short_description = 'Event'

    def description_short(self, obj):
        if len(obj.description) > 80:
            return obj.description[:80] + '...'
        return obj.description
    description_short.short_description = 'Description'


@admin.register(PaymentRetrySchedule)
class PaymentRetryScheduleAdmin(admin.ModelAdmin):
    """Admin interface for payment retry schedules"""
    list_display = [
        'id',
        'tenant_link',
        'retry_number',
        'status_badge',
        'scheduled_for',
        'executed_at',
        'is_overdue_display',
    ]
    list_filter = [
        'status',
        'retry_number',
        ('scheduled_for', admin.DateFieldListFilter),
    ]
    search_fields = [
        'tenant__name',
        'tenant__schema_name',
    ]
    readonly_fields = [
        'payment_order',
        'subscription',
        'tenant',
        'original_attempt',
        'retry_number',
        'scheduled_for',
        'executed_at',
        'status',
        'retry_attempt',
        'skip_reason',
    ]
    actions = ['execute_retry_now', 'skip_retry', 'cancel_retry']
    date_hierarchy = 'scheduled_for'
    ordering = ['scheduled_for']

    def tenant_link(self, obj):
        url = reverse('admin:tenants_tenant_change', args=[obj.tenant.pk])
        return format_html('<a href="{}">{}</a>', url, obj.tenant.name)
    tenant_link.short_description = 'Tenant'

    def status_badge(self, obj):
        colors = {
            'pending': '#FFA500',
            'executing': '#17A2B8',
            'succeeded': '#28A745',
            'failed': '#DC3545',
            'skipped': '#6C757D',
            'cancelled': '#343A40',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.status.upper()
        )
    status_badge.short_description = 'Status'

    def is_overdue_display(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color: red; font-weight: bold;">⚠ OVERDUE</span>')
        return '-'
    is_overdue_display.short_description = 'Overdue?'

    def execute_retry_now(self, request, queryset):
        """Execute selected retries immediately"""
        from .subscription_utils import execute_retry
        count = 0
        for retry in queryset.filter(status='pending'):
            result = execute_retry(retry)
            if result['success']:
                count += 1
        self.message_user(request, f'{count} retry(ies) executed successfully.', messages.SUCCESS)
    execute_retry_now.short_description = 'Execute retry now'

    def skip_retry(self, request, queryset):
        """Skip selected retries"""
        count = queryset.filter(status='pending').update(
            status='skipped',
            skip_reason='Manually skipped by admin',
            executed_at=timezone.now()
        )
        self.message_user(request, f'{count} retry(ies) skipped.', messages.SUCCESS)
    skip_retry.short_description = 'Skip retry'

    def cancel_retry(self, request, queryset):
        """Cancel selected retries"""
        count = queryset.filter(status='pending').update(
            status='cancelled',
            skip_reason='Manually cancelled by admin',
            executed_at=timezone.now()
        )
        self.message_user(request, f'{count} retry(ies) cancelled.', messages.SUCCESS)
    cancel_retry.short_description = 'Cancel retry'


@admin.register(PlatformMetrics)
class PlatformMetricsAdmin(admin.ModelAdmin):
    """Admin interface for platform metrics"""
    list_display = [
        'date',
        'active_subscriptions',
        'mrr_display',
        'successful_payments',
        'failed_payments',
        'payment_success_rate_display',
        'churn_rate_display',
    ]
    list_filter = [
        ('date', admin.DateFieldListFilter),
    ]
    readonly_fields = [
        'date',
        'total_subscriptions',
        'active_subscriptions',
        'trial_subscriptions',
        'suspended_subscriptions',
        'cancelled_subscriptions',
        'new_subscriptions_today',
        'cancelled_today',
        'mrr',
        'arr',
        'total_revenue_today',
        'successful_payments',
        'failed_payments',
        'retry_success_rate',
        'churn_rate',
        'retention_rate',
        'calculated_at',
        'payment_success_rate',
    ]
    ordering = ['-date']

    def mrr_display(self, obj):
        return f'{obj.mrr} GEL'
    mrr_display.short_description = 'MRR'

    def payment_success_rate_display(self, obj):
        rate = obj.payment_success_rate
        color = '#28A745' if rate >= 95 else '#FFC107' if rate >= 85 else '#DC3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            f'{rate:.1f}%'
        )
    payment_success_rate_display.short_description = 'Success Rate'

    def churn_rate_display(self, obj):
        rate = float(obj.churn_rate)
        color = '#28A745' if rate <= 5 else '#FFC107' if rate <= 10 else '#DC3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            f'{rate:.2f}%'
        )
    churn_rate_display.short_description = 'Churn Rate'
