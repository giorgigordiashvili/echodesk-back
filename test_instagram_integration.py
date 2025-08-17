#!/usr/bin/env python
"""
Instagram Integration Status Check
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')
django.setup()

from social_integrations.models import InstagramAccountConnection, FacebookPageConnection
from tenants.models import Tenant
from tenant_schemas.utils import schema_context
import requests

def check_instagram_integration():
    """Check Instagram integration status"""
    print("=== Instagram Integration Status Check ===")
    
    # Get all tenants
    tenants = Tenant.objects.all()
    print(f"📋 Found {tenants.count()} tenants: {[t.schema_name for t in tenants]}")
    
    for tenant in tenants:
        print(f"\n🏢 Checking tenant: {tenant.schema_name}")
        
        try:
            with schema_context(tenant.schema_name):
                # Check Instagram accounts
                instagram_accounts = InstagramAccountConnection.objects.filter(is_active=True)
                print(f"📸 Instagram accounts: {instagram_accounts.count()}")
                
                for account in instagram_accounts:
                    print(f"   - @{account.username} ({account.instagram_account_id})")
                    
                    # Test token validity
                    test_url = f"https://graph.facebook.com/v23.0/{account.instagram_account_id}"
                    params = {'access_token': account.access_token, 'fields': 'id,username'}
                    
                    try:
                        response = requests.get(test_url, params=params)
                        if response.status_code == 200:
                            print(f"     ✅ Token valid")
                        else:
                            print(f"     ❌ Token invalid: {response.status_code} - {response.text}")
                    except Exception as e:
                        print(f"     ⚠️ Token test failed: {e}")
                
                # Check Facebook pages
                facebook_pages = FacebookPageConnection.objects.filter(is_active=True)
                print(f"📘 Facebook pages: {facebook_pages.count()}")
                
                for page in facebook_pages:
                    print(f"   - {page.page_name} ({page.page_id})")
                    
                    # Test page token validity
                    test_url = f"https://graph.facebook.com/v23.0/{page.page_id}"
                    params = {'access_token': page.page_access_token, 'fields': 'id,name'}
                    
                    try:
                        response = requests.get(test_url, params=params)
                        if response.status_code == 200:
                            print(f"     ✅ Page token valid")
                        else:
                            print(f"     ❌ Page token invalid: {response.status_code} - {response.text}")
                    except Exception as e:
                        print(f"     ⚠️ Page token test failed: {e}")
                
                # Check Instagram-Facebook connection
                if instagram_accounts.exists() and facebook_pages.exists():
                    print(f"🔗 Can use Facebook page tokens for Instagram messaging")
                elif instagram_accounts.exists() and not facebook_pages.exists():
                    print(f"⚠️ Instagram accounts exist but no Facebook pages - messaging may not work")
                elif not instagram_accounts.exists():
                    print(f"❌ No Instagram accounts connected")
                    
        except Exception as e:
            print(f"⚠️ Error checking tenant {tenant.schema_name}: {e}")

def check_app_permissions():
    """Check Meta app permissions"""
    print(f"\n=== Meta App Configuration Check ===")
    
    # Get app credentials from environment
    app_id = os.getenv('INSTAGRAM_APP_ID', 'Not set')
    app_secret = os.getenv('INSTAGRAM_APP_SECRET', 'Not set')
    
    print(f"📱 Instagram App ID: {app_id}")
    print(f"🔑 Instagram App Secret: {'Set' if app_secret != 'Not set' else 'Not set'}")
    
    if app_id and app_id != 'Not set':
        # Check app info
        app_url = f"https://graph.facebook.com/v23.0/{app_id}"
        params = {'access_token': f"{app_id}|{app_secret}"}
        
        try:
            response = requests.get(app_url, params=params)
            if response.status_code == 200:
                app_data = response.json()
                print(f"✅ App found: {app_data.get('name', 'Unknown')}")
                print(f"   Category: {app_data.get('category', 'Unknown')}")
            else:
                print(f"❌ App check failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"⚠️ App check error: {e}")

def test_instagram_messaging_permissions():
    """Test Instagram messaging permissions"""
    print(f"\n=== Instagram Messaging Permissions Test ===")
    
    # Get a sample Instagram account from the first tenant
    tenants = Tenant.objects.all()
    test_account = None
    
    for tenant in tenants:
        try:
            with schema_context(tenant.schema_name):
                account = InstagramAccountConnection.objects.filter(is_active=True).first()
                if account:
                    test_account = account
                    break
        except:
            continue
    
    if not test_account:
        print("❌ No Instagram accounts found for testing")
        return
    
    print(f"🧪 Testing with account: @{test_account.username}")
    
    # Test permissions endpoint
    permissions_url = f"https://graph.facebook.com/v23.0/{test_account.instagram_account_id}/permissions"
    params = {'access_token': test_account.access_token}
    
    try:
        response = requests.get(permissions_url, params=params)
        if response.status_code == 200:
            permissions = response.json()
            print(f"✅ Permissions check successful")
            print(f"   Data: {permissions}")
        else:
            print(f"❌ Permissions check failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"⚠️ Permissions test error: {e}")

if __name__ == "__main__":
    check_instagram_integration()
    check_app_permissions()
    test_instagram_messaging_permissions()
    
    print(f"\n=== Next Steps ===")
    print(f"1. Check Meta Developers Console:")
    print(f"   - Go to https://developers.facebook.com/apps/")
    print(f"   - Select your app (ID: {os.getenv('INSTAGRAM_APP_ID', 'Not set')})")
    print(f"   - Products → Instagram → Add if not present")
    print(f"   - App Review → Request 'instagram_manage_messages' permission")
    print(f"")
    print(f"2. Verify Instagram Business Account:")
    print(f"   - Must be connected to a Facebook Page")
    print(f"   - Must be a Business account (not personal)")
    print(f"")
    print(f"3. Test messaging permissions:")
    print(f"   - Add test users in Meta app dashboard")
    print(f"   - Test with those users first")
