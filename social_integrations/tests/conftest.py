"""
Shared test infrastructure for social_integrations app tests.
Extends EchoDeskTenantTestCase with social-specific helpers.
"""
from unittest.mock import patch
from django.utils import timezone
from users.tests.conftest import EchoDeskTenantTestCase
from social_integrations.models import (
    FacebookPageConnection, FacebookMessage,
    InstagramAccountConnection, InstagramMessage,
    WhatsAppBusinessAccount, WhatsAppMessage, WhatsAppMessageTemplate,
    WhatsAppContact, SocialIntegrationSettings, ConversationAutoReply,
    ChatAssignment, ChatRating, ConversationArchive,
    EmailConnection, EmailMessage, EmailDraft, EmailConnectionUserAssignment,
    TikTokShopAccount, TikTokMessage,
    EmailSignature, QuickReply,
    Client, SocialClientCustomField, SocialClientCustomFieldValue, SocialAccount,
    AutoPostSettings, AutoPostContent,
)


class SocialIntegrationTestCase(EchoDeskTenantTestCase):
    """
    Social-integration-specific test case.
    Patches User.has_feature → True so tests don't need full subscription setup.
    Provides factory helpers for all social_integrations models.
    """

    def setUp(self):
        super().setUp()
        self._feature_patcher = patch(
            'users.models.User.has_feature', return_value=True
        )
        self._feature_patcher.start()

    def tearDown(self):
        self._feature_patcher.stop()
        super().tearDown()

    # ── Counters for unique values ──

    _counter = 0

    @classmethod
    def _next(cls):
        cls._counter += 1
        return cls._counter

    # ── Facebook factories ──

    def create_fb_connection(self, page_id=None, page_name='Test Page', **kwargs):
        n = self._next()
        defaults = {
            'page_id': page_id or f'page_{n}',
            'page_name': page_name,
            'page_access_token': f'token_{n}',
        }
        defaults.update(kwargs)
        return FacebookPageConnection.objects.create(**defaults)

    def create_fb_message(self, page_connection=None, sender_id=None, **kwargs):
        n = self._next()
        if page_connection is None:
            page_connection = self.create_fb_connection()
        defaults = {
            'page_connection': page_connection,
            'message_id': f'mid_{n}',
            'sender_id': sender_id or f'sender_{n}',
            'sender_name': f'Sender {n}',
            'message_text': f'Hello {n}',
            'timestamp': timezone.now(),
        }
        defaults.update(kwargs)
        return FacebookMessage.objects.create(**defaults)

    # ── Instagram factories ──

    def create_ig_connection(self, instagram_account_id=None, username='testuser', fb_page=None, **kwargs):
        n = self._next()
        defaults = {
            'instagram_account_id': instagram_account_id or f'ig_{n}',
            'username': username,
            'access_token': f'ig_token_{n}',
        }
        if fb_page:
            defaults['facebook_page'] = fb_page
        defaults.update(kwargs)
        return InstagramAccountConnection.objects.create(**defaults)

    def create_ig_message(self, account_connection=None, sender_id=None, **kwargs):
        n = self._next()
        if account_connection is None:
            account_connection = self.create_ig_connection()
        defaults = {
            'account_connection': account_connection,
            'message_id': f'ig_mid_{n}',
            'sender_id': sender_id or f'ig_sender_{n}',
            'sender_username': f'user{n}',
            'message_text': f'IG Hello {n}',
            'timestamp': timezone.now(),
        }
        defaults.update(kwargs)
        return InstagramMessage.objects.create(**defaults)

    # ── WhatsApp factories ──

    def create_wa_account(self, waba_id=None, **kwargs):
        n = self._next()
        defaults = {
            'waba_id': waba_id or f'waba_{n}',
            'business_name': f'Business {n}',
            'phone_number_id': f'phone_id_{n}',
            'phone_number': f'+1555000{n:04d}',
            'access_token': f'wa_token_{n}',
        }
        defaults.update(kwargs)
        return WhatsAppBusinessAccount.objects.create(**defaults)

    def create_wa_message(self, business_account=None, from_number=None, **kwargs):
        n = self._next()
        if business_account is None:
            business_account = self.create_wa_account()
        defaults = {
            'business_account': business_account,
            'message_id': f'wamid_{n}',
            'from_number': from_number or f'+1555{n:07d}',
            'to_number': business_account.phone_number,
            'message_text': f'WA Hello {n}',
            'timestamp': timezone.now(),
        }
        defaults.update(kwargs)
        return WhatsAppMessage.objects.create(**defaults)

    def create_wa_template(self, business_account=None, name=None, **kwargs):
        n = self._next()
        if business_account is None:
            business_account = self.create_wa_account()
        defaults = {
            'business_account': business_account,
            'name': name or f'template_{n}',
            'language': 'en',
            'status': 'APPROVED',
            'category': 'UTILITY',
        }
        defaults.update(kwargs)
        return WhatsAppMessageTemplate.objects.create(**defaults)

    def create_wa_contact(self, account=None, wa_id=None, **kwargs):
        n = self._next()
        if account is None:
            account = self.create_wa_account()
        defaults = {
            'account': account,
            'wa_id': wa_id or f'contact_{n}',
            'profile_name': f'Contact {n}',
        }
        defaults.update(kwargs)
        return WhatsAppContact.objects.create(**defaults)

    # ── Email factories ──

    def create_email_connection(self, email_address=None, **kwargs):
        n = self._next()
        defaults = {
            'email_address': email_address or f'test{n}@example.com',
            'display_name': f'Test Email {n}',
            'imap_server': 'imap.example.com',
            'imap_port': 993,
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'username': f'test{n}@example.com',
            'encrypted_password': 'dummy_encrypted',
        }
        defaults.update(kwargs)
        return EmailConnection.objects.create(**defaults)

    def create_email_message(self, connection=None, **kwargs):
        n = self._next()
        if connection is None:
            connection = self.create_email_connection()
        defaults = {
            'connection': connection,
            'message_id': f'<msg{n}@example.com>',
            'thread_id': f'thread_{n}',
            'from_email': f'from{n}@example.com',
            'from_name': f'From User {n}',
            'to_emails': [{'email': connection.email_address, 'name': connection.display_name}],
            'subject': f'Test Subject {n}',
            'body_text': f'Test body {n}',
            'timestamp': timezone.now(),
        }
        defaults.update(kwargs)
        return EmailMessage.objects.create(**defaults)

    def create_email_draft(self, connection=None, created_by=None, **kwargs):
        n = self._next()
        if connection is None:
            connection = self.create_email_connection()
        if created_by is None:
            created_by = self.create_user(email=f'draft-user-{n}@test.com')
        defaults = {
            'connection': connection,
            'to_emails': [{'email': f'to{n}@example.com'}],
            'subject': f'Draft Subject {n}',
            'body_text': f'Draft body {n}',
            'created_by': created_by,
        }
        defaults.update(kwargs)
        return EmailDraft.objects.create(**defaults)

    # ── TikTok factories ──

    def create_tiktok_account(self, open_id=None, **kwargs):
        n = self._next()
        defaults = {
            'open_id': open_id or f'tiktok_{n}',
            'seller_name': f'TikTok Seller {n}',
            'access_token': f'tt_access_{n}',
            'refresh_token': f'tt_refresh_{n}',
            'token_expires_at': timezone.now() + timezone.timedelta(days=30),
        }
        defaults.update(kwargs)
        return TikTokShopAccount.objects.create(**defaults)

    def create_tiktok_message(self, shop_account=None, **kwargs):
        n = self._next()
        if shop_account is None:
            shop_account = self.create_tiktok_account()
        defaults = {
            'shop_account': shop_account,
            'message_id': f'tt_mid_{n}',
            'conversation_id': f'tt_conv_{n}',
            'sender_id': f'tt_sender_{n}',
            'message_text': f'TT Hello {n}',
            'timestamp': timezone.now(),
        }
        defaults.update(kwargs)
        return TikTokMessage.objects.create(**defaults)

    # ── Settings, assignments, ratings ──

    def create_settings(self, **kwargs):
        defaults = {
            'refresh_interval': 5000,
        }
        defaults.update(kwargs)
        return SocialIntegrationSettings.objects.create(**defaults)

    def create_chat_assignment(self, user=None, platform='facebook', conversation_id=None, account_id=None, **kwargs):
        n = self._next()
        if user is None:
            user = self.create_user(email=f'assign-user-{n}@test.com')
        defaults = {
            'platform': platform,
            'conversation_id': conversation_id or f'conv_{n}',
            'account_id': account_id or f'acc_{n}',
            'assigned_user': user,
            'status': 'active',
        }
        defaults.update(kwargs)
        return ChatAssignment.objects.create(**defaults)

    def create_chat_rating(self, rated_user=None, **kwargs):
        n = self._next()
        if rated_user is None:
            rated_user = self.create_user(email=f'rated-user-{n}@test.com')
        defaults = {
            'rated_user': rated_user,
            'platform': 'facebook',
            'conversation_id': f'conv_{n}',
            'account_id': f'acc_{n}',
            'rating': 5,
        }
        defaults.update(kwargs)
        return ChatRating.objects.create(**defaults)

    # ── Client / SocialAccount factories ──

    def create_client(self, name=None, **kwargs):
        n = self._next()
        defaults = {
            'name': name or f'Client {n}',
        }
        defaults.update(kwargs)
        return Client.objects.create(**defaults)

    def create_social_account(self, client=None, platform='facebook', platform_id=None, account_connection_id=None, **kwargs):
        n = self._next()
        if client is None:
            client = self.create_client()
        defaults = {
            'client': client,
            'platform': platform,
            'platform_id': platform_id or f'plat_{n}',
            'account_connection_id': account_connection_id or f'conn_{n}',
            'display_name': f'Account {n}',
        }
        defaults.update(kwargs)
        return SocialAccount.objects.create(**defaults)

    # ── Quick replies, signatures, archives ──

    def create_quick_reply(self, title=None, message='Hello!', created_by=None, **kwargs):
        n = self._next()
        if created_by is None:
            created_by = self.create_user(email=f'qr-user-{n}@test.com')
        defaults = {
            'title': title or f'Quick Reply {n}',
            'message': message,
            'created_by': created_by,
        }
        defaults.update(kwargs)
        return QuickReply.objects.create(**defaults)

    def create_conversation_archive(self, user=None, platform='facebook', **kwargs):
        n = self._next()
        defaults = {
            'platform': platform,
            'conversation_id': f'conv_{n}',
            'account_id': f'acc_{n}',
            'archived_by': user,
        }
        defaults.update(kwargs)
        return ConversationArchive.objects.create(**defaults)

    def create_auto_post_settings(self, **kwargs):
        defaults = {
            'is_enabled': False,
            'company_description': 'Test company',
            'posting_time': '10:00',
        }
        defaults.update(kwargs)
        return AutoPostSettings.objects.create(**defaults)

    def create_auto_post_content(self, **kwargs):
        n = self._next()
        defaults = {
            'status': 'draft',
            'facebook_text': f'FB Post {n}',
            'instagram_text': f'IG Post {n}',
            'scheduled_for': timezone.now() + timezone.timedelta(days=1),
        }
        defaults.update(kwargs)
        return AutoPostContent.objects.create(**defaults)
