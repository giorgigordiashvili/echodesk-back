#!/usr/bin/env python3
"""
Test script for Call Logging API
This script demonstrates how to use the call logging API endpoints
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust as needed
API_BASE = f"{BASE_URL}/api"

# You'll need to get an auth token first
# Replace with your actual token
AUTH_TOKEN = "your-auth-token-here"

headers = {
    "Authorization": f"Token {AUTH_TOKEN}",
    "Content-Type": "application/json"
}

def test_outbound_call():
    """Test complete outbound call flow"""
    print("=== Testing Outbound Call Flow ===")
    
    # 1. Initiate call
    print("1. Initiating outbound call...")
    call_data = {
        "recipient_number": "+1234567890",
        "call_type": "voice"
    }
    
    response = requests.post(f"{API_BASE}/call-logs/initiate_call/", 
                           json=call_data, headers=headers)
    if response.status_code == 201:
        call = response.json()
        call_id = call['id']
        print(f"   ✓ Call initiated: {call_id}")
    else:
        print(f"   ✗ Failed to initiate call: {response.text}")
        return
    
    # 2. Simulate ringing (webhook would normally do this)
    print("2. Updating to ringing...")
    status_data = {"status": "ringing"}
    response = requests.patch(f"{API_BASE}/call-logs/{call_id}/update_status/", 
                            json=status_data, headers=headers)
    if response.status_code == 200:
        print("   ✓ Status updated to ringing")
    
    # 3. Answer call
    print("3. Answering call...")
    status_data = {"status": "answered", "notes": "Customer picked up"}
    response = requests.patch(f"{API_BASE}/call-logs/{call_id}/update_status/", 
                            json=status_data, headers=headers)
    if response.status_code == 200:
        print("   ✓ Call answered")
    
    # 4. Start recording
    print("4. Starting recording...")
    response = requests.post(f"{API_BASE}/call-logs/{call_id}/start_recording/", 
                           headers=headers)
    if response.status_code == 201:
        print("   ✓ Recording started")
    
    # 5. Add some events
    print("5. Adding call events...")
    events = [
        {"event_type": "muted", "metadata": {"reason": "background_noise"}},
        {"event_type": "unmuted", "metadata": {"reason": "noise_cleared"}}
    ]
    
    for event in events:
        response = requests.post(f"{API_BASE}/call-logs/{call_id}/add_event/", 
                               json=event, headers=headers)
        if response.status_code == 201:
            print(f"   ✓ Event added: {event['event_type']}")
    
    # 6. Put on hold
    print("6. Putting call on hold...")
    response = requests.post(f"{API_BASE}/call-logs/{call_id}/toggle_hold/", 
                           headers=headers)
    if response.status_code == 200:
        print("   ✓ Call put on hold")
    
    # 7. Resume from hold
    print("7. Resuming call from hold...")
    response = requests.post(f"{API_BASE}/call-logs/{call_id}/toggle_hold/", 
                           headers=headers)
    if response.status_code == 200:
        print("   ✓ Call resumed from hold")
    
    # 8. Stop recording
    print("8. Stopping recording...")
    response = requests.post(f"{API_BASE}/call-logs/{call_id}/stop_recording/", 
                           headers=headers)
    if response.status_code == 200:
        print("   ✓ Recording stopped")
    
    # 9. End call
    print("9. Ending call...")
    response = requests.post(f"{API_BASE}/call-logs/{call_id}/end_call/", 
                           headers=headers)
    if response.status_code == 200:
        print("   ✓ Call ended")
    
    # 10. Get detailed call info
    print("10. Getting call details...")
    response = requests.get(f"{API_BASE}/call-logs/{call_id}/", headers=headers)
    if response.status_code == 200:
        call_details = response.json()
        print(f"   ✓ Call duration: {call_details.get('duration_display', 'N/A')}")
        print(f"   ✓ Total events: {len(call_details.get('events', []))}")
        print(f"   ✓ Recording status: {call_details.get('recording', {}).get('status', 'None')}")
    
    return call_id

def test_webhook_simulation():
    """Test webhook endpoints"""
    print("\n=== Testing Webhook Simulation ===")
    
    # Simulate SIP webhook for incoming call
    print("1. Simulating incoming call webhook...")
    webhook_data = {
        "event_type": "call_ringing",
        "sip_call_id": f"sip-{int(time.time())}",
        "caller_number": "+0987654321",
        "recipient_number": "+1234567890",
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "server": "test-sip-server",
            "codec": "G.711"
        }
    }
    
    # Note: Webhooks don't require authentication
    response = requests.post(f"{API_BASE}/webhooks/sip/", json=webhook_data)
    if response.status_code == 200:
        result = response.json()
        print(f"   ✓ Incoming call logged: {result['call_id']}")
        return result['call_id']
    else:
        print(f"   ✗ Webhook failed: {response.text}")
        return None

def test_statistics():
    """Test statistics endpoint"""
    print("\n=== Testing Statistics ===")
    
    periods = ['today', 'week', 'month']
    for period in periods:
        print(f"Getting stats for {period}...")
        response = requests.get(f"{API_BASE}/call-logs/statistics/?period={period}", 
                              headers=headers)
        if response.status_code == 200:
            stats = response.json()
            print(f"   ✓ {period.title()}: {stats['total_calls']} calls, "
                  f"{stats['answer_rate']}% answer rate")
        else:
            print(f"   ✗ Failed to get {period} stats")

def test_call_list():
    """Test call listing with filtering"""
    print("\n=== Testing Call List ===")
    
    response = requests.get(f"{API_BASE}/call-logs/", headers=headers)
    if response.status_code == 200:
        calls = response.json()
        if isinstance(calls, dict) and 'results' in calls:
            calls = calls['results']  # Paginated response
        
        print(f"   ✓ Found {len(calls)} calls")
        if calls:
            latest_call = calls[0]
            print(f"   ✓ Latest call: {latest_call['caller_number']} → "
                  f"{latest_call['recipient_number']} ({latest_call['status']})")
    else:
        print(f"   ✗ Failed to get call list: {response.text}")

def main():
    """Run all tests"""
    print("Call Logging API Test Script")
    print("=" * 50)
    
    if AUTH_TOKEN == "your-auth-token-here":
        print("⚠️  Please update AUTH_TOKEN in the script with your actual token")
        print("You can get a token by:")
        print("1. Creating a superuser: python manage.py createsuperuser")
        print("2. In Django shell: from rest_framework.authtoken.models import Token; Token.objects.create(user=User.objects.get(email='your@email.com'))")
        return
    
    try:
        # Test outbound call flow
        call_id = test_outbound_call()
        
        # Test webhook simulation
        webhook_call_id = test_webhook_simulation()
        
        # Test statistics
        test_statistics()
        
        # Test call listing
        test_call_list()
        
        print("\n" + "=" * 50)
        print("✓ All tests completed successfully!")
        
    except requests.exceptions.ConnectionError:
        print(f"✗ Could not connect to {BASE_URL}")
        print("Make sure your Django server is running")
    except Exception as e:
        print(f"✗ Test failed with error: {e}")

if __name__ == "__main__":
    main()
