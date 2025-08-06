#!/usr/bin/env python3
"""
Test WebSocket connection to verify if Django Channels is working
"""

import asyncio
import websockets
import json
import sys

async def test_websocket():
    # Test tenant schema - replace with your actual tenant schema
    tenant_schema = "echodesk_georgeguajabidze_gmail_com"
    
    # Try both local and deployed URLs
    urls = [
        f"ws://localhost:8000/ws/messages/{tenant_schema}/",
        f"wss://api.echodesk.ge/ws/messages/{tenant_schema}/"
    ]
    
    for url in urls:
        print(f"\n🔍 Testing WebSocket connection to: {url}")
        
        try:
            # Try to connect (remove timeout parameter)
            websocket = await websockets.connect(url)
            print(f"✅ Connected successfully to {url}")
            
            # Send a ping message
            ping_message = {
                "type": "ping",
                "timestamp": "2024-01-01T00:00:00Z"
            }
            
            await websocket.send(json.dumps(ping_message))
            print(f"📤 Sent ping message")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"📥 Received response: {response}")
            except asyncio.TimeoutError:
                print("⏰ No response received within 5 seconds")
            
            # Keep connection open for a bit to test
            print("🔄 Keeping connection open for 5 seconds...")
            await asyncio.sleep(5)
            
            await websocket.close()
            print("🔌 Connection closed cleanly")
                
        except websockets.exceptions.ConnectionClosed as e:
            print(f"❌ Connection closed: {e}")
        except websockets.exceptions.InvalidStatusCode as e:
            print(f"❌ Invalid status code: {e}")
        except ConnectionRefusedError:
            print(f"❌ Connection refused - server might not be running")
        except OSError as e:
            print(f"❌ Network error: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Starting WebSocket connection test...")
    asyncio.run(test_websocket())
    print("\n✅ Test completed!")
