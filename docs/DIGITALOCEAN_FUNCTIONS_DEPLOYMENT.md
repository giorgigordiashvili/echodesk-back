# DigitalOcean Functions Deployment Guide

This guide explains how to deploy and manage EchoDesk's scheduled functions on DigitalOcean Functions platform.

## Overview

EchoDesk uses DigitalOcean Functions with built-in scheduling for two critical tasks:

1. **recurring-payments** - Charges saved cards for expiring subscriptions (runs daily at 2 AM UTC)
2. **subscription-check** - Monitors subscriptions, sends reminders, suspends overdue accounts (runs daily at 3 AM UTC)

## Why DigitalOcean Functions?

- ✅ Native cron scheduling support
- ✅ Serverless (no server maintenance)
- ✅ Auto-scaling
- ✅ Pay only for execution time
- ✅ Integrated with DigitalOcean infrastructure
- ✅ Easy deployment with `doctl`

## Prerequisites

### 1. Install doctl CLI

```bash
# macOS
brew install doctl

# Linux
cd ~
wget https://github.com/digitalocean/doctl/releases/download/v1.82.0/doctl-1.82.0-linux-amd64.tar.gz
tar xf doctl-1.82.0-linux-amd64.tar.gz
sudo mv doctl /usr/local/bin
```

### 2. Authenticate doctl

```bash
# Create a personal access token at:
# https://cloud.digitalocean.com/account/api/tokens

doctl auth init
# Paste your token when prompted
```

### 3. Enable Functions

```bash
# Connect to your DigitalOcean namespace
doctl serverless connect
```

## Project Structure

```
echodesk-back/
├── functions/
│   ├── project.yml                          # Main configuration
│   └── packages/
│       └── scheduled-tasks/
│           ├── recurring-payments/
│           │   ├── __main__.py              # Function entry point
│           │   ├── requirements.txt         # Python dependencies
│           │   └── build.sh                 # Build script
│           └── subscription-check/
│               ├── __main__.py              # Function entry point
│               ├── requirements.txt         # Python dependencies
│               └── build.sh                 # Build script
```

## Configuration

### Environment Variables

The functions need access to the same environment variables as your Django app:

```bash
# Required environment variables (set in DigitalOcean Functions dashboard)
DJANGO_SETTINGS_MODULE=amanati_crm.settings
SECRET_KEY=<your-secret-key>
DEBUG=False

# Database
DB_NAME=<database-name>
DB_USER=<database-user>
DB_PASSWORD=<database-password>
DB_HOST=<database-host>
DB_PORT=25060

# BOG Payment API
BOG_CLIENT_ID=<your-client-id>
BOG_CLIENT_SECRET=<your-client-secret>

# Email (if using AWS SES)
AWS_ACCESS_KEY_ID=<your-access-key>
AWS_SECRET_ACCESS_KEY=<your-secret-key>
AWS_SES_REGION_NAME=us-east-1
DEFAULT_FROM_EMAIL=noreply@echodesk.ge
```

### Setting Environment Variables

#### Option 1: Via doctl CLI

```bash
# Set environment variables for the entire namespace
doctl serverless namespaces update echodesk --env DJANGO_SETTINGS_MODULE=amanati_crm.settings
doctl serverless namespaces update echodesk --env DB_HOST=your-db-host
# ... repeat for all variables
```

#### Option 2: Via DigitalOcean Dashboard

1. Go to https://cloud.digitalocean.com/functions
2. Select your namespace (echodesk)
3. Click "Settings" → "Environment Variables"
4. Add each variable

## Deployment

### 1. Navigate to Functions Directory

```bash
cd /path/to/echodesk-back/functions
```

### 2. Deploy Functions

```bash
# Deploy all functions and triggers
doctl serverless deploy .

# Expected output:
# Deploying '/path/to/echodesk-back/functions'
#   to namespace 'fn-...'
#   on host 'https://faas-...'
#
# Deployed functions ('doctl sbx fn get <funcName> --url' for URL):
#   - scheduled-tasks/recurring-payments
#   - scheduled-tasks/subscription-check
#
# Deployed triggers:
#   - daily-recurring-payments (scheduled-tasks/recurring-payments)
#   - daily-subscription-check (scheduled-tasks/subscription-check)
```

### 3. Verify Deployment

```bash
# List deployed functions
doctl serverless functions list

# Expected output:
# scheduled-tasks/recurring-payments
# scheduled-tasks/subscription-check

# List triggers
doctl serverless triggers list

# Expected output:
# NAME                        TYPE       FUNCTION
# daily-recurring-payments    scheduler  scheduled-tasks/recurring-payments
# daily-subscription-check    scheduler  scheduled-tasks/subscription-check
```

## Testing

### Test Functions Manually

You can invoke functions manually without waiting for the scheduled trigger:

```bash
# Test recurring payments
doctl serverless functions invoke scheduled-tasks/recurring-payments

# Test subscription check
doctl serverless functions invoke scheduled-tasks/subscription-check
```

### View Function Logs

```bash
# View logs for recurring payments
doctl serverless activations logs --function scheduled-tasks/recurring-payments

# View logs for subscription check
doctl serverless activations logs --function scheduled-tasks/subscription-check

# Follow logs in real-time
doctl serverless activations logs --function scheduled-tasks/recurring-payments --follow
```

### View Recent Activations

```bash
# List recent function executions
doctl serverless activations list

# Get details of specific activation
doctl serverless activations get <activation-id>
```

## Schedule Configuration

The schedule is defined in `functions/project.yml`:

```yaml
triggers:
  - name: daily-recurring-payments
    sourceType: scheduler
    sourceDetails:
      cron: "0 2 * * *"  # Daily at 2:00 AM UTC
```

### Cron Syntax

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
│ │ │ │ │
* * * * *
```

### Common Schedules

```yaml
# Every day at 2 AM UTC
cron: "0 2 * * *"

# Every Monday at 9 AM UTC
cron: "0 9 * * 1"

# First day of month at midnight UTC
cron: "0 0 1 * *"

# Every 6 hours
cron: "0 */6 * * *"

# Twice daily (8 AM and 8 PM UTC)
cron: "0 8,20 * * *"
```

## Updating Functions

### Update Function Code

1. Make changes to `__main__.py` or dependencies
2. Deploy again:

```bash
cd functions
doctl serverless deploy .
```

### Update Schedule

1. Edit `functions/project.yml`
2. Update the `cron` expression
3. Deploy:

```bash
cd functions
doctl serverless deploy .
```

## Monitoring

### Set Up Alerts

Create monitoring alerts for function failures:

1. Go to https://cloud.digitalocean.com/monitoring
2. Create a new alert policy
3. Set conditions:
   - Resource Type: Functions
   - Metric: Activation Errors
   - Threshold: > 0 errors in 5 minutes
4. Add notification channels (email, Slack)

### View Execution History

```bash
# View last 10 activations
doctl serverless activations list --limit 10

# View failed activations only
doctl serverless activations list --limit 10 | grep error
```

### Check Function Health

```bash
# Get function details including error rate
doctl serverless functions get scheduled-tasks/recurring-payments
```

## Troubleshooting

### Function Fails with "Module Not Found"

**Problem:** Missing Python dependencies

**Solution:**
```bash
cd functions/packages/scheduled-tasks/recurring-payments
./build.sh
cd ../../..
doctl serverless deploy .
```

### Function Fails with "Database Connection Error"

**Problem:** Missing or incorrect database environment variables

**Solution:**
```bash
# Verify environment variables are set
doctl serverless namespaces get echodesk

# Update variables if needed
doctl serverless namespaces update echodesk --env DB_HOST=correct-host
```

### Function Times Out

**Problem:** Function execution exceeds time limit (default 60s)

**Solution:** Add timeout configuration to `project.yml`:

```yaml
functions:
  - name: recurring-payments
    runtime: python:3.11
    timeout: 180000  # 3 minutes in milliseconds
```

### Trigger Not Firing

**Problem:** Scheduled trigger not executing

**Solution:**
```bash
# Check trigger exists
doctl serverless triggers list

# Delete and recreate trigger
doctl serverless triggers delete daily-recurring-payments
doctl serverless deploy .
```

### Django Setup Fails

**Problem:** Django can't find settings or models

**Solution:** Ensure `sys.path` includes the Django project root:

```python
# In __main__.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
```

## Cost Estimation

DigitalOcean Functions pricing:

- **Free tier:** 90,000 GB-seconds per month
- **Paid:** $0.0000185 per GB-second after free tier

### Example Calculation

Assuming each function:
- Runs once per day (2 functions × 30 days = 60 executions/month)
- Takes 10 seconds to execute
- Uses 256 MB memory

```
Cost = (60 executions × 10 seconds × 0.256 GB) × $0.0000185
     = 153.6 GB-seconds × $0.0000185
     = $0.00284 per month
```

**Result:** Well within free tier! ✅

## CI/CD Integration

### GitHub Actions Deployment

Create `.github/workflows/deploy-functions.yml`:

```yaml
name: Deploy Functions

on:
  push:
    branches: [main]
    paths:
      - 'functions/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install doctl
        uses: digitalocean/action-doctl@v2
        with:
          token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}

      - name: Deploy functions
        run: |
          doctl serverless connect
          cd functions
          doctl serverless deploy .
```

Add `DIGITALOCEAN_ACCESS_TOKEN` to GitHub Secrets.

## Security Best Practices

1. **Use secrets for sensitive data:**
   - Store DB credentials, API keys in DigitalOcean environment variables
   - Never commit secrets to Git

2. **Limit database permissions:**
   - Create a dedicated database user for functions
   - Grant only necessary permissions

3. **Monitor for anomalies:**
   - Set up alerts for unusual execution patterns
   - Review logs regularly

4. **Keep dependencies updated:**
   - Regularly update `requirements.txt`
   - Test updates in staging first

## Alternative: HTTP Endpoint Trigger

If you prefer external cron services (like Cron-Job.org), you can modify functions to accept HTTP triggers:

```yaml
# In project.yml
functions:
  - name: recurring-payments
    runtime: python:3.11
    web: true  # Enable HTTP access
```

Then call via HTTP:

```bash
curl -X POST https://faas-fra1-123.doserverless.co/api/v1/web/fn-abc/scheduled-tasks/recurring-payments
```

See `docs/CRON_EXTERNAL_SERVICES.md` for this approach.

## Support

- **DigitalOcean Functions Docs:** https://docs.digitalocean.com/products/functions/
- **doctl Reference:** https://docs.digitalocean.com/reference/doctl/
- **Community:** https://www.digitalocean.com/community/tags/functions

## Summary

1. Install and authenticate `doctl`
2. Set environment variables in namespace
3. Deploy: `cd functions && doctl serverless deploy .`
4. Monitor: `doctl serverless activations logs --follow`
5. Update: Edit code, deploy again

Your scheduled tasks are now running automatically! 🎉
