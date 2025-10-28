# Deployment Checklist

Use this checklist when deploying EchoDesk scheduled functions to DigitalOcean.

## Pre-Deployment

- [ ] Install `doctl` CLI tool (v1.82.0+)
- [ ] Authenticate with DigitalOcean: `doctl auth init`
- [ ] Connect to serverless namespace: `doctl serverless connect`
- [ ] Verify database is accessible from DigitalOcean Functions

## Environment Variables

Set these in DigitalOcean Functions namespace:

### Django Core
- [ ] `DJANGO_SETTINGS_MODULE=amanati_crm.settings`
- [ ] `SECRET_KEY=<your-secret-key>`
- [ ] `DEBUG=False`

### Database
- [ ] `DB_NAME=<database-name>`
- [ ] `DB_USER=<database-user>`
- [ ] `DB_PASSWORD=<database-password>`
- [ ] `DB_HOST=<database-host>`
- [ ] `DB_PORT=25060`

### BOG Payment API
- [ ] `BOG_CLIENT_ID=<client-id>`
- [ ] `BOG_CLIENT_SECRET=<client-secret>`
- [ ] `BOG_BASE_URL=https://api.bog.ge/payments/v1`

### Email (AWS SES or SMTP)
- [ ] `AWS_ACCESS_KEY_ID=<key>` (if using SES)
- [ ] `AWS_SECRET_ACCESS_KEY=<secret>` (if using SES)
- [ ] `AWS_SES_REGION_NAME=us-east-1` (if using SES)
- [ ] `DEFAULT_FROM_EMAIL=noreply@echodesk.ge`

## Deployment Steps

```bash
# 1. Navigate to functions directory
cd /path/to/echodesk-back/functions

# 2. Verify project.yml configuration
cat project.yml

# 3. Deploy
doctl serverless deploy .

# 4. Verify deployment
doctl serverless functions list
doctl serverless triggers list
```

## Post-Deployment Verification

### Test Functions Manually

```bash
# Test recurring payments
- [ ] doctl serverless functions invoke scheduled-tasks/recurring-payments
      Expected: Success response with output from Django command

# Test subscription check
- [ ] doctl serverless functions invoke scheduled-tasks/subscription-check
      Expected: Success response with output from Django command
```

### Verify Schedules

```bash
# List triggers
- [ ] doctl serverless triggers list
      Expected: daily-recurring-payments (2:00 AM UTC)
               daily-subscription-check (3:00 AM UTC)
```

### Check Logs

```bash
# View recent activations
- [ ] doctl serverless activations list
      Expected: Recent test invocations visible

# Follow logs
- [ ] doctl serverless activations logs --function scheduled-tasks/recurring-payments --follow
      Expected: Log output from Django command
```

## Monitoring Setup

- [ ] Create alert for function failures
- [ ] Set up email notifications for errors
- [ ] Add monitoring dashboard bookmark
- [ ] Document on-call procedures

## Testing in Production

### Week 1: Monitor Daily

- [ ] Day 1: Check execution logs after 2 AM UTC
- [ ] Day 2: Verify no error activations
- [ ] Day 3: Check database for processed payments
- [ ] Day 7: Review weekly summary

### Verify Behaviors

- [ ] Recurring payments charge saved cards correctly
- [ ] Subscription checks send reminder emails (check SMTP/SES logs)
- [ ] Grace period logic works (test with expired test tenant)
- [ ] Suspensions work correctly (test with overdue test tenant)

## Rollback Plan

If functions fail in production:

```bash
# Option 1: Use HTTP endpoints temporarily
# Deploy cron_views.py endpoints (see CRON_EXTERNAL_SERVICES.md)
# Set up Cron-Job.org to call HTTP endpoints

# Option 2: Disable triggers
doctl serverless triggers delete daily-recurring-payments
doctl serverless triggers delete daily-subscription-check

# Option 3: Run manually
python manage.py process_recurring_payments
python manage.py check_subscription_status
```

## Troubleshooting

Common issues and solutions:

### "Cannot connect to database"
- [ ] Verify `DB_HOST` is correct
- [ ] Check database allows connections from DigitalOcean Functions IPs
- [ ] Verify firewall rules

### "Module not found"
- [ ] Run build.sh in function directory
- [ ] Redeploy: `doctl serverless deploy .`

### "Trigger not firing"
- [ ] Check trigger exists: `doctl serverless triggers list`
- [ ] Verify cron syntax in project.yml
- [ ] Wait 24 hours for first scheduled execution

### "Function timeout"
- [ ] Increase timeout in project.yml (max 10 minutes)
- [ ] Optimize Django queries
- [ ] Consider batch processing

## Success Criteria

- [ ] Functions deploy without errors
- [ ] Manual test invocations succeed
- [ ] Triggers are created and scheduled
- [ ] Logs show Django commands executing
- [ ] First scheduled execution completes successfully
- [ ] No error emails received
- [ ] Monitoring alerts are configured

## Documentation

- [ ] Update team wiki with deployment date
- [ ] Share monitoring dashboard with team
- [ ] Document any custom configuration
- [ ] Add runbook for common issues

## Sign-Off

- **Deployed by:** _______________
- **Date:** _______________
- **Verified by:** _______________
- **Date:** _______________

---

**Next Review:** Schedule review after 1 week of production operation
