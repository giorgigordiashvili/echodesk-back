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
   FACEBOOK_APP_VERSION=v23.0
   FACEBOOK_WEBHOOK_VERIFY_TOKEN=echodesk_webhook_token_2024
   ```

## Step 4: Configure Permissions

1. **App Review > Permissions and Features**
   - Request these essential permissions:
     - `business_management` - **CRITICAL** - To access Pages and Business assets
     - `pages_messaging` - To read and send messages
     - `pages_show_list` - To access list of pages
     - `pages_read_engagement` - To read page posts and comments
     - `pages_manage_metadata` - To access page metadata
     - `public_profile` - Basic profile information
     - `email` - Email address

2. **For Development/Testing**
   - You can test with your own pages without app review
   - Add test users in App Roles > Test Users
   - **Important**: Add your Facebook account as Admin/Developer in the app dashboard

## Step 5: Configure Webhooks (for Production)

1. **Go to Messenger > Settings**
   - Add Callback URL: `https://yourdomain.com/api/social/facebook/webhook/`
   - Verify Token: `echodesk_webhook_token_2024` (must match your .env)
   
2. **Subscribe to Webhook Fields (v23.0)**
   
   **Essential Fields for receiving and sending messages:**
   - `messages` - To receive incoming messages from users
   - `messaging_postbacks` - To handle button clicks and quick replies
   
   **Additional Recommended Fields:**
   - `message_deliveries` - To track message delivery status
   - `message_echoes` - To receive copies of messages sent by your page
   - `message_reads` - To know when users read your messages
   - `messaging_optins` - To handle users opting into messaging
   - `messaging_referrals` - To track how users discovered your page
   - `messaging_account_linking` - For account linking features

3. **Profile Picture Support**
   - Profile pictures are fetched automatically using the Graph API
   - Requires `pages_messaging` permission to access user profile data
   - User profile pictures are retrieved when processing incoming messages

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
- Requires app review for most permissions
- Business verification may be required

## Troubleshooting "No Pages Found"

If you get "No Facebook pages found for this account" error:

1. **Check App Roles**
   - Go to developers.facebook.com/apps/[your-app-id]/roles
   - Add your Facebook account as Admin, Developer, or Tester

2. **Verify business_management Permission**
   - Test API access: `GET /api/social/facebook/api/test/?access_token=YOUR_TOKEN`
   - Check if business_management permission is granted
   - Ensure your app requests business_management in OAuth

3. **Page Admin Rights**
   - You must be an admin of the Facebook page you want to connect
   - Go to facebook.com/[your-page-name]/settings and check admin list

4. **App Development Mode**
   - In Development Mode, only pages owned by app team members are accessible
   - Create a test page or add team members who own pages

5. **Debug Steps**
   - Test OAuth: `GET /api/social/facebook/oauth/start/`
   - Test callback: Use Facebook's Access Token Debugger
   - Check API access: `GET /api/social/facebook/api/test/?access_token=TOKEN`

## Debug Commands

```bash
# Test Facebook integration
python manage.py tenant_command test_facebook_integration -s amanati

# Debug API access with your token
curl "https://api.echodesk.ge/api/social/facebook/api/test/?access_token=YOUR_TOKEN"
```
