"""
Tests for users/notification_utils.py:
- create_notification(): creates Notification record in DB
- Duplicate prevention (30s window): updates existing instead of creating new
- Batch count incrementing on duplicate
- get_unread_count(): returns correct count from DB
- increment_unread() / decrement_unread() / reset_unread(): cache operations
- Preference check: in_app=False skips creation
- Preference check: push=False skips Web Push
- link_url parameter saved to notification
"""
from unittest.mock import patch, MagicMock
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from users.tests.conftest import EchoDeskTenantTestCase
from users.models import Notification, NotificationPreference
from users.notification_utils import (
    create_notification,
    get_unread_count,
    increment_unread,
    decrement_unread,
    reset_unread,
    UNREAD_CACHE_KEY,
)

User = get_user_model()


class TestCreateNotification(EchoDeskTenantTestCase):
    """
    Test create_notification().

    Note: create_notification does not return the notification object
    (implicit None return). Tests verify by querying the DB.
    """

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='notif-util@test.com')
        # Ensure clean slate
        NotificationPreference.objects.filter(user=self.user).delete()
        Notification.objects.filter(user=self.user).delete()

    def tearDown(self):
        NotificationPreference.objects.filter(user=self.user).delete()
        Notification.objects.filter(user=self.user).delete()
        super().tearDown()

    @patch('notifications.utils.send_notification_to_user', return_value=0)
    @patch('asgiref.sync.async_to_sync', return_value=lambda **kw: None)
    def test_creates_notification_record(self, mock_ats, mock_push):
        create_notification(
            user=self.user,
            notification_type='ticket_assigned',
            title='Test Title',
            message='Test message body',
        )
        notif = Notification.objects.filter(
            user=self.user,
            notification_type='ticket_assigned',
            title='Test Title',
        ).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.message, 'Test message body')

    @patch('notifications.utils.send_notification_to_user', return_value=0)
    @patch('asgiref.sync.async_to_sync', return_value=lambda **kw: None)
    def test_link_url_saved(self, mock_ats, mock_push):
        create_notification(
            user=self.user,
            notification_type='ticket_assigned',
            title='Link Test',
            message='M',
            link_url='/tickets/42',
        )
        notif = Notification.objects.get(user=self.user, title='Link Test')
        self.assertEqual(notif.link_url, '/tickets/42')

    @patch('notifications.utils.send_notification_to_user', return_value=0)
    @patch('asgiref.sync.async_to_sync', return_value=lambda **kw: None)
    def test_duplicate_within_30s_updates_existing(self, mock_ats, mock_push):
        create_notification(
            user=self.user,
            notification_type='ticket_commented',
            title='Comment',
            message='First comment',
            ticket_id=99,
        )
        count_before = Notification.objects.filter(user=self.user).count()

        # Second call within 30s for same user + type + ticket
        create_notification(
            user=self.user,
            notification_type='ticket_commented',
            title='Comment',
            message='Second comment',
            ticket_id=99,
        )

        # Should update the existing, not create a new one
        count_after = Notification.objects.filter(user=self.user).count()
        self.assertEqual(count_before, count_after)

        notif = Notification.objects.get(user=self.user, ticket_id=99)
        self.assertEqual(notif.metadata.get('batch_count'), 2)
        self.assertIn('+1 more', notif.message)

    @patch('notifications.utils.send_notification_to_user', return_value=0)
    @patch('asgiref.sync.async_to_sync', return_value=lambda **kw: None)
    def test_batch_count_increments_on_multiple_duplicates(self, mock_ats, mock_push):
        for msg in ['M1', 'M2', 'M3']:
            create_notification(
                user=self.user, notification_type='ticket_commented',
                title='C', message=msg, ticket_id=50,
            )

        notif = Notification.objects.get(user=self.user, ticket_id=50)
        self.assertEqual(notif.metadata.get('batch_count'), 3)

    @patch('notifications.utils.send_notification_to_user', return_value=0)
    @patch('asgiref.sync.async_to_sync', return_value=lambda **kw: None)
    def test_in_app_disabled_skips_creation(self, mock_ats, mock_push):
        NotificationPreference.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            in_app=False,
            sound=True,
            push=True,
        )
        result = create_notification(
            user=self.user,
            notification_type='ticket_assigned',
            title='Suppressed',
            message='Should not create',
        )
        self.assertIsNone(result)
        self.assertFalse(
            Notification.objects.filter(user=self.user, title='Suppressed').exists()
        )

    @patch('notifications.utils.send_notification_to_user', return_value=0)
    @patch('asgiref.sync.async_to_sync', return_value=lambda **kw: None)
    def test_push_disabled_skips_web_push(self, mock_ats, mock_push):
        NotificationPreference.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            in_app=True,
            sound=True,
            push=False,
        )
        create_notification(
            user=self.user,
            notification_type='ticket_assigned',
            title='No Push',
            message='Push disabled',
        )
        # Notification should be created (in_app=True)
        notif = Notification.objects.get(user=self.user, title='No Push')
        self.assertIsNotNone(notif)
        # Web push should NOT have been called
        mock_push.assert_not_called()


# ═══════════════════════════════════════════════════════════
#  Cache helpers
# ═══════════════════════════════════════════════════════════

class TestUnreadCountCache(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='cache-test@test.com')

    def test_get_unread_count_from_db(self):
        """When cache is empty, get_unread_count falls back to DB."""
        Notification.objects.create(
            user=self.user, notification_type='ticket_assigned',
            title='A', message='B', is_read=False,
        )
        Notification.objects.create(
            user=self.user, notification_type='ticket_commented',
            title='C', message='D', is_read=True,
        )
        with patch('users.notification_utils.cache') as mock_cache:
            mock_cache.get.return_value = None  # cache miss
            count = get_unread_count(self.user)
            self.assertEqual(count, 1)
            mock_cache.set.assert_called_once()

    def test_get_unread_count_from_cache(self):
        """When cache has a value, it is returned directly."""
        with patch('users.notification_utils.cache') as mock_cache:
            mock_cache.get.return_value = 5
            count = get_unread_count(self.user)
            self.assertEqual(count, 5)

    def test_increment_unread(self):
        with patch('users.notification_utils.cache') as mock_cache:
            mock_cache.incr.return_value = 3
            increment_unread(self.user, tenant_schema='test')
            mock_cache.incr.assert_called_once()

    def test_increment_unread_seeds_on_value_error(self):
        """When key doesn't exist, cache.incr raises ValueError; we seed from DB."""
        with patch('users.notification_utils.cache') as mock_cache:
            mock_cache.incr.side_effect = ValueError
            mock_cache.get.return_value = None  # cache miss
            increment_unread(self.user, tenant_schema='test')
            mock_cache.set.assert_called()

    def test_decrement_unread(self):
        with patch('users.notification_utils.cache') as mock_cache:
            mock_cache.decr.return_value = 1
            decrement_unread(self.user, tenant_schema='test')
            mock_cache.decr.assert_called_once()

    def test_decrement_unread_clamps_to_zero(self):
        with patch('users.notification_utils.cache') as mock_cache:
            mock_cache.decr.return_value = -1
            decrement_unread(self.user, tenant_schema='test')
            mock_cache.set.assert_called()
            args = mock_cache.set.call_args[0]
            self.assertEqual(args[1], 0)

    def test_decrement_unread_seeds_on_value_error(self):
        with patch('users.notification_utils.cache') as mock_cache:
            mock_cache.decr.side_effect = ValueError
            mock_cache.get.return_value = None
            decrement_unread(self.user, tenant_schema='test')
            mock_cache.set.assert_called()

    def test_reset_unread(self):
        with patch('users.notification_utils.cache') as mock_cache:
            reset_unread(self.user, tenant_schema='test')
            mock_cache.set.assert_called_once()
            args = mock_cache.set.call_args[0]
            self.assertEqual(args[1], 0)
