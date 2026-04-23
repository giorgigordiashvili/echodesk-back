"""Smoke tests for the embeddable chat widget public API (PR 1).

Covers token generation, config lookup, session creation and message posting
for the `/api/widget/public/*` endpoints. WidgetConnection lives in the public
schema (SHARED_APPS/widget_registry); WidgetSession and WidgetMessage live in
each tenant's schema (TENANT_APPS/social_integrations).
"""
from rest_framework import status
from rest_framework.test import APIClient
from tenant_schemas.utils import schema_context

from social_integrations.models import WidgetMessage, WidgetSession
from social_integrations.tests.conftest import SocialIntegrationTestCase
from widget_registry.models import WidgetConnection


class WidgetPublicTestCase(SocialIntegrationTestCase):
    """Base test case that creates a WidgetConnection in the public schema
    pointing at the test tenant schema, and exposes a plain APIClient that
    talks to tenant.test.com (no auth needed — the public endpoints accept
    AllowAny)."""

    def setUp(self):
        super().setUp()
        self.public_client = APIClient()
        # Nothing created by default — each test decides active/inactive + origins.

    def _make_connection(self, **overrides):
        """Create a WidgetConnection row in the public schema."""
        defaults = {
            'tenant_schema': self.tenant.schema_name,
            'widget_token': WidgetConnection.generate_token(),
            'label': 'Test Widget',
            'is_active': True,
            'allowed_origins': ['https://foo.ge'],
            'brand_color': '#2A2B7D',
            'position': 'bottom-right',
            'welcome_message': {},
            'pre_chat_form': {},
            'offline_message': {},
        }
        defaults.update(overrides)
        with schema_context('public'):
            return WidgetConnection.objects.create(**defaults)

    # Convenience wrappers that always route to the tenant subdomain.

    def widget_get(self, url, **extra):
        return self.public_client.get(url, HTTP_HOST='tenant.test.com', **extra)

    def widget_post(self, url, data=None, **extra):
        return self.public_client.post(
            url, data or {}, format='json',
            HTTP_HOST='tenant.test.com', **extra,
        )


class TestGenerateToken(SocialIntegrationTestCase):

    def test_generate_token_format(self):
        """Token starts with 'wgt_live_' and has enough entropy."""
        token = WidgetConnection.generate_token()
        self.assertIsInstance(token, str)
        self.assertTrue(token.startswith('wgt_live_'))
        self.assertGreaterEqual(len(token), 30)

    def test_generate_token_is_unique(self):
        """Two consecutive calls produce different tokens."""
        self.assertNotEqual(
            WidgetConnection.generate_token(),
            WidgetConnection.generate_token(),
        )


class TestWidgetConfig(WidgetPublicTestCase):
    url = '/api/widget/public/config/'

    def test_config_missing_token_returns_400(self):
        resp = self.widget_get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json().get('error'), 'missing_token')

    def test_config_unknown_token_returns_404(self):
        resp = self.widget_get(self.url + '?token=wgt_live_doesnotexist')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.json().get('error'), 'not_found')

    def test_config_disabled_connection_returns_403(self):
        conn = self._make_connection(is_active=False)
        resp = self.widget_get(f'{self.url}?token={conn.widget_token}')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.json().get('error'), 'disabled')

    def test_config_setup_mode_flagged_when_no_allowed_origins(self):
        conn = self._make_connection(allowed_origins=[])
        resp = self.widget_get(f'{self.url}?token={conn.widget_token}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = resp.json()
        self.assertTrue(payload['is_setup_mode'])
        # When setup mode is on, origin_allowed should also be permissive so
        # the embedded widget can bootstrap on any origin during setup.
        self.assertTrue(payload['origin_allowed'])
        self.assertEqual(payload['widget_token'], conn.widget_token)


class TestCreateSession(WidgetPublicTestCase):
    url = '/api/widget/public/sessions/'

    def test_create_session_requires_visitor_id(self):
        conn = self._make_connection()
        resp = self.widget_post(
            self.url,
            {'token': conn.widget_token},
            HTTP_ORIGIN='https://foo.ge',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json().get('error'), 'missing_visitor_id')

    def test_create_session_happy_path(self):
        conn = self._make_connection(allowed_origins=['https://foo.ge'])
        resp = self.widget_post(
            self.url,
            {
                'token': conn.widget_token,
                'visitor_id': 'visitor-abc',
                'visitor_name': 'Alice',
                'visitor_email': 'alice@example.com',
                'page_url': 'https://foo.ge/pricing',
            },
            HTTP_ORIGIN='https://foo.ge',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        body = resp.json()
        self.assertIn('session_id', body)
        self.assertTrue(body['is_new'])

        # Row should exist in the tenant schema.
        with schema_context(self.tenant.schema_name):
            session = WidgetSession.objects.get(session_id=body['session_id'])
            self.assertEqual(session.visitor_id, 'visitor-abc')
            self.assertEqual(session.visitor_name, 'Alice')
            self.assertEqual(session.connection_id, conn.id)

    def test_create_session_rejects_wrong_origin(self):
        conn = self._make_connection(allowed_origins=['https://foo.ge'])
        resp = self.widget_post(
            self.url,
            {'token': conn.widget_token, 'visitor_id': 'visitor-xyz'},
            HTTP_ORIGIN='https://evil.example',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.json().get('error'), 'origin_not_allowed')

    def test_reuse_session_for_same_visitor(self):
        conn = self._make_connection(allowed_origins=['https://foo.ge'])
        first = self.widget_post(
            self.url,
            {'token': conn.widget_token, 'visitor_id': 'returning-1'},
            HTTP_ORIGIN='https://foo.ge',
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        first_body = first.json()

        second = self.widget_post(
            self.url,
            {'token': conn.widget_token, 'visitor_id': 'returning-1'},
            HTTP_ORIGIN='https://foo.ge',
        )
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        second_body = second.json()
        self.assertFalse(second_body['is_new'])
        self.assertEqual(second_body['session_id'], first_body['session_id'])


class TestPostMessage(WidgetPublicTestCase):
    sessions_url = '/api/widget/public/sessions/'
    messages_url = '/api/widget/public/messages/'

    def _bootstrap_session(self, conn):
        """Create a session via the public API and return (session_id, token)."""
        resp = self.widget_post(
            self.sessions_url,
            {'token': conn.widget_token, 'visitor_id': 'msg-visitor'},
            HTTP_ORIGIN='https://foo.ge',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        return resp.json()['session_id']

    def test_post_message_creates_widget_message(self):
        conn = self._make_connection(allowed_origins=['https://foo.ge'])
        session_id = self._bootstrap_session(conn)

        resp = self.widget_post(
            self.messages_url,
            {
                'token': conn.widget_token,
                'session_id': session_id,
                'message_text': 'hello from the widget',
            },
            HTTP_ORIGIN='https://foo.ge',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        body = resp.json()
        self.assertEqual(body['message_text'], 'hello from the widget')
        self.assertTrue(body['is_from_visitor'])

        with schema_context(self.tenant.schema_name):
            msg = WidgetMessage.objects.get(message_id=body['message_id'])
            self.assertTrue(msg.is_from_visitor)
            self.assertEqual(msg.session.session_id, session_id)
            self.assertEqual(msg.message_text, 'hello from the widget')

    def test_post_message_empty_body_returns_400(self):
        conn = self._make_connection(allowed_origins=['https://foo.ge'])
        session_id = self._bootstrap_session(conn)

        resp = self.widget_post(
            self.messages_url,
            {
                'token': conn.widget_token,
                'session_id': session_id,
                'message_text': '',
                'attachments': [],
            },
            HTTP_ORIGIN='https://foo.ge',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json().get('error'), 'empty_message')
