# Cron Job Setup for EchoDesk

## Overview

EchoDesk uses cron jobs to handle various automated tasks:

1. **process_recurring_payments** - Charges saved cards for subscription renewals
2. **check_subscription_status** - Monitors subscriptions and sends notifications
3. **sync_emails** - Syncs emails from IMAP servers for all tenants

## Cron Schedule

Add these to your server's crontab (`crontab -e`):

```bash
# EchoDesk Email Sync (runs every 5 minutes)
*/5 * * * * cd /path/to/echodesk-back && /path/to/python manage.py sync_emails >> /var/log/echodesk/email_sync.log 2>&1

# EchoDesk Recurring Payments (runs daily at 2 AM)
0 2 * * * cd /path/to/echodesk-back && /path/to/python manage.py process_recurring_payments >> /var/log/echodesk/recurring_payments.log 2>&1

# EchoDesk Subscription Status Check (runs daily at 3 AM)
0 3 * * * cd /path/to/echodesk-back && /path/to/python manage.py check_subscription_status >> /var/log/echodesk/subscription_status.log 2>&1
```

## Commands Explained

### 1. sync_emails

Syncs emails from IMAP servers for all tenants with active email connections.

**Options:**
- `--tenant SCHEMA` - Sync only for a specific tenant (by schema name)
- `--max-messages N` - Maximum messages to sync per connection (default: 500)
- `--dry-run` - Show what would be synced without actually syncing

**Examples:**
```bash
# Dry run to see what would be synced
python manage.py sync_emails --dry-run

# Sync for all tenants
python manage.py sync_emails

# Sync for a specific tenant
python manage.py sync_emails --tenant mycompany

# Sync with custom message limit
python manage.py sync_emails --max-messages 1000
```

**What it does:**
1. Iterates through all active tenants
2. For each tenant, finds active email connections
3. Connects to IMAP server and fetches new messages
4. Stores new messages in the database
5. Updates last_sync_at timestamp

### 2. process_recurring_payments

Charges saved cards for subscriptions expiring soon.

**Options:**
- `--dry-run` - Show what would be charged without processing
- `--days-before N` - Process subscriptions expiring within N days (default: 3)

**Examples:**
```bash
# Dry run to see what would be charged
python manage.py process_recurring_payments --dry-run

# Process subscriptions expiring in next 5 days
python manage.py process_recurring_payments --days-before 5

# Normal run (3 days before expiration)
python manage.py process_recurring_payments
```

**What it does:**
1. Finds active subscriptions expiring within 3 days
2. Looks for saved card (from initial payment)
3. Charges the saved card using `bog_service.charge_saved_card()`
4. Creates new PaymentOrder for tracking
5. BOG webhook confirms payment and extends subscription

**Flow:**
```
Subscription expires in 3 days
  ↓
Find PaymentOrder with card_saved=True
  ↓
Charge saved card (bog_service.charge_saved_card)
  ↓
Create new PaymentOrder (status=pending)
  ↓
BOG processes payment
  ↓
Webhook confirms → Subscription extended 30 days
```

### 2. check_subscription_status

Monitors subscription status and handles grace periods.

**Options:**
- `--grace-days N` - Days of grace period after expiration (default: 7)

**Examples:**
```bash
# Check with default 7-day grace period
python manage.py check_subscription_status

# Custom 14-day grace period
python manage.py check_subscription_status --grace-days 14
```

**What it does:**

1. **7 Days Before Expiration:**
   - Sends reminder email to admin
   - "Your subscription expires in 7 days"

2. **3 Days Before Expiration:**
   - Sends urgent reminder email
   - "⚠️ Urgent: expires in 3 days"

3. **Grace Period (0-7 days after expiration):**
   - Sends daily warnings
   - "Payment required - X days until suspension"
   - Account still active

4. **Past Grace Period (7+ days overdue):**
   - Suspends tenant account (`is_active=False`)
   - Deactivates subscription
   - Sends suspension notice
   - Data preserved for reactivation

**Timeline Example:**
```
Day -7:  📧 "Expires in 7 days"
Day -3:  ⚠️  "Expires in 3 days"
Day -2:  🔄 process_recurring_payments runs → charges saved card
Day 0:   Subscription expires
Day 1-7: ⏳ Grace period - daily warnings
Day 7:   🔒 Account suspended
```

## Log Files

Create log directories:
```bash
sudo mkdir -p /var/log/echodesk
sudo chown your-user:your-user /var/log/echodesk
```

View logs:
```bash
# Recent recurring payments
tail -f /var/log/echodesk/recurring_payments.log

# Recent subscription checks
tail -f /var/log/echodesk/subscription_status.log
```

## Email Configuration

Ensure email settings are configured in `settings.py`:

```python
# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'noreply@echodesk.ge'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'EchoDesk <noreply@echodesk.ge>'
```

## Testing

Test commands manually before adding to cron:

```bash
# Test dry run
python manage.py process_recurring_payments --dry-run

# Test subscription check
python manage.py check_subscription_status

# Test email (Django shell)
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Test message', 'noreply@echodesk.ge', ['admin@example.com'])
```

## Monitoring

Monitor cron job execution:

```bash
# Check cron logs
tail -f /var/log/syslog | grep CRON

# Check Django logs
tail -f /var/log/echodesk/*.log

# Check for errors
grep -i error /var/log/echodesk/*.log
```

## Troubleshooting

**Problem:** Cards not being charged

**Solutions:**
1. Check if card_saved=True on initial PaymentOrder
2. Verify bog_order_id is not null
3. Check BOG credentials in .env
4. Run with --dry-run to see what would happen
5. Check logs for BOG API errors

**Problem:** Emails not sending

**Solutions:**
1. Verify EMAIL_* settings in settings.py
2. Test email manually (see Testing section)
3. Check spam folder
4. Verify SMTP credentials

**Problem:** Subscriptions not extending after payment

**Solutions:**
1. Check webhook is being called by BOG
2. Verify webhook endpoint is accessible
3. Check webhook logs in Django
4. Ensure external_order_id matches in PaymentOrder

## Production Deployment

For production with DigitalOcean/AWS:

```bash
# Use absolute paths
0 2 * * * cd /var/www/echodesk-back && /usr/bin/python3 manage.py process_recurring_payments >> /var/log/echodesk/recurring_payments.log 2>&1
0 3 * * * cd /var/www/echodesk-back && /usr/bin/python3 manage.py check_subscription_status >> /var/log/echodesk/subscription_status.log 2>&1

# Set environment variables if needed
0 2 * * * cd /var/www/echodesk-back && /usr/bin/env PATH=/usr/bin:$PATH DJANGO_SETTINGS_MODULE=amanati_crm.settings /usr/bin/python3 manage.py process_recurring_payments >> /var/log/echodesk/recurring_payments.log 2>&1
```

## Next Steps

1. Test commands manually
2. Add to crontab with correct paths
3. Monitor logs for first few runs
4. Verify emails are being sent
5. Test complete flow with a test subscription
