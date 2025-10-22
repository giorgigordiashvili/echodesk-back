# EchoDesk Subscription Management System

## Overview

Your subscription management system is now complete! As a main admin, you can create subscriptions for tenants, and each subscription controls what features and permissions they have access to.

## What's Been Implemented

### 1. **Permission System** (`tenants/permissions.py`)
   - ✅ Decorators for feature checking: `@require_subscription_feature('sip_calling')`
   - ✅ Decorators for limit checking: `@require_subscription_limit('users')`
   - ✅ DRF Permission classes: `HasSubscriptionFeature`, `WithinSubscriptionLimit`
   - ✅ Helper functions: `has_subscription_feature()`, `check_subscription_limit()`
   - ✅ Complete subscription info getter: `get_subscription_info()`

### 2. **Middleware** (`tenants/subscription_middleware.py`)
   - ✅ Automatically attaches subscription to every request
   - ✅ Adds `request.subscription` object
   - ✅ Adds `request.subscription_features` dictionary
   - ✅ Adds `request.has_feature()` helper method

### 3. **Enhanced Admin Interface** (`tenants/admin.py`)
   - ✅ Beautiful visual indicators for subscription status
   - ✅ Usage tracking with color-coded warnings
   - ✅ Feature summary display
   - ✅ Quick actions:
     - Activate/deactivate subscriptions
     - Reset usage counters
     - Extend subscription by 30 days
     - Create basic subscription for tenants
   - ✅ Inline subscription editing when viewing tenants

### 4. **API Endpoints**
   - ✅ `GET /api/subscription/me/` - Get current tenant's subscription info
   - ✅ Existing package endpoints for browsing available plans

### 5. **Documentation**
   - ✅ Complete usage examples in `SUBSCRIPTION_USAGE_EXAMPLES.md`
   - ✅ Code examples for all use cases

## How to Use as Main Admin

### Creating a Subscription for a Tenant

**Option 1: Through Tenant Admin**
1. Go to Django Admin (`/admin/`)
2. Navigate to **Tenants → Tenants**
3. Click on the tenant you want to manage
4. Scroll down to the **Tenant Subscription** inline form
5. Fill in:
   - Package: Select the package (Essential, Professional, Enterprise, etc.)
   - Is active: ✓ (checked)
   - Starts at: Today's date
   - Expires at: End date (optional, leave blank for no expiry)
   - Agent count: Number of agents (for agent-based pricing)
6. Click **Save**

**Option 2: Through Subscription Admin**
1. Go to Django Admin
2. Navigate to **Tenants → Tenant Subscriptions**
3. Click **Add Tenant Subscription**
4. Fill in the form and save

**Option 3: Bulk Create**
1. Go to **Tenants → Tenants**
2. Select multiple tenants (checkboxes)
3. Choose action: **"Create basic subscription for selected tenants"**
4. Click **Go**

### Managing Existing Subscriptions

**View All Subscriptions:**
- **Tenants → Tenant Subscriptions**
- You'll see:
  - Status badges (Active/Inactive)
  - Monthly cost
  - Usage indicators (shows if over limit)
  - Usage percentages

**Admin Actions (bulk operations):**
1. Select subscriptions using checkboxes
2. Choose an action from dropdown:
   - **Activate selected subscriptions**
   - **Deactivate selected subscriptions**
   - **Reset usage counters** (resets WhatsApp and storage usage)
   - **Extend subscription by 30 days**
3. Click **Go**

### Viewing Subscription Details

When you open a subscription, you'll see:
- **Usage Summary Table**: Shows current usage vs limits with color coding
  - 🟢 Green: Under 80%
  - 🟠 Orange: 80-100%
  - 🔴 Red: Over limit
- **Feature Summary**: List of all enabled features
- **Billing Information**: Last billed date, next billing date
- **Usage Logs**: Historical usage events

## How Permissions Work

### Feature-Based Access

Each package has 11 feature flags:
1. `ticket_management` - Ticket management system
2. `email_integration` - Email integration
3. `sip_calling` - Phone calling system
4. `facebook_integration` - Facebook Messenger
5. `instagram_integration` - Instagram DM
6. `whatsapp_integration` - WhatsApp Business
7. `advanced_analytics` - Advanced analytics
8. `api_access` - API access
9. `custom_integrations` - Custom integrations
10. `priority_support` - Priority support
11. `dedicated_account_manager` - Dedicated account manager

**When a tenant tries to access a feature:**
- ✅ If their package includes it → Access granted
- ❌ If their package doesn't include it → 403 Forbidden error

### Limit-Based Access

Each package has 3 usage limits:
1. **Users**: Maximum number of users (CRM-based packages only)
2. **WhatsApp Messages**: Messages per month
3. **Storage**: Storage in GB

**When a tenant reaches a limit:**
- ⚠️ They receive a 403 error explaining the limit
- 📊 Admins can see usage warnings in admin interface
- 🔄 Admins can reset usage counters or upgrade the package

## Example Scenarios

### Scenario 1: Tenant wants to make calls

**Code checks:**
```python
@require_subscription_feature('sip_calling')
def make_call(request):
    # Only accessible if tenant's package has sip_calling=True
    pass
```

**Admin sets up:**
1. Create/Edit tenant's subscription
2. Choose a package with **SIP Calling** enabled (e.g., Professional or Enterprise)
3. Save
4. Tenant can now make calls!

### Scenario 2: Tenant reaches WhatsApp message limit

**What happens:**
1. Package allows 1,000 messages/month
2. Tenant sends 1,000 messages
3. Next message attempt returns 403: "You have reached your WhatsApp limit"

**Admin fixes:**
1. Go to subscription in admin
2. Option A: Reset usage counter (Reset usage action)
3. Option B: Upgrade to higher package with more messages
4. Save changes

### Scenario 3: Adding advanced features

**Tenant requests:**
"We need advanced analytics and API access"

**Admin action:**
1. Go to tenant's subscription
2. Change package from "Essential" to "Professional"
3. Verify Professional package has:
   - ✓ advanced_analytics = True
   - ✓ api_access = True
4. Save
5. Features are immediately available!

## Package Pricing Models

### Agent-Based Pricing
- Cost = `package price × number of agents`
- Example: 5₾/agent × 10 agents = 50₾/month
- No user limit (unlimited users)
- Used for: Essential, Professional, Enterprise plans

### CRM-Based Pricing
- Fixed monthly cost
- Includes specific number of users
- Example: 249₾/month for up to 25 users
- Used for: Startup, Business, Corporate plans

## API for Tenants

Tenants can check their own subscription:

```bash
GET /api/subscription/me/
Authorization: Token {tenant_token}
```

**Response:**
```json
{
  "has_subscription": true,
  "package": {
    "id": 2,
    "name": "Professional",
    "pricing_model": "Agent-based"
  },
  "subscription": {
    "is_active": true,
    "monthly_cost": 150.00,
    "agent_count": 10
  },
  "features": {
    "ticket_management": true,
    "sip_calling": true,
    "advanced_analytics": true,
    ...
  },
  "limits": {
    "max_users": null,
    "max_whatsapp_messages": 5000,
    "max_storage_gb": 20
  },
  "usage": {
    "current_users": 8,
    "whatsapp_messages_used": 1250,
    "storage_used_gb": 5.3
  }
}
```

## Developer Usage

See `SUBSCRIPTION_USAGE_EXAMPLES.md` for complete code examples.

**Quick examples:**

```python
# Check feature in view
if request.has_feature('sip_calling'):
    allow_calls()

# Decorator for feature
@require_subscription_feature('whatsapp_integration')
def send_whatsapp(request):
    pass

# DRF ViewSet
class CallViewSet(viewsets.ModelViewSet):
    permission_classes = [HasSubscriptionFeature]
    required_feature = 'sip_calling'
```

## Database Schema

```
Package
├── Features (11 boolean fields)
├── Limits (max_users, max_whatsapp_messages, max_storage_gb)
└── Pricing (price_gel, pricing_model, billing_period)

Tenant (1) ──→ TenantSubscription (1)
                ├── Package (FK)
                ├── Usage counters
                └── Billing info

TenantSubscription (1) ──→ UsageLog (many)
                            └── Event tracking
```

## Next Steps

1. ✅ **System is ready to use!**
2. Create your packages in admin if you haven't already
3. Assign subscriptions to tenants
4. Start using permission decorators in your views
5. Monitor usage through admin interface

## Support & Documentation

- **Full code examples**: `tenants/SUBSCRIPTION_USAGE_EXAMPLES.md`
- **Permission utilities**: `tenants/permissions.py`
- **Middleware**: `tenants/subscription_middleware.py`
- **Admin interface**: Django Admin → Tenants section

---

**You're all set!** 🎉

Your subscription system is fully operational. You can now control tenant access to features and manage their usage limits from the Django admin interface.
