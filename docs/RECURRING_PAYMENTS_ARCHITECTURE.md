# Recurring Payments Architecture

Complete overview of EchoDesk's recurring payment and subscription management system.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EchoDesk Backend                              │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                   Django Application                           │ │
│  │                                                                │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │ │
│  │  │   Tenants    │  │   Payment    │  │     BOG      │       │ │
│  │  │    Models    │  │    Orders    │  │   Service    │       │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │ │
│  │         │                  │                  │               │ │
│  └─────────┼──────────────────┼──────────────────┼───────────────┘ │
│            │                  │                  │                   │
│            ▼                  ▼                  ▼                   │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │              PostgreSQL Database                        │       │
│  │  • Tenant subscriptions                                 │       │
│  │  • Payment orders                                       │       │
│  │  • Saved card references (bog_order_id)                │       │
│  └─────────────────────────────────────────────────────────┘       │
└───────────────────────────────────────────────────────────────────┘
                              │
                              │ Scheduled Tasks
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              DigitalOcean Functions (Serverless)                     │
│                                                                       │
│  ┌───────────────────────────────┐  ┌───────────────────────────┐  │
│  │   recurring-payments          │  │   subscription-check       │  │
│  │                               │  │                            │  │
│  │   Trigger: Daily 2 AM UTC     │  │   Trigger: Daily 3 AM UTC  │  │
│  │   Schedule: 0 2 * * *         │  │   Schedule: 0 3 * * *      │  │
│  │                               │  │                            │  │
│  │   Actions:                    │  │   Actions:                 │  │
│  │   • Find expiring subs        │  │   • Send 7-day reminders   │  │
│  │   • Check saved cards         │  │   • Send 3-day alerts      │  │
│  │   • Charge via BOG API        │  │   • Grace period warnings  │  │
│  │   • Create payment orders     │  │   • Suspend overdue        │  │
│  └───────────────────────────────┘  └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ API Calls
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Bank of Georgia (BOG)                            │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  Payment Processing                                      │       │
│  │  • Saved card charging: /orders/{id}/subscribe          │       │
│  │  • Card management: /orders/{id}/subscriptions          │       │
│  └──────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ Webhooks
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Payment Webhook                               │
│                                                                       │
│  https://api.echodesk.ge/api/payments/webhook/                      │
│                                                                       │
│  Receives payment confirmations and updates:                         │
│  • Payment status (paid/failed)                                      │
│  • Subscription renewal                                              │
│  • Card saving confirmation                                          │
└─────────────────────────────────────────────────────────────────────┘
```

## Payment Flow

### 1. Initial Registration (Card Saving)

```
User Registers
    │
    ├──> Creates PaymentOrder
    │    • order_id = "PAY-xxxxx"
    │    • amount = package price
    │    • card_saved = False
    │
    ├──> BOG: Create Payment
    │    POST /ecommerce/orders
    │    Returns: bog_order_id, payment_url
    │
    ├──> BOG: Enable Card Saving
    │    PUT /orders/{bog_order_id}/subscriptions
    │    Returns: 202 Accepted
    │
    ├──> User Redirected to Payment Page
    │    Enters card details
    │
    └──> BOG: Webhook Callback
         POST /api/payments/webhook/
         • Update PaymentOrder status = 'paid'
         • Set card_saved = True
         • Store bog_order_id for future charges
         • Create tenant & subscription
```

### 2. Recurring Payment (Automated)

```
DigitalOcean Function: recurring-payments
Daily at 2:00 AM UTC
    │
    ├──> Query: Find subscriptions expiring in 3 days
    │    WHERE next_billing_date <= NOW() + 3 days
    │    AND card_saved = True
    │
    ├──> For each subscription:
    │    │
    │    ├──> Get saved card reference
    │    │    • Find PaymentOrder with bog_order_id
    │    │
    │    ├──> BOG: Charge Saved Card
    │    │    POST /orders/{bog_order_id}/subscribe
    │    │    Body: {
    │    │      amount: package_price,
    │    │      external_order_id: "REC-xxxxx",
    │    │      callback_url: webhook_url
    │    │    }
    │    │
    │    ├──> Create New PaymentOrder
    │    │    • order_id = "REC-xxxxx"
    │    │    • metadata.type = 'recurring'
    │    │    • status = 'pending'
    │    │
    │    └──> BOG: Webhook Callback (async)
    │         • Update status = 'paid'
    │         • Extend subscription (next_billing_date += 30 days)
    │
    └──> Log results
         Success: X charged
         Failed: Y failed
         Skipped: Z (no saved card)
```

### 3. Subscription Monitoring

```
DigitalOcean Function: subscription-check
Daily at 3:00 AM UTC
    │
    ├──> 7-Day Reminders
    │    Query: expires_at = NOW() + 7 days
    │    └──> Send email: "Subscription expires in 7 days"
    │
    ├──> 3-Day Urgent Reminders
    │    Query: expires_at = NOW() + 3 days
    │    └──> Send email: "Urgent: Expires in 3 days"
    │
    ├──> Grace Period Warnings
    │    Query: NOW() > expires_at > NOW() - 7 days
    │    └──> Send email: "Payment required, X days until suspension"
    │
    └──> Account Suspensions
         Query: expires_at < NOW() - 7 days
         └──> Set tenant.is_active = False
              Set subscription.is_active = False
              Send email: "Account suspended"
```

## Data Models

### PaymentOrder

```python
class PaymentOrder(models.Model):
    order_id = CharField(max_length=100, unique=True)
    bog_order_id = CharField(max_length=100, null=True)  # BOG's internal ID
    card_saved = BooleanField(default=False)             # Card saved?
    tenant = ForeignKey(Tenant)
    package = ForeignKey(Package)
    amount = DecimalField(max_digits=10, decimal_places=2)
    status = CharField(choices=['pending', 'paid', 'failed'])
    paid_at = DateTimeField(null=True)
    metadata = JSONField(default=dict)  # {'type': 'recurring', 'parent_order_id': ...}
```

### TenantSubscription

```python
class TenantSubscription(models.Model):
    tenant = OneToOneField(Tenant)
    package = ForeignKey(Package)
    is_active = BooleanField(default=True)
    expires_at = DateTimeField()
    next_billing_date = DateTimeField()
    agent_count = PositiveIntegerField(default=1)
```

## Timeline Example

Day-by-day example of how the system works:

```
Day 1 (Oct 1):
    • User registers, pays 100 GEL
    • Card saved: bog_order_id = "BOG123"
    • Subscription: expires_at = Nov 1

Day 25 (Oct 25):
    • subscription-check runs: 7-day reminder sent
    • "Your subscription expires on Nov 1"

Day 28 (Oct 28):
    • subscription-check runs: 3-day urgent reminder
    • "Urgent: Expires in 3 days"

Day 29 (Oct 29):
    • recurring-payments runs: Finds subscription (expires in 3 days)
    • Charges saved card (bog_order_id = "BOG123")
    • Creates new order: "REC-abc123"
    • BOG webhook confirms payment
    • Subscription extended: expires_at = Dec 1

Day 59 (Nov 29):
    • Cycle repeats: Charge 3 days before Dec 1
```

## Failure Scenarios

### Scenario 1: Payment Fails

```
Day 29: recurring-payments charges card
    └──> BOG returns error (insufficient funds)
         └──> PaymentOrder status = 'failed'

Day 32 (Nov 1): subscription-check runs
    └──> Subscription expired but within grace period
         └──> Send email: "Payment failed, 7 days until suspension"

Day 39 (Nov 8): subscription-check runs
    └──> Grace period over
         └──> Set tenant.is_active = False
              Send email: "Account suspended"
```

### Scenario 2: User Deletes Card

```
User clicks "Delete Saved Card"
    └──> API: DELETE /api/payments/saved-card/delete/
         └──> BOG: DELETE /orders/{bog_order_id}/subscriptions
              └──> Update: card_saved = False

Day 29: recurring-payments runs
    └──> No saved card found
         └──> Skip charging
              Log: "No saved card, skipping"

Day 32 (Nov 1): subscription-check runs
    └──> Send expiration reminders
         └──> User must manually pay
```

### Scenario 3: Manual Payment

```
User subscription expired
User clicks "Pay Now"
    └──> API: POST /api/payments/manual/
         └──> BOG: Create new payment
              └──> User redirected to payment page
                   └──> User enters card
                        └──> BOG webhook confirms
                             └──> Subscription renewed
                                  New card saved
```

## Frontend Integration

Users can manage their subscription from Settings:

```typescript
// SavedCardManager component shows:
┌─────────────────────────────────────────┐
│ Saved Payment Card                      │
│                                         │
│ Status: ● Card saved                    │
│ Last payment: Oct 1, 2024               │
│ Auto-renewal: Enabled                   │
│                                         │
│ [Delete Card]  [Pay Now]                │
│                                         │
│ ℹ️ Your card will be automatically      │
│   charged 3 days before renewal         │
└─────────────────────────────────────────┘
```

## Key Features

1. **Automatic Renewals** - No user action required
2. **Advance Charging** - 3 days before expiration (time to handle failures)
3. **Grace Period** - 7 days after expiration before suspension
4. **Multi-tier Reminders** - 7 days, 3 days, grace period warnings
5. **Card Management** - Users can delete saved cards anytime
6. **Manual Fallback** - Users can manually pay if auto-payment fails
7. **Transparent Status** - Clear UI showing card and renewal status

## Security Considerations

1. **No card data stored** - Only BOG's order_id reference
2. **Secure webhooks** - Verified payment confirmations
3. **Token authentication** - Environment-based secrets
4. **Encrypted database** - PCI compliance not required (BOG handles cards)
5. **Access control** - Users can only see/manage their own cards

## Monitoring & Alerts

- Function execution logs in DigitalOcean
- Failed payment tracking in PaymentOrder
- Email notifications to users at each stage
- Optional: Slack/email alerts for admin on failures

## Cost Analysis

**DigitalOcean Functions:**
- 2 functions × 30 days = 60 executions/month
- ~10 seconds per execution
- Free tier: 90,000 GB-seconds/month
- **Estimated cost: $0.00** (well within free tier)

**BOG Transaction Fees:**
- Standard payment processing fees apply
- Recurring charges same as regular payments

## Future Enhancements

1. **Retry Logic** - Automatic retry for failed charges
2. **Multiple Cards** - Allow users to have backup payment methods
3. **Payment History** - Full transaction history UI
4. **Dunning Management** - Smart retry schedules
5. **Prorated Upgrades** - Mid-cycle plan changes
6. **Usage-based Billing** - Dynamic pricing based on usage
7. **Invoice Generation** - PDF invoices for each payment

## Related Documentation

- `/docs/BOG_INTEGRATION_GUIDE.md` - BOG API integration details
- `/docs/DIGITALOCEAN_FUNCTIONS_DEPLOYMENT.md` - Function deployment guide
- `/functions/README.md` - Quick reference for functions
- `/docs/CRON_EXTERNAL_SERVICES.md` - Alternative scheduling approaches
