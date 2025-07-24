#!/usr/bin/env python
"""
Test script for tenant registration API
"""
import os
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')
django.setup()

import json
from django.test import Client
from django.urls import reverse

def test_registration_api():
    """Test the public tenant registration API"""
    
    client = Client()
    
    print("🧪 Testing tenant registration API...\n")
    
    # Test data for new tenant
    registration_data = {
        'company_name': 'Test Company',
        'domain': 'testcompany',
        'description': 'A test company for API testing',
        'admin_email': 'admin@testcompany.com',
        'admin_password': 'TestPassword123',
        'admin_first_name': 'Test',
        'admin_last_name': 'Admin'
    }
    
    print("📋 Registration Data:")
    for key, value in registration_data.items():
        if key == 'admin_password':
            print(f"   {key}: {'*' * len(value)}")
        else:
            print(f"   {key}: {value}")
    
    print(f"\n🌐 Testing endpoint: /api/register/")
    
    try:
        # Make the registration request
        response = client.post(
            '/api/register/',
            data=json.dumps(registration_data),
            content_type='application/json',
            HTTP_HOST='echodesk.ge'  # Simulate main domain
        )
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 201:
            result = response.json()
            print("✅ Registration successful!")
            print(f"   🏢 Tenant: {result['tenant']['name']}")
            print(f"   🌐 Domain: {result['tenant']['domain']}")
            print(f"   🔗 Login URL: {result['login_url']}")
            print(f"   📧 Admin Email: {result['credentials']['email']}")
        else:
            print("❌ Registration failed!")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Error: {response.content}")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_registration_api()
