from django.contrib import admin
from .models import WidgetConnection


@admin.register(WidgetConnection)
class WidgetConnectionAdmin(admin.ModelAdmin):
    list_display = ('label', 'tenant_schema', 'widget_token', 'is_active', 'created_at')
    list_filter = ('is_active', 'tenant_schema')
    search_fields = ('widget_token', 'label', 'tenant_schema')
    readonly_fields = ('widget_token', 'created_at', 'updated_at')
