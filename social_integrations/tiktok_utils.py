"""
TikTok Shop Partner Center API Utilities

TikTok Shop API Documentation:
- Authorization: https://partner.tiktokshop.com/docv2/page/6507ead7b99d5302be949ba9
- Customer Service: https://partner.tiktokshop.com/docv2/page/650aa425defece02be728da4

Key Details:
- Region: ROW (services.tiktokshop.com / open-api.tiktokglobalshop.com)
- Auth: HMAC-SHA256 request signing on every API call
- Token: x-tts-access-token header (not Bearer)
"""

import hmac
import hashlib
import json
import logging
import time
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from django.conf import settings

logger = logging.getLogger(__name__)

# TikTok Shop API URLs (ROW region)
TIKTOK_SHOP_AUTH_URL = "https://services.tiktokshop.com/open/authorize"
TIKTOK_SHOP_TOKEN_URL = "https://auth.tiktok-shops.com/api/v2/token/get"
TIKTOK_SHOP_REFRESH_URL = "https://auth.tiktok-shops.com/api/v2/token/refresh"
TIKTOK_SHOP_API_BASE = "https://open-api.tiktokglobalshop.com"


def get_tiktok_shop_config() -> Dict[str, str]:
    """Get TikTok Shop configuration from settings"""
    social_settings = getattr(settings, 'SOCIAL_INTEGRATIONS', {})
    return {
        'app_key': social_settings.get('TIKTOK_SHOP_APP_KEY', ''),
        'app_secret': social_settings.get('TIKTOK_SHOP_APP_SECRET', ''),
        'service_id': social_settings.get('TIKTOK_SHOP_SERVICE_ID', ''),
        'redirect_uri': social_settings.get('TIKTOK_SHOP_REDIRECT_URI', ''),
    }


def generate_sign(path: str, params: Dict[str, str], body: str = '',
                   content_type: str = 'application/json') -> str:
    """
    Generate HMAC-SHA256 signature for TikTok Shop API requests.

    Algorithm:
    1. Extract all query params except 'sign' and 'access_token'
    2. Sort params alphabetically by key
    3. Concatenate as {key}{value} pairs
    4. Prepend the request path
    5. If Content-Type is not multipart/form-data, append body
    6. Wrap: {app_secret}{concatenated_string}{app_secret}
    7. HMAC-SHA256 with app_secret as key -> hex digest
    """
    config = get_tiktok_shop_config()
    app_secret = config['app_secret']

    # Filter out sign and access_token
    sign_params = {k: v for k, v in params.items() if k not in ('sign', 'access_token')}

    # Sort alphabetically by key
    sorted_params = sorted(sign_params.items(), key=lambda x: x[0])

    # Concatenate key-value pairs
    param_str = ''.join(f'{k}{v}' for k, v in sorted_params)

    # Build sign base: path + sorted params
    sign_base = path + param_str

    # Append body if not multipart
    if content_type and 'multipart/form-data' not in content_type:
        sign_base += body

    # Wrap with app_secret
    sign_base = app_secret + sign_base + app_secret

    # HMAC-SHA256
    signature = hmac.new(
        app_secret.encode('utf-8'),
        sign_base.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return signature


def _make_shop_api_request(method: str, path: str, access_token: str,
                           shop_cipher: str, params: Optional[Dict] = None,
                           body: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Make a signed request to the TikTok Shop API.

    All requests require: app_key, timestamp, shop_cipher, sign as query params
    and x-tts-access-token header.
    """
    config = get_tiktok_shop_config()
    timestamp = str(int(time.time()))

    # Build query params
    query_params = {
        'app_key': config['app_key'],
        'timestamp': timestamp,
        'shop_cipher': shop_cipher,
    }
    if params:
        query_params.update(params)

    # Serialize body
    body_str = ''
    if body is not None:
        body_str = json.dumps(body, separators=(',', ':'))

    # Generate signature
    content_type = 'application/json'
    sign = generate_sign(path, query_params, body_str, content_type)
    query_params['sign'] = sign
    query_params['access_token'] = access_token

    url = f"{TIKTOK_SHOP_API_BASE}{path}"

    headers = {
        'x-tts-access-token': access_token,
        'Content-Type': content_type,
    }

    try:
        if method.upper() == 'GET':
            response = requests.get(url, params=query_params, headers=headers, timeout=30)
        else:
            response = requests.post(url, params=query_params, headers=headers,
                                     data=body_str.encode('utf-8') if body_str else None,
                                     timeout=30)

        response.raise_for_status()
        result = response.json()

        if result.get('code') != 0:
            error_msg = result.get('message', 'Unknown error')
            logger.error(f"TikTok Shop API error on {path}: code={result.get('code')}, message={error_msg}")
            raise Exception(f"TikTok Shop API error: {error_msg}")

        return result.get('data', {})

    except requests.RequestException as e:
        logger.error(f"TikTok Shop API request failed ({path}): {e}")
        raise


def get_oauth_url(state: str) -> str:
    """
    Generate TikTok Shop Partner Center OAuth authorization URL.

    Args:
        state: State parameter for CSRF protection (include tenant info)

    Returns:
        Full OAuth authorization URL
    """
    config = get_tiktok_shop_config()
    return f"{TIKTOK_SHOP_AUTH_URL}?service_id={config['service_id']}&state={state}"


def exchange_code_for_token(auth_code: str) -> Dict[str, Any]:
    """
    Exchange authorization code for access and refresh tokens via TikTok Shop token endpoint.

    Args:
        auth_code: Authorization code from OAuth callback

    Returns:
        Dict containing access_token, refresh_token, open_id, seller_name, etc.
    """
    config = get_tiktok_shop_config()

    params = {
        'app_key': config['app_key'],
        'app_secret': config['app_secret'],
        'auth_code': auth_code,
        'grant_type': 'authorized_code',
    }

    try:
        response = requests.get(TIKTOK_SHOP_TOKEN_URL, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()

        if result.get('code') != 0:
            error_msg = result.get('message', 'Unknown error')
            logger.error(f"TikTok Shop token exchange error: {result}")
            raise Exception(f"TikTok Shop API error: {error_msg}")

        data = result.get('data', {})

        # Calculate expiration times
        access_expires_in = data.get('access_token_expire_in', 604800)  # Default 7 days
        refresh_expires_in = data.get('refresh_token_expire_in', 5184000)  # Default 60 days
        access_expires_at = datetime.now() + timedelta(seconds=access_expires_in)
        refresh_expires_at = datetime.now() + timedelta(seconds=refresh_expires_in)

        return {
            'access_token': data.get('access_token'),
            'refresh_token': data.get('refresh_token'),
            'access_token_expire_in': access_expires_in,
            'refresh_token_expire_in': refresh_expires_in,
            'access_expires_at': access_expires_at,
            'refresh_expires_at': refresh_expires_at,
            'open_id': data.get('open_id'),
            'seller_name': data.get('seller_name', ''),
            'seller_base_region': data.get('seller_base_region', ''),
            'user_type': data.get('user_type', 0),
            'granted_scopes': data.get('granted_scopes', ''),
        }

    except requests.RequestException as e:
        logger.error(f"TikTok Shop token exchange request failed: {e}")
        raise


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """
    Refresh an expired access token via TikTok Shop refresh endpoint.

    Args:
        refresh_token: The refresh token from initial OAuth

    Returns:
        Dict containing new access_token, refresh_token, expiration times
    """
    config = get_tiktok_shop_config()

    params = {
        'app_key': config['app_key'],
        'app_secret': config['app_secret'],
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }

    try:
        response = requests.get(TIKTOK_SHOP_REFRESH_URL, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()

        if result.get('code') != 0:
            error_msg = result.get('message', 'Unknown error')
            logger.error(f"TikTok Shop token refresh error: {result}")
            raise Exception(f"TikTok Shop API error: {error_msg}")

        data = result.get('data', {})

        access_expires_in = data.get('access_token_expire_in', 604800)
        refresh_expires_in = data.get('refresh_token_expire_in', 5184000)
        access_expires_at = datetime.now() + timedelta(seconds=access_expires_in)
        refresh_expires_at = datetime.now() + timedelta(seconds=refresh_expires_in)

        return {
            'access_token': data.get('access_token'),
            'refresh_token': data.get('refresh_token', refresh_token),
            'access_token_expire_in': access_expires_in,
            'refresh_token_expire_in': refresh_expires_in,
            'access_expires_at': access_expires_at,
            'refresh_expires_at': refresh_expires_at,
            'open_id': data.get('open_id'),
            'seller_name': data.get('seller_name', ''),
            'seller_base_region': data.get('seller_base_region', ''),
            'granted_scopes': data.get('granted_scopes', ''),
        }

    except requests.RequestException as e:
        logger.error(f"TikTok Shop token refresh request failed: {e}")
        raise


def get_authorized_shops(access_token: str) -> list:
    """
    Get the list of authorized shops for the authenticated seller.

    Args:
        access_token: Valid access token

    Returns:
        List of shop dicts with shop_id, shop_cipher, shop_name, region, etc.
    """
    config = get_tiktok_shop_config()
    path = "/authorization/202309/shops"
    timestamp = str(int(time.time()))

    query_params = {
        'app_key': config['app_key'],
        'timestamp': timestamp,
    }

    sign = generate_sign(path, query_params, '', 'application/json')
    query_params['sign'] = sign
    query_params['access_token'] = access_token

    url = f"{TIKTOK_SHOP_API_BASE}{path}"

    headers = {
        'x-tts-access-token': access_token,
        'Content-Type': 'application/json',
    }

    try:
        response = requests.get(url, params=query_params, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()

        if result.get('code') != 0:
            error_msg = result.get('message', 'Unknown error')
            logger.error(f"TikTok Shop get_authorized_shops error: {result}")
            raise Exception(f"TikTok Shop API error: {error_msg}")

        return result.get('data', {}).get('shops', [])

    except requests.RequestException as e:
        logger.error(f"TikTok Shop get_authorized_shops request failed: {e}")
        raise


def get_conversations(access_token: str, shop_cipher: str,
                      page_size: int = 20, page_token: str = '') -> Dict[str, Any]:
    """
    Get customer service conversations.

    Args:
        access_token: Valid access token
        shop_cipher: Shop cipher for the target shop
        page_size: Number of conversations per page
        page_token: Token for pagination

    Returns:
        Dict with conversations list and next_page_token
    """
    path = "/customer_service/202309/conversations"
    params = {'page_size': str(page_size)}
    if page_token:
        params['page_token'] = page_token

    return _make_shop_api_request('GET', path, access_token, shop_cipher, params=params)


def get_conversation_messages(access_token: str, shop_cipher: str,
                              conversation_id: str, page_size: int = 20,
                              page_token: str = '') -> Dict[str, Any]:
    """
    Get messages for a specific conversation.

    Args:
        access_token: Valid access token
        shop_cipher: Shop cipher for the target shop
        conversation_id: Conversation ID
        page_size: Number of messages per page
        page_token: Token for pagination

    Returns:
        Dict with messages list and next_page_token
    """
    path = f"/customer_service/202309/conversations/{conversation_id}/messages"
    params = {'page_size': str(page_size)}
    if page_token:
        params['page_token'] = page_token

    return _make_shop_api_request('GET', path, access_token, shop_cipher, params=params)


def send_message(access_token: str, shop_cipher: str, conversation_id: str,
                 msg_type: str = 'TEXT', content: str = '') -> Dict[str, Any]:
    """
    Send a message in a conversation.

    Args:
        access_token: Valid access token
        shop_cipher: Shop cipher for the target shop
        conversation_id: Conversation ID to send message in
        msg_type: Message type (TEXT, IMAGE, etc.)
        content: JSON string of message content, e.g. '{"content": "hello"}'

    Returns:
        Dict with message_id
    """
    path = f"/customer_service/202309/conversations/{conversation_id}/messages"
    body = {
        'type': msg_type,
        'content': content,
    }

    return _make_shop_api_request('POST', path, access_token, shop_cipher, body=body)


def create_conversation(access_token: str, shop_cipher: str,
                        buyer_user_id: str) -> Dict[str, Any]:
    """
    Create a new conversation with a buyer.

    Args:
        access_token: Valid access token
        shop_cipher: Shop cipher for the target shop
        buyer_user_id: Buyer's user ID

    Returns:
        Dict with conversation_id
    """
    path = "/customer_service/202309/conversations"
    body = {
        'buyer_user_id': buyer_user_id,
    }

    return _make_shop_api_request('POST', path, access_token, shop_cipher, body=body)


def read_message(access_token: str, shop_cipher: str,
                 conversation_id: str) -> Dict[str, Any]:
    """
    Mark messages in a conversation as read.

    Args:
        access_token: Valid access token
        shop_cipher: Shop cipher for the target shop
        conversation_id: Conversation ID

    Returns:
        API response data
    """
    path = f"/customer_service/202309/conversations/{conversation_id}/messages/read"

    return _make_shop_api_request('POST', path, access_token, shop_cipher, body={})


def verify_webhook_signature(app_key: str, app_secret: str,
                             payload: str, signature: str) -> bool:
    """
    Verify TikTok Shop webhook signature.

    TTSPC uses Authorization header with HMAC-SHA256:
    sign_base = app_key + payload
    key = app_secret

    Args:
        app_key: TikTok Shop app key
        app_secret: TikTok Shop app secret
        payload: Raw request body string
        signature: Signature from Authorization header

    Returns:
        True if signature is valid
    """
    if not app_secret or not signature:
        logger.warning("Missing app_secret or signature for webhook verification")
        return False

    try:
        sign_base = app_key + payload
        expected_signature = hmac.new(
            app_secret.encode('utf-8'),
            sign_base.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        return False


def ensure_valid_token(account) -> Optional[str]:
    """
    Ensure the account has a valid access token, refreshing if needed.

    Args:
        account: TikTokShopAccount instance

    Returns:
        Valid access token or None if refresh failed
    """
    from django.utils import timezone

    # Check if token is still valid (with 5 minute buffer)
    if account.token_expires_at > timezone.now() + timedelta(minutes=5):
        return account.get_access_token()

    # Check if refresh token is also expired
    if (account.refresh_token_expires_at and
            account.refresh_token_expires_at <= timezone.now()):
        logger.error(f"Refresh token expired for TikTok Shop account {account.open_id}")
        account.is_active = False
        account.deactivated_at = timezone.now()
        account.deactivation_reason = 'expired_token'
        account.deactivation_error = 'Refresh token expired'
        account.save(update_fields=['is_active', 'deactivated_at', 'deactivation_reason', 'deactivation_error'])
        return None

    # Token expired or expiring soon, try to refresh
    try:
        current_refresh_token = account.get_refresh_token()
        if not current_refresh_token:
            logger.error(f"No refresh token for TikTok Shop account {account.open_id}")
            return None

        new_tokens = refresh_access_token(current_refresh_token)

        # Update account with new tokens
        account.set_tokens(new_tokens['access_token'], new_tokens['refresh_token'])
        account.token_expires_at = new_tokens['access_expires_at']
        account.refresh_token_expires_at = new_tokens['refresh_expires_at']
        account.scope = new_tokens.get('granted_scopes', account.scope)
        account.save(update_fields=[
            'access_token', 'refresh_token', 'token_expires_at',
            'refresh_token_expires_at', 'scope', 'updated_at'
        ])

        logger.info(f"Refreshed TikTok Shop token for account {account.open_id}")
        return new_tokens['access_token']

    except Exception as e:
        logger.error(f"Failed to refresh TikTok Shop token for {account.open_id}: {e}")
        account.is_active = False
        account.deactivated_at = timezone.now()
        account.deactivation_reason = 'expired_token'
        account.deactivation_error = str(e)
        account.save(update_fields=['is_active', 'deactivated_at', 'deactivation_reason', 'deactivation_error'])
        return None
