# Instagram Integration Setup Guide

This guide will walk you through setting up Instagram messaging integration for your EchoDesk application using Meta Developer platform.

## Prerequisites

- Facebook Developer Account
- Business Instagram Account
- Facebook Page connected to your Instagram Business Account
- Your Django application deployed and accessible via HTTPS

## Step 1: Create a Meta App

1. **Go to Meta Developers**
   - Visit https://developers.facebook.com/
   - Log in with your Facebook account

2. **Create New App**
   - Click "Create App"
   - Select "Business" as the app type
   - Fill in your app details:
     - App Name: "EchoDesk Social Integration"
     - App Contact Email: your-email@domain.com
     - Business Account: Select or create one

3. **App Dashboard**
   - Once created, you'll see your App ID and App Secret
   - **IMPORTANT**: Save these credentials securely

## Step 2: Configure Instagram Basic Display

1. **Add Instagram Basic Display Product**
   - In your app dashboard, click "Add Product"
   - Find "Instagram Basic Display" and click "Set Up"

2. **Configure Basic Display**
   - Go to Instagram Basic Display > Basic Display
   - Click "Create New App"
   - Fill in the display name: "EchoDesk"

## Step 3: Configure Instagram Graph API

1. **Add Instagram Graph API Product**
   - In your app dashboard, click "Add Product"
   - Find "Instagram Graph API" and click "Set Up"

2. **Configure Graph API**
   - This allows you to manage Instagram business accounts
   - You'll need this for messaging capabilities

## Step 4: Set up Webhooks

1. **Add Webhooks Product**
   - In your app dashboard, click "Add Product"
   - Find "Webhooks" and click "Set Up"

2. **Configure Instagram Webhooks**
   - Click "Instagram" in the webhooks section
   - Add your callback URL: `https://your-domain.com/api/social/instagram/webhook/`
   - Add verify token: create a random string (e.g., "instagram_webhook_verify_token_2024")
   - Subscribe to these fields:
     - `messages`
     - `messaging_handovers`
     - `messaging_postbacks`

## Step 5: Update Django Settings

Add these settings to your `amanati_crm/settings.py`:

```python
# Instagram Configuration
INSTAGRAM_APP_ID = 'your_instagram_app_id'
INSTAGRAM_APP_SECRET = 'your_instagram_app_secret'
INSTAGRAM_WEBHOOK_VERIFY_TOKEN = 'instagram_webhook_verify_token_2024'
INSTAGRAM_REDIRECT_URI = 'https://your-domain.com/api/social/instagram/oauth/callback/'

# Scopes for Instagram permissions
INSTAGRAM_SCOPES = [
    'instagram_basic',
    'instagram_manage_messages',
    'pages_show_list',
    'pages_read_engagement',
    'business_management'
]
```

## Step 6: Environment Variables

Create/update your `.env` file:

```bash
# Instagram API Configuration
INSTAGRAM_APP_ID=your_instagram_app_id_here
INSTAGRAM_APP_SECRET=your_instagram_app_secret_here
INSTAGRAM_WEBHOOK_VERIFY_TOKEN=instagram_webhook_verify_token_2024
INSTAGRAM_REDIRECT_URI=https://your-domain.com/api/social/instagram/oauth/callback/
```

## Step 7: Instagram Business Account Setup

1. **Convert to Business Account**
   - Make sure your Instagram account is a Business Account
   - Go to Instagram app > Settings > Account > Switch to Professional Account

2. **Connect to Facebook Page**
   - Your Instagram Business Account must be connected to a Facebook Page
   - Go to Instagram Settings > Business > Page

## Step 8: App Review Process

For production use, you'll need to submit your app for review:

1. **Required Permissions**
   - `instagram_basic`
   - `instagram_manage_messages`
   - `pages_show_list`
   - `pages_read_engagement`

2. **Submission Requirements**
   - Privacy Policy URL: `https://your-domain.com/legal/privacy/`
   - Terms of Service URL: `https://your-domain.com/legal/terms/`
   - Data Deletion Instructions: `https://your-domain.com/legal/data-deletion/`
   - App Review Submission with use case explanation

## Step 9: Testing Your Integration

1. **Test Webhook**
   ```bash
   # Test webhook verification
   curl -X GET "https://your-domain.com/api/social/instagram/webhook/?hub.mode=subscribe&hub.challenge=test&hub.verify_token=instagram_webhook_verify_token_2024"
   ```

2. **Test OAuth Flow**
   - Navigate to: `https://your-domain.com/api/social/instagram/oauth/start/`
   - Complete the authorization flow
   - Check if the account is connected

3. **Test Message Reception**
   - Send a message to your Instagram Business Account
   - Check if the webhook receives the message
   - Verify the message is stored in your database

## Step 10: Important URLs for Meta App Configuration

Add these URLs to your Meta App settings:

1. **OAuth Redirect URIs**
   ```
   https://your-domain.com/api/social/instagram/oauth/callback/
   ```

2. **Webhook Callback URL**
   ```
   https://your-domain.com/api/social/instagram/webhook/
   ```

3. **Privacy Policy URL**
   ```
   https://your-domain.com/legal/privacy/
   ```

4. **Terms of Service URL**
   ```
   https://your-domain.com/legal/terms/
   ```

5. **Data Deletion Instructions URL**
   ```
   https://your-domain.com/legal/data-deletion/
   ```

## Troubleshooting

### Common Issues

1. **Webhook Verification Fails**
   - Ensure your verify token matches exactly
   - Check that your server returns plain text, not JSON
   - Verify HTTPS is working correctly

2. **OAuth Flow Fails**
   - Check redirect URI matches exactly
   - Verify app is not in sandbox mode (or test with sandbox users)
   - Ensure Instagram account is connected to a Facebook Page

3. **Messages Not Received**
   - Verify webhook subscriptions are active
   - Check that Instagram account is a Business Account
   - Ensure proper permissions are granted

4. **Permission Errors**
   - For development: App works with developers/testers only
   - For production: Submit for App Review with required permissions

### Debug Commands

```bash
# Check webhook endpoint
curl -X GET "https://your-domain.com/api/social/instagram/webhook/?hub.mode=subscribe&hub.challenge=test&hub.verify_token=your_verify_token"

# Check OAuth start endpoint
curl -X GET "https://your-domain.com/api/social/instagram/oauth/start/"

# Check connection status
curl -X GET "https://your-domain.com/api/social/instagram/connection/status/" -H "Authorization: Bearer your_jwt_token"
```

## Next Steps

1. **Deploy Changes**: Make sure your backend is deployed with the new Instagram integration
2. **Configure Meta App**: Follow steps 1-4 to set up your Meta Developer app
3. **Update Settings**: Add your app credentials to settings/environment variables
4. **Test Integration**: Use the testing steps to verify everything works
5. **Submit for Review**: Once testing is complete, submit your app for review if needed for production

## Security Notes

- Never commit API keys to version control
- Use environment variables for all sensitive credentials
- Implement proper rate limiting for webhook endpoints
- Validate all incoming webhook data
- Use HTTPS for all endpoints
- Implement proper error handling and logging

## Support

- Meta Developer Documentation: https://developers.facebook.com/docs/instagram-api/
- Instagram Graph API Reference: https://developers.facebook.com/docs/instagram-api/reference
- Webhooks Guide: https://developers.facebook.com/docs/graph-api/webhooks/
