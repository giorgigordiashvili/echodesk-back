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

# Check if telegram is available
try:
    import telegram
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed. Telegram notifications disabled.")


def get_bot():
    """Get configured Telegram bot instance"""
    if not TELEGRAM_AVAILABLE:
        return None

    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured. Notifications disabled.")
        return None

    return Bot(token=bot_token)


def get_chat_id():
    """Get configured Telegram chat ID"""
    chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)
    if not chat_id:
        logger.warning("TELEGRAM_CHAT_ID not configured. Notifications disabled.")
    return chat_id


def send_telegram_message(message, parse_mode='HTML', disable_notification=False):
    """
    Send a message to Telegram

    Args:
        message: Message text (supports HTML formatting)
        parse_mode: 'HTML' or 'Markdown'
        disable_notification: If True, sends silently

    Returns:
        bool: True if sent successfully, False otherwise
    """
    if not TELEGRAM_AVAILABLE:
        logger.debug("Telegram not available, skipping notification")
        return False

    bot = get_bot()
    chat_id = get_chat_id()

    if not bot or not chat_id:
        return False

    try:
        bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=parse_mode,
            disable_notification=disable_notification
        )
        logger.info("Telegram notification sent successfully")
        return True
    except TelegramError as e:
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
    package = subscription.package

    message = f"""
🎉 <b>New Subscription Created!</b>

👤 <b>Tenant:</b> {tenant.name}
📧 <b>Email:</b> {tenant.admin_email}
📦 <b>Package:</b> {package.display_name if package else 'Feature-based'}
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

    message = f"""
🚨 <b>Subscription SUSPENDED!</b>

👤 <b>Tenant:</b> {tenant.name}
📧 <b>Email:</b> {tenant.admin_email}
📦 <b>Package:</b> {subscription.package.display_name if subscription.package else 'Feature-based'}

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
    if not TELEGRAM_AVAILABLE:
        return {
            'success': False,
            'message': 'python-telegram-bot not installed'
        }

    bot = get_bot()
    chat_id = get_chat_id()

    if not bot:
        return {
            'success': False,
            'message': 'TELEGRAM_BOT_TOKEN not configured'
        }

    if not chat_id:
        return {
            'success': False,
            'message': 'TELEGRAM_CHAT_ID not configured'
        }

    try:
        bot.send_message(
            chat_id=chat_id,
            text="✅ <b>Telegram Bot Connected!</b>\n\nEchoDesk notifications are now active.",
            parse_mode='HTML'
        )
        return {
            'success': True,
            'message': 'Test message sent successfully'
        }
    except TelegramError as e:
        return {
            'success': False,
            'message': f'Telegram error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'Unexpected error: {str(e)}'
        }
