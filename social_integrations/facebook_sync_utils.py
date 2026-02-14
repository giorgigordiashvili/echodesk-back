"""
Facebook & Instagram Chat History Sync Utilities

This module provides functions to sync historical messages from Facebook Messenger
and Instagram DMs using the Graph API conversations endpoint.

API Endpoints used:
- GET /{account-id}/conversations - list conversations
- GET /{conversation-id}/messages - get messages for a conversation
"""

import logging
import requests
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.db import IntegrityError

from .models import (
    FacebookPageConnection,
    FacebookMessage,
    InstagramAccountConnection,
    InstagramMessage,
)

logger = logging.getLogger(__name__)

# Constants
GRAPH_API_VERSION = 'v23.0'
GRAPH_API_BASE_URL = f'https://graph.facebook.com/{GRAPH_API_VERSION}'
MAX_CONVERSATIONS_DEFAULT = 100
MAX_MESSAGES_PER_CONVERSATION = 500


class SyncError(Exception):
    """Base exception for sync errors"""
    pass


class TokenExpiredError(SyncError):
    """Raised when access token has expired"""
    pass


class RateLimitError(SyncError):
    """Raised when rate limited by Facebook API"""
    pass


class PermissionDeniedError(SyncError):
    """Raised when permissions are insufficient"""
    pass


def handle_api_error(response_data, response_status):
    """
    Handle Facebook API error responses.

    Args:
        response_data: Parsed JSON response
        response_status: HTTP status code

    Raises:
        TokenExpiredError: If token is expired (error codes 190, 102)
        RateLimitError: If rate limited (error code 4)
        PermissionDeniedError: If permission denied (error code 10)
        SyncError: For other API errors
    """
    if 'error' not in response_data:
        return

    error = response_data['error']
    error_code = error.get('code')
    error_message = error.get('message', 'Unknown error')
    error_subcode = error.get('error_subcode')

    logger.error(f"Facebook API error: code={error_code}, subcode={error_subcode}, message={error_message}")

    # Token expired
    if error_code in [190, 102]:
        raise TokenExpiredError(f"Access token expired: {error_message}")

    # Rate limited
    if error_code == 4:
        raise RateLimitError(f"Rate limited by Facebook API: {error_message}")

    # Permission denied
    if error_code == 10:
        raise PermissionDeniedError(f"Permission denied: {error_message}")

    # Generic error
    raise SyncError(f"Facebook API error ({error_code}): {error_message}")


def fetch_conversations(access_token, account_id, platform='facebook', limit=25):
    """
    Fetch conversations for a Facebook page or Instagram account.

    Args:
        access_token: Page/account access token
        account_id: Page ID (Facebook) or Instagram Account ID
        platform: 'facebook' or 'instagram'
        limit: Number of conversations to fetch per page (max 25)

    Returns:
        Generator yielding conversation data dicts

    Raises:
        SyncError: On API errors
    """
    url = f"{GRAPH_API_BASE_URL}/{account_id}/conversations"

    params = {
        'access_token': access_token,
        'fields': 'participants,updated_time,id',
        'limit': min(limit, 25),  # Facebook API max is 25 per page
    }

    # For Instagram, we need to specify the platform
    if platform == 'instagram':
        params['platform'] = 'instagram'

    conversations_fetched = 0

    while url and conversations_fetched < MAX_CONVERSATIONS_DEFAULT:
        try:
            response = requests.get(url, params=params, timeout=30)
            response_data = response.json()

            if response.status_code != 200:
                handle_api_error(response_data, response.status_code)

            data = response_data.get('data', [])

            for conv in data:
                conversations_fetched += 1
                yield conv

                if conversations_fetched >= MAX_CONVERSATIONS_DEFAULT:
                    break

            # Check for pagination
            paging = response_data.get('paging', {})
            url = paging.get('next')
            params = {}  # Params are included in the next URL

        except requests.RequestException as e:
            logger.error(f"Network error fetching conversations: {e}")
            raise SyncError(f"Network error: {e}")


def fetch_conversation_messages(access_token, conversation_id, limit=100, since_timestamp=None):
    """
    Fetch messages for a specific conversation.

    Args:
        access_token: Page/account access token
        conversation_id: Conversation ID from conversations endpoint
        limit: Max messages to fetch per API call (max 100)
        since_timestamp: Only fetch messages after this timestamp (ISO format)

    Returns:
        Generator yielding message data dicts

    Raises:
        SyncError: On API errors
    """
    url = f"{GRAPH_API_BASE_URL}/{conversation_id}/messages"

    params = {
        'access_token': access_token,
        'fields': 'id,message,from,to,created_time,attachments',
        'limit': min(limit, 100),
    }

    # Filter by time if specified
    if since_timestamp:
        params['since'] = since_timestamp

    messages_fetched = 0

    while url and messages_fetched < MAX_MESSAGES_PER_CONVERSATION:
        try:
            response = requests.get(url, params=params, timeout=30)
            response_data = response.json()

            if response.status_code != 200:
                handle_api_error(response_data, response.status_code)

            data = response_data.get('data', [])

            for msg in data:
                messages_fetched += 1
                yield msg

                if messages_fetched >= MAX_MESSAGES_PER_CONVERSATION:
                    break

            # Check for pagination
            paging = response_data.get('paging', {})
            url = paging.get('next')
            params = {}  # Params are included in the next URL

        except requests.RequestException as e:
            logger.error(f"Network error fetching messages: {e}")
            raise SyncError(f"Network error: {e}")


def fetch_sender_profile(access_token, sender_id, platform='facebook'):
    """
    Fetch profile information for a message sender.

    Args:
        access_token: Page/account access token
        sender_id: PSID (Facebook) or IGSID (Instagram)
        platform: 'facebook' or 'instagram'

    Returns:
        Dict with name, profile_pic_url, username (for Instagram)
    """
    try:
        if platform == 'facebook':
            # For Facebook, try to get name from message object
            url = f"{GRAPH_API_BASE_URL}/{sender_id}"
            params = {
                'access_token': access_token,
                'fields': 'name',
            }
        else:
            # For Instagram, can only get name and username
            url = f"{GRAPH_API_BASE_URL}/{sender_id}"
            params = {
                'access_token': access_token,
                'fields': 'name,username',
            }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            result = {
                'name': data.get('name', ''),
                'username': data.get('username', ''),
            }

            # Try to get profile picture for Facebook
            if platform == 'facebook':
                try:
                    pic_url = f"{GRAPH_API_BASE_URL}/{sender_id}/picture"
                    pic_params = {
                        'type': 'large',
                        'redirect': 'false',
                        'access_token': access_token,
                    }
                    pic_response = requests.get(pic_url, params=pic_params, timeout=10)
                    if pic_response.status_code == 200:
                        pic_data = pic_response.json()
                        if pic_data.get('data', {}).get('url'):
                            result['profile_pic_url'] = pic_data['data']['url']
                except Exception:
                    pass

            return result

        return {'name': '', 'username': '', 'profile_pic_url': None}

    except Exception as e:
        logger.warning(f"Error fetching sender profile for {sender_id}: {e}")
        return {'name': '', 'username': '', 'profile_pic_url': None}


def save_facebook_message(page_connection, message_data, page_id):
    """
    Save a Facebook message to the database.

    Args:
        page_connection: FacebookPageConnection instance
        message_data: Message data from Graph API
        page_id: The Facebook page ID

    Returns:
        Tuple of (message, created) - the message object and whether it was created
    """
    message_id = message_data.get('id')

    if not message_id:
        logger.warning("Message has no ID, skipping")
        return None, False

    # Check if message already exists
    existing = FacebookMessage.objects.filter(message_id=message_id).first()
    if existing:
        return existing, False

    # Parse message data
    sender = message_data.get('from', {})
    sender_id = sender.get('id', '')
    sender_name = sender.get('name', '')

    # Determine if message is from the page
    is_from_page = (sender_id == page_id)

    # Parse timestamp
    created_time = message_data.get('created_time')
    if created_time:
        try:
            timestamp = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
        except ValueError:
            timestamp = timezone.now()
    else:
        timestamp = timezone.now()

    # Parse attachments
    attachments = []
    attachment_type = ''
    attachment_url = None
    raw_attachments = message_data.get('attachments', {}).get('data', [])

    for att in raw_attachments:
        att_type = att.get('type', 'file')
        att_url = att.get('url') or att.get('file_url')

        attachments.append({
            'type': att_type,
            'url': att_url,
            'name': att.get('name', ''),
        })

        if not attachment_type and att_type:
            # Map Facebook types to our types
            type_mapping = {
                'image': 'image',
                'video': 'video',
                'audio': 'audio',
                'file': 'file',
                'location': 'location',
                'fallback': 'fallback',
            }
            attachment_type = type_mapping.get(att_type, 'file')
            attachment_url = att_url

    # Get profile info if not from page
    profile_pic_url = None
    if not is_from_page and sender_id:
        try:
            profile_info = fetch_sender_profile(
                page_connection.page_access_token,
                sender_id,
                'facebook'
            )
            if not sender_name:
                sender_name = profile_info.get('name', '')
            profile_pic_url = profile_info.get('profile_pic_url')
        except Exception as e:
            logger.warning(f"Error fetching profile for {sender_id}: {e}")

    try:
        message = FacebookMessage.objects.create(
            page_connection=page_connection,
            message_id=message_id,
            sender_id=sender_id,
            sender_name=sender_name,
            profile_pic_url=profile_pic_url,
            message_text=message_data.get('message', ''),
            attachment_type=attachment_type,
            attachment_url=attachment_url,
            attachments=attachments,
            timestamp=timestamp,
            is_from_page=is_from_page,
            is_delivered=True,  # Historical messages were delivered
            is_read=True,  # Historical messages were read
            is_read_by_staff=is_from_page,  # Outgoing messages are "read"
        )
        return message, True

    except IntegrityError:
        # Race condition - message was created by another process
        existing = FacebookMessage.objects.filter(message_id=message_id).first()
        return existing, False


def save_instagram_message(account_connection, message_data, account_id):
    """
    Save an Instagram message to the database.

    Args:
        account_connection: InstagramAccountConnection instance
        message_data: Message data from Graph API
        account_id: The Instagram account ID

    Returns:
        Tuple of (message, created) - the message object and whether it was created
    """
    message_id = message_data.get('id')

    if not message_id:
        logger.warning("Message has no ID, skipping")
        return None, False

    # Check if message already exists
    existing = InstagramMessage.objects.filter(message_id=message_id).first()
    if existing:
        return existing, False

    # Parse message data
    sender = message_data.get('from', {})
    sender_id = sender.get('id', '')
    sender_name = sender.get('name', '')

    # Determine if message is from the business
    is_from_business = (sender_id == account_id)

    # Parse timestamp
    created_time = message_data.get('created_time')
    if created_time:
        try:
            timestamp = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
        except ValueError:
            timestamp = timezone.now()
    else:
        timestamp = timezone.now()

    # Parse attachments
    attachments = []
    attachment_type = ''
    attachment_url = None
    raw_attachments = message_data.get('attachments', {}).get('data', [])

    for att in raw_attachments:
        att_type = att.get('type', 'file')
        att_url = att.get('url') or att.get('file_url')

        attachments.append({
            'type': att_type,
            'url': att_url,
            'name': att.get('name', ''),
        })

        if not attachment_type and att_type:
            # Map Instagram types to our types
            type_mapping = {
                'image': 'image',
                'video': 'video',
                'audio': 'audio',
                'file': 'file',
                'share': 'share',
                'story_mention': 'story_mention',
                'story_reply': 'story_reply',
            }
            attachment_type = type_mapping.get(att_type, 'file')
            attachment_url = att_url

    # Get profile info if not from business
    sender_username = ''
    sender_profile_pic = None
    if not is_from_business and sender_id:
        try:
            profile_info = fetch_sender_profile(
                account_connection.access_token,
                sender_id,
                'instagram'
            )
            if not sender_name:
                sender_name = profile_info.get('name', '')
            sender_username = profile_info.get('username', '')
        except Exception as e:
            logger.warning(f"Error fetching Instagram profile for {sender_id}: {e}")

    try:
        message = InstagramMessage.objects.create(
            account_connection=account_connection,
            message_id=message_id,
            sender_id=sender_id,
            sender_name=sender_name,
            sender_username=sender_username,
            sender_profile_pic=sender_profile_pic,
            message_text=message_data.get('message', ''),
            attachment_type=attachment_type,
            attachment_url=attachment_url,
            attachments=attachments,
            timestamp=timestamp,
            is_from_business=is_from_business,
            is_delivered=True,  # Historical messages were delivered
            is_read=True,  # Historical messages were read
            is_read_by_staff=is_from_business,  # Outgoing messages are "read"
        )
        return message, True

    except IntegrityError:
        # Race condition - message was created by another process
        existing = InstagramMessage.objects.filter(message_id=message_id).first()
        return existing, False


def sync_facebook_conversations(page_connection, max_conversations=100, force=False):
    """
    Sync Facebook Messenger conversations for a page.

    Args:
        page_connection: FacebookPageConnection instance
        max_conversations: Maximum number of conversations to sync
        force: Force resync even if already completed

    Returns:
        Dict with sync results:
            - conversations_synced: int
            - messages_synced: int
            - errors: list of error messages
    """
    result = {
        'conversations_synced': 0,
        'messages_synced': 0,
        'errors': [],
    }

    if not page_connection.is_active:
        result['errors'].append('Page connection is not active')
        return result

    # Skip if already synced (unless forced)
    if page_connection.sync_status == 'completed' and not force:
        logger.info(f"Page {page_connection.page_name} already synced, skipping")
        return result

    # Calculate since timestamp based on sync_days_back
    since_date = timezone.now() - timedelta(days=page_connection.sync_days_back)
    since_timestamp = since_date.isoformat()

    # Update status to syncing
    page_connection.sync_status = 'syncing'
    page_connection.last_sync_error = ''
    page_connection.save(update_fields=['sync_status', 'last_sync_error'])

    try:
        logger.info(f"Starting Facebook sync for page {page_connection.page_name}")

        # Fetch conversations
        for conv in fetch_conversations(
            page_connection.page_access_token,
            page_connection.page_id,
            platform='facebook',
            limit=25
        ):
            if result['conversations_synced'] >= max_conversations:
                break

            conversation_id = conv.get('id')
            if not conversation_id:
                continue

            try:
                # Fetch messages for this conversation
                messages_in_conv = 0
                for msg in fetch_conversation_messages(
                    page_connection.page_access_token,
                    conversation_id,
                    limit=100,
                    since_timestamp=since_timestamp
                ):
                    message_obj, created = save_facebook_message(
                        page_connection,
                        msg,
                        page_connection.page_id
                    )

                    if created:
                        result['messages_synced'] += 1
                        messages_in_conv += 1

                result['conversations_synced'] += 1
                logger.debug(f"Synced {messages_in_conv} messages from conversation {conversation_id}")

            except SyncError as e:
                error_msg = f"Error syncing conversation {conversation_id}: {e}"
                logger.error(error_msg)
                result['errors'].append(error_msg)

        # Update connection with results
        page_connection.sync_status = 'completed'
        page_connection.last_sync_at = timezone.now()
        page_connection.conversations_synced = result['conversations_synced']
        page_connection.messages_synced = result['messages_synced']
        page_connection.last_sync_error = '\n'.join(result['errors'][:10]) if result['errors'] else ''
        page_connection.save(update_fields=[
            'sync_status', 'last_sync_at', 'conversations_synced',
            'messages_synced', 'last_sync_error'
        ])

        logger.info(
            f"Facebook sync completed for {page_connection.page_name}: "
            f"{result['conversations_synced']} conversations, {result['messages_synced']} messages"
        )

    except TokenExpiredError as e:
        page_connection.sync_status = 'failed'
        page_connection.last_sync_error = str(e)
        page_connection.is_active = False
        page_connection.deactivated_at = timezone.now()
        page_connection.deactivation_reason = 'token_expired'
        page_connection.save(update_fields=[
            'sync_status', 'last_sync_error', 'is_active',
            'deactivated_at', 'deactivation_reason'
        ])
        result['errors'].append(str(e))

    except SyncError as e:
        page_connection.sync_status = 'failed'
        page_connection.last_sync_error = str(e)
        page_connection.save(update_fields=['sync_status', 'last_sync_error'])
        result['errors'].append(str(e))

    except Exception as e:
        logger.exception(f"Unexpected error syncing Facebook page {page_connection.page_id}")
        page_connection.sync_status = 'failed'
        page_connection.last_sync_error = str(e)
        page_connection.save(update_fields=['sync_status', 'last_sync_error'])
        result['errors'].append(str(e))

    return result


def sync_instagram_conversations(account_connection, max_conversations=100, force=False):
    """
    Sync Instagram DM conversations for an account.

    Args:
        account_connection: InstagramAccountConnection instance
        max_conversations: Maximum number of conversations to sync
        force: Force resync even if already completed

    Returns:
        Dict with sync results:
            - conversations_synced: int
            - messages_synced: int
            - errors: list of error messages
    """
    result = {
        'conversations_synced': 0,
        'messages_synced': 0,
        'errors': [],
    }

    if not account_connection.is_active:
        result['errors'].append('Instagram account is not active')
        return result

    # Skip if already synced (unless forced)
    if account_connection.sync_status == 'completed' and not force:
        logger.info(f"Instagram @{account_connection.username} already synced, skipping")
        return result

    # Calculate since timestamp based on sync_days_back
    since_date = timezone.now() - timedelta(days=account_connection.sync_days_back)
    since_timestamp = since_date.isoformat()

    # Update status to syncing
    account_connection.sync_status = 'syncing'
    account_connection.last_sync_error = ''
    account_connection.save(update_fields=['sync_status', 'last_sync_error'])

    try:
        logger.info(f"Starting Instagram sync for @{account_connection.username}")

        # Fetch conversations
        for conv in fetch_conversations(
            account_connection.access_token,
            account_connection.instagram_account_id,
            platform='instagram',
            limit=25
        ):
            if result['conversations_synced'] >= max_conversations:
                break

            conversation_id = conv.get('id')
            if not conversation_id:
                continue

            try:
                # Fetch messages for this conversation
                messages_in_conv = 0
                for msg in fetch_conversation_messages(
                    account_connection.access_token,
                    conversation_id,
                    limit=100,
                    since_timestamp=since_timestamp
                ):
                    message_obj, created = save_instagram_message(
                        account_connection,
                        msg,
                        account_connection.instagram_account_id
                    )

                    if created:
                        result['messages_synced'] += 1
                        messages_in_conv += 1

                result['conversations_synced'] += 1
                logger.debug(f"Synced {messages_in_conv} messages from Instagram conversation {conversation_id}")

            except SyncError as e:
                error_msg = f"Error syncing Instagram conversation {conversation_id}: {e}"
                logger.error(error_msg)
                result['errors'].append(error_msg)

        # Update connection with results
        account_connection.sync_status = 'completed'
        account_connection.last_sync_at = timezone.now()
        account_connection.conversations_synced = result['conversations_synced']
        account_connection.messages_synced = result['messages_synced']
        account_connection.last_sync_error = '\n'.join(result['errors'][:10]) if result['errors'] else ''
        account_connection.save(update_fields=[
            'sync_status', 'last_sync_at', 'conversations_synced',
            'messages_synced', 'last_sync_error'
        ])

        logger.info(
            f"Instagram sync completed for @{account_connection.username}: "
            f"{result['conversations_synced']} conversations, {result['messages_synced']} messages"
        )

    except TokenExpiredError as e:
        account_connection.sync_status = 'failed'
        account_connection.last_sync_error = str(e)
        account_connection.is_active = False
        account_connection.save(update_fields=['sync_status', 'last_sync_error', 'is_active'])
        result['errors'].append(str(e))

    except SyncError as e:
        account_connection.sync_status = 'failed'
        account_connection.last_sync_error = str(e)
        account_connection.save(update_fields=['sync_status', 'last_sync_error'])
        result['errors'].append(str(e))

    except Exception as e:
        logger.exception(f"Unexpected error syncing Instagram @{account_connection.username}")
        account_connection.sync_status = 'failed'
        account_connection.last_sync_error = str(e)
        account_connection.save(update_fields=['sync_status', 'last_sync_error'])
        result['errors'].append(str(e))

    return result


def sync_all_facebook_pages(tenant_schema=None, pending_only=False, force=False):
    """
    Sync messages for all active Facebook pages.

    Args:
        tenant_schema: Optional schema name to limit sync to single tenant
        pending_only: Only sync pages with 'pending' status
        force: Force resync even if already completed

    Returns:
        Dict with total results across all pages
    """
    from django_tenants.utils import schema_context, get_tenant_model

    total_results = {
        'pages_synced': 0,
        'conversations_synced': 0,
        'messages_synced': 0,
        'errors': [],
    }

    TenantModel = get_tenant_model()

    if tenant_schema:
        tenants = TenantModel.objects.filter(schema_name=tenant_schema)
    else:
        tenants = TenantModel.objects.exclude(schema_name='public')

    for tenant in tenants:
        with schema_context(tenant.schema_name):
            pages = FacebookPageConnection.objects.filter(is_active=True)

            if pending_only:
                pages = pages.filter(sync_status='pending')

            for page in pages:
                try:
                    result = sync_facebook_conversations(page, force=force)
                    total_results['pages_synced'] += 1
                    total_results['conversations_synced'] += result['conversations_synced']
                    total_results['messages_synced'] += result['messages_synced']
                    total_results['errors'].extend(result['errors'])
                except Exception as e:
                    error_msg = f"Error syncing page {page.page_name} in {tenant.schema_name}: {e}"
                    logger.error(error_msg)
                    total_results['errors'].append(error_msg)

    return total_results


def sync_all_instagram_accounts(tenant_schema=None, pending_only=False, force=False):
    """
    Sync messages for all active Instagram accounts.

    Args:
        tenant_schema: Optional schema name to limit sync to single tenant
        pending_only: Only sync accounts with 'pending' status
        force: Force resync even if already completed

    Returns:
        Dict with total results across all accounts
    """
    from django_tenants.utils import schema_context, get_tenant_model

    total_results = {
        'accounts_synced': 0,
        'conversations_synced': 0,
        'messages_synced': 0,
        'errors': [],
    }

    TenantModel = get_tenant_model()

    if tenant_schema:
        tenants = TenantModel.objects.filter(schema_name=tenant_schema)
    else:
        tenants = TenantModel.objects.exclude(schema_name='public')

    for tenant in tenants:
        with schema_context(tenant.schema_name):
            accounts = InstagramAccountConnection.objects.filter(is_active=True)

            if pending_only:
                accounts = accounts.filter(sync_status='pending')

            for account in accounts:
                try:
                    result = sync_instagram_conversations(account, force=force)
                    total_results['accounts_synced'] += 1
                    total_results['conversations_synced'] += result['conversations_synced']
                    total_results['messages_synced'] += result['messages_synced']
                    total_results['errors'].extend(result['errors'])
                except Exception as e:
                    error_msg = f"Error syncing @{account.username} in {tenant.schema_name}: {e}"
                    logger.error(error_msg)
                    total_results['errors'].append(error_msg)

    return total_results
