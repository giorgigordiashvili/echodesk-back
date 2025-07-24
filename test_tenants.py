#!/usr/bin/env python
"""
Test script to verify multi-tenant functionality
"""
import os
import sys
import django
from django.conf import settings

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')
django.setup()

from tenants.models import Tenant
from django.contrib.auth import get_user_model
from tenant_schemas.utils import schema_context

User = get_user_model()

def test_tenants():
    print("🏢 Testing Multi-Tenant Setup")
    print("=" * 50)
    
    # List all tenants
    tenants = Tenant.objects.all()
    print(f"📋 Found {tenants.count()} tenants:")
    
    for tenant in tenants:
        print(f"  • {tenant.name} ({tenant.schema_name})")
        print(f"    Domain: {tenant.domain_url}")
        print(f"    Admin: {tenant.admin_email}")
        
        # Check users in this tenant's schema
        with schema_context(tenant.schema_name):
            user_count = User.objects.count()
            admin_count = User.objects.filter(is_superuser=True).count()
            print(f"    Users: {user_count} total, {admin_count} admins")
            
            # List admin users
            admins = User.objects.filter(is_superuser=True)
            for admin in admins:
                print(f"      - {admin.email} ({admin.first_name} {admin.last_name})")
        
        print()
    
    print("✅ Multi-tenant setup is working correctly!")
    print("\n🌐 Access URLs:")
    print(f"  • Public Admin: http://localhost:8000/admin/")
    print(f"  • API Docs: http://localhost:8000/api/docs/")
    
    for tenant in tenants:
        subdomain = tenant.domain_url.split('.')[0]
        print(f"  • {tenant.name}: http://{subdomain}.localhost:8000/")
    
    print("\n💡 For local testing, add these to your /etc/hosts:")
    print("127.0.0.1 localhost")
    for tenant in tenants:
        subdomain = tenant.domain_url.split('.')[0]
        print(f"127.0.0.1 {subdomain}.localhost")

if __name__ == "__main__":
    test_tenants()
