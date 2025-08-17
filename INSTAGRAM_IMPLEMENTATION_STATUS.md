# Instagram Messaging Integration - Implementation Guide

## Current Status
✅ **Backend API Updated** - All API calls now use v23.0
✅ **Frontend Component Created** - UnifiedMessagesManagement.tsx with Instagram + Facebook support
✅ **Database Schema Fixed** - Instagram message_id field supports longer IDs
✅ **Webhook Processing Fixed** - Now handles both 'changes' and 'messaging' webhook formats

## Key Changes Made

### 1. Backend Updates (`social_integrations/views.py`)
- Updated Instagram send message API to use Facebook Page tokens
- Added better error handling with troubleshooting information
- All API versions updated to v23.0
- Added Instagram message filtering by account_id and conversation_id

### 2. Frontend Updates
- Created `UnifiedMessagesManagement.tsx` with unified inbox
- Shows both Facebook and Instagram messages in one interface
- Platform filtering (All, Facebook, Instagram)
- Real-time auto-refresh every 5 seconds
- Supports sending messages to both platforms

### 3. Database Schema
- Increased `InstagramMessage.message_id` field from 100 to 255 characters
- Applied migration to all tenant schemas

## Meta Developers Console Requirements

### Required App Configuration:
1. **App Type**: Business (not Consumer)
2. **Products**: Add "Instagram" product
3. **Permissions Needed**:
   - `instagram_manage_messages` ⚠️ **Requires App Review**
   - `pages_messaging`
   - `pages_manage_metadata`

### Instagram Business Account Requirements:
- Must be an Instagram **Business Account** (not personal)
- Must be connected to a **Facebook Page**
- The Facebook Page must be verified and published

### App Review Process:
The `instagram_manage_messages` permission requires Meta's approval. You need to:
1. Go to App Review → Permissions and Features
2. Request `instagram_manage_messages`
3. Provide detailed use case description
4. Submit for review (can take 3-7 business days)

## Testing & Troubleshooting

### For Testing Before App Review:
1. Add test Instagram accounts in **Roles** → **Test Users**
2. Connect those accounts to your app
3. Test messaging with test users only

### Common Issues & Solutions:

#### Error: "Application does not have the capability to make this API call"
**Cause**: Missing `instagram_manage_messages` permission
**Solution**: Submit app for review with this permission

#### Error: "Invalid access token"
**Cause**: Instagram account not properly connected to Facebook Page
**Solution**: Re-connect Instagram account through Facebook Business Manager

#### Error: "User not found" or messaging fails
**Cause**: Trying to message users not connected to your app
**Solution**: Only message users who have interacted with your Instagram account first

### Testing Script:
Run the integration test:
```bash
python test_instagram_integration.py
```

## API Endpoints Available

### Instagram Messages:
- `GET /api/social/instagram-messages/` - List messages (with filtering)
- `POST /api/social/instagram/send-message/` - Send message

### Instagram Accounts:
- `GET /api/social/instagram-accounts/` - List connected accounts
- `GET /api/social/instagram/status/` - Connection status

### Unified Messages (Frontend):
- Access via Dashboard → Messages section
- Shows when Facebook OR Instagram is connected
- Unified inbox with platform indicators

## Next Steps

### Immediate Actions Required:
1. **Submit App for Review** in Meta Developers Console
2. **Request `instagram_manage_messages` permission**
3. **Add test users** for immediate testing

### Optional Improvements:
1. Add proper Instagram-to-Facebook page mapping
2. Implement read receipts for Instagram
3. Add support for Instagram media messages
4. Add conversation archiving/management

### Production Readiness:
1. ✅ Database schema ready
2. ✅ API endpoints ready
3. ✅ Frontend interface ready
4. ⚠️ **Pending**: Meta app review approval
5. ✅ Error handling and logging implemented

## Configuration Summary

Your current app configuration:
- **Instagram App ID**: `1447634119998674`
- **API Version**: `v23.0` (updated)
- **Webhook Token**: `echodesk_instagram_webhook_token_2024`
- **Redirect URI**: `https://api.echodesk.ge/api/social/instagram/oauth/callback/`

The integration is **technically ready** but requires Meta's approval for production messaging.
