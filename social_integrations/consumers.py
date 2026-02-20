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
