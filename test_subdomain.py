#!/usr/bin/env python
"""
Test script to verify subdomain routing and tenant isolation
"""
import os
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')
django.setup()

from django.test import RequestFactory
from amanati_crm.middleware import EchoDeskTenantMiddleware
from tenant_schemas.utils import get_public_schema_name
from tenants.models import Tenant

def test_subdomain_routing():
    """Test that subdomains route to the correct tenant schema"""
    
    # Create request factory
    factory = RequestFactory()
    
    # Create a dummy get_response function
    def get_response(request):
        return None
    
    middleware = EchoDeskTenantMiddleware(get_response)
    
    print("🧪 Testing subdomain routing...\n")
    
    # Test main domain
    print("1️⃣ Testing main domain (echodesk.ge):")
    request = factory.get('/')
    request.META['HTTP_HOST'] = 'echodesk.ge'
    
    try:
        middleware.process_request(request)
        print(f"   ✅ Schema: {request.tenant.schema_name}")
        print(f"   🌐 Domain: {request.tenant.domain_url}")
        print(f"   📋 URL Conf: {getattr(request, 'urlconf', 'default')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()
    
    # Test amanati subdomain
    print("2️⃣ Testing amanati subdomain (amanati.echodesk.ge):")
    request = factory.get('/')
    request.META['HTTP_HOST'] = 'amanati.echodesk.ge'
    
    try:
        middleware.process_request(request)
        print(f"   ✅ Schema: {request.tenant.schema_name}")
        print(f"   🌐 Domain: {request.tenant.domain_url}")
        print(f"   📋 URL Conf: {getattr(request, 'urlconf', 'default')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()
    
    # List all tenants
    print("3️⃣ Available tenants:")
    tenants = Tenant.objects.all()
    for tenant in tenants:
        print(f"   📁 {tenant.schema_name}: {tenant.domain_url} ({tenant.name})")

if __name__ == "__main__":
    test_subdomain_routing()
