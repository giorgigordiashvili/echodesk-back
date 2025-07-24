#!/usr/bin/env python
"""
Test script to verify tenant admin user credentials
"""
import os
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')
django.setup()

from django.contrib.auth import authenticate
from tenant_schemas.utils import schema_context
from tenants.models import Tenant

def test_tenant_login(tenant_schema, email, password):
    """Test login for a tenant admin user"""
    print(f"\n🔍 Testing login for tenant: {tenant_schema}")
    print(f"📧 Email: {email}")
    print(f"🔑 Password: {'*' * len(password)}")
    
    try:
        # Get tenant
        tenant = Tenant.objects.get(schema_name=tenant_schema)
        print(f"✅ Found tenant: {tenant.name} ({tenant.domain_url})")
        
        # Switch to tenant schema and test authentication
        with schema_context(tenant.schema_name):
            user = authenticate(username=email, password=password)
            if user:
                print(f"✅ Login successful!")
                print(f"👤 User: {user.first_name} {user.last_name} ({user.email})")
                print(f"🔐 Is staff: {user.is_staff}")
                print(f"🛡️  Is superuser: {user.is_superuser}")
                return True
            else:
                print(f"❌ Login failed - Invalid credentials")
                return False
                
    except Tenant.DoesNotExist:
        print(f"❌ Tenant '{tenant_schema}' not found")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    # Test the amanati tenant login
    test_tenant_login("amanati", "amanati@echodesk.ge", "Giorgi123")
