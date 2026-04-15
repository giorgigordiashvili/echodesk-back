"""
Tests for the NotificationConsumer WebSocket consumer (users.consumers.NotificationConsumer).

Tests cover:
- connect: authenticated user joins group and receives unread count
- connect: unauthenticated user is rejected with error message and closed
- receive: mark_read message marks notification as read
- receive: mark_all_read message marks all notifications as read
- receive: get_unread_count returns current count
- receive: ping responds with pong
- receive: invalid JSON returns error
- disconnect: user leaves group cleanly
- notification_created handler sends notification to client
- notification_read handler sends read confirmation
- unread_count_update handler sends count update

Uses unittest.mock to avoid real Redis/channel-layer dependencies.
"""
import json
from unittest.mock import patch, AsyncMock, MagicMock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from users.tests.conftest import EchoDeskTenantTestCase
from users.consumers import NotificationConsumer
from users.models import Notification

User = get_user_model()


class MockChannelLayer:
    """Minimal mock for a channel layer used in consumer tests."""

    def __init__(self):
        self.groups = {}

    async def group_add(self, group, channel_name):
        self.groups.setdefault(group, set()).add(channel_name)

    async def group_discard(self, group, channel_name):
        if group in self.groups:
            self.groups[group].discard(channel_name)

    async def group_send(self, group, message):
        pass


def _build_consumer(user=None, tenant_schema='test'):
    """Create a NotificationConsumer with mocked scope and transport."""
    consumer = NotificationConsumer()
    consumer.scope = {
        'type': 'websocket',
        'url_route': {'kwargs': {'tenant_schema': tenant_schema}},
        'user': user or AnonymousUser(),
    }
    consumer.channel_name = 'test-channel-001'
    consumer.channel_layer = MockChannelLayer()
    # Mock the send/accept/close methods
    consumer.send = AsyncMock()
    consumer.accept = AsyncMock()
    consumer.close = AsyncMock()
    return consumer


# ============================================================================
# Connection tests
# ============================================================================

class TestNotificationConsumerConnect(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='ws-connect@test.com')

    @patch.object(NotificationConsumer, 'get_unread_count', new_callable=AsyncMock, return_value=3)
    async def test_authenticated_connect_joins_group(self, mock_count):
        consumer = _build_consumer(user=self.user)
        await consumer.connect()

        consumer.accept.assert_called_once()
        # Should have joined the notifications group
        expected_group = f'notifications_test_{self.user.id}'
        self.assertIn(expected_group, consumer.channel_layer.groups)
        self.assertIn('test-channel-001', consumer.channel_layer.groups[expected_group])

    @patch.object(NotificationConsumer, 'get_unread_count', new_callable=AsyncMock, return_value=5)
    async def test_authenticated_connect_sends_initial_state(self, mock_count):
        consumer = _build_consumer(user=self.user)
        await consumer.connect()

        # Should send connection confirmation
        consumer.send.assert_called()
        sent_data = json.loads(consumer.send.call_args[1]['text_data'])
        self.assertEqual(sent_data['type'], 'connection')
        self.assertEqual(sent_data['status'], 'connected')
        self.assertEqual(sent_data['unread_count'], 5)
        self.assertEqual(sent_data['user_id'], self.user.id)

    async def test_unauthenticated_rejected(self):
        consumer = _build_consumer(user=AnonymousUser())
        await consumer.connect()

        consumer.accept.assert_called_once()
        # Should send error message
        error_call = consumer.send.call_args_list[0]
        sent_data = json.loads(error_call[1]['text_data'])
        self.assertEqual(sent_data['type'], 'error')
        self.assertEqual(sent_data['code'], 'UNAUTHENTICATED')
        # Should close connection
        consumer.close.assert_called_once_with(code=4001)


# ============================================================================
# Disconnect tests
# ============================================================================

class TestNotificationConsumerDisconnect(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='ws-disconnect@test.com')

    @patch.object(NotificationConsumer, 'get_unread_count', new_callable=AsyncMock, return_value=0)
    async def test_disconnect_leaves_group(self, mock_count):
        consumer = _build_consumer(user=self.user)
        await consumer.connect()

        expected_group = f'notifications_test_{self.user.id}'
        self.assertIn('test-channel-001', consumer.channel_layer.groups[expected_group])

        await consumer.disconnect(close_code=1000)

        # Channel should have been removed from group
        self.assertNotIn('test-channel-001', consumer.channel_layer.groups.get(expected_group, set()))

    async def test_disconnect_without_connect(self):
        """Disconnecting without ever connecting should not raise."""
        consumer = _build_consumer(user=self.user)
        # No connect() called, so notifications_group_name is not set
        await consumer.disconnect(close_code=1000)
        # Should not raise


# ============================================================================
# Receive message tests
# ============================================================================

class TestNotificationConsumerReceive(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='ws-receive@test.com')

    async def test_ping_responds_with_pong(self):
        consumer = _build_consumer(user=self.user)
        consumer.notifications_group_name = f'notifications_test_{self.user.id}'

        await consumer.receive(text_data=json.dumps({
            'type': 'ping',
            'timestamp': 1234567890,
        }))

        consumer.send.assert_called()
        sent_data = json.loads(consumer.send.call_args[1]['text_data'])
        self.assertEqual(sent_data['type'], 'pong')
        self.assertEqual(sent_data['timestamp'], 1234567890)

    @patch.object(NotificationConsumer, 'mark_notification_read', new_callable=AsyncMock, return_value=True)
    @patch.object(NotificationConsumer, 'get_unread_count', new_callable=AsyncMock, return_value=2)
    async def test_mark_read_sends_confirmation(self, mock_count, mock_mark):
        consumer = _build_consumer(user=self.user)
        consumer.notifications_group_name = f'notifications_test_{self.user.id}'

        await consumer.receive(text_data=json.dumps({
            'type': 'mark_read',
            'notification_id': 42,
        }))

        mock_mark.assert_called_once_with(42)
        consumer.send.assert_called()
        sent_data = json.loads(consumer.send.call_args[1]['text_data'])
        self.assertEqual(sent_data['type'], 'notification_read')
        self.assertEqual(sent_data['notification_id'], 42)
        self.assertEqual(sent_data['unread_count'], 2)

    @patch.object(NotificationConsumer, 'mark_notification_read', new_callable=AsyncMock, return_value=False)
    async def test_mark_read_failure_sends_nothing(self, mock_mark):
        consumer = _build_consumer(user=self.user)
        consumer.notifications_group_name = f'notifications_test_{self.user.id}'

        await consumer.receive(text_data=json.dumps({
            'type': 'mark_read',
            'notification_id': 99999,
        }))

        # When mark fails, no confirmation is sent
        consumer.send.assert_not_called()

    @patch.object(NotificationConsumer, 'mark_all_notifications_read', new_callable=AsyncMock, return_value=5)
    async def test_mark_all_read_sends_confirmation(self, mock_mark_all):
        consumer = _build_consumer(user=self.user)
        consumer.notifications_group_name = f'notifications_test_{self.user.id}'

        await consumer.receive(text_data=json.dumps({
            'type': 'mark_all_read',
        }))

        mock_mark_all.assert_called_once()
        consumer.send.assert_called()
        sent_data = json.loads(consumer.send.call_args[1]['text_data'])
        self.assertEqual(sent_data['type'], 'all_notifications_read')
        self.assertEqual(sent_data['marked_count'], 5)
        self.assertEqual(sent_data['unread_count'], 0)

    @patch.object(NotificationConsumer, 'get_unread_count', new_callable=AsyncMock, return_value=7)
    async def test_get_unread_count_sends_count(self, mock_count):
        consumer = _build_consumer(user=self.user)
        consumer.notifications_group_name = f'notifications_test_{self.user.id}'

        await consumer.receive(text_data=json.dumps({
            'type': 'get_unread_count',
        }))

        consumer.send.assert_called()
        sent_data = json.loads(consumer.send.call_args[1]['text_data'])
        self.assertEqual(sent_data['type'], 'unread_count')
        self.assertEqual(sent_data['count'], 7)

    async def test_invalid_json_returns_error(self):
        consumer = _build_consumer(user=self.user)
        consumer.notifications_group_name = f'notifications_test_{self.user.id}'

        await consumer.receive(text_data='not valid json {{{')

        consumer.send.assert_called()
        sent_data = json.loads(consumer.send.call_args[1]['text_data'])
        self.assertEqual(sent_data['type'], 'error')
        self.assertIn('Invalid JSON', sent_data['message'])


# ============================================================================
# Event handler tests (messages from Django views/signals)
# ============================================================================

class TestNotificationConsumerHandlers(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='ws-handler@test.com')

    async def test_notification_created_handler(self):
        consumer = _build_consumer(user=self.user)
        consumer.notifications_group_name = f'notifications_test_{self.user.id}'

        event = {
            'type': 'notification_created',
            'notification': {
                'id': 1,
                'title': 'New Ticket',
                'message': 'You have been assigned a ticket',
            },
            'unread_count': 3,
        }

        await consumer.notification_created(event)

        consumer.send.assert_called_once()
        sent_data = json.loads(consumer.send.call_args[1]['text_data'])
        self.assertEqual(sent_data['type'], 'notification_created')
        self.assertEqual(sent_data['notification']['title'], 'New Ticket')
        self.assertEqual(sent_data['unread_count'], 3)

    async def test_notification_read_handler(self):
        consumer = _build_consumer(user=self.user)
        consumer.notifications_group_name = f'notifications_test_{self.user.id}'

        event = {
            'type': 'notification_read',
            'notification_id': 42,
            'unread_count': 1,
        }

        await consumer.notification_read(event)

        consumer.send.assert_called_once()
        sent_data = json.loads(consumer.send.call_args[1]['text_data'])
        self.assertEqual(sent_data['type'], 'notification_read')
        self.assertEqual(sent_data['notification_id'], 42)
        self.assertEqual(sent_data['unread_count'], 1)

    async def test_unread_count_update_handler(self):
        consumer = _build_consumer(user=self.user)
        consumer.notifications_group_name = f'notifications_test_{self.user.id}'

        event = {
            'type': 'unread_count_update',
            'count': 10,
        }

        await consumer.unread_count_update(event)

        consumer.send.assert_called_once()
        sent_data = json.loads(consumer.send.call_args[1]['text_data'])
        self.assertEqual(sent_data['type'], 'unread_count_update')
        self.assertEqual(sent_data['count'], 10)
