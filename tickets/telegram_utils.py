import logging
import requests

logger = logging.getLogger(__name__)


def send_board_telegram_message(bot_token, chat_id, message, parse_mode='HTML'):
    """
    Send a message to Telegram using the HTTP API.

    Returns:
        bool: True if sent successfully, False otherwise
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': parse_mode,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Board Telegram notification sent successfully")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send board Telegram notification: {e}")
        return False


def send_board_telegram_document(bot_token, chat_id, file_url, caption=None, parse_mode='HTML'):
    """
    Send a document to Telegram by URL.

    Returns:
        bool: True if sent successfully, False otherwise
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

    payload = {
        'chat_id': chat_id,
        'document': file_url,
    }
    if caption:
        payload['caption'] = caption
        payload['parse_mode'] = parse_mode

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info("Board Telegram document sent successfully")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send board Telegram document: {e}")
        return False


def send_board_telegram_photo(bot_token, chat_id, photo_url, caption=None, parse_mode='HTML'):
    """
    Send a photo to Telegram by URL.

    Returns:
        bool: True if sent successfully, False otherwise
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"

    payload = {
        'chat_id': chat_id,
        'photo': photo_url,
    }
    if caption:
        payload['caption'] = caption
        payload['parse_mode'] = parse_mode

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info("Board Telegram photo sent successfully")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send board Telegram photo: {e}")
        return False
