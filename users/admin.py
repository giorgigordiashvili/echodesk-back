from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Display settings
    list_display = (
        'email', 
        'get_full_name', 
        'is_active_badge', 
        'is_staff_badge',
        'last_login_formatted',
        'date_joined_formatted',
        'user_actions'
    )
    list_filter = (
        'is_active', 
        'is_staff', 
        'is_superuser',
        'date_joined',
        'last_login'
    )
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    list_per_page = 25
    
    # Form settings
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'is_staff', 'is_active'),
        }),
    )
    
    readonly_fields = ('last_login', 'date_joined')
    filter_horizontal = ('groups', 'user_permissions')
    
    # Custom methods for better display
    def get_full_name(self, obj):
        """Display full name or email if no name provided"""
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.email
    get_full_name.short_description = 'Full Name'
    
    def is_active_badge(self, obj):
        """Display active status as colored badge"""
        if obj.is_active:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Active</span>'
            )
        return format_html(
            '<span style="color: #dc3545; font-weight: bold;">✗ Inactive</span>'
        )
    is_active_badge.short_description = 'Status'
    
    def is_staff_badge(self, obj):
        """Display staff status as badge"""
        if obj.is_staff:
            return format_html(
                '<span style="background: #007bff; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">STAFF</span>'
            )
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">USER</span>'
        )
    is_staff_badge.short_description = 'Role'
    
    def last_login_formatted(self, obj):
        """Format last login date"""
        if obj.last_login:
            return obj.last_login.strftime('%Y-%m-%d %H:%M')
        return 'Never'
    last_login_formatted.short_description = 'Last Login'
    
    def date_joined_formatted(self, obj):
        """Format date joined"""
        return obj.date_joined.strftime('%Y-%m-%d %H:%M')
    date_joined_formatted.short_description = 'Joined'
    
    def user_actions(self, obj):
        """Display action buttons"""
        actions = []
        
        # View user details
        view_url = reverse('admin:users_user_change', args=[obj.pk])
        actions.append(f'<a href="{view_url}" style="color: #007bff;">Edit</a>')
        
        # Toggle active status
        if obj.is_active:
            actions.append('<span style="color: #28a745;">Active</span>')
        else:
            actions.append('<span style="color: #dc3545;">Inactive</span>')
            
        return mark_safe(' | '.join(actions))
    user_actions.short_description = 'Actions'
    
    # Custom actions
    actions = ['activate_users', 'deactivate_users']
    
    def activate_users(self, request, queryset):
        """Bulk activate users"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} user(s) activated successfully.')
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        """Bulk deactivate users"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} user(s) deactivated successfully.')
    deactivate_users.short_description = "Deactivate selected users"
