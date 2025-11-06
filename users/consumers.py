"""
WebSocket consumers for real-time notification functionality.
"""

import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from tenant_schemas.utils import schema_context
from .models import Notification


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notification updates.
    Handles new notifications, read status updates, and unread count changes.
    """

    async def connect(self):
        self.tenant_schema = self.scope['url_route']['kwargs']['tenant_schema']
        self.user = self.scope.get('user', AnonymousUser())

        print(f"[NotificationWS] Connection attempt - User: {self.user}, Tenant: {self.tenant_schema}")

        # Only allow authenticated users to receive notifications
        if self.user.is_anonymous:
            print(f"[NotificationWS] Rejecting connection - User not authenticated")
            await self.accept()
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Authentication required',
                'code': 'UNAUTHENTICATED'
            }))
            await self.close(code=4001)
            return

        # Join the notifications group for this specific user in this tenant
        # This ensures users only receive their own notifications
        self.notifications_group_name = f'notifications_{self.tenant_schema}_{self.user.id}'

        await self.channel_layer.group_add(
            self.notifications_group_name,
            self.channel_name
        )

        await self.accept()

        # Get initial unread count
        unread_count = await self.get_unread_count()

        # Send initial connection confirmation with unread count
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'tenant': self.tenant_schema,
            'user_id': self.user.id,
            'unread_count': unread_count
        }))

        print(f"[NotificationWS] Connected successfully for user {self.user.email} in tenant {self.tenant_schema}")

    async def disconnect(self, close_code):
        # Leave the notifications group
        if hasattr(self, 'notifications_group_name'):
            await self.channel_layer.group_discard(
                self.notifications_group_name,
                self.channel_name
            )
            print(f"[NotificationWS] Disconnected user {self.user.id if not self.user.is_anonymous else 'anonymous'}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages from client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'ping':
                # Respond to ping with pong for connection health check
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))

            elif message_type == 'mark_read':
                # Mark a notification as read
                notification_id = data.get('notification_id')
                if notification_id:
                    success = await self.mark_notification_read(notification_id)
                    if success:
                        # Get updated unread count
                        unread_count = await self.get_unread_count()

                        # Send confirmation
                        await self.send(text_data=json.dumps({
                            'type': 'notification_read',
                            'notification_id': notification_id,
                            'unread_count': unread_count
                        }))

            elif message_type == 'mark_all_read':
                # Mark all notifications as read
                count = await self.mark_all_notifications_read()

                # Send confirmation
                await self.send(text_data=json.dumps({
                    'type': 'all_notifications_read',
                    'marked_count': count,
                    'unread_count': 0
                }))

            elif message_type == 'get_unread_count':
                # Get current unread count
                unread_count = await self.get_unread_count()

                await self.send(text_data=json.dumps({
                    'type': 'unread_count',
                    'count': unread_count
                }))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            print(f"[NotificationWS] Error handling message: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))

    # Handlers for messages sent from Django views/signals
    async def notification_created(self, event):
        """Send new notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'notification_created',
            'notification': event['notification'],
            'unread_count': event.get('unread_count', 1)
        }))

    async def notification_read(self, event):
        """Send notification read status update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'notification_read',
            'notification_id': event['notification_id'],
            'unread_count': event.get('unread_count', 0)
        }))

    async def unread_count_update(self, event):
        """Send unread count update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'unread_count_update',
            'count': event['count']
        }))

    # Database operations
    @database_sync_to_async
    def get_unread_count(self):
        """Get the count of unread notifications for the current user"""
        with schema_context(self.tenant_schema):
            return Notification.objects.filter(
                user=self.user,
                is_read=False
            ).count()

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark a single notification as read"""
        try:
            with schema_context(self.tenant_schema):
                from django.utils import timezone
                notification = Notification.objects.get(
                    id=notification_id,
                    user=self.user
                )
                if not notification.is_read:
                    notification.is_read = True
                    notification.read_at = timezone.now()
                    notification.save(update_fields=['is_read', 'read_at'])
                return True
        except Notification.DoesNotExist:
            return False
        except Exception as e:
            print(f"[NotificationWS] Error marking notification {notification_id} as read: {str(e)}")
            return False

    @database_sync_to_async
    def mark_all_notifications_read(self):
        """Mark all unread notifications as read"""
        try:
            with schema_context(self.tenant_schema):
                from django.utils import timezone
                count = Notification.objects.filter(
                    user=self.user,
                    is_read=False
                ).update(
                    is_read=True,
                    read_at=timezone.now()
                )
                return count
        except Exception as e:
            print(f"[NotificationWS] Error marking all notifications as read: {str(e)}")
            return 0


# Utility functions for sending WebSocket messages from Django views/signals
async def send_notification_to_user(tenant_schema, user_id, notification_data, unread_count=None):
    """
    Send new notification to a specific user via WebSocket.
    Call this from signals when a new notification is created.

    Args:
        tenant_schema: The tenant schema name
        user_id: The user ID to send notification to
        notification_data: Dictionary containing notification data
        unread_count: Optional unread count to include in the message
    """
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()

    # Send to user's notification group
    await channel_layer.group_send(
        f'notifications_{tenant_schema}_{user_id}',
        {
            'type': 'notification_created',
            'notification': notification_data,
            'unread_count': unread_count
        }
    )


async def send_notification_read_update(tenant_schema, user_id, notification_id, unread_count=None):
    """
    Send notification read status update to a specific user via WebSocket.

    Args:
        tenant_schema: The tenant schema name
        user_id: The user ID
        notification_id: The notification ID that was read
        unread_count: Optional updated unread count
    """
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()

    await channel_layer.group_send(
        f'notifications_{tenant_schema}_{user_id}',
        {
            'type': 'notification_read',
            'notification_id': notification_id,
            'unread_count': unread_count
        }
    )


async def send_unread_count_update(tenant_schema, user_id, count):
    """
    Send unread count update to a specific user via WebSocket.

    Args:
        tenant_schema: The tenant schema name
        user_id: The user ID
        count: The updated unread count
    """
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()

    await channel_layer.group_send(
        f'notifications_{tenant_schema}_{user_id}',
        {
            'type': 'unread_count_update',
            'count': count
        }
    )
