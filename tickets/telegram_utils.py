import logging
import requests

logger = logging.getLogger(__name__)


def send_board_telegram_message(bot_token, chat_id, message, parse_mode='HTML'):
    """
    Send a message to Telegram using the HTTP API.

    Args:
        bot_token: Telegram bot token (decrypted)
        chat_id: Telegram chat ID
        message: Message text (supports HTML formatting)
        parse_mode: 'HTML' or 'Markdown'

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
