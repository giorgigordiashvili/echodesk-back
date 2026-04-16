import requests
import logging

logger = logging.getLogger(__name__)


def send_sms(api_key: str, phone_number: str, message: str) -> dict:
    """Send SMS via sender.ge API."""
    clean = phone_number.replace('+', '').replace(' ', '').replace('-', '')
    if clean.startswith('995'):
        clean = clean[3:]
    if len(clean) != 9 or not clean.startswith('5'):
        logger.warning(f"Invalid Georgian mobile number: {phone_number}")
        return {'error': 'Invalid Georgian mobile number'}

    try:
        resp = requests.post('https://sender.ge/api/send.php', data={
            'apikey': api_key,
            'destination': clean,
            'content': message,
            'smsno': 2,
        }, timeout=10)
        data = resp.json()
        logger.info(f"SMS sent to {clean}: messageId={data.get('messageId')}")
        return data
    except Exception as e:
        logger.error(f"SMS send failed: {e}")
        return {'error': str(e)}
