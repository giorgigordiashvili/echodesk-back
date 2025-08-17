#!/usr/bin/env python
"""
Quick test for Instagram send message fix
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

def test_instagram_send_message_tokens():
    """Test that Instagram send message can access the correct tokens"""
    print("=== Testing Instagram Send Message Token Access ===")
    
    # Get all tenants
    tenants = Tenant.objects.all()
    
    for tenant in tenants:
        print(f"\n🏢 Checking tenant: {tenant.schema_name}")
        
        try:
            with schema_context(tenant.schema_name):
                # Check Instagram accounts
                instagram_accounts = InstagramAccountConnection.objects.filter(is_active=True)
                facebook_pages = FacebookPageConnection.objects.filter(is_active=True)
                
                print(f"📸 Instagram accounts: {instagram_accounts.count()}")
                print(f"📘 Facebook pages: {facebook_pages.count()}")
                
                if instagram_accounts.exists() and facebook_pages.exists():
                    instagram_account = instagram_accounts.first()
                    facebook_page = facebook_pages.first()
                    
                    print(f"✅ Instagram account: @{instagram_account.username}")
                    print(f"✅ Facebook page: {facebook_page.page_name}")
                    
                    # Test accessing the tokens (without making API calls)
                    try:
                        instagram_token = instagram_account.access_token
                        page_token = facebook_page.page_access_token
                        
                        print(f"✅ Instagram token accessible: {len(instagram_token)} chars")
                        print(f"✅ Facebook page token accessible: {len(page_token)} chars")
                        
                        # This simulates what the send message function does
                        selected_token = page_token if page_token else instagram_token
                        print(f"✅ Selected token for messaging: {len(selected_token)} chars")
                        
                    except AttributeError as e:
                        print(f"❌ Token access error: {e}")
                        
                elif instagram_accounts.exists() and not facebook_pages.exists():
                    instagram_account = instagram_accounts.first()
                    print(f"⚠️ Only Instagram account: @{instagram_account.username}")
                    print(f"⚠️ No Facebook pages - will use Instagram token")
                    
                    try:
                        instagram_token = instagram_account.access_token
                        print(f"✅ Instagram token accessible: {len(instagram_token)} chars")
                    except AttributeError as e:
                        print(f"❌ Instagram token access error: {e}")
                        
                else:
                    print(f"❌ No Instagram accounts or Facebook pages found")
                    
        except Exception as e:
            print(f"⚠️ Error checking tenant {tenant.schema_name}: {e}")

if __name__ == "__main__":
    test_instagram_send_message_tokens()
    print(f"\n=== Fix Applied ===")
    print(f"✅ Updated instagram_send_message to use 'page_access_token' instead of 'access_token'")
    print(f"✅ The 'FacebookPageConnection' attribute error should now be resolved")
    print(f"✅ Ready to test Instagram message sending again")
