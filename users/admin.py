from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group
from .models import User, Department


# Unregister the default Group admin and register our custom one
admin.site.unregister(Group)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Department admin interface"""
    list_display = ('name', 'description', 'get_employee_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    
    def get_employee_count(self, obj):
        return obj.employees.count()
    get_employee_count.short_description = 'Employees'


# TenantGroup admin removed - groups are no longer used


class CustomGroupAdmin(BaseGroupAdmin):
    """Custom Group admin with better permission display"""
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


class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ('email', 'first_name', 'last_name', 'department', 'role', 'status', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('role', 'status', 'department', 'is_active', 'is_staff', 'groups')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number', 'job_title', 'department')}),
        ('User Management', {'fields': ('role', 'status')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
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
    filter_horizontal = ('groups', 'user_permissions')
    readonly_fields = ('date_joined', 'last_login')


# Register models
admin.site.register(User, UserAdmin)
admin.site.register(Group, CustomGroupAdmin)
