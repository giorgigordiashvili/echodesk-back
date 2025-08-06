#!/usr/bin/env python3
"""
Test script for Instagram API endpoints
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/social"

def test_instagram_endpoints():
    print("🧪 Testing Instagram API endpoints...")
    
    # Test Instagram OAuth start endpoint
    print("\n1. Testing Instagram OAuth start endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/instagram/oauth/start/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   OAuth URL generated: {data.get('oauth_url', 'N/A')[:100]}...")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test Instagram connection status endpoint  
    print("\n2. Testing Instagram connection status endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/instagram/status/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Connected: {data.get('connected')}")
            print(f"   Accounts: {data.get('accounts_count', 0)}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test Instagram conversations endpoint
    print("\n3. Testing Instagram conversations endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/instagram/conversations/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Conversations: {len(data.get('conversations', []))}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test Instagram webhook verification
    print("\n4. Testing Instagram webhook verification...")
    try:
        params = {
            'hub.mode': 'subscribe',
            'hub.verify_token': 'echodesk_instagram_webhook_token_2024',
            'hub.challenge': 'test_challenge_123'
        }
        response = requests.get(f"{BASE_URL}/instagram/webhook/", params=params)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Challenge response: {response.text}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    print("\n✅ Instagram API endpoint tests completed!")

if __name__ == "__main__":
    test_instagram_endpoints()
