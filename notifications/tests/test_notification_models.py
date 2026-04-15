"""
Tests for notification-related models:
- PushSubscription: creation, defaults, str representation, indexing
- NotificationLog: creation, defaults, str, status choices
- In-app Notification (users.Notification): creation, defaults, mark_as_read, ordering
- NotificationPreference: creation, defaults, unique_together
"""
from django.contrib.auth import get_user_model
from django.utils import timezone

from users.tests.conftest import EchoDeskTenantTestCase
from notifications.models import PushSubscription, NotificationLog
from users.models import Notification, NotificationPreference

User = get_user_model()


# ============================================================================
# PushSubscription model
# ============================================================================

class TestPushSubscriptionModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='pushsub-model@test.com')

    def test_create_subscription(self):
        sub = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.example.com/sub/model-test',
            p256dh='test-p256dh-key',
            auth='test-auth-secret',
        )
        self.assertEqual(sub.user, self.user)
        self.assertEqual(sub.endpoint, 'https://push.example.com/sub/model-test')

    def test_default_is_active(self):
        sub = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.example.com/active-default',
            p256dh='key', auth='secret',
        )
        self.assertTrue(sub.is_active)

    def test_str_includes_user_email(self):
        sub = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.example.com/str-test',
            p256dh='key', auth='secret',
        )
        self.assertIn('pushsub-model@test.com', str(sub))

    def test_endpoint_unique(self):
        PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.example.com/unique-ep',
            p256dh='key1', auth='secret1',
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            PushSubscription.objects.create(
                user=self.user,
                endpoint='https://push.example.com/unique-ep',
                p256dh='key2', auth='secret2',
            )

    def test_ordering_newest_first(self):
        sub1 = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.example.com/order-1',
            p256dh='k', auth='a',
        )
        sub2 = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.example.com/order-2',
            p256dh='k', auth='a',
        )
        subs = list(PushSubscription.objects.filter(user=self.user))
        self.assertEqual(subs[0].pk, sub2.pk)  # newest first

    def test_user_agent_blank_allowed(self):
        sub = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.example.com/blank-ua',
            p256dh='key', auth='secret',
            user_agent='',
        )
        self.assertEqual(sub.user_agent, '')

    def test_timestamps_auto_set(self):
        sub = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.example.com/timestamps',
            p256dh='key', auth='secret',
        )
        self.assertIsNotNone(sub.created_at)
        self.assertIsNotNone(sub.updated_at)


# ============================================================================
# NotificationLog model
# ============================================================================

class TestNotificationLogModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='notiflog-model@test.com')

    def test_create_notification_log(self):
        log = NotificationLog.objects.create(
            user=self.user,
            title='Test Log',
            body='Log body',
            status='sent',
        )
        self.assertEqual(log.title, 'Test Log')
        self.assertEqual(log.body, 'Log body')

    def test_default_status_pending(self):
        log = NotificationLog.objects.create(
            user=self.user,
            title='Default Status',
            body='Should be pending',
        )
        self.assertEqual(log.status, 'pending')

    def test_str_includes_email_and_title(self):
        log = NotificationLog.objects.create(
            user=self.user,
            title='Str Test',
            body='Body',
            status='sent',
        )
        s = str(log)
        self.assertIn('notiflog-model@test.com', s)
        self.assertIn('Str Test', s)
        self.assertIn('sent', s)

    def test_data_field_default_empty_dict(self):
        log = NotificationLog.objects.create(
            user=self.user,
            title='Data Default',
            body='Check data',
        )
        self.assertEqual(log.data, {})

    def test_data_field_stores_json(self):
        log = NotificationLog.objects.create(
            user=self.user,
            title='Data Custom',
            body='With data',
            data={'ticket_id': 42, 'type': 'assignment'},
        )
        self.assertEqual(log.data['ticket_id'], 42)

    def test_subscription_nullable(self):
        log = NotificationLog.objects.create(
            user=self.user,
            title='No Sub',
            body='Body',
            subscription=None,
        )
        self.assertIsNone(log.subscription)

    def test_error_message_blank_allowed(self):
        log = NotificationLog.objects.create(
            user=self.user,
            title='No Error',
            body='Body',
            error_message='',
        )
        self.assertEqual(log.error_message, '')

    def test_ordering_newest_first(self):
        log1 = NotificationLog.objects.create(
            user=self.user, title='Log 1', body='B',
        )
        log2 = NotificationLog.objects.create(
            user=self.user, title='Log 2', body='B',
        )
        logs = list(NotificationLog.objects.filter(user=self.user))
        self.assertEqual(logs[0].pk, log2.pk)  # newest first

    def test_status_choices(self):
        valid = [choice[0] for choice in NotificationLog.STATUS_CHOICES]
        self.assertEqual(valid, ['pending', 'sent', 'failed'])


# ============================================================================
# In-app Notification model (users.Notification)
# ============================================================================

class TestInAppNotificationModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='inapp-notif@test.com')

    def test_create_notification(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            title='Ticket Assigned',
            message='You have been assigned ticket #42',
        )
        self.assertEqual(notif.notification_type, 'ticket_assigned')
        self.assertEqual(notif.title, 'Ticket Assigned')

    def test_is_read_defaults_to_false(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='ticket_commented',
            title='New Comment',
            message='Someone commented on your ticket',
        )
        self.assertFalse(notif.is_read)
        self.assertIsNone(notif.read_at)

    def test_mark_as_read(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            title='Read Test',
            message='Mark me as read',
        )
        notif.mark_as_read()
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.assertIsNotNone(notif.read_at)

    def test_mark_as_read_idempotent(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            title='Idempotent Test',
            message='Read twice',
        )
        notif.mark_as_read()
        first_read_at = notif.read_at
        notif.mark_as_read()  # second call should be no-op
        self.assertEqual(notif.read_at, first_read_at)

    def test_notification_user_relationship(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            title='FK Test',
            message='Belongs to user',
        )
        self.assertEqual(notif.user, self.user)
        self.assertIn(notif, self.user.notifications.all())

    def test_str_representation(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            title='Str Test',
            message='Check str',
        )
        s = str(notif)
        self.assertIn('inapp-notif@test.com', s)

    def test_ordering_newest_first(self):
        n1 = Notification.objects.create(
            user=self.user, notification_type='ticket_assigned',
            title='First', message='First',
        )
        n2 = Notification.objects.create(
            user=self.user, notification_type='ticket_assigned',
            title='Second', message='Second',
        )
        notifs = list(Notification.objects.filter(user=self.user))
        self.assertEqual(notifs[0].pk, n2.pk)  # newest first

    def test_metadata_defaults_to_empty_dict(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            title='Meta Test',
            message='Check metadata',
        )
        self.assertEqual(notif.metadata, {})

    def test_metadata_stores_extra_data(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            title='Meta Custom',
            message='With metadata',
            metadata={'actor_name': 'Jane', 'old_value': 'open'},
        )
        self.assertEqual(notif.metadata['actor_name'], 'Jane')

    def test_ticket_id_nullable(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='message_received',
            title='No Ticket',
            message='Message notification',
            ticket_id=None,
        )
        self.assertIsNone(notif.ticket_id)

    def test_link_url_default_empty(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            title='Link Default',
            message='Check link',
        )
        self.assertEqual(notif.link_url, '')

    def test_notification_type_choices(self):
        valid = [choice[0] for choice in Notification.NOTIFICATION_TYPES]
        self.assertIn('ticket_assigned', valid)
        self.assertIn('message_received', valid)
        self.assertIn('invoice_created', valid)
        self.assertIn('leave_request_submitted', valid)
        self.assertIn('booking_confirmed', valid)
        self.assertIn('call_missed', valid)


# ============================================================================
# NotificationPreference model
# ============================================================================

class TestNotificationPreferenceModel(EchoDeskTenantTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(email='notifpref@test.com')

    def test_create_preference(self):
        pref = NotificationPreference.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
        )
        self.assertTrue(pref.in_app)
        self.assertTrue(pref.sound)
        self.assertTrue(pref.push)

    def test_preference_defaults(self):
        pref = NotificationPreference.objects.create(
            user=self.user,
            notification_type='ticket_commented',
        )
        self.assertTrue(pref.in_app)
        self.assertTrue(pref.sound)
        self.assertTrue(pref.push)

    def test_preference_custom_values(self):
        pref = NotificationPreference.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            in_app=True,
            sound=False,
            push=False,
        )
        self.assertTrue(pref.in_app)
        self.assertFalse(pref.sound)
        self.assertFalse(pref.push)

    def test_unique_together_user_and_type(self):
        NotificationPreference.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            NotificationPreference.objects.create(
                user=self.user,
                notification_type='ticket_assigned',
            )

    def test_str_includes_email_and_type(self):
        pref = NotificationPreference.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
        )
        s = str(pref)
        self.assertIn('notifpref@test.com', s)
        self.assertIn('ticket_assigned', s)

    def test_different_users_same_type(self):
        other = self.create_user(email='other-pref@test.com')
        pref1 = NotificationPreference.objects.create(
            user=self.user, notification_type='ticket_assigned',
        )
        pref2 = NotificationPreference.objects.create(
            user=other, notification_type='ticket_assigned',
        )
        self.assertNotEqual(pref1.pk, pref2.pk)
