# Bank of Georgia Payment Integration Guide

This document describes the Bank of Georgia (BOG) payment gateway integration in EchoDesk.

## Overview

The integration has been fully migrated from Flitt to Bank of Georgia's payment API. All subscription payments and tenant registrations now use BOG's payment gateway.

## Documentation

Official BOG Payment API Documentation: https://api.bog.ge/docs/en/payments/introduction

## Configuration

### Required Environment Variables

Add the following to your `.env` file or environment configuration:

```bash
# Bank of Georgia Payment Gateway
BOG_CLIENT_ID=your_client_id_here
BOG_CLIENT_SECRET=your_client_secret_here
BOG_AUTH_URL=https://oauth2.bog.ge/auth/realms/bog/protocol/openid-connect/token
BOG_API_BASE_URL=https://api.bog.ge/payments/v1
```

### Getting Credentials

1. Contact Bank of Georgia to set up a merchant account
2. You will receive:
   - `client_id`: Unique business identifier
   - `client_secret`: Secure credential (keep confidential)
3. Add these credentials to your environment variables

## Architecture

### Files Modified/Created

1. **Created:**
   - `tenants/bog_payment.py` - BOG payment service with OAuth authentication and order management

2. **Modified:**
   - `tenants/payment_views.py` - Updated to use BOG service instead of Flitt
   - `tenants/views.py` - Updated registration flow for BOG
   - `tenants/urls.py` - Updated webhook endpoint name
   - `amanati_crm/settings.py` - Replaced Flitt config with BOG config

3. **Removed:**
   - `tenants/flitt_payment.py` - Old Flitt payment service
   - `SUBSCRIPTION_AND_PAYMENT_SYSTEM.md` - Old Flitt documentation
   - `FLITT_INTEGRATION_COMPLETE.md` - Old Flitt integration doc

## Payment Flow

### 1. Authentication

BOG uses OAuth 2.0 with client credentials grant:

```
POST https://oauth2.bog.ge/auth/realms/bog/protocol/openid-connect/token
Authorization: Basic <base64(client_id:client_secret)>
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
```

Response includes `access_token` (JWT) valid for a specific duration.

### 2. Creating a Payment Order

```
POST https://api.bog.ge/payments/v1/ecommerce/orders
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "callback_url": "https://api.echodesk.ge/api/payments/webhook/",
  "external_order_id": "SUB-ABC123",
  "purchase_units": {
    "currency": "GEL",
    "total_amount": 100.00,
    "basket": [
      {
        "product_id": "subscription",
        "description": "EchoDesk Professional - Company Name",
        "quantity": 1,
        "unit_price": 100.00
      }
    ]
  },
  "redirect_urls": {
    "success": "https://tenant.echodesk.ge/settings/subscription/success",
    "fail": "https://tenant.echodesk.ge/settings/subscription/failed"
  },
  "buyer": {
    "full_name": "Customer Name",
    "masked_email": "customer@example.com"
  }
}
```

Response includes:
- `id`: BOG order ID
- `_links.redirect.href`: URL to redirect customer for payment
- `_links.details.href`: URL to check payment status

### 3. Customer Payment

Customer is redirected to BOG's payment page where they:
1. Enter card details
2. Complete 3D Secure authentication
3. Confirm payment

### 4. Webhook Callback

BOG sends a POST request to the callback URL:

```json
{
  "event": "order_payment",
  "zoned_request_time": "2024-01-01T12:00:00.000000Z",
  "body": {
    "order_id": "bog-order-id",
    "order_status": {
      "key": "completed"
    },
    "code": "100",
    "transaction_id": "txn-123456",
    "transfer_amount": 100.00,
    "currency": "GEL",
    "transfer_method": "card"
  }
}
```

**Status Values:**
- `completed` + code `100`: Payment successful
- `rejected`: Payment failed
- `processing`: Payment in progress
- `refunded`: Payment refunded
- `refunded_partially`: Partial refund

### 5. Payment Verification

The backend:
1. Receives the webhook
2. Verifies the order_id exists in database
3. Checks status is `completed` and code is `100`
4. Creates/updates tenant subscription
5. Activates the subscription
6. Returns HTTP 200 to acknowledge receipt

## API Endpoints

### Create Subscription Payment

```
POST /api/payments/create/
Authorization: Token <user_token>

{
  "package_id": 1,
  "agent_count": 5
}
```

Returns payment URL for redirect.

### Check Payment Status

```
GET /api/payments/status/<order_id>/
Authorization: Token <user_token>
```

Returns current payment status.

### Webhook (BOG Callback)

```
POST /api/payments/webhook/
Content-Type: application/json
Callback-Signature: <optional_signature>

{
  "event": "order_payment",
  "body": { ... }
}
```

Processes payment completion.

### Cancel Subscription

```
POST /api/payments/cancel/
Authorization: Token <user_token>
```

Deactivates current subscription.

## Response Codes

BOG uses specific response codes in webhooks:

- **100**: Successful payment
- **101**: Limited card usage
- **103**: Invalid card
- **104**: Transaction count exceeded
- **105**: Expired card
- **106**: Amount limit exceeded
- **107**: Insufficient funds
- **108**: Authentication declined
- **109**: Technical issue
- **110**: Transaction expired
- **111**: Authentication timeout
- **112**: General error
- **200**: Successful preauthorization

## Testing

### Development Testing

1. Configure BOG test credentials in `.env`
2. Create a test package in Django admin
3. Initiate a payment through the API
4. Use BOG's test card numbers
5. Complete payment on test environment
6. Verify webhook is received and subscription is created

### Webhook Testing Locally

Use ngrok or similar to expose local webhook endpoint:

```bash
ngrok http 8000
```

Update `settings.py` temporarily:

```python
API_DOMAIN = 'https://your-ngrok-url.ngrok.io'
```

## Security Considerations

1. **Credentials**: Keep `BOG_CLIENT_SECRET` secure and never commit to version control
2. **HTTPS**: All BOG API calls must use HTTPS
3. **Webhook Signature**: Optionally verify `Callback-Signature` header (requires BOG public key)
4. **Token Caching**: Access tokens are cached with 5-minute buffer before expiration
5. **Idempotency**: Use unique order IDs to prevent duplicate charges

## Error Handling

The service handles:
- Authentication failures → Returns error message
- Network timeouts → Logs error and returns error status
- Invalid responses → Logs and raises ValueError
- Missing configuration → Returns 503 Service Unavailable

## Monitoring

Key events logged:
- Access token generation
- Payment order creation
- Webhook receipts
- Payment status checks
- Errors and failures

Check logs:
```bash
tail -f logs/django.log | grep -i "bog\|payment"
```

## Migration Notes

### Changes from Flitt

1. **Authentication**: OAuth 2.0 instead of API key
2. **Request Format**: JSON body instead of URL parameters
3. **Webhook Format**: Different payload structure
4. **Status Codes**: BOG-specific status values and response codes
5. **Order Creation**: More detailed basket information required

### Backward Compatibility

- API endpoints remain the same for frontend
- Database models unchanged (PaymentOrder, etc.)
- Subscription flow unchanged from user perspective

## Support

For BOG API issues:
- Technical Documentation: https://api.bog.ge/docs/en/
- Contact: Bank of Georgia merchant support

For EchoDesk integration issues:
- Check logs: `tenants.bog_payment` and `tenants.payment_views`
- Verify configuration: `bog_service.is_configured()`
- Test authentication: Access token generation

## Future Enhancements

Potential improvements:
1. Implement RSA signature verification for webhooks
2. Add support for saved cards / recurring payments
3. Implement refund API
4. Add Apple Pay / Google Pay support
5. Support multiple currencies (USD, EUR)
6. Add payment retry logic

---

**Integration completed**: 2025-10-28
**BOG API Version**: v1
**Documentation**: https://api.bog.ge/docs/en/payments/introduction
