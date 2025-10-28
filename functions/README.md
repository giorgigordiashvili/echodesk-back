# EchoDesk Scheduled Functions

DigitalOcean serverless functions with cron scheduling for EchoDesk backend tasks.

## Quick Start

```bash
# Install doctl
brew install doctl  # macOS
# or download from https://github.com/digitalocean/doctl/releases

# Authenticate
doctl auth init

# Connect to namespace
doctl serverless connect

# Deploy
cd functions
doctl serverless deploy .

# View logs
doctl serverless activations logs --function scheduled-tasks/recurring-payments --follow
```

## Functions

### 1. recurring-payments

**Schedule:** Daily at 2:00 AM UTC
**Purpose:** Charges saved cards for subscriptions expiring within 3 days

```bash
# Test manually
doctl serverless functions invoke scheduled-tasks/recurring-payments

# View logs
doctl serverless activations logs --function scheduled-tasks/recurring-payments
```

### 2. subscription-check

**Schedule:** Daily at 3:00 AM UTC
**Purpose:**
- Sends 7-day and 3-day expiration reminders
- Sends grace period warnings
- Suspends accounts past grace period (7 days)

```bash
# Test manually
doctl serverless functions invoke scheduled-tasks/subscription-check

# View logs
doctl serverless activations logs --function scheduled-tasks/subscription-check
```

## Environment Variables

Set in DigitalOcean Functions namespace settings:

```
DJANGO_SETTINGS_MODULE=amanati_crm.settings
SECRET_KEY=<your-secret>
DB_HOST=<db-host>
DB_NAME=<db-name>
DB_USER=<db-user>
DB_PASSWORD=<db-password>
DB_PORT=25060
BOG_CLIENT_ID=<client-id>
BOG_CLIENT_SECRET=<client-secret>
```

## Project Structure

```
functions/
├── project.yml                    # Function definitions & schedules
├── README.md                      # This file
└── packages/
    └── scheduled-tasks/
        ├── recurring-payments/
        │   ├── __main__.py       # Entry point
        │   ├── requirements.txt  # Dependencies
        │   └── build.sh          # Build script
        └── subscription-check/
            ├── __main__.py
            ├── requirements.txt
            └── build.sh
```

## Documentation

- **Full Deployment Guide:** See `docs/DIGITALOCEAN_FUNCTIONS_DEPLOYMENT.md`
- **DigitalOcean Docs:** https://docs.digitalocean.com/products/functions/

## Monitoring

```bash
# List recent executions
doctl serverless activations list

# View function details
doctl serverless functions get scheduled-tasks/recurring-payments

# Check triggers
doctl serverless triggers list
```

## Troubleshooting

### Function not executing?

```bash
# Check triggers exist
doctl serverless triggers list

# Redeploy
doctl serverless deploy .
```

### Database connection errors?

```bash
# Verify environment variables
doctl serverless namespaces get echodesk
```

### Module not found?

```bash
# Rebuild dependencies
cd packages/scheduled-tasks/recurring-payments
./build.sh
cd ../../..
doctl serverless deploy .
```

## Cost

Both functions run once daily (~20 seconds each):
- **Monthly executions:** 60 (2 functions × 30 days)
- **Estimated cost:** $0.003/month (well within free tier)

## CI/CD

Functions auto-deploy on push to `main` if changes detected in `functions/**` directory.

See `.github/workflows/deploy-functions.yml` (if configured).
