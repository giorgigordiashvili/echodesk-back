# Facebook App Setup Guide for EchoDesk

## Step 1: Create a Facebook App

1. **Go to Facebook Developers Console**
   - Visit: https://developers.facebook.com/
   - Login with your Facebook account

2. **Create New App**
   - Click "Create App"
   - Choose "Business" as the app type
   - Fill in app details:
     - App Name: `EchoDesk Integration` (or your preferred name)
     - App Contact Email: Your email
     - Business Account: Select your business account (or create one)

## Step 2: Configure App for Page Messaging

1. **Add Facebook Login Product**
   - In your app dashboard, click "Add Product"
   - Find "Facebook Login" and click "Set Up"

2. **Configure Facebook Login Settings**
   - Go to Facebook Login > Settings
   - Add Valid OAuth Redirect URIs:
     ```
     http://localhost:8000/api/social/facebook/oauth/callback/
     https://yourdomain.com/api/social/facebook/oauth/callback/
     ```

3. **Add Messenger Product**
   - Click "Add Product" again
   - Find "Messenger" and click "Set Up"
   - This allows your app to receive messages from Facebook pages

## Step 3: Get App Credentials

1. **Get App ID and Secret**
   - Go to App Dashboard > Settings > Basic
   - Copy the "App ID" - this is your `FACEBOOK_APP_ID`
   - Click "Show" next to "App Secret" - this is your `FACEBOOK_APP_SECRET`

2. **Update your .env file**
   ```bash
   FACEBOOK_APP_ID=your-actual-app-id-here
   FACEBOOK_APP_SECRET=your-actual-app-secret-here
   FACEBOOK_APP_VERSION=v18.0
   FACEBOOK_WEBHOOK_VERIFY_TOKEN=echodesk_webhook_token_2024
   ```

## Step 4: Configure Permissions

1. **App Review > Permissions and Features**
   - Request these permissions:
     - `pages_messaging` - To read and send messages
     - `pages_show_list` - To access list of pages
     - `pages_read_engagement` - To read page posts and comments
     - `pages_manage_metadata` - To access page metadata

2. **For Development/Testing**
   - You can test with your own pages without app review
   - Add test users in App Roles > Test Users

## Step 5: Configure Webhooks (for Production)

1. **Go to Messenger > Settings**
   - Add Callback URL: `https://yourdomain.com/api/social/facebook/webhook/`
   - Verify Token: `echodesk_webhook_token_2024` (must match your .env)
   - Subscribe to: `messages`, `messaging_postbacks`

## Step 6: Test Integration

After updating your .env file with real credentials, test the integration:

```bash
cd /path/to/echodesk-back
python manage.py tenant_command test_facebook_integration -s amanati
```

## Security Notes

- **Never commit real credentials to Git**
- **Use different credentials for development and production**
- **Regularly rotate your App Secret**
- **Enable Two-Factor Authentication on your Facebook account**

## Troubleshooting

- **Invalid OAuth redirect URI**: Make sure the callback URL in Facebook app matches your server
- **App not approved**: Some permissions require Facebook app review for production use
- **Webhook verification failed**: Ensure verify token matches between Facebook and your .env file

## Development vs Production

**Development:**
- Use localhost URLs in Facebook app settings
- Can test with your own pages immediately
- No app review needed for basic testing

**Production:**
- Use HTTPS URLs only
- Submit app for review for advanced permissions
- Configure proper webhook endpoints
