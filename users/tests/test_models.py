"""
Tests for the users app models: User, UserManager, TenantGroup, Notification.
"""
from django.utils import timezone
from django.contrib.auth import get_user_model

from users.models import TenantGroup, Notification
from users.tests.conftest import EchoDeskTenantTestCase

User = get_user_model()


class TestUserManager(EchoDeskTenantTestCase):
    """Tests for UserManager.create_user / create_superuser."""

    def test_create_user_sets_email_and_password(self):
        user = User.objects.create_user(
            email='new@test.com', password='pass1234'
        )
        self.assertEqual(user.email, 'new@test.com')
        self.assertTrue(user.check_password('pass1234'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_normalizes_email(self):
        user = User.objects.create_user(
            email='User@EXAMPLE.com', password='pass1234'
        )
        self.assertEqual(user.email, 'User@example.com')

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password='pass1234')

    def test_create_superuser_sets_flags(self):
        su = User.objects.create_superuser(
            email='super@test.com', password='pass1234'
        )
        self.assertTrue(su.is_staff)
        self.assertTrue(su.is_superuser)
        self.assertEqual(su.role, 'admin')

    def test_create_superuser_without_staff_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email='su@test.com', password='p', is_staff=False
            )


class TestUserProperties(EchoDeskTenantTestCase):
    """Tests for User model properties and permission helpers."""

    def test_is_admin_true_for_admin_role(self):
        user = self.create_user(role='admin')
        self.assertTrue(user.is_admin)

    def test_is_admin_true_for_superuser(self):
        user = self.create_user(email='su@test.com', is_superuser=True, role='agent')
        self.assertTrue(user.is_admin)

    def test_is_admin_false_for_agent(self):
        user = self.create_user(role='agent')
        self.assertFalse(user.is_admin)

    def test_is_manager_true_for_manager_and_admin(self):
        mgr = self.create_user(email='mgr@test.com', role='manager')
        adm = self.create_user(email='adm@test.com', role='admin')
        self.assertTrue(mgr.is_manager)
        self.assertTrue(adm.is_manager)

    def test_is_manager_false_for_agent(self):
        user = self.create_user(role='agent')
        self.assertFalse(user.is_manager)

    def test_get_full_name_with_names(self):
        user = self.create_user(first_name='John', last_name='Doe')
        self.assertEqual(user.get_full_name(), 'John Doe')

    def test_get_full_name_fallback_to_email(self):
        user = self.create_user()
        self.assertEqual(user.get_full_name(), user.email)

    def test_str_returns_email(self):
        user = self.create_user()
        self.assertEqual(str(user), user.email)


class TestUserPermissions(EchoDeskTenantTestCase):
    """Tests for User.has_permission()."""

    def test_has_permission_superuser_always_true(self):
        su = self.create_user(email='su@test.com', is_superuser=True)
        self.assertTrue(su.has_permission('manage_users'))
        self.assertTrue(su.has_permission('nonexistent_perm'))

    def test_has_permission_individual_flag(self):
        user = self.create_user(can_manage_users=True)
        self.assertTrue(user.has_permission('manage_users'))

    def test_has_permission_role_based_admin(self):
        admin = self.create_user(email='adm@test.com', role='admin')
        # Admin role gives manage_users via role_permissions
        self.assertTrue(admin.has_permission('manage_users'))
        self.assertTrue(admin.has_permission('manage_groups'))

    def test_has_permission_role_based_manager(self):
        mgr = self.create_user(email='mgr@test.com', role='manager')
        # Manager gets view_all_tickets via role_permissions
        self.assertTrue(mgr.has_permission('view_all_tickets'))
        # Manager does NOT get manage_users (admin only)
        self.assertFalse(mgr.has_permission('manage_users'))

    def test_has_permission_agent_denied(self):
        agent = self.create_user(role='agent')
        self.assertFalse(agent.has_permission('manage_users'))
        self.assertFalse(agent.has_permission('manage_groups'))

    def test_has_permission_not_found_returns_false(self):
        user = self.create_user()
        self.assertFalse(user.has_permission('totally_fake_permission'))

    def test_get_all_permissions_includes_role_and_individual(self):
        admin = self.create_user(
            email='adm@test.com', role='admin', can_export_data=True
        )
        perms = admin.get_all_permissions()
        self.assertIn('manage_users', perms)
        self.assertIn('export_data', perms)

    def test_get_user_permissions_list(self):
        user = self.create_user(can_view_all_tickets=True, can_export_data=True)
        perms = user.get_user_permissions_list()
        self.assertIn('view_all_tickets', perms)
        self.assertIn('export_data', perms)
        self.assertNotIn('manage_users', perms)

    def test_get_user_permissions_includes_social(self):
        user = self.create_user(
            email='social@test.com',
            can_manage_social_connections=True,
            can_view_social_messages=True,
            can_send_social_messages=True,
            can_manage_social_settings=True,
        )
        perms = user.get_user_permissions_list()
        self.assertIn('manage_social_connections', perms)
        self.assertIn('view_social_messages', perms)
        self.assertIn('send_social_messages', perms)
        self.assertIn('manage_social_settings', perms)


class TestTenantGroup(EchoDeskTenantTestCase):
    """Tests for TenantGroup model methods."""

    def test_str_returns_name(self):
        group = self.create_tenant_group(name='Support')
        self.assertEqual(str(group), 'Support')

    def test_get_feature_keys_empty(self):
        group = self.create_tenant_group(name='Empty Group')
        self.assertEqual(group.get_feature_keys(), [])

    def test_has_feature_false_when_no_features(self):
        group = self.create_tenant_group(name='No Features')
        self.assertFalse(group.has_feature('ticket_management'))

    def test_unique_name_constraint(self):
        self.create_tenant_group(name='Unique')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            TenantGroup.objects.create(name='Unique')


class TestNotification(EchoDeskTenantTestCase):
    """Tests for Notification model."""

    def setUp(self):
        super().setUp()
        self.user = self.create_user()

    def test_create_notification(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            title='Test Notification',
            message='You have been assigned a ticket.',
        )
        self.assertEqual(notif.user, self.user)
        self.assertEqual(notif.notification_type, 'ticket_assigned')
        self.assertFalse(notif.is_read)

    def test_mark_as_read(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            title='Test',
            message='Test message',
        )
        self.assertFalse(notif.is_read)
        self.assertIsNone(notif.read_at)

        notif.mark_as_read()
        notif.refresh_from_db()

        self.assertTrue(notif.is_read)
        self.assertIsNotNone(notif.read_at)

    def test_notification_ordering(self):
        """Notifications are ordered newest first."""
        n1 = Notification.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            title='First',
            message='First message',
        )
        n2 = Notification.objects.create(
            user=self.user,
            notification_type='ticket_commented',
            title='Second',
            message='Second message',
        )
        notifs = list(Notification.objects.filter(user=self.user))
        self.assertEqual(notifs[0].id, n2.id)
        self.assertEqual(notifs[1].id, n1.id)

    def test_str_representation(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='ticket_assigned',
            title='Test',
            message='Msg',
        )
        self.assertIn('Ticket Assigned', str(notif))
        self.assertIn(self.user.email, str(notif))
