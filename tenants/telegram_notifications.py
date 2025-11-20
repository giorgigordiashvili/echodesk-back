"""
Telegram Bot Notifications for Subscription Events

Sends real-time notifications to Telegram for:
- New subscription creations
- Payment successes
- Payment failures
- Payment retries
- Subscription suspensions

Setup Instructions:
1. Create a bot with @BotFather on Telegram
2. Get your bot token from @BotFather
3. Get your chat ID by sending a message to your bot and visiting:
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
4. Set environment variables:
   - TELEGRAM_BOT_TOKEN=<your bot token>
   - TELEGRAM_CHAT_ID=<your chat id>
"""

import logging
from django.conf import settings
from decimal import Decimal
from datetime import datetime

logger = logging.getLogger(__name__)

import requests


def send_telegram_message(message, parse_mode='HTML', disable_notification=False):
    """
    Send a message to Telegram using HTTP API (synchronous)

    Args:
        message: Message text (supports HTML formatting)
        parse_mode: 'HTML' or 'Markdown'
        disable_notification: If True, sends silently

    Returns:
        bool: True if sent successfully, False otherwise
    """
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)

    if not bot_token:
        logger.debug("TELEGRAM_BOT_TOKEN not configured. Notifications disabled.")
        return False

    if not chat_id:
        logger.debug("TELEGRAM_CHAT_ID not configured. Notifications disabled.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': parse_mode,
        'disable_notification': disable_notification
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        logger.info("Telegram notification sent successfully")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending Telegram notification: {e}")
        return False


def notify_subscription_created(subscription):
    """
    Notify when a new subscription is created

    Args:
        subscription: TenantSubscription instance
    """
    tenant = subscription.tenant
    selected_features = subscription.selected_features.filter(is_active=True)
    features_list = ', '.join([f.name for f in selected_features]) if selected_features.exists() else 'None'

    message = f"""
🎉 <b>New Subscription Created!</b>

👤 <b>Tenant:</b> {tenant.name}
📧 <b>Email:</b> {tenant.admin_email}
✨ <b>Features:</b> {features_list}
💰 <b>Monthly Cost:</b> {subscription.monthly_cost} GEL
👥 <b>Agents:</b> {subscription.agent_count}

{'🆓 <b>Trial:</b> Yes' if subscription.is_trial else ''}
{'📅 <b>Trial Ends:</b> ' + subscription.trial_ends_at.strftime('%Y-%m-%d') if subscription.is_trial and subscription.trial_ends_at else ''}

🆔 <b>Subscription ID:</b> {subscription.id}
⏰ <b>Created:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    send_telegram_message(message.strip())


def notify_payment_success(payment_attempt, subscription=None):
    """
    Notify when a payment succeeds

    Args:
        payment_attempt: PaymentAttempt instance
        subscription: TenantSubscription instance (optional)
    """
    if not subscription and payment_attempt.subscription:
        subscription = payment_attempt.subscription

    tenant_name = subscription.tenant.name if subscription else payment_attempt.tenant.name
    amount = payment_attempt.amount

    # Check if this is a retry payment
    retry_text = ""
    if payment_attempt.is_retry:
        retry_text = f"\n🔄 <b>Retry Payment:</b> Attempt #{payment_attempt.attempt_number}"

    message = f"""
✅ <b>Payment Successful!</b>

👤 <b>Tenant:</b> {tenant_name}
💵 <b>Amount:</b> {amount} GEL{retry_text}

🆔 <b>BOG Order ID:</b> {payment_attempt.bog_order_id}
📋 <b>Payment ID:</b> {payment_attempt.id}
⏰ <b>Completed:</b> {payment_attempt.completed_at.strftime('%Y-%m-%d %H:%M:%S') if payment_attempt.completed_at else 'N/A'}
"""

    # Silent notification for successful payments to avoid spam
    send_telegram_message(message.strip(), disable_notification=True)


def notify_payment_failed(payment_attempt, subscription=None):
    """
    Notify when a payment fails

    Args:
        payment_attempt: PaymentAttempt instance
        subscription: TenantSubscription instance (optional)
    """
    if not subscription and payment_attempt.subscription:
        subscription = payment_attempt.subscription

    tenant_name = subscription.tenant.name if subscription else payment_attempt.tenant.name
    amount = payment_attempt.amount
    reason = payment_attempt.failed_reason or 'Unknown error'
    error_code = payment_attempt.bog_error_code or 'N/A'

    # Check if this is a retry payment
    retry_text = ""
    if payment_attempt.is_retry:
        retry_text = f"\n🔄 <b>Retry Attempt:</b> #{payment_attempt.attempt_number}"

    message = f"""
❌ <b>Payment Failed!</b>

👤 <b>Tenant:</b> {tenant_name}
💵 <b>Amount:</b> {amount} GEL{retry_text}

⚠️ <b>Reason:</b> {reason}
🔢 <b>Error Code:</b> {error_code}

🆔 <b>BOG Order ID:</b> {payment_attempt.bog_order_id}
📋 <b>Payment ID:</b> {payment_attempt.id}
⏰ <b>Failed At:</b> {payment_attempt.attempted_at.strftime('%Y-%m-%d %H:%M:%S')}
"""

    # Important notification - don't silence
    send_telegram_message(message.strip(), disable_notification=False)


def notify_retry_scheduled(subscription, retry_schedule):
    """
    Notify when a payment retry is scheduled

    Args:
        subscription: TenantSubscription instance
        retry_schedule: PaymentRetrySchedule instance
    """
    tenant = subscription.tenant
    scheduled_time = retry_schedule.scheduled_for.strftime('%Y-%m-%d %H:%M:%S')

    message = f"""
🔄 <b>Payment Retry Scheduled</b>

👤 <b>Tenant:</b> {tenant.name}
📧 <b>Email:</b> {tenant.admin_email}

🔢 <b>Retry Number:</b> {retry_schedule.retry_number} of 3
⏰ <b>Scheduled For:</b> {scheduled_time}

💰 <b>Monthly Cost:</b> {subscription.monthly_cost} GEL
📋 <b>Failed Payments:</b> {subscription.failed_payment_count}

🆔 <b>Retry ID:</b> {retry_schedule.id}
"""

    send_telegram_message(message.strip())


def notify_subscription_suspended(subscription, reason='Payment failures'):
    """
    Notify when a subscription is suspended

    Args:
        subscription: TenantSubscription instance
        reason: Reason for suspension
    """
    tenant = subscription.tenant

    selected_features = subscription.selected_features.filter(is_active=True)
    features_list = ', '.join([f.name for f in selected_features]) if selected_features.exists() else 'None'

    message = f"""
🚨 <b>Subscription SUSPENDED!</b>

👤 <b>Tenant:</b> {tenant.name}
📧 <b>Email:</b> {tenant.admin_email}
✨ <b>Features:</b> {features_list}

⚠️ <b>Reason:</b> {reason}
💰 <b>Monthly Cost:</b> {subscription.monthly_cost} GEL
📋 <b>Failed Payments:</b> {subscription.failed_payment_count}

🆔 <b>Subscription ID:</b> {subscription.id}
⏰ <b>Suspended:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚡️ <b>Action Required:</b> Contact tenant to resolve payment issue
"""

    # Critical notification
    send_telegram_message(message.strip(), disable_notification=False)


def notify_retry_success(subscription, payment_attempt):
    """
    Notify when a retry payment succeeds

    Args:
        subscription: TenantSubscription instance
        payment_attempt: PaymentAttempt instance
    """
    tenant = subscription.tenant

    message = f"""
🎉 <b>Retry Payment Successful!</b>

👤 <b>Tenant:</b> {tenant.name}
💵 <b>Amount:</b> {payment_attempt.amount} GEL

✅ <b>Subscription Restored</b>
🔄 <b>Retry Attempt:</b> #{payment_attempt.attempt_number}

🆔 <b>BOG Order ID:</b> {payment_attempt.bog_order_id}
⏰ <b>Completed:</b> {payment_attempt.completed_at.strftime('%Y-%m-%d %H:%M:%S') if payment_attempt.completed_at else 'N/A'}
"""

    send_telegram_message(message.strip())


def notify_all_retries_exhausted(subscription):
    """
    Notify when all payment retries have been exhausted

    Args:
        subscription: TenantSubscription instance
    """
    tenant = subscription.tenant

    message = f"""
⛔️ <b>All Payment Retries EXHAUSTED!</b>

👤 <b>Tenant:</b> {tenant.name}
📧 <b>Email:</b> {tenant.admin_email}

💰 <b>Monthly Cost:</b> {subscription.monthly_cost} GEL
📋 <b>Total Failed Attempts:</b> {subscription.failed_payment_count}

⚠️ <b>Status:</b> Subscription will be suspended
🆔 <b>Subscription ID:</b> {subscription.id}

⚡️ <b>Urgent Action Required:</b> Contact tenant immediately!
"""

    # Critical notification
    send_telegram_message(message.strip(), disable_notification=False)


def test_telegram_connection():
    """
    Test Telegram bot connection
    Returns dict with status and message
    """
    test_message = "✅ <b>Telegram Bot Connected!</b>\n\nEchoDesk notifications are now active."

    result = send_telegram_message(test_message)

    if result:
        return {
            'success': True,
            'message': 'Test message sent successfully'
        }
    else:
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)

        if not bot_token:
            return {
                'success': False,
                'message': 'TELEGRAM_BOT_TOKEN not configured'
            }
        elif not chat_id:
            return {
                'success': False,
                'message': 'TELEGRAM_CHAT_ID not configured'
            }
        else:
            return {
                'success': False,
                'message': 'Failed to send message - check logs for details'
            }
