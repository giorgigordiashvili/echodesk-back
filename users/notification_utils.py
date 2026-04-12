"""
Reusable notification utilities.

Centralises `create_notification` (previously in tickets/signals.py) so that
any module can import it without circular-import issues.  Also provides Redis-
backed caching helpers for unread counts (Phase 2).
"""

from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from datetime import timedelta

# ---------------------------------------------------------------------------
# Redis cache helpers (Phase 2)
# ---------------------------------------------------------------------------

UNREAD_CACHE_KEY = 'notif_unread:{tenant}:{user_id}'
UNREAD_CACHE_TTL = 300  # 5 minutes


def _resolve_tenant(tenant_schema):
    """Return an explicit tenant schema or fall back to the current connection."""
    if tenant_schema:
        return tenant_schema
    return getattr(connection, 'schema_name', 'public')


def get_unread_count(user, tenant_schema=None):
    """Get unread count from Redis cache, falling back to DB."""
    tenant_schema = _resolve_tenant(tenant_schema)
    cache_key = UNREAD_CACHE_KEY.format(tenant=tenant_schema, user_id=user.id)
    count = cache.get(cache_key)
    if count is None:
        from users.models import Notification
        count = Notification.objects.filter(user=user, is_read=False).count()
        cache.set(cache_key, count, UNREAD_CACHE_TTL)
    return count


def increment_unread(user, tenant_schema=None):
    """Increment cached unread count."""
    tenant_schema = _resolve_tenant(tenant_schema)
    cache_key = UNREAD_CACHE_KEY.format(tenant=tenant_schema, user_id=user.id)
    try:
        cache.incr(cache_key)
    except ValueError:
        # Key doesn't exist yet — seed from DB
        get_unread_count(user, tenant_schema)


def decrement_unread(user, tenant_schema=None):
    """Decrement cached unread count."""
    tenant_schema = _resolve_tenant(tenant_schema)
    cache_key = UNREAD_CACHE_KEY.format(tenant=tenant_schema, user_id=user.id)
    try:
        new_val = cache.decr(cache_key)
        if new_val < 0:
            cache.set(cache_key, 0, UNREAD_CACHE_TTL)
    except ValueError:
        get_unread_count(user, tenant_schema)


def reset_unread(user, tenant_schema=None):
    """Reset cached unread count to 0 (e.g. mark-all-read)."""
    tenant_schema = _resolve_tenant(tenant_schema)
    cache_key = UNREAD_CACHE_KEY.format(tenant=tenant_schema, user_id=user.id)
    cache.set(cache_key, 0, UNREAD_CACHE_TTL)


# ---------------------------------------------------------------------------
# Core notification creator (moved from tickets/signals.py)
# ---------------------------------------------------------------------------

def create_notification(user, notification_type, title, message, ticket_id=None,
                        metadata=None, link_url=''):
    """
    Create a Notification row, broadcast it over WebSocket, and send a Web Push.

    Includes duplicate / batching logic (Phase 5): within a 30-second window for
    the same user + type + ticket, the existing notification is updated rather
    than creating a duplicate.
    """
    from users.models import Notification
    from users.consumers import send_notification_to_user
    from asgiref.sync import async_to_sync
    from django.utils.timesince import timesince

    if metadata is None:
        metadata = {}

    tenant_schema = getattr(connection, 'schema_name', 'public')

    # --- Phase 5: batching / debounce (30-second window) ---
    recent = Notification.objects.filter(
        user=user,
        notification_type=notification_type,
        ticket_id=ticket_id,
        created_at__gte=timezone.now() - timedelta(seconds=30),
    ).first()

    if recent:
        # Update the existing notification instead of creating a new one
        batch_count = recent.metadata.get('batch_count', 1) + 1
        recent.message = f"{message} (+{batch_count - 1} more)"
        recent.metadata['batch_count'] = batch_count
        recent.metadata.update(metadata)
        recent.is_read = False  # Re-mark as unread
        if link_url:
            recent.link_url = link_url
        recent.save(update_fields=['message', 'metadata', 'is_read', 'link_url'])
        notification = recent
    else:
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            ticket_id=ticket_id,
            link_url=link_url,
            metadata=metadata,
        )
        # Increment cached unread count
        increment_unread(user, tenant_schema)

    # --- Build unread count (from cache) ---
    unread_count = get_unread_count(user, tenant_schema)

    # --- WebSocket broadcast ---
    notification_data = {
        'id': notification.id,
        'notification_type': notification.notification_type,
        'title': notification.title,
        'message': notification.message,
        'ticket_id': notification.ticket_id,
        'link_url': notification.link_url,
        'metadata': notification.metadata,
        'is_read': notification.is_read,
        'created_at': notification.created_at.isoformat(),
        'read_at': notification.read_at.isoformat() if notification.read_at else None,
        'time_ago': timesince(notification.created_at),
        'user': notification.user.id,
        'user_name': notification.user.get_full_name() or notification.user.email,
    }

    try:
        async_to_sync(send_notification_to_user)(
            tenant_schema=tenant_schema,
            user_id=user.id,
            notification_data=notification_data,
            unread_count=unread_count,
        )
    except Exception as e:
        print(f"[notification_utils] Error broadcasting via WebSocket: {e}")

    # --- Web Push ---
    try:
        from notifications.utils import send_notification_to_user as send_push

        nav_url = link_url or (f'/tickets/{ticket_id}' if ticket_id else '/')

        send_push(
            user=user,
            title=title,
            body=message,
            data={
                'ticket_id': ticket_id,
                'notification_type': notification_type,
                'notification_id': notification.id,
                'url': nav_url,
            },
            icon='/favicon.ico',
            url=nav_url,
            tag=f'echodesk-{ticket_id or notification.id}',
        )
        print(f"[notification_utils] Web Push sent for notification {notification.id}")
    except Exception as e:
        print(f"[notification_utils] Error sending Web Push: {e}")


# ---------------------------------------------------------------------------
# Social message notification helper
# ---------------------------------------------------------------------------

def create_social_message_notification(platform, sender_name, message_text,
                                       conversation_id, sender_id,
                                       assigned_user_id=None):
    """
    Create a 'message_received' notification for an incoming social message.

    If the conversation is assigned to a specific user, only that user is
    notified.  Otherwise, up to 10 active users in the tenant are notified.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    title = f"New {platform} message from {sender_name}"
    msg = (message_text or '')[:100]
    meta = {
        'platform': platform,
        'conversation_id': conversation_id,
        'sender_name': sender_name,
        'sender_id': sender_id,
    }
    link = f'/messages?conversation={conversation_id}'

    if assigned_user_id:
        try:
            user = User.objects.get(id=assigned_user_id, is_active=True)
            create_notification(
                user=user,
                notification_type='message_received',
                title=title,
                message=msg,
                ticket_id=None,
                metadata=meta,
                link_url=link,
            )
        except User.DoesNotExist:
            pass
    else:
        # No assignment — notify up to 10 active users
        users = User.objects.filter(is_active=True)[:10]
        for user in users:
            create_notification(
                user=user,
                notification_type='message_received',
                title=title,
                message=msg,
                ticket_id=None,
                metadata=meta,
                link_url=link,
            )
