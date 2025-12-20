"""
TikTok API Utilities for OAuth and Messaging

TikTok API Documentation:
- OAuth: https://developers.tiktok.com/doc/login-kit-web
- Messaging: https://developers.tiktok.com/doc/direct-message-api

Key Constraints:
- 48-hour messaging window after user initiates
- Max 10 consecutive messages per window
- 10 QPS rate limit
- Not available in US/EEA/UK/Switzerland
"""

import hmac
import hashlib
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from django.conf import settings

logger = logging.getLogger(__name__)

# TikTok API URLs
TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_REVOKE_URL = "https://open.tiktokapis.com/v2/oauth/revoke/"
TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


def get_tiktok_config() -> Dict[str, str]:
    """Get TikTok configuration from settings"""
    social_settings = getattr(settings, 'SOCIAL_INTEGRATIONS', {})
    return {
        'client_id': social_settings.get('TIKTOK_CLIENT_ID', ''),
        'client_secret': social_settings.get('TIKTOK_CLIENT_SECRET', ''),
        'redirect_uri': social_settings.get('TIKTOK_REDIRECT_URI', ''),
        'webhook_secret': social_settings.get('TIKTOK_WEBHOOK_SECRET', ''),
    }


def get_oauth_url(state: str) -> str:
    """
    Generate TikTok OAuth authorization URL

    Args:
        state: State parameter for CSRF protection (include tenant info)

    Returns:
        Full OAuth authorization URL
    """
    config = get_tiktok_config()

    # Scopes for TikTok integration
    # Currently using only Login Kit scopes (approved by default)
    #
    # To enable messaging, apply for these scopes in TikTok Developer Portal:
    # - message.list.read, message.list.send, message.list.manage
    # Then add them to this list after approval
    scopes = ",".join([
        "user.info.basic",
    ])

    params = {
        'client_key': config['client_id'],
        'redirect_uri': config['redirect_uri'],
        'response_type': 'code',
        'scope': scopes,
        'state': state,
    }

    return f"{TIKTOK_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str) -> Dict[str, Any]:
    """
    Exchange authorization code for access and refresh tokens

    Args:
        code: Authorization code from OAuth callback

    Returns:
        Dict containing access_token, refresh_token, expires_in, open_id, scope
    """
    config = get_tiktok_config()

    data = {
        'client_key': config['client_id'],
        'client_secret': config['client_secret'],
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': config['redirect_uri'],
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    try:
        response = requests.post(TIKTOK_TOKEN_URL, data=data, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()

        if 'error' in result:
            logger.error(f"TikTok token exchange error: {result}")
            raise Exception(f"TikTok API error: {result.get('error_description', result.get('error'))}")

        # Calculate token expiration time
        expires_in = result.get('expires_in', 86400)  # Default 24 hours
        expires_at = datetime.now() + timedelta(seconds=expires_in)

        return {
            'access_token': result.get('access_token'),
            'refresh_token': result.get('refresh_token'),
            'expires_in': expires_in,
            'expires_at': expires_at,
            'open_id': result.get('open_id'),
            'scope': result.get('scope', ''),
        }
    except requests.RequestException as e:
        logger.error(f"TikTok token exchange request failed: {e}")
        raise


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """
    Refresh an expired access token

    Args:
        refresh_token: The refresh token from initial OAuth

    Returns:
        Dict containing new access_token, refresh_token, expires_in
    """
    config = get_tiktok_config()

    data = {
        'client_key': config['client_id'],
        'client_secret': config['client_secret'],
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    try:
        response = requests.post(TIKTOK_TOKEN_URL, data=data, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()

        if 'error' in result:
            logger.error(f"TikTok token refresh error: {result}")
            raise Exception(f"TikTok API error: {result.get('error_description', result.get('error'))}")

        expires_in = result.get('expires_in', 86400)
        expires_at = datetime.now() + timedelta(seconds=expires_in)

        return {
            'access_token': result.get('access_token'),
            'refresh_token': result.get('refresh_token', refresh_token),  # May return same token
            'expires_in': expires_in,
            'expires_at': expires_at,
            'open_id': result.get('open_id'),
            'scope': result.get('scope', ''),
        }
    except requests.RequestException as e:
        logger.error(f"TikTok token refresh request failed: {e}")
        raise


def revoke_access_token(access_token: str) -> bool:
    """
    Revoke an access token (for disconnect)

    Args:
        access_token: The access token to revoke

    Returns:
        True if successful, False otherwise
    """
    config = get_tiktok_config()

    data = {
        'client_key': config['client_id'],
        'client_secret': config['client_secret'],
        'token': access_token,
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    try:
        response = requests.post(TIKTOK_REVOKE_URL, data=data, headers=headers, timeout=30)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error(f"TikTok token revoke failed: {e}")
        return False


def get_user_info(access_token: str) -> Dict[str, Any]:
    """
    Fetch TikTok user profile information

    Args:
        access_token: Valid access token

    Returns:
        Dict containing user info (open_id, union_id, avatar_url, display_name, etc.)
    """
    url = f"{TIKTOK_API_BASE}/user/info/"

    # Fields to request
    fields = "open_id,union_id,avatar_url,display_name,username"

    headers = {
        'Authorization': f'Bearer {access_token}',
    }

    params = {
        'fields': fields,
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()

        if result.get('error', {}).get('code') != 'ok':
            error = result.get('error', {})
            logger.error(f"TikTok user info error: {error}")
            raise Exception(f"TikTok API error: {error.get('message', 'Unknown error')}")

        return result.get('data', {}).get('user', {})
    except requests.RequestException as e:
        logger.error(f"TikTok user info request failed: {e}")
        raise


def send_message(access_token: str, recipient_open_id: str, message_type: str = 'text',
                 text: str = None, media_url: str = None) -> Dict[str, Any]:
    """
    Send a message to a TikTok user

    Note: User must have messaged the business first (within 48 hours)
    Max 10 consecutive messages per 48-hour window

    Args:
        access_token: Valid access token
        recipient_open_id: Recipient's open_id
        message_type: 'text', 'image', 'video', or 'card'
        text: Message text (for text type)
        media_url: Media URL (for image/video types)

    Returns:
        Dict containing message_id and status
    """
    url = f"{TIKTOK_API_BASE}/message/send/"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }

    # Build message payload based on type
    message = {
        'recipient': {
            'open_id': recipient_open_id,
        },
        'message_type': message_type,
    }

    if message_type == 'text' and text:
        message['text'] = {'text': text}
    elif message_type in ('image', 'video') and media_url:
        message['media'] = {'url': media_url}

    try:
        response = requests.post(url, headers=headers, json=message, timeout=30)
        response.raise_for_status()
        result = response.json()

        if result.get('error', {}).get('code') != 'ok':
            error = result.get('error', {})
            logger.error(f"TikTok send message error: {error}")
            raise Exception(f"TikTok API error: {error.get('message', 'Unknown error')}")

        return result.get('data', {})
    except requests.RequestException as e:
        logger.error(f"TikTok send message request failed: {e}")
        raise


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify TikTok webhook signature using HMAC-SHA256

    Args:
        payload: Raw request body bytes
        signature: Signature from X-Tiktok-Signature header

    Returns:
        True if signature is valid, False otherwise
    """
    config = get_tiktok_config()
    webhook_secret = config.get('webhook_secret', '')

    if not webhook_secret or not signature:
        logger.warning("Missing webhook secret or signature")
        return False

    try:
        # Compute expected signature
        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        # Compare signatures (timing-safe comparison)
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        return False


def parse_webhook_timestamp(timestamp_str: str) -> datetime:
    """
    Parse TikTok webhook timestamp to datetime

    Args:
        timestamp_str: Timestamp string from webhook (could be Unix epoch or ISO format)

    Returns:
        datetime object
    """
    try:
        # Try Unix timestamp (seconds or milliseconds)
        ts = int(timestamp_str)
        if ts > 10000000000:  # Milliseconds
            ts = ts / 1000
        return datetime.fromtimestamp(ts)
    except (ValueError, TypeError):
        pass

    try:
        # Try ISO format
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        pass

    # Fallback to current time
    logger.warning(f"Could not parse TikTok timestamp: {timestamp_str}")
    return datetime.now()


def ensure_valid_token(account) -> Optional[str]:
    """
    Ensure the account has a valid access token, refreshing if needed

    Args:
        account: TikTokCreatorAccount instance

    Returns:
        Valid access token or None if refresh failed
    """
    from django.utils import timezone

    # Check if token is still valid (with 5 minute buffer)
    if account.token_expires_at > timezone.now() + timedelta(minutes=5):
        return account.get_access_token()

    # Token expired or expiring soon, try to refresh
    try:
        refresh_token = account.get_refresh_token()
        if not refresh_token:
            logger.error(f"No refresh token for TikTok account {account.open_id}")
            return None

        new_tokens = refresh_access_token(refresh_token)

        # Update account with new tokens
        account.set_tokens(new_tokens['access_token'], new_tokens['refresh_token'])
        account.token_expires_at = new_tokens['expires_at']
        account.scope = new_tokens.get('scope', account.scope)
        account.save(update_fields=['access_token', 'refresh_token', 'token_expires_at', 'scope', 'updated_at'])

        logger.info(f"Refreshed TikTok token for account {account.open_id}")
        return new_tokens['access_token']

    except Exception as e:
        logger.error(f"Failed to refresh TikTok token for {account.open_id}: {e}")
        # Mark account as deactivated due to expired token
        account.is_active = False
        account.deactivated_at = timezone.now()
        account.deactivation_reason = 'expired_token'
        account.deactivation_error = str(e)
        account.save(update_fields=['is_active', 'deactivated_at', 'deactivation_reason', 'deactivation_error'])
        return None
