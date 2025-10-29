# SendGrid Email Setup for EchoDesk

## Current Issue: 403 Forbidden Error

The SendGrid API is returning a 403 Forbidden error when trying to send emails. This is because the sender email address needs to be verified in SendGrid.

## How to Fix

### Option 1: Verify Domain (Recommended for Production)

1. Go to [SendGrid Sender Authentication](https://app.sendgrid.com/settings/sender_auth)
2. Click "Verify a Domain"
3. Add your domain: `echodesk.ge`
4. Follow the DNS configuration steps provided by SendGrid
5. Wait for verification (can take up to 48 hours)

Once verified, you can send from any email address on that domain (e.g., `noreply@echodesk.ge`)

### Option 2: Single Sender Verification (Quick for Testing)

1. Go to [SendGrid Sender Authentication](https://app.sendgrid.com/settings/sender_auth)
2. Click "Verify a Single Sender"
3. Fill out the form with sender details:
   - **From Name**: EchoDesk
   - **From Email Address**: Use an email you have access to (e.g., your Gmail)
   - **Reply To**: Same as from email
   - **Company Address**: Your company address
4. Click "Create"
5. Check your email and click the verification link
6. Update `.env` file:
   ```bash
   SENDGRID_FROM_EMAIL=your-verified-email@gmail.com
   SENDGRID_FROM_NAME=EchoDesk
   ```

### Option 3: Check API Key Permissions

1. Go to [SendGrid API Keys](https://app.sendgrid.com/settings/api_keys)
2. Find your API key (starts with `SG.`)
3. Make sure it has **"Mail Send"** permission:
   - Either **Full Access**
   - Or **Restricted Access** with "Mail Send" enabled
4. If not, create a new API key with proper permissions:
   - Click "Create API Key"
   - Choose "Restricted Access"
   - Enable "Mail Send" permission
   - Copy the API key
   - Update `.env`:
     ```bash
     SENDGRID_API_KEY=your-new-api-key
     ```

## Environment Variables

Add these to your `.env` file:

```bash
# SendGrid Configuration
SENDGRID_API_KEY=your-api-key-here
SENDGRID_FROM_EMAIL=noreply@echodesk.ge  # Must be verified!
SENDGRID_FROM_NAME=EchoDesk
```

## Testing Email Sending

After setup, test by creating a new user in the system. Check the logs for:

```
✅ Email sent successfully to user@example.com
```

Or error messages that will guide you to the solution.

## Important Notes

- **Domain Verification is best for production** - allows sending from any email on your domain
- **Single Sender is quick for testing** - but only works for that specific email address
- **API Key must have Mail Send permission** - check this if you get 403 errors
- User creation will still work even if email fails - users just won't receive their password via email

## Current Configuration

- From Email: `noreply@echodesk.ge` (default)
- From Name: `EchoDesk` (default)
- API Key: Set in `.env`

## What Emails Are Sent

1. **Tenant Creation Email**: Sent when a new tenant is created (welcome email with login details)
2. **User Invitation Email**: Sent when admin creates a new user (includes temporary password)
3. **Password Reset Email**: Sent when user requests password reset (future feature)
