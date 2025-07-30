from django.contrib import admin
from django.contrib.admin import AdminSite
from django.urls import path
from django.shortcuts import render
from django.db.models import Count
from django.utils.html import format_html

try:
    from users.models import User
    HAS_USERS_APP = True
except ImportError:
    # Users app not available in public schema
    HAS_USERS_APP = False
    User = None


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
    
    def get_user_statistics(self):
        """Get user statistics for dashboard"""
        if not HAS_USERS_APP or not User:
            return {
                'total': 0,
                'active': 0,
                'inactive': 0,
                'staff': 0,
                'active_percentage': 0,
            }
        
        try:
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
            # Handle case where users table doesn't exist in current schema
            return {
                'total': 0,
                'active': 0,
                'inactive': 0,
                'staff': 0,
                'active_percentage': 0,
            }
    
    def get_recent_users(self):
        """Get recent users for dashboard"""
        if not HAS_USERS_APP or not User:
            return []
        
        try:
            return User.objects.order_by('-date_joined')[:10]
        except Exception:
            # Handle case where users table doesn't exist in current schema
            return []
    
    def index(self, request, extra_context=None):
        """Override admin index to show custom dashboard"""
        extra_context = extra_context or {}
        extra_context['dashboard_stats'] = self.get_user_statistics()
        return super().index(request, extra_context)


# Create custom admin site instance
admin_site = AmanatiCRMAdminSite(name='amanati_admin')
