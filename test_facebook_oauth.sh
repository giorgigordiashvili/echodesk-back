#!/bin/bash

echo "=== Testing Facebook OAuth Endpoints ==="
echo

# Test the basic callback endpoint
echo "1. Testing callback endpoint (GET):"
echo "URL: https://api.echodesk.ge/api/social/facebook/oauth/callback/"
curl -s "https://api.echodesk.ge/api/social/facebook/oauth/callback/" | python3 -m json.tool
echo

# Test with some sample parameters that Facebook might send
echo "2. Testing callback with error (user denied):"
echo "URL: https://api.echodesk.ge/api/social/facebook/oauth/callback/?error=access_denied&error_description=User+denied"
curl -s "https://api.echodesk.ge/api/social/facebook/oauth/callback/?error=access_denied&error_description=User+denied" | python3 -m json.tool
echo

# Test with sample code parameter
echo "3. Testing callback with code:"
echo "URL: https://api.echodesk.ge/api/social/facebook/oauth/callback/?code=sample_code_123&state=test"
curl -s "https://api.echodesk.ge/api/social/facebook/oauth/callback/?code=sample_code_123&state=test" | python3 -m json.tool
echo

# Test debug endpoint
echo "4. Testing debug endpoint:"
echo "URL: https://api.echodesk.ge/api/social/facebook/oauth/debug/"
curl -s "https://api.echodesk.ge/api/social/facebook/oauth/debug/" | python3 -m json.tool
echo

echo "=== Test completed ==="
echo
echo "Next steps:"
echo "1. Make sure your Facebook app redirect URI is: https://api.echodesk.ge/api/social/facebook/oauth/callback/"
echo "2. Test the OAuth flow by visiting the OAuth start URL"
echo "3. Check the debug endpoint to see what Facebook actually sends"
