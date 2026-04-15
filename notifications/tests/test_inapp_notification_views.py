"""
Tests for in-app notification API endpoints (users.views.NotificationViewSet):
- List notifications (paginated, current user only)
- Unread count
- Mark single notification as read
- Mark all notifications as read
- Notification detail
- Delete notification
- Notifications scoped to user (can't see other users' notifications)
- Notification ordering (newest first)
- Filter unread only
- Clear all read notifications
- Notification preference list and bulk update
"""
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status

from users.tests.conftest import EchoDeskTenantTestCase
from users.models import Notification, NotificationPreference

User = get_user_model()

# The NotificationViewSet is registered at /api/notifications/
NOTIF_URL = '/api/notifications/'
PREF_URL = '/api/notification-preferences/'
PREF_BULK_URL = '/api/notification-preferences/bulk/'


def _results(resp):
    """Extract results from paginated or plain response."""
    if isinstance(resp.data, dict) and 'results' in resp.data:
        return resp.data['results']
    return resp.data


class NotifTestMixin:
    """Shared helpers for in-app notification view tests."""

    def _make_notification(self, user, **kw):
        defaults = {
            'user': user,
            'notification_type': 'ticket_assigned',
            'title': 'Test Notification',
            'message': 'You have a new notification',
            'is_read': False,
        }
        defaults.update(kw)
        return Notification.objects.create(**defaults)


# ============================================================================
# List notifications
# ============================================================================

class TestListNotifications(NotifTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='list-notif@test.com')

    def test_list_returns_200(self):
        self._make_notification(self.user)
        resp = self.api_get(NOTIF_URL, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_list_returns_user_notifications(self):
        self._make_notification(self.user, title='N1')
        self._make_notification(self.user, title='N2')
        resp = self.api_get(NOTIF_URL, user=self.user)
        results = _results(resp)
        self.assertGreaterEqual(len(results), 2)

    def test_unauthenticated_denied(self):
        resp = self.api_get(NOTIF_URL)
        self.assertIn(resp.status_code, [401, 403])


# ============================================================================
# Unread count
# ============================================================================

class TestUnreadCount(NotifTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='unread-count@test.com')

    def test_unread_count_zero(self):
        resp = self.api_get(f'{NOTIF_URL}unread_count/', user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 0)

    def test_unread_count_correct(self):
        self._make_notification(self.user, is_read=False)
        self._make_notification(self.user, is_read=False)
        self._make_notification(self.user, is_read=True)
        resp = self.api_get(f'{NOTIF_URL}unread_count/', user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 2)


# ============================================================================
# Mark as read (single)
# ============================================================================

class TestMarkAsRead(NotifTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='mark-read@test.com')

    def test_mark_single_as_read(self):
        notif = self._make_notification(self.user, is_read=False)
        resp = self.api_post(
            f'{NOTIF_URL}{notif.pk}/mark_read/',
            user=self.user,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.assertIsNotNone(notif.read_at)

    def test_mark_already_read_is_idempotent(self):
        notif = self._make_notification(self.user, is_read=True)
        notif.read_at = timezone.now()
        notif.save()
        resp = self.api_post(
            f'{NOTIF_URL}{notif.pk}/mark_read/',
            user=self.user,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_mark_nonexistent_notification_returns_404(self):
        resp = self.api_post(
            f'{NOTIF_URL}99999/mark_read/',
            user=self.user,
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ============================================================================
# Mark all as read
# ============================================================================

class TestMarkAllAsRead(NotifTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='mark-all@test.com')

    def test_mark_all_as_read(self):
        self._make_notification(self.user, is_read=False, title='A')
        self._make_notification(self.user, is_read=False, title='B')
        self._make_notification(self.user, is_read=True, title='C')
        resp = self.api_post(f'{NOTIF_URL}mark_all_read/', user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['updated'], 2)
        # Verify all are now read
        unread = Notification.objects.filter(user=self.user, is_read=False).count()
        self.assertEqual(unread, 0)

    def test_mark_all_read_when_none_unread(self):
        self._make_notification(self.user, is_read=True)
        resp = self.api_post(f'{NOTIF_URL}mark_all_read/', user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['updated'], 0)


# ============================================================================
# Notification detail
# ============================================================================

class TestNotificationDetail(NotifTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='detail-notif@test.com')

    def test_retrieve_single(self):
        notif = self._make_notification(self.user, title='Detail Test')
        resp = self.api_get(f'{NOTIF_URL}{notif.pk}/', user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['title'], 'Detail Test')

    def test_retrieve_includes_metadata(self):
        notif = self._make_notification(
            self.user,
            metadata={'actor_name': 'Admin User', 'old_value': 'open'},
        )
        resp = self.api_get(f'{NOTIF_URL}{notif.pk}/', user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['metadata']['actor_name'], 'Admin User')

    def test_retrieve_nonexistent_returns_404(self):
        resp = self.api_get(f'{NOTIF_URL}99999/', user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ============================================================================
# Delete notification
# ============================================================================

class TestDeleteNotification(NotifTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='delete-notif@test.com')

    def test_delete_notification(self):
        notif = self._make_notification(self.user)
        resp = self.api_delete(f'{NOTIF_URL}{notif.pk}/', user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(pk=notif.pk).exists())


# ============================================================================
# Notifications belong to user (isolation)
# ============================================================================

class TestNotificationsBelongToUser(NotifTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user1 = self.create_user(email='user1-notif@test.com')
        self.user2 = self.create_user(email='user2-notif@test.com')

    def test_cannot_see_other_users_notifications(self):
        self._make_notification(self.user1, title='User1 Only')
        self._make_notification(self.user2, title='User2 Only')
        resp = self.api_get(NOTIF_URL, user=self.user1)
        results = _results(resp)
        titles = [r['title'] for r in results]
        self.assertIn('User1 Only', titles)
        self.assertNotIn('User2 Only', titles)

    def test_cannot_read_other_users_notification(self):
        notif = self._make_notification(self.user2, title='Secret')
        resp = self.api_get(f'{NOTIF_URL}{notif.pk}/', user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_other_users_notification(self):
        notif = self._make_notification(self.user2)
        resp = self.api_delete(f'{NOTIF_URL}{notif.pk}/', user=self.user1)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Notification.objects.filter(pk=notif.pk).exists())

    def test_unread_count_scoped_to_user(self):
        self._make_notification(self.user1, is_read=False)
        self._make_notification(self.user2, is_read=False)
        self._make_notification(self.user2, is_read=False)
        resp = self.api_get(f'{NOTIF_URL}unread_count/', user=self.user1)
        self.assertEqual(resp.data['count'], 1)

    def test_mark_all_read_scoped_to_user(self):
        self._make_notification(self.user1, is_read=False)
        self._make_notification(self.user2, is_read=False)
        self.api_post(f'{NOTIF_URL}mark_all_read/', user=self.user1)
        # User2's notification should still be unread
        self.assertEqual(
            Notification.objects.filter(user=self.user2, is_read=False).count(),
            1,
        )


# ============================================================================
# Notification ordering
# ============================================================================

class TestNotificationOrdering(NotifTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='ordering-notif@test.com')

    def test_newest_first(self):
        n1 = self._make_notification(self.user, title='First')
        n2 = self._make_notification(self.user, title='Second')
        n3 = self._make_notification(self.user, title='Third')
        resp = self.api_get(NOTIF_URL, user=self.user)
        results = _results(resp)
        titles = [r['title'] for r in results]
        self.assertEqual(titles[0], 'Third')
        self.assertEqual(titles[-1], 'First')


# ============================================================================
# Clear all read notifications
# ============================================================================

class TestClearAllRead(NotifTestMixin, EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='clear-notif@test.com')

    def test_clear_all_read_deletes_read_only(self):
        self._make_notification(self.user, is_read=True, title='Read')
        self._make_notification(self.user, is_read=False, title='Unread')
        resp = self.api_delete(f'{NOTIF_URL}clear_all/', user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['deleted'], 1)
        # Unread should remain
        remaining = Notification.objects.filter(user=self.user)
        self.assertEqual(remaining.count(), 1)
        self.assertEqual(remaining.first().title, 'Unread')

    def test_clear_all_read_when_none_read(self):
        self._make_notification(self.user, is_read=False)
        resp = self.api_delete(f'{NOTIF_URL}clear_all/', user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['deleted'], 0)


# ============================================================================
# Notification preferences
# ============================================================================

class TestNotificationPreferencesAPI(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='pref-api@test.com')

    def test_list_preferences(self):
        NotificationPreference.objects.create(
            user=self.user, notification_type='ticket_assigned',
        )
        resp = self.api_get(PREF_URL, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_list_preferences_empty(self):
        resp = self.api_get(PREF_URL, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_bulk_update_preferences(self):
        resp = self.api_put(PREF_BULK_URL, [
            {'notification_type': 'ticket_assigned', 'in_app': True, 'sound': False, 'push': False},
            {'notification_type': 'ticket_commented', 'in_app': True, 'sound': True, 'push': True},
        ], user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)
        # Verify DB
        pref = NotificationPreference.objects.get(
            user=self.user, notification_type='ticket_assigned',
        )
        self.assertFalse(pref.sound)
        self.assertFalse(pref.push)

    def test_bulk_update_invalid_body(self):
        resp = self.api_put(PREF_BULK_URL, {'not': 'a list'}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_denied(self):
        resp = self.api_get(PREF_URL)
        self.assertIn(resp.status_code, [401, 403])
