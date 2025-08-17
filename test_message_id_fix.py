#!/usr/bin/env python
"""
Test script to verify Instagram message ID length fix
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')
django.setup()

from social_integrations.models import InstagramMessage, InstagramAccountConnection
from tenant_schemas.utils import schema_context
from django.utils import timezone

def test_long_message_id():
    """Test saving an Instagram message with a long message ID"""
    
    # The long message ID from your webhook
    long_message_id = "aWdfZAG1faXRlbToxOklHTWVzc2FnZAUlEOjE3ODQxNDc2MjM5NTUzMDA5OjM0MDI4MjM2Njg0MTcxMDMwMTI0NDI2MDAxMzM0OTIyMTMxOTQ5MDozMjM4MjY0MDg3OTk0OTMwMTgwNTk2NzYxNTE0Njg1MjM1MgZDZD"
    
    print(f"Testing message ID length: {len(long_message_id)} characters")
    print(f"Message ID: {long_message_id}")
    
    with schema_context('amanati'):
        # Get the Instagram account connection
        account_connection = InstagramAccountConnection.objects.get(
            instagram_account_id="17841476239553009"
        )
        print(f"✅ Found account connection: @{account_connection.username}")
        
        # Check if message already exists
        existing_message = InstagramMessage.objects.filter(message_id=long_message_id).first()
        if existing_message:
            print(f"⚠️ Message already exists: {existing_message.id}")
            print(f"   Text: '{existing_message.message_text}'")
            print(f"   Created: {existing_message.created_at}")
            return existing_message
        
        # Try to create a new message with the long ID
        try:
            message_obj = InstagramMessage.objects.create(
                account_connection=account_connection,
                message_id=long_message_id,
                conversation_id="1433370864782884",
                sender_id="1433370864782884",
                sender_username="user_1433370864782884",
                message_text="uu",
                message_type="text",
                timestamp=timezone.now(),
                is_from_business=False
            )
            print(f"✅ SUCCESS: Message created with ID {message_obj.id}")
            print(f"   Database ID: {message_obj.id}")
            print(f"   Message ID: {message_obj.message_id}")
            print(f"   Text: '{message_obj.message_text}'")
            return message_obj
            
        except Exception as e:
            print(f"❌ FAILED to create message: {e}")
            return None

if __name__ == "__main__":
    print("=== Testing Instagram Message ID Length Fix ===")
    result = test_long_message_id()
    
    if result:
        print(f"\n✅ Test PASSED: Long message ID can be saved")
    else:
        print(f"\n❌ Test FAILED: Could not save long message ID")
