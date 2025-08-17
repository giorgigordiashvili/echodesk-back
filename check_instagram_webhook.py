#!/usr/bin/env python
"""
Quick script to debug Instagram webhook processing
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')
django.setup()

from social_integrations.models import InstagramAccountConnection
from tenants.models import Tenant
from tenant_schemas.utils import schema_context

def check_instagram_account(instagram_account_id):
    """Check if Instagram account exists in any tenant"""
    print(f"🔍 Checking for Instagram account ID: {instagram_account_id}")
    
    # Get all tenants
    tenants = Tenant.objects.all()
    print(f"📋 Found {tenants.count()} tenants: {[t.schema_name for t in tenants]}")
    
    found_accounts = []
    
    for tenant in tenants:
        try:
            with schema_context(tenant.schema_name):
                # Check for the specific account
                account = InstagramAccountConnection.objects.filter(
                    instagram_account_id=instagram_account_id
                ).first()
                
                if account:
                    found_accounts.append({
                        'tenant': tenant.schema_name,
                        'account': account,
                        'is_active': account.is_active
                    })
                    print(f"✅ Found in {tenant.schema_name}: @{account.username} (active: {account.is_active})")
                
                # Also list all Instagram accounts in this tenant
                all_accounts = InstagramAccountConnection.objects.all()
                if all_accounts.exists():
                    print(f"📱 All Instagram accounts in {tenant.schema_name}:")
                    for acc in all_accounts:
                        print(f"   - @{acc.username} ({acc.instagram_account_id}) - active: {acc.is_active}")
                else:
                    print(f"❌ No Instagram accounts found in {tenant.schema_name}")
                    
        except Exception as e:
            print(f"⚠️ Error checking tenant {tenant.schema_name}: {e}")
    
    if not found_accounts:
        print(f"❌ Instagram account {instagram_account_id} not found in any tenant")
    
    return found_accounts

if __name__ == "__main__":
    # The Instagram account ID from your webhook
    webhook_account_id = "17841476239553009"
    
    print("=== Instagram Webhook Debug ===")
    results = check_instagram_account(webhook_account_id)
    
    if results:
        print(f"\n✅ Account found in {len(results)} tenant(s)")
        for result in results:
            print(f"   - Tenant: {result['tenant']}")
            print(f"   - Account: {result['account']}")
            print(f"   - Active: {result['is_active']}")
    else:
        print(f"\n❌ Account {webhook_account_id} not found in any tenant")
        print("💡 You may need to connect this Instagram account through the OAuth flow")
