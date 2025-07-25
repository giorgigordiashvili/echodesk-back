#!/usr/bin/env python
"""
Test script for SIP functionality
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')
django.setup()

from tenant_schemas.utils import schema_context
from crm.models import SipConfiguration, CallLog
from users.models import User
from tenants.models import Tenant
from datetime import datetime, timedelta
from django.utils import timezone

def test_sip_functionality():
    print("Testing SIP functionality...")
    
    # Get a tenant
    tenant = Tenant.objects.filter(schema_name='amanati').first()
    if not tenant:
        print("No tenant found with schema 'amanati'")
        return
    
    print(f"Testing with tenant: {tenant.name}")
    
    # Use tenant context
    with schema_context(tenant.schema_name):
        # Get a user
        user = User.objects.first()
        if not user:
            print("No users found in tenant")
            return
        
        print(f"Testing with user: {user.email}")
        
        # Test SIP Configuration creation
        print("\n1. Creating SIP Configuration...")
        try:
            sip_config = SipConfiguration.objects.create(
                name='Test SIP Provider',
                sip_server='sip.example.com',
                sip_port=5060,
                username='testuser',
                password='testpass123',
                realm='example.com',
                stun_server='stun:stun.l.google.com:19302',
                is_active=True,
                is_default=True,
                max_concurrent_calls=5,
                created_by=user
            )
            print(f"✓ Created SIP configuration: {sip_config}")
        except Exception as e:
            print(f"✗ Error creating SIP configuration: {e}")
            return
        
        # Test CallLog creation
        print("\n2. Creating Call Log...")
        try:
            call_log = CallLog.objects.create(
                caller_number='+995555123456',
                recipient_number='+995555654321',
                direction='outbound',
                call_type='voice',
                status='answered',
                handled_by=user,
                sip_configuration=sip_config,
                started_at=timezone.now(),
                answered_at=timezone.now() + timedelta(seconds=3),
                ended_at=timezone.now() + timedelta(minutes=5),
                duration=timedelta(minutes=5),
                notes='Test call from SIP integration'
            )
            print(f"✓ Created call log: {call_log}")
        except Exception as e:
            print(f"✗ Error creating call log: {e}")
            return
        
        # Test statistics
        print("\n3. Testing statistics...")
        try:
            sip_configs = SipConfiguration.objects.all()
            calls = CallLog.objects.all()
            print(f"✓ SIP Configurations: {sip_configs.count()}")
            print(f"✓ Call Logs: {calls.count()}")
            
            for config in sip_configs:
                print(f"  - {config.name}: {config.sip_server}:{config.sip_port}")
            
            for call in calls:
                print(f"  - Call {call.call_id}: {call.caller_number} → {call.recipient_number} ({call.status})")
        except Exception as e:
            print(f"✗ Error getting statistics: {e}")
        
        print("\n✓ All tests completed successfully!")

if __name__ == '__main__':
    test_sip_functionality()
