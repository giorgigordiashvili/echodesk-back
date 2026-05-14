"""
Tests for PR3 cross-user reactivity broadcasts.

Each mutation (assign / unassign / transfer / start-session / end-session /
mark-read / mark-unread / mark-all-read / archive / unarchive / archive-all)
should fire a `channel_layer.group_send` to the `messages_<tenant>` group
with the additive event type that /messages-beta consumes.

The legacy /messages page ignores these unknown event types, so adding them
is purely additive and these tests guard us from regressing that promise.
"""
from unittest.mock import AsyncMock, patch
from rest_framework import status

from social_integrations.tests.conftest import SocialIntegrationTestCase


def _make_async_channel_layer():
    """A bare-bones async channel layer mock whose `group_send` records calls."""
    channel_layer = AsyncMock()
    channel_layer.group_send = AsyncMock()
    return channel_layer


def _types_sent(channel_layer):
    return [call.args[1]["type"] for call in channel_layer.group_send.call_args_list]


def _groups_sent(channel_layer):
    return [call.args[0] for call in channel_layer.group_send.call_args_list]


class TestAssignmentBroadcasts(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email="assign-bcast@test.com")
        self.assign_url = "/api/social/assignments/assign/"
        self.unassign_url = "/api/social/assignments/unassign/"

    def _enable_assignment_mode(self):
        from social_integrations.models import SocialIntegrationSettings
        settings, _ = SocialIntegrationSettings.objects.get_or_create(pk=1)
        settings.chat_assignment_enabled = True
        settings.session_management_enabled = True
        settings.save(update_fields=["chat_assignment_enabled", "session_management_enabled"])

    def test_assign_chat_broadcasts_assignment_update(self):
        self._enable_assignment_mode()
        channel_layer = _make_async_channel_layer()
        with patch("social_integrations.consumers.get_channel_layer", return_value=channel_layer):
            resp = self.api_post(
                self.assign_url,
                {"platform": "facebook", "conversation_id": "sender_1", "account_id": "page_1"},
                user=self.agent,
            )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        types = _types_sent(channel_layer)
        self.assertIn("assignment_update", types)
        # And it must land on the tenant-wide group so every connected agent
        # in the tenant sees it.
        for group in _groups_sent(channel_layer):
            self.assertTrue(group.startswith("messages_"), f"unexpected group: {group}")

    def test_unassign_broadcasts_with_null_user(self):
        from social_integrations.models import ChatAssignment

        self._enable_assignment_mode()
        ChatAssignment.objects.create(
            platform="facebook",
            conversation_id="sender_2",
            account_id="page_1",
            assigned_user=self.agent,
            status="active",
        )

        channel_layer = _make_async_channel_layer()
        with patch("social_integrations.consumers.get_channel_layer", return_value=channel_layer):
            resp = self.api_post(
                self.unassign_url,
                {"platform": "facebook", "conversation_id": "sender_2", "account_id": "page_1"},
                user=self.agent,
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Find the assignment_update frame and confirm its assigned_user_id is None.
        frames = [call.args[1] for call in channel_layer.group_send.call_args_list]
        assignment_frames = [f for f in frames if f.get("type") == "assignment_update"]
        self.assertTrue(assignment_frames, "expected an assignment_update frame")
        self.assertIsNone(assignment_frames[-1]["assigned_user_id"])


class TestReadStateBroadcasts(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email="readbcast@test.com")

    def test_mark_read_broadcasts_zero_unread(self):
        conn = self.create_fb_connection()
        msg = self.create_fb_message(page_connection=conn, is_from_page=False)

        channel_layer = _make_async_channel_layer()
        with patch("social_integrations.consumers.get_channel_layer", return_value=channel_layer):
            resp = self.api_post(
                "/api/social/mark-read/",
                {"platform": "facebook", "conversation_id": msg.sender_id},
                user=self.agent,
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        types = _types_sent(channel_layer)
        self.assertIn("read_state_update", types)
        # Locate the read_state_update frame and verify the unread_count is 0.
        for call in channel_layer.group_send.call_args_list:
            payload = call.args[1]
            if payload.get("type") == "read_state_update":
                self.assertEqual(payload["unread_count"], 0)
                self.assertEqual(payload["conversation_id"], msg.sender_id)
                self.assertEqual(payload["platform"], "facebook")
                break
        else:
            self.fail("read_state_update frame not emitted")

    def test_mark_all_read_emits_bulk_frame_per_platform(self):
        channel_layer = _make_async_channel_layer()
        with patch("social_integrations.consumers.get_channel_layer", return_value=channel_layer):
            resp = self.api_post(
                "/api/social/mark-all-read/",
                {"platform": "facebook,instagram"},
                user=self.agent,
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        frames = [
            call.args[1]
            for call in channel_layer.group_send.call_args_list
            if call.args[1].get("type") == "read_state_update"
        ]
        platforms = {f["platform"] for f in frames}
        self.assertEqual(platforms, {"facebook", "instagram"})
        # Bulk frames have conversation_id=None — that's how clients know
        # "wipe all unread for this platform".
        for f in frames:
            self.assertIsNone(f["conversation_id"])


class TestArchiveBroadcasts(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email="archbcast@test.com")

    def test_archive_conversation_broadcasts(self):
        conn = self.create_fb_connection()
        channel_layer = _make_async_channel_layer()
        with patch("social_integrations.consumers.get_channel_layer", return_value=channel_layer):
            resp = self.api_post(
                "/api/social/conversations/archive/",
                {
                    "conversations": [{
                        "platform": "facebook",
                        "conversation_id": "sender_99",
                        "account_id": conn.page_id,
                    }]
                },
                user=self.agent,
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        frames = [
            call.args[1]
            for call in channel_layer.group_send.call_args_list
            if call.args[1].get("type") == "archive_update"
        ]
        self.assertTrue(frames, "expected an archive_update frame")
        self.assertTrue(frames[0]["archived"])
        self.assertEqual(frames[0]["conversation_id"], "sender_99")

    def test_unarchive_broadcasts_archived_false(self):
        # First archive so the unarchive has something to remove.
        from social_integrations.models import ConversationArchive
        conn = self.create_fb_connection()
        ConversationArchive.objects.create(
            platform="facebook",
            conversation_id="sender_77",
            account_id=conn.page_id,
            archived_by=self.agent,
        )

        channel_layer = _make_async_channel_layer()
        with patch("social_integrations.consumers.get_channel_layer", return_value=channel_layer):
            resp = self.api_post(
                "/api/social/conversations/unarchive/",
                {
                    "conversations": [{
                        "platform": "facebook",
                        "conversation_id": "sender_77",
                        "account_id": conn.page_id,
                    }]
                },
                user=self.agent,
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        frames = [
            call.args[1]
            for call in channel_layer.group_send.call_args_list
            if call.args[1].get("type") == "archive_update"
        ]
        self.assertTrue(frames, "expected an archive_update frame on unarchive")
        self.assertFalse(frames[0]["archived"])


class TestBroadcastsAreBestEffort(SocialIntegrationTestCase):
    """If the channel layer blows up we still want the REST mutation to succeed."""

    def setUp(self):
        super().setUp()
        self.agent = self.create_user(email="besteffort@test.com")

    def test_mark_read_succeeds_even_if_channel_layer_raises(self):
        conn = self.create_fb_connection()
        msg = self.create_fb_message(page_connection=conn, is_from_page=False)

        boom = AsyncMock()
        boom.group_send.side_effect = RuntimeError("redis is on fire")
        with patch("social_integrations.consumers.get_channel_layer", return_value=boom):
            resp = self.api_post(
                "/api/social/mark-read/",
                {"platform": "facebook", "conversation_id": msg.sender_id},
                user=self.agent,
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
