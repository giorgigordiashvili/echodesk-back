"""
Tests for Email-related models.
Verifies creation, defaults, constraints, ordering, and relationships
for EmailConnection, EmailMessage, EmailDraft, EmailConnectionUserAssignment,
and EmailSignature.
"""
from django.db import IntegrityError
from django.utils import timezone
from social_integrations.tests.conftest import SocialIntegrationTestCase
from social_integrations.models import (
    EmailConnection, EmailMessage, EmailDraft,
    EmailConnectionUserAssignment, EmailSignature,
)


class TestEmailConnectionModel(SocialIntegrationTestCase):

    def test_email_connection_creation(self):
        """Creates an EmailConnection with all fields populated."""
        conn = self.create_email_connection(
            email_address='full@example.com',
            display_name='Full Connection',
            imap_server='imap.full.com',
            imap_port=993,
            smtp_server='smtp.full.com',
            smtp_port=587,
        )
        self.assertEqual(conn.email_address, 'full@example.com')
        self.assertEqual(conn.display_name, 'Full Connection')
        self.assertEqual(conn.imap_server, 'imap.full.com')
        self.assertEqual(conn.imap_port, 993)
        self.assertEqual(conn.smtp_server, 'smtp.full.com')
        self.assertEqual(conn.smtp_port, 587)
        self.assertTrue(conn.is_active)
        self.assertIsNotNone(conn.created_at)
        self.assertIsNotNone(conn.updated_at)

    def test_email_connection_defaults(self):
        """Verifies default values on EmailConnection fields."""
        conn = self.create_email_connection()
        self.assertTrue(conn.is_active)
        self.assertTrue(conn.imap_use_ssl)
        self.assertTrue(conn.smtp_use_tls)
        self.assertFalse(conn.smtp_use_ssl)
        self.assertEqual(conn.sync_folder, 'INBOX')
        self.assertEqual(conn.sync_days_back, 365)
        self.assertFalse(conn.signature_enabled)
        self.assertEqual(conn.signature_html, '')
        self.assertEqual(conn.signature_text, '')
        self.assertIsNone(conn.last_sync_at)
        self.assertEqual(conn.last_sync_error, '')

    def test_email_connection_str_with_display_name(self):
        """__str__ returns display_name when set."""
        conn = self.create_email_connection(display_name='Support')
        self.assertEqual(str(conn), 'Support')

    def test_email_connection_str_without_display_name(self):
        """__str__ falls back to email_address when display_name is empty."""
        conn = self.create_email_connection(
            email_address='fallback@example.com', display_name='',
        )
        self.assertEqual(str(conn), 'fallback@example.com')

    def test_email_connection_set_get_password(self):
        """set_password encrypts and get_password decrypts correctly."""
        conn = self.create_email_connection()
        conn.set_password('my_secret_pass')
        conn.save()
        conn.refresh_from_db()
        self.assertEqual(conn.get_password(), 'my_secret_pass')

    def test_email_connection_get_password_bad_signature(self):
        """get_password returns None when the encrypted_password is invalid."""
        conn = self.create_email_connection()
        conn.encrypted_password = 'not-a-valid-signed-value'
        conn.save()
        self.assertIsNone(conn.get_password())

    def test_email_connection_cascade_deletes_messages(self):
        """Deleting a connection cascades to its messages."""
        conn = self.create_email_connection()
        msg = self.create_email_message(connection=conn)
        msg_id = msg.id
        conn.delete()
        self.assertFalse(EmailMessage.objects.filter(id=msg_id).exists())

    def test_email_connection_cascade_deletes_drafts(self):
        """Deleting a connection cascades to its drafts."""
        conn = self.create_email_connection()
        user = self.create_user(email='cascade-draft@test.com')
        draft = self.create_email_draft(connection=conn, created_by=user)
        draft_id = draft.id
        conn.delete()
        self.assertFalse(EmailDraft.objects.filter(id=draft_id).exists())


class TestEmailMessageModel(SocialIntegrationTestCase):

    def test_email_message_creation(self):
        """Creates an EmailMessage with required fields."""
        conn = self.create_email_connection()
        msg = self.create_email_message(
            connection=conn,
            subject='Test Subject',
            from_email='sender@example.com',
            from_name='Sender Name',
        )
        self.assertEqual(msg.subject, 'Test Subject')
        self.assertEqual(msg.from_email, 'sender@example.com')
        self.assertEqual(msg.from_name, 'Sender Name')
        self.assertEqual(msg.connection, conn)
        self.assertIsNotNone(msg.message_id)
        self.assertIsNotNone(msg.timestamp)
        self.assertIsNotNone(msg.created_at)

    def test_email_message_folder_default(self):
        """Default folder is 'INBOX'."""
        conn = self.create_email_connection()
        msg = self.create_email_message(connection=conn)
        self.assertEqual(msg.folder, 'INBOX')

    def test_email_message_custom_folder(self):
        """Folder can be set to a custom value."""
        conn = self.create_email_connection()
        msg = self.create_email_message(connection=conn, folder='Sent')
        self.assertEqual(msg.folder, 'Sent')

    def test_email_message_thread_id(self):
        """Messages with the same thread_id are queryable as a group."""
        conn = self.create_email_connection()
        msg1 = self.create_email_message(
            connection=conn,
            thread_id='thread-ABC',
            message_id='<abc1@test.com>',
        )
        msg2 = self.create_email_message(
            connection=conn,
            thread_id='thread-ABC',
            message_id='<abc2@test.com>',
        )
        msg3 = self.create_email_message(
            connection=conn,
            thread_id='thread-XYZ',
            message_id='<xyz1@test.com>',
        )
        thread_msgs = EmailMessage.objects.filter(thread_id='thread-ABC')
        self.assertEqual(thread_msgs.count(), 2)
        self.assertIn(msg1, thread_msgs)
        self.assertIn(msg2, thread_msgs)
        self.assertNotIn(msg3, thread_msgs)

    def test_email_message_boolean_defaults(self):
        """Boolean flags default to False."""
        conn = self.create_email_connection()
        msg = self.create_email_message(connection=conn)
        self.assertFalse(msg.is_from_business)
        self.assertFalse(msg.is_read)
        self.assertFalse(msg.is_starred)
        self.assertFalse(msg.is_answered)
        self.assertFalse(msg.is_draft)
        self.assertFalse(msg.is_read_by_staff)
        self.assertFalse(msg.is_deleted)

    def test_email_message_json_defaults(self):
        """JSON fields default to empty lists."""
        conn = self.create_email_connection()
        msg = EmailMessage.objects.create(
            connection=conn,
            message_id=f'<json-default@test.com>',
            from_email='sender@test.com',
            timestamp=timezone.now(),
        )
        self.assertEqual(msg.cc_emails, [])
        self.assertEqual(msg.bcc_emails, [])
        self.assertEqual(msg.labels, [])
        self.assertEqual(msg.attachments, [])

    def test_email_message_unique_message_id(self):
        """message_id field has a unique constraint."""
        conn = self.create_email_connection()
        self.create_email_message(
            connection=conn, message_id='<unique-test@test.com>',
        )
        with self.assertRaises(IntegrityError):
            self.create_email_message(
                connection=conn, message_id='<unique-test@test.com>',
            )

    def test_email_message_ordering(self):
        """Messages are ordered by -timestamp (newest first)."""
        conn = self.create_email_connection()
        now = timezone.now()
        old = self.create_email_message(
            connection=conn,
            timestamp=now - timezone.timedelta(hours=2),
            message_id='<old@test.com>',
        )
        mid = self.create_email_message(
            connection=conn,
            timestamp=now - timezone.timedelta(hours=1),
            message_id='<mid@test.com>',
        )
        new = self.create_email_message(
            connection=conn,
            timestamp=now,
            message_id='<new@test.com>',
        )
        messages = list(EmailMessage.objects.filter(connection=conn))
        self.assertEqual(messages[0].id, new.id)
        self.assertEqual(messages[1].id, mid.id)
        self.assertEqual(messages[2].id, old.id)

    def test_email_message_is_deleted_filter(self):
        """Default queryset includes all; filtering is_deleted=False excludes soft-deleted."""
        conn = self.create_email_connection()
        active = self.create_email_message(
            connection=conn, is_deleted=False, message_id='<active-flt@test.com>',
        )
        deleted = self.create_email_message(
            connection=conn, is_deleted=True, message_id='<deleted-flt@test.com>',
        )
        all_msgs = EmailMessage.objects.filter(connection=conn)
        self.assertEqual(all_msgs.count(), 2)
        active_msgs = EmailMessage.objects.filter(connection=conn, is_deleted=False)
        self.assertEqual(active_msgs.count(), 1)
        self.assertEqual(active_msgs.first().id, active.id)

    def test_email_message_str(self):
        """__str__ includes subject and sender info."""
        conn = self.create_email_connection()
        msg = self.create_email_message(
            connection=conn,
            subject='Hello World',
            from_name='John Doe',
        )
        s = str(msg)
        self.assertIn('Hello World', s)
        self.assertIn('John Doe', s)

    def test_email_message_soft_delete_fields(self):
        """Soft-delete populates deleted_at and deleted_by."""
        conn = self.create_email_connection()
        user = self.create_user(email='deleter@test.com')
        msg = self.create_email_message(connection=conn)
        now = timezone.now()
        msg.is_deleted = True
        msg.deleted_at = now
        msg.deleted_by = user
        msg.save()
        msg.refresh_from_db()
        self.assertTrue(msg.is_deleted)
        self.assertIsNotNone(msg.deleted_at)
        self.assertEqual(msg.deleted_by, user)

    def test_email_message_to_emails_json(self):
        """to_emails stores JSON array of recipient dicts."""
        conn = self.create_email_connection()
        recipients = [
            {'email': 'a@test.com', 'name': 'Alice'},
            {'email': 'b@test.com', 'name': 'Bob'},
        ]
        msg = self.create_email_message(connection=conn, to_emails=recipients)
        msg.refresh_from_db()
        self.assertEqual(len(msg.to_emails), 2)
        self.assertEqual(msg.to_emails[0]['email'], 'a@test.com')
        self.assertEqual(msg.to_emails[1]['name'], 'Bob')


class TestEmailDraftModel(SocialIntegrationTestCase):

    def test_email_draft_creation(self):
        """Creates an EmailDraft with all expected fields."""
        conn = self.create_email_connection()
        user = self.create_user(email='draft-create@test.com')
        draft = self.create_email_draft(
            connection=conn,
            created_by=user,
            subject='Draft Subject',
            body_text='Draft body',
        )
        self.assertEqual(draft.connection, conn)
        self.assertEqual(draft.created_by, user)
        self.assertEqual(draft.subject, 'Draft Subject')
        self.assertEqual(draft.body_text, 'Draft body')
        self.assertIsNotNone(draft.created_at)
        self.assertIsNotNone(draft.updated_at)

    def test_email_draft_defaults(self):
        """Draft boolean and JSON fields have correct defaults."""
        conn = self.create_email_connection()
        user = self.create_user(email='draft-defaults@test.com')
        draft = self.create_email_draft(connection=conn, created_by=user)
        self.assertFalse(draft.is_reply_all)
        self.assertFalse(draft.is_forward)
        self.assertIsNone(draft.reply_to_message)
        self.assertEqual(draft.cc_emails, [])
        self.assertEqual(draft.bcc_emails, [])
        self.assertEqual(draft.attachments, [])

    def test_email_draft_reply_to(self):
        """Draft can reference a reply_to_message."""
        conn = self.create_email_connection()
        user = self.create_user(email='draft-reply@test.com')
        original_msg = self.create_email_message(
            connection=conn, subject='Original',
        )
        draft = self.create_email_draft(
            connection=conn,
            created_by=user,
            reply_to_message=original_msg,
            is_reply_all=True,
        )
        self.assertEqual(draft.reply_to_message, original_msg)
        self.assertTrue(draft.is_reply_all)

    def test_email_draft_reply_to_set_null(self):
        """Deleting the original message sets reply_to_message to NULL (not cascade)."""
        conn = self.create_email_connection()
        user = self.create_user(email='draft-setnull@test.com')
        original_msg = self.create_email_message(connection=conn)
        draft = self.create_email_draft(
            connection=conn, created_by=user, reply_to_message=original_msg,
        )
        original_msg.delete()
        draft.refresh_from_db()
        self.assertIsNone(draft.reply_to_message)

    def test_email_draft_ordering(self):
        """Drafts are ordered by -updated_at (most recently updated first)."""
        conn = self.create_email_connection()
        user = self.create_user(email='draft-order@test.com')
        d1 = self.create_email_draft(
            connection=conn, created_by=user, subject='First',
        )
        d2 = self.create_email_draft(
            connection=conn, created_by=user, subject='Second',
        )
        # Touch d1 to make its updated_at newer
        d1.subject = 'First Updated'
        d1.save()
        drafts = list(EmailDraft.objects.filter(created_by=user))
        self.assertEqual(drafts[0].id, d1.id)

    def test_email_draft_str(self):
        """__str__ includes subject."""
        conn = self.create_email_connection()
        user = self.create_user(email='draft-str@test.com')
        draft = self.create_email_draft(
            connection=conn, created_by=user, subject='My Draft',
        )
        self.assertEqual(str(draft), 'Draft: My Draft')

    def test_email_draft_str_no_subject(self):
        """__str__ shows 'No subject' when subject is empty."""
        conn = self.create_email_connection()
        user = self.create_user(email='draft-nosub@test.com')
        draft = self.create_email_draft(
            connection=conn, created_by=user, subject='',
        )
        self.assertEqual(str(draft), 'Draft: No subject')

    def test_email_draft_cascade_on_user_delete(self):
        """Deleting the owning user cascades to their drafts."""
        conn = self.create_email_connection()
        user = self.create_user(email='draft-cascade@test.com')
        draft = self.create_email_draft(connection=conn, created_by=user)
        draft_id = draft.id
        user.delete()
        self.assertFalse(EmailDraft.objects.filter(id=draft_id).exists())


class TestEmailConnectionUserAssignmentModel(SocialIntegrationTestCase):

    def test_email_connection_assignment(self):
        """Creates an assignment linking a user to a connection."""
        conn = self.create_email_connection()
        user = self.create_user(email='assign-user@test.com')
        admin = self.create_admin(email='assign-admin@test.com')
        assignment = EmailConnectionUserAssignment.objects.create(
            connection=conn, user=user, assigned_by=admin,
        )
        self.assertEqual(assignment.connection, conn)
        self.assertEqual(assignment.user, user)
        self.assertEqual(assignment.assigned_by, admin)
        self.assertIsNotNone(assignment.assigned_at)

    def test_email_connection_assignment_unique(self):
        """The (connection, user) pair must be unique."""
        conn = self.create_email_connection()
        user = self.create_user(email='assign-unique@test.com')
        EmailConnectionUserAssignment.objects.create(
            connection=conn, user=user,
        )
        with self.assertRaises(IntegrityError):
            EmailConnectionUserAssignment.objects.create(
                connection=conn, user=user,
            )

    def test_email_connection_assignment_str(self):
        """__str__ shows user email -> connection email."""
        conn = self.create_email_connection(email_address='conn-str@example.com')
        user = self.create_user(email='user-str@test.com')
        assignment = EmailConnectionUserAssignment.objects.create(
            connection=conn, user=user,
        )
        s = str(assignment)
        self.assertIn('user-str@test.com', s)
        self.assertIn('conn-str@example.com', s)

    def test_assignment_cascade_on_connection_delete(self):
        """Deleting the connection cascades to assignments."""
        conn = self.create_email_connection()
        user = self.create_user(email='assign-cascade-conn@test.com')
        assignment = EmailConnectionUserAssignment.objects.create(
            connection=conn, user=user,
        )
        aid = assignment.id
        conn.delete()
        self.assertFalse(
            EmailConnectionUserAssignment.objects.filter(id=aid).exists()
        )

    def test_assignment_cascade_on_user_delete(self):
        """Deleting the user cascades to their assignments."""
        conn = self.create_email_connection()
        user = self.create_user(email='assign-cascade-user@test.com')
        assignment = EmailConnectionUserAssignment.objects.create(
            connection=conn, user=user,
        )
        aid = assignment.id
        user.delete()
        self.assertFalse(
            EmailConnectionUserAssignment.objects.filter(id=aid).exists()
        )

    def test_assignment_assigned_by_set_null(self):
        """Deleting the assigning admin sets assigned_by to NULL."""
        conn = self.create_email_connection()
        user = self.create_user(email='assign-setnull-user@test.com')
        admin = self.create_admin(email='assign-setnull-admin@test.com')
        assignment = EmailConnectionUserAssignment.objects.create(
            connection=conn, user=user, assigned_by=admin,
        )
        admin.delete()
        assignment.refresh_from_db()
        self.assertIsNone(assignment.assigned_by)

    def test_multiple_users_one_connection(self):
        """Multiple users can be assigned to the same connection."""
        conn = self.create_email_connection()
        u1 = self.create_user(email='multi-assign-1@test.com')
        u2 = self.create_user(email='multi-assign-2@test.com')
        EmailConnectionUserAssignment.objects.create(connection=conn, user=u1)
        EmailConnectionUserAssignment.objects.create(connection=conn, user=u2)
        self.assertEqual(
            EmailConnectionUserAssignment.objects.filter(connection=conn).count(), 2,
        )

    def test_one_user_multiple_connections(self):
        """One user can be assigned to multiple connections."""
        conn1 = self.create_email_connection(email_address='multi-conn-1@example.com')
        conn2 = self.create_email_connection(email_address='multi-conn-2@example.com')
        user = self.create_user(email='multi-conn-user@test.com')
        EmailConnectionUserAssignment.objects.create(connection=conn1, user=user)
        EmailConnectionUserAssignment.objects.create(connection=conn2, user=user)
        self.assertEqual(
            EmailConnectionUserAssignment.objects.filter(user=user).count(), 2,
        )


class TestEmailSignatureModel(SocialIntegrationTestCase):

    def test_email_signature_creation(self):
        """Creates an EmailSignature with all fields."""
        user = self.create_user(email='sig-creator@test.com')
        sig = EmailSignature.objects.create(
            sender_name='Support Team',
            signature_html='<b>Thanks</b>',
            signature_text='Thanks',
            is_enabled=True,
            include_on_reply=False,
            created_by=user,
        )
        self.assertEqual(sig.sender_name, 'Support Team')
        self.assertEqual(sig.signature_html, '<b>Thanks</b>')
        self.assertEqual(sig.signature_text, 'Thanks')
        self.assertTrue(sig.is_enabled)
        self.assertFalse(sig.include_on_reply)
        self.assertEqual(sig.created_by, user)
        self.assertIsNotNone(sig.created_at)
        self.assertIsNotNone(sig.updated_at)

    def test_email_signature_defaults(self):
        """Verifies default values for EmailSignature fields."""
        sig = EmailSignature.objects.create()
        self.assertEqual(sig.sender_name, '')
        self.assertEqual(sig.signature_html, '')
        self.assertEqual(sig.signature_text, '')
        self.assertTrue(sig.is_enabled)
        self.assertTrue(sig.include_on_reply)
        self.assertIsNone(sig.created_by)

    def test_email_signature_str_enabled(self):
        """__str__ shows 'enabled' status."""
        sig = EmailSignature.objects.create(is_enabled=True)
        self.assertIn('enabled', str(sig))

    def test_email_signature_str_disabled(self):
        """__str__ shows 'disabled' status."""
        sig = EmailSignature.objects.create(is_enabled=False)
        self.assertIn('disabled', str(sig))

    def test_email_signature_created_by_set_null(self):
        """Deleting the creator sets created_by to NULL."""
        user = self.create_user(email='sig-setnull@test.com')
        sig = EmailSignature.objects.create(created_by=user)
        user.delete()
        sig.refresh_from_db()
        self.assertIsNone(sig.created_by)
