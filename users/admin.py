from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group
from .models import User, Department, TenantGroup


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


@admin.register(TenantGroup)
class TenantGroupAdmin(admin.ModelAdmin):
    """TenantGroup admin interface"""
    list_display = ('name', 'description', 'get_member_count', 'get_permissions_summary')
    list_filter = (
        'can_view_all_tickets', 'can_manage_users', 'can_make_calls', 
        'can_manage_groups', 'can_manage_settings'
    )
    search_fields = ('name', 'description')
    ordering = ('name',)
    
    def get_member_count(self, obj):
        return obj.tenant_groups.count()
    get_member_count.short_description = 'Members'
    
    def get_permissions_summary(self, obj):
        permissions = []
        if obj.can_view_all_tickets:
            permissions.append('View All Tickets')
        if obj.can_manage_users:
            permissions.append('Manage Users')
        if obj.can_make_calls:
            permissions.append('Make Calls')
        if obj.can_manage_groups:
            permissions.append('Manage Groups')
        if obj.can_manage_settings:
            permissions.append('Manage Settings')
        return ', '.join(permissions) if permissions else 'No special permissions'
    get_permissions_summary.short_description = 'Key Permissions'


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
