from django.contrib import admin
from .models import PushSubscription, NotificationLog


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    """Admin for push subscriptions."""
    list_display = ('user', 'endpoint_short', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__email', 'endpoint')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

    def endpoint_short(self, obj):
        """Show shortened endpoint."""
        return obj.endpoint[:50] + '...' if len(obj.endpoint) > 50 else obj.endpoint
    endpoint_short.short_description = 'Endpoint'


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """Admin for notification logs."""
    list_display = ('user', 'title', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__email', 'title', 'body')
    readonly_fields = ('user', 'subscription', 'title', 'body', 'data', 'status', 'error_message', 'created_at')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        """Don't allow manual creation."""
        return False
