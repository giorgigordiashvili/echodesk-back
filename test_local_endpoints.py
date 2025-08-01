#!/usr/bin/env python3

import os
import sys
import django
import requests
from time import sleep

# Add the project root to Python path
sys.path.insert(0, '/Users/giorgigordiashvili/Support/AmanatiLTD/echodesk-back')

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')
django.setup()

def test_local_endpoints():
    """Test Facebook OAuth endpoints locally"""
    base_url = "http://127.0.0.1:8000"
    
    print("=== Testing Facebook OAuth Endpoints Locally ===")
    print(f"Base URL: {base_url}")
    print()
    
    # Test endpoints
    endpoints = [
        "/api/social/facebook/oauth/callback/",
        "/api/social/facebook/oauth/debug/",
        "/api/social/facebook/status/",
    ]
    
    for endpoint in endpoints:
        url = base_url + endpoint
        print(f"Testing: {endpoint}")
        try:
            response = requests.get(url, timeout=5)
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                print(f"  Response: {response.json()}")
            else:
                print(f"  Response: {response.text[:200]}...")
        except requests.exceptions.ConnectionError as e:
            print(f"  Error: Cannot connect to server - {e}")
        except Exception as e:
            print(f"  Error: {e}")
        print()
    
    # Test callback with parameters
    print("Testing callback with sample parameters:")
    test_params = [
        "?error=access_denied&error_description=User+denied",
        "?code=sample_code_123&state=test",
        ""
    ]
    
    for params in test_params:
        url = base_url + "/api/social/facebook/oauth/callback/" + params
        print(f"  URL: {url}")
        try:
            response = requests.get(url, timeout=5)
            print(f"    Status: {response.status_code}")
            if response.headers.get('content-type', '').startswith('application/json'):
                print(f"    Response: {response.json()}")
            else:
                print(f"    Response: {response.text[:100]}...")
        except Exception as e:
            print(f"    Error: {e}")
        print()

if __name__ == "__main__":
    test_local_endpoints()
