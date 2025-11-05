from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group
from django.db import connection
from tenant_schemas.utils import get_public_schema_name
from .models import User, Department, Notification


# Unregister the default Group admin and register our custom one
admin.site.unregister(Group)


class TenantAwareAdminMixin:
    """Mixin to restrict admin models to tenant schemas only"""

    def has_module_permission(self, request):
        """Only show this admin in tenant schemas, not public schema"""
        if hasattr(connection, 'schema_name'):
            schema_name = connection.schema_name
        else:
            schema_name = get_public_schema_name()

        # Hide from public schema admin
        if schema_name == get_public_schema_name():
            return False

        return super().has_module_permission(request)


@admin.register(Department)
class DepartmentAdmin(TenantAwareAdminMixin, admin.ModelAdmin):
    """Department admin interface - Only available in tenant schemas"""
    list_display = ('name', 'description', 'get_employee_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')

    def get_employee_count(self, obj):
        return obj.employees.count()
    get_employee_count.short_description = 'Employees'


# TenantGroup admin removed - groups are no longer used


class CustomGroupAdmin(TenantAwareAdminMixin, BaseGroupAdmin):
    """Custom Group admin with better permission display - Only in tenant schemas"""
    list_display = ('name', 'get_user_count', 'get_permissions_count')
    list_filter = ('permissions',)
    search_fields = ('name',)
    filter_horizontal = ('permissions',)

    def get_user_count(self, obj):
        return obj.user_set.count()
    get_user_count.short_description = 'Users'

    def get_permissions_count(self, obj):
        return obj.permissions.count()
    get_permissions_count.short_description = 'Permissions'


class UserAdmin(TenantAwareAdminMixin, BaseUserAdmin):
    """User admin interface - Only available in tenant schemas"""
    model = User
    list_display = ('email', 'first_name', 'last_name', 'department', 'role', 'status', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('role', 'status', 'department', 'is_active', 'is_staff')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number', 'job_title', 'department')}),
        ('User Management', {'fields': ('role', 'status')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Invitation tracking', {'fields': ('invited_by', 'invitation_sent_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'department', 'role'),
        }),
    )
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    readonly_fields = ('date_joined', 'last_login')
    filter_horizontal = ()  # No groups or user_permissions fields


@admin.register(Notification)
class NotificationAdmin(TenantAwareAdminMixin, admin.ModelAdmin):
    """Notification admin interface - Only available in tenant schemas"""
    list_display = ('user', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__email', 'title', 'message')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'read_at')
    list_select_related = ('user',)

    fieldsets = (
        (None, {
            'fields': ('user', 'notification_type', 'title', 'message')
        }),
        ('Ticket Info', {
            'fields': ('ticket_id', 'metadata')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at', 'created_at')
        }),
    )


# Register models
admin.site.register(User, UserAdmin)
admin.site.register(Group, CustomGroupAdmin)
