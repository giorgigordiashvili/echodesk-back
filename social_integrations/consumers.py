"""
WebSocket consumers for real-time messaging functionality.
"""

import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from tenant_schemas.utils import schema_context
from .models import FacebookMessage, FacebookPageConnection


class MessagesConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time message updates.
    Handles new incoming messages and message status updates.
    """
    
    async def connect(self):
        self.tenant_schema = self.scope['url_route']['kwargs']['tenant_schema']
        self.user = self.scope.get('user', AnonymousUser())
        
        # For now, allow all connections to test WebSocket functionality
        # TODO: Add proper authentication when WebSocket auth is configured
        print(f"[WebSocket] Connection attempt - User: {self.user}, Tenant: {self.tenant_schema}")
        
        # Join the messages group for this tenant
        self.messages_group_name = f'messages_{self.tenant_schema}'
        
        await self.channel_layer.group_add(
            self.messages_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'tenant': self.tenant_schema,
            'user_authenticated': not self.user.is_anonymous
        }))
        
        print(f"[WebSocket] Connected successfully for tenant: {self.tenant_schema}")
    
    async def disconnect(self, close_code):
        # Leave the messages group
        if hasattr(self, 'messages_group_name'):
            await self.channel_layer.group_discard(
                self.messages_group_name,
                self.channel_name
            )
    
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
            
            elif message_type == 'subscribe_conversation':
                # Subscribe to specific conversation updates
                conversation_id = data.get('conversation_id')
                if conversation_id:
                    self.conversation_group_name = f'conversation_{self.tenant_schema}_{conversation_id}'
                    await self.channel_layer.group_add(
                        self.conversation_group_name,
                        self.channel_name
                    )
                    
                    await self.send(text_data=json.dumps({
                        'type': 'subscription',
                        'status': 'subscribed',
                        'conversation_id': conversation_id
                    }))
            
            elif message_type == 'unsubscribe_conversation':
                # Unsubscribe from conversation updates
                conversation_id = data.get('conversation_id')
                if conversation_id and hasattr(self, 'conversation_group_name'):
                    await self.channel_layer.group_discard(
                        self.conversation_group_name,
                        self.channel_name
                    )
                    
                    await self.send(text_data=json.dumps({
                        'type': 'subscription',
                        'status': 'unsubscribed',
                        'conversation_id': conversation_id
                    }))
        
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
    
    # Handlers for messages sent from Django views/signals
    async def new_message(self, event):
        """Send new message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message'],
            'conversation_id': event['conversation_id'],
            'timestamp': event['timestamp'],
            'assigned_user_id': event.get('assigned_user_id'),  # None if unassigned
        }))
    
    async def message_status_update(self, event):
        """Send message status update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message_status',
            'message_id': event['message_id'],
            'status': event['status'],
            'timestamp': event['timestamp']
        }))
    
    async def conversation_update(self, event):
        """Send conversation update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'conversation_update',
            'conversation_id': event['conversation_id'],
            'last_message': event['last_message'],
            'timestamp': event['timestamp']
        }))


class WidgetVisitorConsumer(AsyncWebsocketConsumer):
    """
    WebSocket endpoint for a website visitor's widget chat session.

    URL: /ws/widget/<token>/<session_id>/
    - Anonymous (no JWT/session auth) — token + session_id are the credential pair.
    - Joins group `widget_visitor_<session_id>` so agent replies land in real time.
    - Messages sent by the client create a WidgetMessage row and broadcast to
      both the visitor's group AND the agent's `messages_<tenant_schema>` group
      (reused as-is from Facebook / WhatsApp / etc.).
    """

    async def connect(self):
        self.token = self.scope['url_route']['kwargs']['token']
        self.session_id = self.scope['url_route']['kwargs']['session_id']

        resolved = await self._resolve()
        if not resolved:
            await self.close(code=4004)
            return

        self.connection_id, self.tenant_schema, self.widget_connection_pk = resolved
        self.visitor_group = f'widget_visitor_{self.session_id}'
        # Kept as a plain string (not a group we're *subscribed to*) so
        # inbound visitor WS messages can still broadcast to the agent
        # tenant group when the visitor sends via the WS `message` frame.
        self.tenant_group = f'messages_{self.tenant_schema}'
        # NOTE: we deliberately DO NOT join messages_<tenant> here. Every
        # widget broadcast is sent to both groups by widget_public_messages
        # and widget_admin_send_message, so subscribing to the tenant group
        # would deliver every frame twice to the visitor's iframe. Only
        # agents need the tenant-wide group (via MessagesConsumer).
        await self.channel_layer.group_add(self.visitor_group, self.channel_name)

        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'session_id': self.session_id,
        }))

    @database_sync_to_async
    def _resolve(self):
        """Validate token + session_id. Returns (connection_id, tenant_schema, pk) or None."""
        from widget_registry.models import WidgetConnection
        from .models import WidgetSession
        from tenant_schemas.utils import schema_context, get_public_schema_name

        with schema_context(get_public_schema_name()):
            try:
                conn = WidgetConnection.objects.get(widget_token=self.token, is_active=True)
            except WidgetConnection.DoesNotExist:
                return None
            conn_id = conn.id
            conn_pk = conn.pk
            tenant_schema = conn.tenant_schema
        with schema_context(tenant_schema):
            exists = WidgetSession.objects.filter(
                session_id=self.session_id, connection_id=conn_id
            ).exists()
        if not exists:
            return None
        return conn_id, tenant_schema, conn_pk

    async def disconnect(self, close_code):
        if hasattr(self, 'visitor_group'):
            await self.channel_layer.group_discard(self.visitor_group, self.channel_name)
        # tenant_group is intentionally never joined (see connect) so nothing
        # to discard here.

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'invalid_json'}))
            return

        mtype = data.get('type')
        if mtype == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong', 'timestamp': data.get('timestamp')}))
            return
        if mtype == 'message':
            text = (data.get('text') or '').strip()
            attachments = data.get('attachments') or []
            if not text and not attachments:
                await self.send(text_data=json.dumps({'type': 'error', 'message': 'empty_message'}))
                return
            msg_dict = await self._persist_visitor_message(text, attachments if isinstance(attachments, list) else [])
            if not msg_dict:
                await self.send(text_data=json.dumps({'type': 'error', 'message': 'session_expired'}))
                return
            # Broadcast to both groups so agent sidebar AND other widget tabs update.
            conversation_id = f"widget_{self.connection_id}_{self.session_id}"
            await self.channel_layer.group_send(self.visitor_group, {
                'type': 'new_message',
                'message': msg_dict,
                'conversation_id': conversation_id,
                'timestamp': msg_dict.get('timestamp'),
            })
            await self.channel_layer.group_send(self.tenant_group, {
                'type': 'new_message',
                'message': msg_dict,
                'conversation_id': conversation_id,
                'timestamp': msg_dict.get('timestamp'),
            })
            return

    @database_sync_to_async
    def _persist_visitor_message(self, text, attachments):
        import uuid
        from django.utils import timezone
        from datetime import timedelta
        from .models import WidgetMessage, WidgetSession

        STALE = timedelta(hours=24)
        with schema_context(self.tenant_schema):
            try:
                session = WidgetSession.objects.get(
                    session_id=self.session_id, connection_id=self.connection_id
                )
            except WidgetSession.DoesNotExist:
                return None
            now = timezone.now()
            if now - session.last_seen_at > STALE:
                return None
            msg = WidgetMessage.objects.create(
                session=session,
                message_id=uuid.uuid4().hex,
                message_text=text,
                attachments=attachments,
                is_from_visitor=True,
                is_delivered=True,
                delivered_at=now,
                timestamp=now,
            )
            session.last_seen_at = now
            session.save(update_fields=['last_seen_at'])
            return {
                'message_id': msg.message_id,
                'message_text': msg.message_text,
                'attachments': msg.attachments,
                'is_from_visitor': True,
                'timestamp': msg.timestamp.isoformat(),
                'session_id': self.session_id,
                'connection_id': self.connection_id,
                'platform': 'widget',
            }

    # Outbound handlers invoked by channel_layer.group_send
    async def new_message(self, event):
        """Forward new_message events to the visitor iframe.

        We're only subscribed to the session-scoped group (visitor_group),
        so every frame we receive here is already scoped to this session.
        """
        msg = event.get('message') or {}
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': msg,
            'conversation_id': event.get('conversation_id'),
            'timestamp': event.get('timestamp'),
        }))

    @staticmethod
    def _session_from_conversation_id(conv_id):
        # conversation_id format: widget_<connection_id>_<session_id>
        if not conv_id or not conv_id.startswith('widget_'):
            return None
        parts = conv_id.split('_', 2)
        return parts[2] if len(parts) == 3 else None


class TypingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for typing indicators.
    Handles typing start/stop events for conversations.
    """

    async def connect(self):
        self.tenant_schema = self.scope['url_route']['kwargs']['tenant_schema']
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.user = self.scope.get('user', AnonymousUser())

        print(f"[TypingWebSocket] Connection attempt - Tenant: {self.tenant_schema}, Conversation: {self.conversation_id}, User: {self.user}, Is Anonymous: {self.user.is_anonymous}")

        # Only allow authenticated users
        if self.user.is_anonymous:
            print(f"[TypingWebSocket] Rejecting connection - User not authenticated")
            # Send error message before closing
            await self.accept()
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Authentication required',
                'code': 'UNAUTHENTICATED'
            }))
            await self.close(code=4001)
            return

        # Join the typing group for this conversation
        self.typing_group_name = f'typing_{self.tenant_schema}_{self.conversation_id}'

        await self.channel_layer.group_add(
            self.typing_group_name,
            self.channel_name
        )

        await self.accept()

        print(f"[TypingWebSocket] Connection accepted for user {self.user.email}")

        # Send initial connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'conversation_id': self.conversation_id
        }))
    
    async def disconnect(self, close_code):
        # Leave the typing group and notify others that user stopped typing
        if hasattr(self, 'typing_group_name'):
            await self.channel_layer.group_send(
                self.typing_group_name,
                {
                    'type': 'user_stopped_typing',
                    'user_id': str(self.user.id) if not self.user.is_anonymous else 'anonymous',
                    'timestamp': asyncio.get_event_loop().time()
                }
            )
            
            await self.channel_layer.group_discard(
                self.typing_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle typing events from client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'ping':
                # Respond to ping with pong for connection health check
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
                print('[TypingWebSocket] Pong sent')

            elif message_type == 'typing_start':
                # Broadcast typing start to other users in conversation
                await self.channel_layer.group_send(
                    self.typing_group_name,
                    {
                        'type': 'user_started_typing',
                        'user_id': str(self.user.id),
                        'user_name': f"{self.user.first_name} {self.user.last_name}".strip() or self.user.email,
                        'timestamp': asyncio.get_event_loop().time()
                    }
                )

            elif message_type == 'typing_stop':
                # Broadcast typing stop to other users in conversation
                await self.channel_layer.group_send(
                    self.typing_group_name,
                    {
                        'type': 'user_stopped_typing',
                        'user_id': str(self.user.id),
                        'timestamp': asyncio.get_event_loop().time()
                    }
                )

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
    
    # Handlers for typing events
    async def user_started_typing(self, event):
        """Send typing start notification to WebSocket"""
        # Don't send the event back to the user who triggered it
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'typing_start',
                'user_id': event['user_id'],
                'user_name': event.get('user_name', 'Unknown'),
                'timestamp': event['timestamp']
            }))
    
    async def user_stopped_typing(self, event):
        """Send typing stop notification to WebSocket"""
        # Don't send the event back to the user who triggered it
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'typing_stop',
                'user_id': event['user_id'],
                'timestamp': event['timestamp']
            }))


# Utility functions for sending WebSocket messages from Django views
async def send_new_message_notification(tenant_schema, conversation_id, message_data):
    """
    Send new message notification to all connected clients.
    Call this from views when a new message is received or sent.
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    
    # Send to general messages group
    await channel_layer.group_send(
        f'messages_{tenant_schema}',
        {
            'type': 'new_message',
            'message': message_data,
            'conversation_id': conversation_id,
            'timestamp': message_data.get('timestamp')
        }
    )
    
    # Send to specific conversation group
    await channel_layer.group_send(
        f'conversation_{tenant_schema}_{conversation_id}',
        {
            'type': 'new_message',
            'message': message_data,
            'conversation_id': conversation_id,
            'timestamp': message_data.get('timestamp')
        }
    )


async def send_conversation_update(tenant_schema, conversation_id, last_message_data):
    """
    Send conversation update notification.
    Call this when a conversation's last message changes.
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    
    await channel_layer.group_send(
        f'messages_{tenant_schema}',
        {
            'type': 'conversation_update',
            'conversation_id': conversation_id,
            'last_message': last_message_data,
            'timestamp': last_message_data.get('timestamp')
        }
    )
