#!/usr/bin/env python3
"""
Test Instagram webhook handler with the actual webhook format received
"""

import requests
import json

# The actual webhook data you received
webhook_data = {
    "entry": [
        {
            "id": "0", 
            "time": 1754520281, 
            "changes": [
                {
                    "field": "messages", 
                    "value": {
                        "sender": {"id": "12334"}, 
                        "recipient": {"id": "23245"}, 
                        "timestamp": "1527459824", 
                        "message": {"mid": "random_mid", "text": "random_text"}
                    }
                }
            ]
        }
    ], 
    "object": "instagram"
}

def test_instagram_webhook():
    print("🧪 Testing Instagram webhook with actual received data...")
    
    # Test webhook endpoint
    webhook_url = "https://api.echodesk.ge/api/social/instagram/webhook/"
    
    try:
        response = requests.post(
            webhook_url,
            json=webhook_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"📤 Webhook Response Status: {response.status_code}")
        print(f"📤 Webhook Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Webhook processed successfully!")
        else:
            print(f"❌ Webhook failed with status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Webhook test failed: {e}")

if __name__ == "__main__":
    test_instagram_webhook()
