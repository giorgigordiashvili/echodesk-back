# EchoDesk Subscription & Payment System

Complete guide for subscription management with Flitt payment integration.

## Table of Contents

1. [System Overview](#system-overview)
2. [Backend Implementation](#backend-implementation)
3. [Frontend Implementation](#frontend-implementation)
4. [Flitt Payment Integration](#flitt-payment-integration)
5. [Usage Guide](#usage-guide)
6. [API Endpoints](#api-endpoints)
7. [Testing](#testing)

---

## System Overview

### Architecture

```
┌─────────────────┐
│   Django Admin  │ ← Create packages & manage subscriptions
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Backend API   │ ← Subscription logic & payment processing
├─────────────────┤
│ - Permissions   │
│ - Subscriptions │
│ - Payments      │
│ - Webhooks      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐         ┌──────────────┐
│  Next.js App    │────────→│ Flitt API    │
├─────────────────┤         └──────────────┘
│ - Feature Gates │
│ - Upgrade UI    │
│ - Payment Flow  │
└─────────────────┘
```

### Features

✅ **Backend:**
- Subscription-based feature control
- Usage limit tracking (users, WhatsApp, storage)
- Permission decorators and middleware
- Flitt payment gateway integration
- Webhook handling for payment events
- Admin interface for subscription management

✅ **Frontend:**
- Subscription context and hooks
- Feature-gated component rendering
- Usage statistics display
- Upgrade/payment dialogs
- Real-time subscription status

---

## Backend Implementation

### 1. Models

**Key Models:**
- `Package` - Subscription plans with features and pricing
- `TenantSubscription` - Links tenants to packages
- `UsageLog` - Tracks usage events for billing

**Features per package (11 flags):**
- ticket_management
- email_integration
- sip_calling
- facebook_integration
- instagram_integration
- whatsapp_integration
- advanced_analytics
- api_access
- custom_integrations
- priority_support
- dedicated_account_manager

### 2. Permission System

**Location:** `tenants/permissions.py`

```python
# Decorator usage
@require_subscription_feature('sip_calling')
def make_call(request):
    pass

# DRF permission class
class CallViewSet(viewsets.ModelViewSet):
    permission_classes = [HasSubscriptionFeature]
    required_feature = 'sip_calling'
```

### 3. Middleware

**Location:** `tenants/subscription_middleware.py`

Automatically attaches subscription info to every request:
- `request.subscription`
- `request.subscription_features`
- `request.has_feature(name)`

**Add to settings.py:**
```python
MIDDLEWARE = [
    'amanati_crm.middleware.EchoDeskTenantMiddleware',
    'tenants.subscription_middleware.SubscriptionMiddleware',  # Add here
    # ... rest of middleware
]
```

### 4. Payment Integration

**Location:** `tenants/flitt_payment.py`

Core service for Flitt integration.

---

## Frontend Implementation

### 1. Subscription Context

**Location:** `src/contexts/SubscriptionContext.tsx`

Provides subscription data throughout the app.

**Add to layout.tsx:**
```tsx
import { SubscriptionProvider } from '@/contexts/SubscriptionContext';

<AuthProvider>
  <SubscriptionProvider>
    {children}
  </SubscriptionProvider>
</AuthProvider>
```

### 2. Feature Gating

**Location:** `src/components/subscription/FeatureGate.tsx`

```tsx
// Hide features not included in subscription
<FeatureGate feature="sip_calling">
  <CallButton />
</FeatureGate>

// Conditional rendering
const { hasFeature } = useSubscription();
if (hasFeature('advanced_analytics')) {
  // Show analytics
}
```

### 3. Subscription Pages

**Subscription Management:** `/settings/subscription`
- View current plan
- Usage statistics
- Feature list
- Upgrade button

### 4. Upgrade Dialog

**Location:** `src/components/subscription/UpgradeDialog.tsx`

Shows available packages and initiates payment flow.

---

## Flitt Payment Integration

### Setup Steps

#### 1. Get Flitt Credentials

Contact Flitt (https://flitt.com/) to get:
- API Key
- Secret Key
- Merchant ID

#### 2. Configure Backend

**Add to `settings.py` or `.env`:**
```python
# Flitt Payment Configuration
FLITT_API_KEY = 'your-api-key-here'
FLITT_SECRET_KEY = 'your-secret-key-here'
FLITT_MERCHANT_ID = 'your-merchant-id-here'
FLITT_BASE_URL = 'https://api.flitt.com'  # Or correct Flitt API URL
```

#### 3. Update Flitt Integration

**File:** `tenants/flitt_payment.py`

The current implementation is a template. Update these methods based on actual Flitt documentation:

1. **`_generate_signature()`** - Update signature generation algorithm
2. **`create_payment()`** - Update API endpoint and request format
3. **`check_payment_status()`** - Update status check endpoint
4. **Webhook signature verification** - Update according to Flitt specs

**Example (update with actual Flitt docs):**
```python
def create_payment(self, amount, currency='GEL', ...):
    # Update this endpoint based on Flitt docs
    response = requests.post(
        f'{self.base_url}/api/v1/payments',  # Real Flitt endpoint
        json={
            # Real Flitt payload structure
            'merchant_id': self.merchant_id,
            'amount': amount,
            'currency': currency,
            # ... other Flitt-required fields
        },
        headers={
            'Authorization': f'Bearer {self.api_key}',
            # ... other Flitt-required headers
        }
    )
```

#### 4. Configure Webhook

In your Flitt dashboard, set webhook URL to:
```
https://api.echodesk.ge/api/payments/webhook/
```

**Webhook Events:**
- `payment.succeeded` - Payment completed successfully
- `payment.failed` - Payment failed
- `payment.refunded` - Payment refunded

#### 5. Test Payment Flow

1. Create a test payment in development
2. Use Flitt's test card numbers
3. Verify webhook reception
4. Check subscription creation/update

---

## Usage Guide

### For Admins

#### 1. Create Packages

1. Go to Django Admin → Packages
2. Click "Add Package"
3. Fill in details:
   - Name, display name, description
   - Pricing model (agent-based or CRM-based)
   - Price in GEL
   - Max limits (users, WhatsApp, storage)
   - **Check features to enable** ← Important!
4. Save

#### 2. Assign Subscriptions

**Method 1 - Through Tenant:**
1. Go to Tenants → Select tenant
2. Scroll to "Tenant Subscription" inline form
3. Select package, set dates, agent count
4. Save

**Method 2 - Bulk Create:**
1. Go to Tenants → Tenants
2. Select tenants
3. Action: "Create basic subscription for selected tenants"

### For Tenants (End Users)

#### 1. View Subscription

Navigate to: `/settings/subscription`

See:
- Current plan details
- Usage statistics with progress bars
- Enabled features
- Billing information

#### 2. Upgrade Plan

1. Click "Upgrade" or "View Plans"
2. Select a higher-tier package
3. For agent-based: Choose number of agents
4. Click "Proceed to Payment"
5. Complete payment on Flitt page
6. Redirected back with confirmation

### For Developers

#### Protect a Feature

```python
# Backend
from tenants.permissions import require_subscription_feature

@api_view(['POST'])
@require_subscription_feature('whatsapp_integration')
def send_whatsapp(request):
    # Only accessible if tenant has WhatsApp integration
    pass
```

```tsx
// Frontend
import { FeatureGate } from '@/components/subscription/FeatureGate';

<FeatureGate feature="whatsapp_integration">
  <WhatsAppButton />
</FeatureGate>
```

#### Check Limits

```python
# Backend
from tenants.permissions import check_subscription_limit

def add_user(request):
    limit_check = check_subscription_limit(request, 'users')
    if not limit_check['within_limit']:
        return Response({'error': 'User limit reached'}, status=403)
```

```tsx
// Frontend
const { isWithinLimit } = useSubscription();
if (!isWithinLimit('users')) {
  // Show upgrade prompt
}
```

---

## API Endpoints

### Subscription

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/subscription/me/` | Get current subscription | Required |

### Payments

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/payments/create/` | Create payment session | Required |
| GET | `/api/payments/status/<id>/` | Check payment status | Required |
| POST | `/api/payments/webhook/` | Flitt webhook | None (verified) |
| POST | `/api/payments/cancel/` | Cancel subscription | Required |

### Packages (Public)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/packages/` | List all packages | None |
| GET | `/api/packages/by-model/` | Packages by pricing model | None |
| GET | `/api/packages/<id>/features/` | Package features | None |

---

## Testing

### 1. Test Subscription Features

```python
# Create test tenant with subscription
tenant = Tenant.objects.create(schema_name='test', name='Test Corp')
package = Package.objects.create(
    name='professional',
    price_gel=15,
    sip_calling=True,
    whatsapp_integration=True
)
subscription = TenantSubscription.objects.create(
    tenant=tenant,
    package=package,
    is_active=True,
    starts_at=timezone.now()
)

# Test feature access
assert subscription.package.sip_calling == True
```

### 2. Test Permission Decorators

```python
from django.test import RequestFactory
from tenants.permissions import has_subscription_feature

factory = RequestFactory()
request = factory.get('/')
request.tenant = tenant

# Should return True
assert has_subscription_feature(request, 'sip_calling') == True

# Should return False
assert has_subscription_feature(request, 'api_access') == False
```

### 3. Test Payment Flow (Manual)

1. Create test package
2. Create payment via API:
   ```bash
   curl -X POST http://tenant.api.echodesk.ge/api/payments/create/ \
     -H "Authorization: Token YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"package_id": 1, "agent_count": 5}'
   ```
3. Get payment URL from response
4. Test Flitt payment page
5. Verify webhook received
6. Check subscription created/updated

### 4. Test Frontend

1. Start dev server: `npm run dev`
2. Login as tenant
3. Navigate to `/settings/subscription`
4. Check subscription display
5. Test upgrade dialog
6. Verify feature gating works

---

## Troubleshooting

### Payment Not Working

1. **Check Flitt Configuration:**
   ```python
   from tenants.flitt_payment import flitt_service
   print(flitt_service.is_configured())  # Should be True
   ```

2. **Check Logs:**
   ```bash
   tail -f logs/django.log | grep -i payment
   ```

3. **Verify Webhook:**
   - Check webhook URL in Flitt dashboard
   - Test webhook locally with ngrok
   - Verify signature validation

### Features Not Showing

1. **Check Subscription:**
   ```python
   tenant.current_subscription  # Should not be None
   ```

2. **Check Package Features:**
   ```python
   subscription.package.sip_calling  # Should be True if enabled
   ```

3. **Check Frontend Context:**
   ```tsx
   const { subscription } = useSubscription();
   console.log(subscription);  # Should show subscription data
   ```

### Usage Limits Not Working

1. **Update Counters:**
   ```python
   subscription.whatsapp_messages_used += 1
   subscription.save()
   ```

2. **Check Limits:**
   ```python
   subscription.can_send_whatsapp_message()  # Returns bool
   ```

---

## Next Steps

1. ✅ Get Flitt API credentials
2. ✅ Update `flitt_payment.py` with real Flitt endpoints
3. ✅ Configure webhook in Flitt dashboard
4. ✅ Test payment flow end-to-end
5. ✅ Set up production environment variables
6. ✅ Create test packages in admin
7. ✅ Assign subscriptions to tenants
8. ✅ Test feature gating in production

---

## Support

For questions or issues:
- Backend: Check `tenants/permissions.py` and `tenants/flitt_payment.py`
- Frontend: Check `src/contexts/SubscriptionContext.tsx`
- Admin: Check `tenants/admin.py`
- Documentation: This file and `SUBSCRIPTION_USAGE_EXAMPLES.md`

**Flitt Support:** Contact Flitt directly for API documentation and integration help.

---

**Generated with [Claude Code](https://claude.com/claude-code)**
