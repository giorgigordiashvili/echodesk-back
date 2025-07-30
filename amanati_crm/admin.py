from django.contrib import admin
from django.contrib.admin import AdminSite
from django.urls import path
from django.shortcuts import render
from django.db.models import Count
from django.utils.html import format_html
from django.db import connection


class AmanatiCRMAdminSite(AdminSite):
    """Custom admin site for Amanati CRM"""
    
    site_header = 'Amanati CRM Administration'
    site_title = 'Amanati CRM Admin'
    index_title = 'Welcome to Amanati CRM Administration'
    
    def get_urls(self):
        """Add custom URLs to admin"""
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='dashboard'),
        ]
        return custom_urls + urls
    
    def dashboard_view(self, request):
        """Custom dashboard view with statistics"""
        context = {
            'title': 'Dashboard',
            'user_stats': self.get_user_statistics(),
            'recent_users': self.get_recent_users(),
        }
        return render(request, 'admin/dashboard.html', context)
    
    def is_tenant_schema(self):
        """Check if we're in a tenant schema (not public)"""
        schema_name = connection.schema_name if hasattr(connection, 'schema_name') else 'public'
        return schema_name != 'public'
    
    def get_user_statistics(self):
        """Get user statistics for dashboard"""
        # Only try to get user stats in tenant schemas
        if not self.is_tenant_schema():
            return {
                'total': 0,
                'active': 0,
                'inactive': 0,
                'staff': 0,
                'active_percentage': 0,
            }
        
        try:
            from users.models import User
            total_users = User.objects.count()
            active_users = User.objects.filter(is_active=True).count()
            staff_users = User.objects.filter(is_staff=True).count()
            inactive_users = total_users - active_users
            
            return {
                'total': total_users,
                'active': active_users,
                'inactive': inactive_users,
                'staff': staff_users,
                'active_percentage': round((active_users / total_users * 100) if total_users > 0 else 0, 1),
            }
        except Exception:
            # Handle any import or database errors
            return {
                'total': 0,
                'active': 0,
                'inactive': 0,
                'staff': 0,
                'active_percentage': 0,
            }
    
    def get_recent_users(self):
        """Get recent users for dashboard"""
        # Only try to get users in tenant schemas
        if not self.is_tenant_schema():
            return []
        
        try:
            from users.models import User
            return User.objects.order_by('-date_joined')[:10]
        except Exception:
            # Handle any import or database errors
            return []
    
    def index(self, request, extra_context=None):
        """Override admin index to show custom dashboard"""
        extra_context = extra_context or {}
        
        # Only add dashboard stats in tenant schemas
        if self.is_tenant_schema():
            extra_context['dashboard_stats'] = self.get_user_statistics()
        else:
            # For public schema, provide empty stats
            extra_context['dashboard_stats'] = {
                'total': 0,
                'active': 0,
                'inactive': 0,
                'staff': 0,
                'active_percentage': 0,
            }
        
        return super().index(request, extra_context)


# Create custom admin site instance
admin_site = AmanatiCRMAdminSite(name='amanati_admin')
