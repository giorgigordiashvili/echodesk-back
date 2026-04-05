"""
Tests for notification API endpoints:
- VAPID public key  (GET  /api/notifications/vapid-public-key/)
- Subscribe         (POST /api/notifications/subscribe/)
- Unsubscribe       (POST /api/notifications/unsubscribe/)
- Test notification  (POST /api/notifications/test/)
- Subscriptions list (GET  /api/notifications/subscriptions/)
- Logs              (GET  /api/notifications/logs/)

Also tests the Notification model (in-app notifications from users app).
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status

from users.tests.conftest import EchoDeskTenantTestCase
from notifications.models import PushSubscription, NotificationLog

User = get_user_model()

# ── URL constants ──
VAPID_URL = '/notifications/vapid-public-key/'
SUBSCRIBE_URL = '/notifications/subscribe/'
UNSUBSCRIBE_URL = '/notifications/unsubscribe/'
TEST_URL = '/notifications/test/'
SUBS_LIST_URL = '/notifications/subscriptions/'
LOGS_URL = '/notifications/logs/'


class TestVapidPublicKey(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='vapid@test.com')

    @patch('notifications.views.get_vapid_keys')
    def test_returns_public_key(self, mock_keys):
        mock_keys.return_value = {'public_key': 'test-vapid-public-key-123'}
        resp = self.api_get(VAPID_URL, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['public_key'], 'test-vapid-public-key-123')

    def test_unauthenticated_denied(self):
        resp = self.api_get(VAPID_URL)
        self.assertIn(resp.status_code, [401, 403])


class TestSubscribe(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='sub@test.com')
        self.sub_data = {
            'subscription': {
                'endpoint': 'https://push.example.com/sub/abc123',
                'keys': {
                    'p256dh': 'test-p256dh-key',
                    'auth': 'test-auth-secret',
                },
            }
        }

    def test_subscribe_creates_subscription(self):
        resp = self.api_post(SUBSCRIBE_URL, self.sub_data, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data['created'])
        self.assertTrue(
            PushSubscription.objects.filter(
                user=self.user,
                endpoint='https://push.example.com/sub/abc123',
            ).exists()
        )

    def test_subscribe_same_endpoint_updates(self):
        # First subscription
        self.api_post(SUBSCRIBE_URL, self.sub_data, user=self.user)
        # Subscribe again from same endpoint
        resp = self.api_post(SUBSCRIBE_URL, self.sub_data, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['created'])
        self.assertEqual(
            PushSubscription.objects.filter(
                endpoint='https://push.example.com/sub/abc123',
            ).count(), 1
        )

    def test_subscribe_missing_keys_returns_400(self):
        resp = self.api_post(SUBSCRIBE_URL, {
            'subscription': {'endpoint': 'https://push.example.com/bad'},
        }, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_denied(self):
        resp = self.api_post(SUBSCRIBE_URL, self.sub_data)
        self.assertIn(resp.status_code, [401, 403])


class TestUnsubscribe(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='unsub@test.com')
        self.sub = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.example.com/unsub/xyz',
            p256dh='key',
            auth='secret',
            is_active=True,
        )

    def test_unsubscribe_deactivates(self):
        resp = self.api_post(UNSUBSCRIBE_URL, {
            'endpoint': 'https://push.example.com/unsub/xyz',
        }, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.is_active)

    def test_unsubscribe_not_found(self):
        resp = self.api_post(UNSUBSCRIBE_URL, {
            'endpoint': 'https://push.example.com/nonexistent',
        }, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class TestTestNotification(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='testnotif@test.com')

    @patch('notifications.views.send_notification_to_user', return_value=1)
    def test_send_test_notification_success(self, mock_send):
        resp = self.api_post(TEST_URL, {}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('1 device', resp.data['message'])
        mock_send.assert_called_once()

    @patch('notifications.views.send_notification_to_user', return_value=0)
    def test_send_test_notification_no_subs(self, mock_send):
        resp = self.api_post(TEST_URL, {}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_denied(self):
        resp = self.api_post(TEST_URL, {})
        self.assertIn(resp.status_code, [401, 403])


class TestSubscriptionsList(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='listub@test.com')

    def test_list_active_subscriptions(self):
        PushSubscription.objects.create(
            user=self.user, endpoint='https://push.example.com/1',
            p256dh='k1', auth='a1', is_active=True,
        )
        PushSubscription.objects.create(
            user=self.user, endpoint='https://push.example.com/2',
            p256dh='k2', auth='a2', is_active=False,
        )
        resp = self.api_get(SUBS_LIST_URL, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Only active ones
        self.assertEqual(len(resp.data), 1)

    def test_other_users_subs_not_visible(self):
        other = self.create_user(email='other@test.com')
        PushSubscription.objects.create(
            user=other, endpoint='https://push.example.com/other',
            p256dh='k', auth='a', is_active=True,
        )
        resp = self.api_get(SUBS_LIST_URL, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)


class TestNotificationLogs(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='logs@test.com')

    def test_list_logs(self):
        NotificationLog.objects.create(
            user=self.user, title='Test', body='Body', status='sent',
        )
        resp = self.api_get(LOGS_URL, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['title'], 'Test')

    def test_logs_limited_to_50(self):
        for i in range(55):
            NotificationLog.objects.create(
                user=self.user, title=f'Log {i}', body='B', status='sent',
            )
        resp = self.api_get(LOGS_URL, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(resp.data), 50)

    def test_other_users_logs_not_visible(self):
        other = self.create_user(email='otherlog@test.com')
        NotificationLog.objects.create(
            user=other, title='Secret', body='Private', status='sent',
        )
        resp = self.api_get(LOGS_URL, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)


# ═══════════════════════════════════════════════════════════
#  Model tests
# ═══════════════════════════════════════════════════════════

class TestPushSubscriptionModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='model@test.com')

    def test_str(self):
        sub = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.example.com/long-endpoint-string',
            p256dh='key', auth='secret',
        )
        self.assertIn('model@test.com', str(sub))

    def test_default_is_active(self):
        sub = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.example.com/default',
            p256dh='key', auth='secret',
        )
        self.assertTrue(sub.is_active)


class TestNotificationLogModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='logmodel@test.com')

    def test_str(self):
        log = NotificationLog.objects.create(
            user=self.user, title='Hello', body='World', status='sent',
        )
        self.assertIn('logmodel@test.com', str(log))
        self.assertIn('Hello', str(log))

    def test_default_status_pending(self):
        log = NotificationLog.objects.create(
            user=self.user, title='Pending', body='Test',
        )
        self.assertEqual(log.status, 'pending')
