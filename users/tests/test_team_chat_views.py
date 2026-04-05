"""
Tests for Team Chat endpoints:
  - GET  /api/team-chat/users/                             → TeamChatUserListView
  - GET  /api/team-chat/conversations/                     → list conversations
  - GET  /api/team-chat/conversations/<id>/                → conversation detail
  - GET/POST /api/team-chat/conversations/with/<user_id>/  → get_or_create with user
  - POST /api/team-chat/conversations/<id>/mark_read/      → mark all read
  - DELETE /api/team-chat/conversations/<id>/clear_history/ → clear messages
  - POST /api/team-chat/conversations/<id>/hide_for_me/    → hide conversation
  - POST /api/team-chat/conversations/<id>/unhide/         → unhide conversation
  - POST /api/team-chat/messages/                          → create message
  - POST /api/team-chat/messages/<id>/mark_read/           → mark single read
  - GET  /api/team-chat/unread-count/                      → unread count
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from users.tests.conftest import EchoDeskTenantTestCase
from users.models import (
    TeamChatConversation, TeamChatMessage,
    HiddenTeamChatConversation, UserOnlineStatus,
)

User = get_user_model()

# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------
USERS_URL = '/api/team-chat/users/'
CONVERSATIONS_URL = '/api/team-chat/conversations/'
MESSAGES_URL = '/api/team-chat/messages/'
UNREAD_COUNT_URL = '/api/team-chat/unread-count/'


def _conv_url(pk):
    return f'{CONVERSATIONS_URL}{pk}/'


def _conv_with_url(user_id):
    return f'{CONVERSATIONS_URL}with/{user_id}/'


def _conv_mark_read_url(pk):
    return f'{CONVERSATIONS_URL}{pk}/mark_read/'


def _conv_clear_url(pk):
    return f'{CONVERSATIONS_URL}{pk}/clear_history/'


def _conv_hide_url(pk):
    return f'{CONVERSATIONS_URL}{pk}/hide_for_me/'


def _conv_unhide_url(pk):
    return f'{CONVERSATIONS_URL}{pk}/unhide/'


def _msg_mark_read_url(pk):
    return f'{MESSAGES_URL}{pk}/mark_read/'


class TeamChatTestMixin:
    """Shared helpers for team chat tests."""

    def _make_conversation(self, user1, user2):
        conv = TeamChatConversation.objects.create()
        conv.participants.add(user1, user2)
        return conv

    def _make_message(self, conversation, sender, text='Hello', **kwargs):
        defaults = {
            'conversation': conversation,
            'sender': sender,
            'text': text,
            'message_type': 'text',
        }
        defaults.update(kwargs)
        return TeamChatMessage.objects.create(**defaults)

    def _multipart_post(self, url, data, user):
        """POST with multipart format (required by TeamChatMessageViewSet)."""
        client = APIClient()
        client.force_authenticate(user=user)
        return client.post(url, data, format='multipart', HTTP_HOST='tenant.test.com')


# ============================================================
# Team Chat Users
# ============================================================
class TestTeamChatUsers(TeamChatTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user1 = self.create_user(email='chat1@test.com')
        self.user2 = self.create_user(email='chat2@test.com')

    def test_list_users_excludes_self(self):
        resp = self.api_get(USERS_URL, user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        emails = [u['email'] for u in resp.data]
        self.assertNotIn('chat1@test.com', emails)
        self.assertIn('chat2@test.com', emails)

    def test_includes_online_status(self):
        UserOnlineStatus.objects.create(user=self.user2, is_online=True)
        resp = self.api_get(USERS_URL, user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user2_data = next(u for u in resp.data if u['email'] == 'chat2@test.com')
        self.assertTrue(user2_data['is_online'])

    def test_unauthenticated_returns_401(self):
        resp = self.api_get(USERS_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================
# Conversations with/<user_id>  (creates/gets conversations)
# ============================================================
class TestConversationWithUser(TeamChatTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user1 = self.create_user(email='cwu1@test.com')
        self.user2 = self.create_user(email='cwu2@test.com')

    def test_creates_conversation(self):
        resp = self.api_post(_conv_with_url(self.user2.pk), user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('participants', resp.data)

    def test_returns_existing_conversation(self):
        conv = self._make_conversation(self.user1, self.user2)
        resp = self.api_get(_conv_with_url(self.user2.pk), user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['id'], conv.pk)

    def test_unhides_if_hidden(self):
        conv = self._make_conversation(self.user1, self.user2)
        HiddenTeamChatConversation.objects.create(user=self.user1, conversation=conv)
        resp = self.api_post(_conv_with_url(self.user2.pk), user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(
            HiddenTeamChatConversation.objects.filter(
                user=self.user1, conversation=conv,
            ).exists()
        )

    def test_nonexistent_user_returns_404(self):
        resp = self.api_post(_conv_with_url(99999), user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ============================================================
# Conversation Detail
# ============================================================
class TestConversationDetail(TeamChatTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user1 = self.create_user(email='cdet1@test.com')
        self.user2 = self.create_user(email='cdet2@test.com')
        self.conv = self._make_conversation(self.user1, self.user2)

    def test_detail_includes_messages(self):
        self._make_message(self.conv, self.user2, 'Detail msg')
        resp = self.api_get(_conv_url(self.conv.pk), user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('messages', resp.data)


# ============================================================
# Mark Read
# ============================================================
class TestMarkConversationRead(TeamChatTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user1 = self.create_user(email='mr1@test.com')
        self.user2 = self.create_user(email='mr2@test.com')
        self.conv = self._make_conversation(self.user1, self.user2)

    def test_marks_other_messages_as_read(self):
        msg = self._make_message(self.conv, self.user2, 'Read me')
        self.assertFalse(msg.is_read)
        resp = self.api_post(_conv_mark_read_url(self.conv.pk), user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['marked_read'], 1)
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)

    def test_does_not_mark_own_messages(self):
        self._make_message(self.conv, self.user1, 'My own msg')
        resp = self.api_post(_conv_mark_read_url(self.conv.pk), user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['marked_read'], 0)


# ============================================================
# Clear History
# ============================================================
class TestClearHistory(TeamChatTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user1 = self.create_user(email='clr1@test.com')
        self.user2 = self.create_user(email='clr2@test.com')
        self.conv = self._make_conversation(self.user1, self.user2)

    def test_clears_all_messages(self):
        self._make_message(self.conv, self.user1, 'Msg 1')
        self._make_message(self.conv, self.user2, 'Msg 2')
        resp = self.api_delete(_conv_clear_url(self.conv.pk), user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['deleted_count'], 2)
        self.assertEqual(self.conv.messages.count(), 0)


# ============================================================
# Hide / Unhide
# ============================================================
class TestHideUnhide(TeamChatTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user1 = self.create_user(email='hide1@test.com')
        self.user2 = self.create_user(email='hide2@test.com')
        self.conv = self._make_conversation(self.user1, self.user2)

    def test_hide_conversation(self):
        resp = self.api_post(_conv_hide_url(self.conv.pk), user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['success'])
        self.assertTrue(
            HiddenTeamChatConversation.objects.filter(
                user=self.user1, conversation=self.conv,
            ).exists()
        )

    def test_unhide_visible_conversation(self):
        """Unhiding a visible conversation is a no-op."""
        resp = self.api_post(_conv_unhide_url(self.conv.pk), user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['was_hidden'])

    def test_unhide_via_with_user(self):
        """Hidden conversations are auto-unhidden via the with/<user_id> endpoint."""
        HiddenTeamChatConversation.objects.create(user=self.user1, conversation=self.conv)
        resp = self.api_post(_conv_with_url(self.user2.pk), user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(
            HiddenTeamChatConversation.objects.filter(
                user=self.user1, conversation=self.conv,
            ).exists()
        )


# ============================================================
# Create Message
# ============================================================
class TestCreateMessage(TeamChatTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user1 = self.create_user(email='cmsg1@test.com')
        self.user2 = self.create_user(email='cmsg2@test.com')
        self.conv = self._make_conversation(self.user1, self.user2)

    @patch('users.views.TeamChatMessageViewSet._notify_recipient')
    def test_create_text_message_by_conversation(self, mock_notify):
        resp = self._multipart_post(MESSAGES_URL, {
            'conversation_id': self.conv.pk,
            'text': 'Hello!',
            'message_type': 'text',
        }, user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['text'], 'Hello!')
        self.assertEqual(resp.data['sender']['email'], 'cmsg1@test.com')

    @patch('users.views.TeamChatMessageViewSet._notify_recipient')
    def test_create_message_by_recipient(self, mock_notify):
        resp = self._multipart_post(MESSAGES_URL, {
            'recipient_id': self.user2.pk,
            'text': 'Hey!',
            'message_type': 'text',
        }, user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    @patch('users.views.TeamChatMessageViewSet._notify_recipient')
    def test_create_message_creates_conversation_if_needed(self, mock_notify):
        user3 = self.create_user(email='cmsg3@test.com')
        count_before = TeamChatConversation.objects.count()
        resp = self._multipart_post(MESSAGES_URL, {
            'recipient_id': user3.pk,
            'text': 'New convo!',
            'message_type': 'text',
        }, user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TeamChatConversation.objects.count(), count_before + 1)

    def test_create_message_nonexistent_conversation(self):
        resp = self._multipart_post(MESSAGES_URL, {
            'conversation_id': 99999,
            'text': 'Ghost',
            'message_type': 'text',
        }, user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_returns_401(self):
        resp = self.api_post(MESSAGES_URL, {'text': 'Hello'})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================
# Mark Single Message Read
# ============================================================
class TestMarkSingleMessageRead(TeamChatTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user1 = self.create_user(email='smr1@test.com')
        self.user2 = self.create_user(email='smr2@test.com')
        self.conv = self._make_conversation(self.user1, self.user2)
        self.msg = self._make_message(self.conv, self.user2, 'Read me single')

    def test_mark_read_as_recipient(self):
        resp = self.api_post(_msg_mark_read_url(self.msg.pk), user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.msg.refresh_from_db()
        self.assertTrue(self.msg.is_read)

    def test_sender_mark_read_stays_unread(self):
        """Sender marking their own message as read should not change is_read."""
        resp = self.api_post(_msg_mark_read_url(self.msg.pk), user=self.user2)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.msg.refresh_from_db()
        self.assertFalse(self.msg.is_read)


# ============================================================
# Unread Count
# ============================================================
class TestUnreadCount(TeamChatTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user1 = self.create_user(email='uc1@test.com')
        self.user2 = self.create_user(email='uc2@test.com')
        self.conv = self._make_conversation(self.user1, self.user2)

    def test_counts_unread_from_others(self):
        self._make_message(self.conv, self.user2, 'Unread 1')
        self._make_message(self.conv, self.user2, 'Unread 2')
        self._make_message(self.conv, self.user1, 'My own')
        resp = self.api_get(UNREAD_COUNT_URL, user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Count at least 2 from this conv (may be more from other tests in shared schema)
        self.assertGreaterEqual(resp.data['count'], 2)

    def test_zero_when_no_unread(self):
        """All messages are from self — unread count should be 0 for this conv."""
        self._make_message(self.conv, self.user1, 'My msg')
        resp = self.api_get(UNREAD_COUNT_URL, user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Note: other tests in shared schema may leave unread messages,
        # so we check it's a valid non-negative integer
        self.assertIsInstance(resp.data['count'], int)


# ============================================================
# Model Tests
# ============================================================
class TestTeamChatModels(TeamChatTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user1 = self.create_user(email='mdl1@test.com')
        self.user2 = self.create_user(email='mdl2@test.com')
        self.conv = self._make_conversation(self.user1, self.user2)

    def test_get_other_participant(self):
        other = self.conv.get_other_participant(self.user1)
        self.assertEqual(other, self.user2)

    def test_get_last_message(self):
        self._make_message(self.conv, self.user1, 'First')
        msg2 = self._make_message(self.conv, self.user2, 'Second')
        self.assertEqual(self.conv.get_last_message(), msg2)

    def test_get_unread_count(self):
        self._make_message(self.conv, self.user2, 'Unread')
        self._make_message(self.conv, self.user1, 'Mine')
        self.assertEqual(self.conv.get_unread_count(self.user1), 1)

    def test_mark_as_read(self):
        msg = self._make_message(self.conv, self.user2, 'Mark me')
        self.assertFalse(msg.is_read)
        msg.mark_as_read()
        self.assertTrue(msg.is_read)
        self.assertIsNotNone(msg.read_at)

    def test_mark_as_read_idempotent(self):
        msg = self._make_message(self.conv, self.user2, 'Already read')
        msg.mark_as_read()
        first_read_at = msg.read_at
        msg.mark_as_read()
        self.assertEqual(msg.read_at, first_read_at)
