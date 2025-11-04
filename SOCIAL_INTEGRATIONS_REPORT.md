# Echodesk Social Media Integration Report

## Executive Summary

The Echodesk project has a **Facebook integration** feature that is partially implemented and multi-tenant aware. It currently supports Facebook Page connections, messaging, and webhook callbacks. The system uses Django REST Framework for API endpoints and Django Channels for WebSocket support.

---

## 1. Database Models

### 1.1 FacebookPageConnection Model
**Location:** `/Users/giorgigordiashvili/Echodesk/echodesk-back/social_integrations/models.py`

```python
class FacebookPageConnection(models.Model):
    page_id = CharField(max_length=100, unique=True)
    page_name = CharField(max_length=200)
    page_access_token = TextField()
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

**Purpose:** Stores Facebook page connection details for a tenant
**Key Features:**
- Multi-tenant isolation via Django tenant schemas
- Stores page access tokens for API calls
- Enable/disable individual page connections

### 1.2 FacebookMessage Model
**Location:** `/Users/giorgigordiashvili/Echodesk/echodesk-back/social_integrations/models.py`

```python
class FacebookMessage(models.Model):
    page_connection = ForeignKey(FacebookPageConnection, on_delete=CASCADE)
    message_id = CharField(max_length=100, unique=True)
    sender_id = CharField(max_length=100)
    sender_name = CharField(max_length=200)
    profile_pic_url = URLField(max_length=500, blank=True, null=True)
    message_text = TextField()
    timestamp = DateTimeField()
    is_from_page = BooleanField(default=False)
    created_at = DateTimeField(auto_now_add=True)
```

**Purpose:** Stores incoming and outgoing Facebook messages
**Key Features:**
- Tracks both messages from users to page and page to users
- Stores user profile pictures
- Maintains message history with timestamps
- Orders messages by timestamp descending

---

## 2. API Endpoints

### 2.1 ViewSets (REST API)

#### FacebookPageConnectionViewSet
**Type:** ModelViewSet (CRUD operations)
**Permissions:** `IsAuthenticated`
**Base URL:** `/api/social/facebook-pages/`

**Methods:**
- `GET /facebook-pages/` - List all connected pages (for current tenant)
- `POST /facebook-pages/` - Create new page connection
- `GET /facebook-pages/{id}/` - Retrieve specific page
- `PUT /facebook-pages/{id}/` - Update page connection
- `DELETE /facebook-pages/{id}/` - Delete page connection

**Serializer:** `FacebookPageConnectionSerializer`

#### FacebookMessageViewSet
**Type:** ReadOnlyModelViewSet (List/Retrieve only)
**Permissions:** `IsAuthenticated`
**Base URL:** `/api/social/facebook-messages/`

**Methods:**
- `GET /facebook-messages/` - List messages for all pages (current tenant)
- `GET /facebook-messages/{id}/` - Retrieve specific message

**Serializer:** `FacebookMessageSerializer`

### 2.2 Function-Based Views

#### OAuth Flow

**1. facebook_oauth_start**
- **URL:** `GET /api/social/facebook/oauth/start/`
- **Permissions:** `IsAuthenticated`
- **Purpose:** Generate Facebook OAuth URL for user authorization
- **Returns:** OAuth URL with proper scopes and redirect_uri

**Scopes Requested:**
- `business_management` - Access to Pages and Business assets
- `pages_messaging` - Read and send messages on behalf of pages
- `pages_show_list` - Access list of pages
- `pages_read_engagement` - Read page posts and comments
- `pages_manage_metadata` - Access page metadata
- `public_profile` - Basic profile information
- `email` - Email address

**2. facebook_oauth_callback**
- **URL:** `GET /api/social/facebook/oauth/callback/`
- **Permissions:** `IsPublic` (no auth required - Facebook callback)
- **Purpose:** Handle Facebook OAuth callback, exchange code for token
- **Process:**
  1. Receives authorization code from Facebook
  2. Exchanges code for access token
  3. Fetches user's Facebook pages
  4. Stores page connections in tenant database
  5. Clears existing connections for tenant and saves new ones
  6. Redirects to frontend with success/error status
- **Multi-tenant:** Extracts tenant from state parameter

#### Connection Management

**3. facebook_connection_status**
- **URL:** `GET /api/social/facebook/status/`
- **Permissions:** `IsAuthenticated`
- **Returns:** List of connected pages with metadata

**4. facebook_disconnect**
- **URL:** `POST /api/social/facebook/disconnect/`
- **Permissions:** `IsAuthenticated`
- **Purpose:** Disconnect all Facebook pages for tenant
- **Deletes:**
  - All FacebookPageConnection records
  - All associated FacebookMessage records
- **Returns:** Deletion statistics

#### Messaging

**5. facebook_send_message**
- **URL:** `POST /api/social/facebook/send-message/`
- **Permissions:** `IsAuthenticated`
- **Request Body:**
  ```json
  {
    "recipient_id": "facebook_user_id",
    "message": "message text",
    "page_id": "facebook_page_id"
  }
  ```
- **Purpose:** Send message to Facebook user via Graph API
- **Response:** Message ID from Facebook or error

#### Webhooks

**6. facebook_webhook**
- **URL:** `GET|POST /api/social/facebook/webhook/`
- **Permissions:** `IsPublic` (csrf_exempt)
- **GET:** Facebook webhook verification
- **POST:** Handle incoming Facebook messages
- **Process:**
  1. Verifies webhook token
  2. Finds tenant by page_id
  3. Processes incoming messages
  4. Fetches sender profile data
  5. Saves messages to database
  6. Supports both standard and developer console test formats

#### Admin OAuth Endpoints

**7. facebook_oauth_admin_start**
- **URL:** `/api/social/admin/facebook/oauth/start/`
- **Permissions:** `@staff_member_required`, `@login_required`
- **Purpose:** Initiate OAuth from Django admin

**8. facebook_oauth_admin_callback**
- **URL:** `/api/social/admin/facebook/oauth/callback/`
- **Permissions:** `@staff_member_required`
- **Purpose:** Handle admin OAuth callback, create/update page connections

#### Debug/Test Endpoints

**9. facebook_debug_callback** (lines 967-993)
- Test endpoint for debugging

**10. webhook_test_endpoint** (lines 995-1026)
- Test webhook receipt

**11. debug_facebook_pages** (lines 1027-1078)
- Debug connected pages

**12. debug_database_status** (lines 1079-1126)
- Check database state

**13. test_facebook_api_access** (lines 1127-1239)
- Test Facebook API connectivity

**14. test_database_save** (lines 1240-1280)
- Test message saving

---

## 3. Serializers

**Location:** `/Users/giorgigordiashvili/Echodesk/echodesk-back/social_integrations/serializers.py`

### FacebookPageConnectionSerializer
```python
fields = ['id', 'page_id', 'page_name', 'is_active', 'created_at', 'updated_at']
read_only_fields = ['id', 'created_at', 'updated_at']
```

### FacebookMessageSerializer
```python
fields = [
    'id', 'message_id', 'sender_id', 'sender_name', 'profile_pic_url',
    'message_text', 'timestamp', 'is_from_page', 'page_name', 'created_at'
]
read_only_fields = ['id', 'created_at']
```

### FacebookSendMessageSerializer
```python
fields = [
    'recipient_id',    # Facebook user ID to send message to
    'message',         # Message text to send
    'page_id'          # Facebook page ID to send from
]
```

---

## 4. WebSocket Support

**Location:** `/Users/giorgigordiashvili/Echodesk/echodesk-back/social_integrations/consumers.py`

### MessagesConsumer (AsyncWebsocketConsumer)
**WebSocket URL:** `ws://api.echodesk.ge/ws/messages/{tenant_schema}/`

**Features:**
- Real-time message notifications
- Conversation subscriptions
- Ping/pong for connection health
- Connection confirmation

**Events Handled:**
- `new_message` - New incoming/sent message
- `message_status_update` - Message status changes
- `conversation_update` - Conversation last message update

### TypingConsumer (AsyncWebsocketConsumer)
**WebSocket URL:** `ws://api.echodesk.ge/ws/typing/{tenant_schema}/{conversation_id}/`

**Features:**
- Typing indicators for conversations
- Requires authenticated users
- Broadcasts typing start/stop events
- Prevents echo of own typing status

---

## 5. Permissions and Access Control

### Current Permissions Model

**ViewSet Level:**
- `FacebookPageConnectionViewSet` - `IsAuthenticated`
- `FacebookMessageViewSet` - `IsAuthenticated`
- `facebook_oauth_start` - `IsAuthenticated`
- `facebook_connection_status` - `IsAuthenticated`
- `facebook_disconnect` - `IsAuthenticated`
- `facebook_send_message` - `IsAuthenticated`

**Public Endpoints (no auth required):**
- `facebook_oauth_callback` - Facebook's OAuth redirect (no auth)
- `facebook_webhook` - Incoming webhook from Facebook (csrf_exempt)
- All `/debug/` endpoints - No authentication

### User Model Permissions

**Location:** `/Users/giorgigordiashvili/Echodesk/echodesk-back/users/models.py`

User roles:
- `admin` - Administrator (full access)
- `manager` - Manager (elevated permissions)
- `agent` - Agent (limited permissions)
- `viewer` - Viewer (read-only)

User permission flags (not currently used for social integrations):
```python
can_manage_settings
can_manage_users
can_manage_groups
can_view_all_tickets
can_make_calls
# ... many more ticket/board specific permissions
```

**Groups (TenantGroup):**
- Feature-based access control via `TenantGroup.features`
- Can be used to control social media feature access
- Currently not integrated with social integrations app

---

## 6. Configuration

**Location:** `/Users/giorgigordiashvili/Echodesk/echodesk-back/amanati_crm/settings.py`

```python
SOCIAL_INTEGRATIONS = {
    'FACEBOOK_APP_ID': FACEBOOK_APP_ID,
    'FACEBOOK_APP_SECRET': FACEBOOK_APP_SECRET,
    'FACEBOOK_API_VERSION': FACEBOOK_APP_VERSION,  # v23.0
    'FACEBOOK_VERIFY_TOKEN': config('FACEBOOK_WEBHOOK_VERIFY_TOKEN', 
                                   default='echodesk_webhook_token_2024'),
    'FACEBOOK_SCOPES': [
        'business_management',
        'pages_messaging',
        'pages_show_list',
        'pages_read_engagement',
        'pages_manage_metadata',
        'public_profile',
        'email',
    ],
}
```

---

## 7. Multi-Tenancy Implementation

**Key Functions:**

### find_tenant_by_page_id(page_id)
- Searches all tenant schemas for a Facebook page
- Uses `schema_context()` from tenant_schemas package
- Returns tenant schema name if found

### Schema Context Usage
- Tenant isolation via `schema_context(tenant_schema)`
- Data automatically scoped to tenant's database
- OAuth callback extracts tenant from state parameter

---

## 8. Supported Platforms

Currently **ONLY FACEBOOK** is implemented:
- ✅ Facebook Pages
- ✅ Facebook Messenger
- ❌ Instagram (mentioned in code but not implemented)
- ❌ WhatsApp (mentioned in management command `drop_instagram_whatsapp_tables.py`)

---

## 9. Existing Functionality

### Fully Implemented:
1. Facebook page OAuth connection (user and admin flows)
2. Multiple page management per tenant
3. Facebook message reception via webhooks
4. Message storage and retrieval
5. Sending messages to Facebook users
6. Webhook verification and event handling
7. User profile picture fetching
8. Multi-tenant isolation
9. WebSocket support for real-time updates
10. Admin interface for page management

### Partially Implemented:
1. WebSocket consumers (defined but WebSocket auth needs work)
2. Legal compliance pages (privacy policy, terms, data deletion callbacks)
3. Message status tracking (basic - only stored messages)

### Not Implemented:
1. Role-based access control for social features
2. Permission checks for specific actions
3. Instagram integration
4. WhatsApp integration
5. Conversation threading/grouping
6. User-level permissions for managing pages
7. Audit logging for social actions
8. Rate limiting for API calls
9. Message templates/quick replies
10. Automatic message categorization

---

## 10. What Needs to be Added for Complete Feature

### High Priority:
1. **Role-Based Access Control**
   - Add permissions for: `can_manage_social_integrations`, `can_send_messages`, `can_view_messages`
   - Integrate with User model's permission system
   - Add permission checks to ViewSets using custom permission classes

2. **User-Level Page Management**
   - Add User FK to FacebookPageConnection model
   - Allow admins to assign pages to specific users/teams
   - Filter pages by user permissions

3. **Conversation Model**
   - Group messages into conversations
   - Track conversation metadata (last message, status, assigned user)
   - Filter messages by conversation

4. **Custom Permission Classes**
   - `HasSocialIntegrationPermission` - Check if user can manage integrations
   - `HasPageAccessPermission` - Check if user can access specific page
   - `HasConversationAccessPermission` - Check if user can view conversation

5. **API Improvements**
   - Add filtering/searching for messages
   - Add pagination for large message sets
   - Add sorting options
   - Include conversation endpoints

6. **Audit Logging**
   - Log all connection/disconnection events
   - Log message send/receive events
   - Track user actions on social integrations

### Medium Priority:
1. **WebSocket Authentication**
   - Currently allows anonymous connections (TODO in code)
   - Implement proper token-based auth

2. **Rate Limiting**
   - Prevent message flooding
   - API rate limiting per user/page

3. **Enhanced Error Handling**
   - Better error messages for Facebook API failures
   - Graceful handling of revoked tokens

4. **Message Status Tracking**
   - Delivery status (sent, delivered, read)
   - Read receipts

5. **Admin Interface**
   - Better page management UI
   - Message filtering and search
   - User assignment interface

### Low Priority:
1. **Features**
   - Message templates
   - Quick replies
   - Auto-responders
   - Message scheduling
   - Integration with tickets/conversations
   - CRM linking

2. **Analytics**
   - Message volume per page
   - Response times
   - User engagement metrics

3. **Additional Platforms**
   - Instagram Business Account support
   - WhatsApp Business API
   - Twitter/X API
   - LinkedIn Page messaging

---

## 11. File Structure Summary

```
social_integrations/
├── __init__.py
├── apps.py
├── models.py                    # FacebookPageConnection, FacebookMessage
├── serializers.py               # API serializers
├── views.py (1280 lines)        # Main views, OAuth, webhooks
├── admin_views.py               # Admin OAuth flows
├── admin.py                     # Django admin customization
├── consumers.py                 # WebSocket consumers
├── routing.py                   # WebSocket routing
├── urls.py                      # URL routing
├── legal_views.py               # Privacy/terms/data deletion
├── migrations/
│   └── 0001_initial.py          # Initial schema
├── migrations_backup/           # Backup migrations
└── management/commands/
    ├── test_facebook_integration.py
    └── drop_instagram_whatsapp_tables.py
```

---

## 12. Security Considerations

**Currently Implemented:**
- CSRF protection on non-webhook endpoints
- Webhook token verification
- Page access token storage (not exposed in API responses)
- Multi-tenant isolation via schemas

**Needs Implementation:**
- Role-based access control
- User permission checks
- Audit logging
- Rate limiting
- WebSocket authentication
- Token refresh mechanism for expired Facebook tokens
- Secure token storage considerations

---

## 13. Next Steps for Implementation

1. **Phase 1: Permissions Foundation**
   - Add permission fields to User model
   - Create custom permission classes
   - Implement permission checks in views

2. **Phase 2: Access Control**
   - Add User FK to FacebookPageConnection
   - Implement page-level permissions
   - Add conversation model and routing

3. **Phase 3: Conversation Threading**
   - Create Conversation model
   - Implement conversation grouping logic
   - Add conversation endpoints

4. **Phase 4: Enhanced Features**
   - WebSocket authentication
   - Audit logging
   - Rate limiting
   - Message status tracking

---

## Conclusion

The Echodesk social integrations app has a solid foundation with Facebook integration working well. The multi-tenant architecture is properly implemented, and the basic CRUD operations are functional. The main gaps are:

1. **Permission/Access Control** - No role-based restrictions currently enforced
2. **User Assignment** - No way to assign pages or conversations to users
3. **Conversation Grouping** - Messages aren't grouped into conversations
4. **WebSocket Auth** - WebSocket endpoints need proper authentication
5. **Audit Trail** - No logging of user actions

These additions would transform it from a basic messaging storage system into a complete social media management platform with proper multi-user, multi-page support and access control.
