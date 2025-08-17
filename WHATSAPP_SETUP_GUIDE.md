# WhatsApp Business API Integration Setup Guide

This guide will walk you through setting up WhatsApp Business API integration for your EchoDesk application.

## Prerequisites

- Meta Business Account
- WhatsApp Business Account
- Phone number for WhatsApp Business
- Your Django application deployed and accessible via HTTPS

## WhatsApp Business API Overview

WhatsApp Business API is different from Facebook/Instagram OAuth. It requires:

1. A business verification process with Meta
2. Manual setup of access tokens and phone numbers
3. Webhook configuration for receiving messages
4. Business verification and approval process

## Step 1: Create WhatsApp Business Account

1. **Go to WhatsApp Business**

   - Visit https://business.whatsapp.com/
   - Click "Get Started"

2. **Create Business Profile**

   - Add your business information
   - Verify your business details
   - Add business phone number

3. **Link to Meta Business Manager**
   - Go to https://business.facebook.com/
   - Navigate to "WhatsApp Accounts"
   - Link your WhatsApp Business Account

## Step 2: Set Up WhatsApp Business API Access

1. **Access Meta Business Manager**

   - Go to https://business.facebook.com/
   - Select your business account

2. **Navigate to WhatsApp**

   - Go to "WhatsApp Accounts" in the left sidebar
   - Select your WhatsApp Business Account

3. **Get Your Credentials**
   You'll need these values:
   - **Business Account ID**: Found in WhatsApp Account settings
   - **Phone Number ID**: Found in your phone number settings
   - **Access Token**: Generate a permanent token (see Step 3)

## Step 3: Generate Access Token

1. **Go to Meta Developers**

   - Visit https://developers.facebook.com/
   - Select your app (or create one if needed)

2. **Add WhatsApp Product**

   - In your app dashboard, click "Add Product"
   - Find "WhatsApp" and click "Set Up"

3. **Generate Token**

   - Go to WhatsApp > API Setup
   - Select your Business Account
   - Select your Phone Number
   - Generate and copy the access token
   - **Important**: This token expires in 24 hours for testing

4. **Create Permanent Token** (For Production)
   - Follow Meta's guide to create a permanent access token
   - This requires additional business verification

## Step 4: Configure Webhooks

1. **In Meta Developers Console**

   - Go to WhatsApp > Configuration
   - Add webhook URL: `https://api.echodesk.ge/api/social/whatsapp/webhook/`
   - Add verify token: `echodesk_whatsapp_webhook_token_2024`

2. **Subscribe to Webhook Fields**
   - `messages` - Receive incoming messages
   - `message_deliveries` - Get delivery confirmations
   - `message_reads` - Get read receipts

## Step 5: Update Your Django Settings

Your `.env` file already contains the basic configuration:

```bash
# WhatsApp Business API Settings
WHATSAPP_WEBHOOK_VERIFY_TOKEN=echodesk_whatsapp_webhook_token_2024
WHATSAPP_API_VERSION=v23.0
```

No additional app ID/secret needed - WhatsApp uses access tokens directly.

## Step 6: Connect Your WhatsApp Account

Use the Django API to connect your WhatsApp Business Account:

### Method 1: Using API Endpoint

```bash
curl -X POST "https://api.echodesk.ge/api/social/whatsapp/connect/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "business_account_id": "YOUR_BUSINESS_ACCOUNT_ID",
    "phone_number_id": "YOUR_PHONE_NUMBER_ID",
    "access_token": "YOUR_ACCESS_TOKEN"
  }'
```

### Method 2: Using Frontend Interface

Once the frontend is built, you'll have a UI to:

1. Enter your WhatsApp Business credentials
2. Verify connection
3. Start receiving messages

## Step 7: Testing Your Integration

### Test Webhook Verification

```bash
curl -X GET "https://api.echodesk.ge/api/social/whatsapp/webhook/?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=echodesk_whatsapp_webhook_token_2024"
```

Should return: `test123`

### Test Connection Setup

```bash
curl -X GET "https://api.echodesk.ge/api/social/whatsapp/setup/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Test Message Reception

1. Send a message to your WhatsApp Business number
2. Check your webhook endpoint receives the message
3. Verify the message is stored in your database

## Step 8: Available API Endpoints

Once deployed, you'll have these endpoints:

### ViewSets (CRUD operations)

- `GET /api/social/whatsapp-connections/` - List connections
- `POST /api/social/whatsapp-connections/` - Create connection
- `GET /api/social/whatsapp-messages/` - List messages
- `GET /api/social/whatsapp-messages/{id}/` - Get specific message

### Custom Endpoints

- `GET /api/social/whatsapp/setup/` - Get setup instructions
- `POST /api/social/whatsapp/connect/` - Connect business account
- `GET /api/social/whatsapp/status/` - Check connection status
- `POST /api/social/whatsapp/disconnect/` - Disconnect account
- `POST /api/social/whatsapp/webhook/` - Webhook for incoming messages

## Step 9: Business Verification (Production)

For production use, you need:

1. **Business Verification**

   - Verify your business with Meta
   - Provide business documentation
   - Complete identity verification

2. **API Access Approval**

   - Apply for production API access
   - Demonstrate your use case
   - Show compliance with WhatsApp policies

3. **Rate Limits**
   - Development: 250 conversations/day
   - Production: Higher limits based on approval

## Step 10: Important Considerations

### Message Types Supported

- Text messages
- Images, documents, audio, video
- Location messages
- Template messages (for business-initiated conversations)

### Pricing

- WhatsApp Business API has usage-based pricing
- Charges per conversation (24-hour window)
- Different rates for different countries

### Compliance

- Follow WhatsApp Business Policy
- Obtain user consent for messaging
- Provide opt-out mechanisms
- Maintain message history as required

## Troubleshooting

### Common Issues

1. **Webhook Verification Fails**

   - Check verify token matches exactly
   - Ensure HTTPS is working
   - Verify webhook URL is accessible

2. **Access Token Issues**

   - Tokens expire (24h for temp tokens)
   - Generate permanent token for production
   - Check token permissions

3. **Phone Number Not Working**

   - Ensure phone number is verified
   - Check Business Account is approved
   - Verify phone number ID is correct

4. **Messages Not Received**
   - Check webhook subscriptions
   - Verify webhook URL is correct
   - Check server logs for errors

### Debug Commands

```bash
# Test webhook
curl -X GET "https://api.echodesk.ge/api/social/whatsapp/webhook/?hub.mode=subscribe&hub.challenge=test&hub.verify_token=echodesk_whatsapp_webhook_token_2024"

# Check connection status
curl -X GET "https://api.echodesk.ge/api/social/whatsapp/status/" -H "Authorization: Bearer YOUR_TOKEN"

# Test phone number API
curl -X GET "https://graph.facebook.com/v23.0/PHONE_NUMBER_ID" -H "Authorization: Bearer ACCESS_TOKEN"
```

## Next Steps

1. **Deploy Changes**: The backend is ready and pushed to git
2. **Set Up WhatsApp Business Account**: Follow steps 1-3
3. **Configure Webhooks**: Follow step 4
4. **Connect Account**: Use API to connect your WhatsApp
5. **Test Integration**: Send test messages
6. **Business Verification**: For production use

## Security Notes

- Store access tokens securely (encrypted)
- Implement rate limiting
- Validate webhook signatures in production
- Use HTTPS for all endpoints
- Log webhook events for debugging
- Implement proper error handling

## Support Resources

- WhatsApp Business API Documentation: https://developers.facebook.com/docs/whatsapp
- Meta Business Help Center: https://www.facebook.com/business/help
- WhatsApp Business API Pricing: https://developers.facebook.com/docs/whatsapp/pricing
- Business Verification Guide: https://www.facebook.com/business/help/159334372093366
