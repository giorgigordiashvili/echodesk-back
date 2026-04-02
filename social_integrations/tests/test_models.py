"""
Tests for social_integrations models.
Verifies creation, str methods, defaults, constraints.
"""
from django.db import IntegrityError
from django.utils import timezone
from social_integrations.tests.conftest import SocialIntegrationTestCase
from social_integrations.models import (
    SocialIntegrationSettings, Client, EmailConnection,
)


class TestFacebookModels(SocialIntegrationTestCase):

    def test_fb_connection_str(self):
        conn = self.create_fb_connection(page_name='My Page')
        self.assertIn('My Page', str(conn))

    def test_fb_connection_defaults(self):
        conn = self.create_fb_connection()
        self.assertTrue(conn.is_active)
        self.assertFalse(conn.has_publishing_permission)

    def test_fb_message_str_with_text(self):
        msg = self.create_fb_message(message_text='Hello World')
        self.assertIn('Hello World', str(msg))

    def test_fb_message_str_with_attachment(self):
        msg = self.create_fb_message(message_text='', attachment_type='image')
        self.assertIn('[image]', str(msg))

    def test_fb_connection_unique_page_id(self):
        self.create_fb_connection(page_id='duplicate_page')
        with self.assertRaises(IntegrityError):
            self.create_fb_connection(page_id='duplicate_page')


class TestInstagramModels(SocialIntegrationTestCase):

    def test_ig_connection_str(self):
        conn = self.create_ig_connection(username='coolshop')
        self.assertEqual(str(conn), '@coolshop - Instagram')

    def test_ig_message_str(self):
        conn = self.create_ig_connection()
        msg = self.create_ig_message(account_connection=conn, message_text='Hi IG')
        self.assertIn('Hi IG', str(msg))


class TestWhatsAppModels(SocialIntegrationTestCase):

    def test_wa_account_str(self):
        acct = self.create_wa_account(business_name='TestBiz', phone_number='+1234')
        self.assertIn('TestBiz', str(acct))

    def test_wa_message_str(self):
        msg = self.create_wa_message(message_text='WA msg')
        self.assertIn('WA msg', str(msg))

    def test_wa_template_str(self):
        tmpl = self.create_wa_template(name='order_confirm')
        self.assertIn('order_confirm', str(tmpl))

    def test_wa_contact_str(self):
        acct = self.create_wa_account()
        contact = self.create_wa_contact(account=acct, profile_name='John')
        self.assertIn('John', str(contact))


class TestEmailModels(SocialIntegrationTestCase):

    def test_email_connection_str(self):
        conn = self.create_email_connection(email_address='hello@test.com', display_name='Hello')
        self.assertEqual(str(conn), 'Hello')

    def test_email_message_str(self):
        msg = self.create_email_message(subject='Invoice #123')
        self.assertIn('Invoice #123', str(msg))

    def test_email_draft_str(self):
        draft = self.create_email_draft(subject='My Draft')
        self.assertEqual(str(draft), 'Draft: My Draft')

    def test_email_connection_password(self):
        conn = self.create_email_connection()
        conn.set_password('secret123')
        conn.save()
        self.assertEqual(conn.get_password(), 'secret123')


class TestSettingsModel(SocialIntegrationTestCase):

    def test_settings_str(self):
        s = self.create_settings(refresh_interval=3000)
        self.assertIn('3000', str(s))

    def test_settings_clamps_min(self):
        s = self.create_settings(refresh_interval=100)
        self.assertEqual(s.refresh_interval, 1000)

    def test_settings_clamps_max(self):
        s = self.create_settings(refresh_interval=999999)
        self.assertEqual(s.refresh_interval, 60000)


class TestChatAssignmentModel(SocialIntegrationTestCase):

    def test_assignment_str(self):
        user = self.create_user(email='assign-str@test.com')
        assignment = self.create_chat_assignment(user=user, platform='whatsapp')
        self.assertIn('whatsapp', str(assignment))

    def test_full_conversation_id_facebook(self):
        user = self.create_user(email='fci-fb@test.com')
        a = self.create_chat_assignment(user=user, platform='facebook', conversation_id='c1', account_id='p1')
        self.assertEqual(a.full_conversation_id, 'fb_p1_c1')

    def test_full_conversation_id_email(self):
        user = self.create_user(email='fci-email@test.com')
        a = self.create_chat_assignment(user=user, platform='email', conversation_id='thread1', account_id='conn1')
        self.assertEqual(a.full_conversation_id, 'email_conn1_thread1')


class TestChatRatingModel(SocialIntegrationTestCase):

    def test_rating_str_with_score(self):
        r = self.create_chat_rating(rating=4)
        self.assertIn('4/5', str(r))

    def test_rating_str_pending(self):
        r = self.create_chat_rating(rating=0)
        self.assertIn('Pending', str(r))


class TestClientModel(SocialIntegrationTestCase):

    def test_client_str(self):
        c = self.create_client(name='Jane Doe')
        self.assertEqual(str(c), 'Jane Doe')

    def test_client_full_name(self):
        c = self.create_client(first_name='Jane', last_name='Doe')
        self.assertEqual(c.full_name, 'Jane Doe')

    def test_client_password(self):
        c = self.create_client()
        c.set_password('mypass')
        self.assertTrue(c.check_password('mypass'))
        self.assertFalse(c.check_password('wrong'))


class TestQuickReplyModel(SocialIntegrationTestCase):

    def test_quick_reply_str(self):
        qr = self.create_quick_reply(title='Thanks')
        self.assertEqual(str(qr), 'Thanks')


class TestAutoPostModels(SocialIntegrationTestCase):

    def test_auto_post_settings_str(self):
        s = self.create_auto_post_settings(is_enabled=True)
        self.assertIn('True', str(s))

    def test_auto_post_content_str(self):
        c = self.create_auto_post_content(status='draft')
        self.assertIn('draft', str(c))


class TestConversationArchiveModel(SocialIntegrationTestCase):

    def test_archive_str(self):
        user = self.create_user(email='archiver@test.com')
        a = self.create_conversation_archive(user=user, platform='instagram')
        self.assertIn('instagram', str(a))
