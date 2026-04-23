"""HTTP views for the embeddable chat widget.

Public endpoints (AllowAny, rate-limited) accept a widget token in the
request body or query string; the token resolves the tenant schema so
visitors never need to know the tenant's subdomain. Authenticated
endpoints are for tenant admins/agents to manage connections and read
conversation transcripts.
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from tenant_schemas.utils import schema_context

from widget_registry.models import WidgetConnection
from .models import WidgetMessage, WidgetSession
from .widget_serializers import (
    WidgetConnectionSerializer,
    WidgetMessageSerializer,
    WidgetSessionSerializer,
)
from .widget_utils import (
    check_origin_allowed,
    client_ip,
    is_tenant_online,
    request_origin,
    resolve_widget_connection,
)

logger = logging.getLogger(__name__)

SESSION_STALE_AFTER = timedelta(hours=24)


def _error(code: str, status_code: int, detail: str | None = None):
    payload = {'error': code}
    if detail:
        payload['detail'] = detail
    return Response(payload, status=status_code)


@api_view(['GET', 'OPTIONS'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='60/m', block=True)
def widget_public_config(request):
    """Return widget branding + behaviour config for the given token."""
    token = request.query_params.get('token') or request.query_params.get('t')
    conn, err = resolve_widget_connection(token)
    if err == 'missing_token':
        return _error('missing_token', status.HTTP_400_BAD_REQUEST)
    if err == 'not_found':
        return _error('not_found', status.HTTP_404_NOT_FOUND)
    if err == 'disabled':
        return _error('disabled', status.HTTP_403_FORBIDDEN)

    is_setup_mode = not conn.allowed_origins
    origin_allowed = bool(conn.allowed_origins) and request_origin(request) in conn.allowed_origins

    data = {
        'widget_token': conn.widget_token,
        'brand_color': conn.brand_color,
        'position': conn.position,
        'welcome_message': conn.welcome_message or {},
        'pre_chat_form': conn.pre_chat_form or {},
        'offline_message': conn.offline_message or {},
        'voice_enabled': conn.voice_enabled,
        'is_online': is_tenant_online(conn.tenant_schema),
        'is_setup_mode': is_setup_mode,
        'origin_allowed': origin_allowed or is_setup_mode,
    }
    return Response(data)


@api_view(['POST'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='30/h', block=True)
def widget_public_sessions(request):
    """Create (or return the existing) visitor session."""
    body = request.data or {}
    token = body.get('token')
    visitor_id = (body.get('visitor_id') or '').strip()
    if not visitor_id:
        return _error('missing_visitor_id', status.HTTP_400_BAD_REQUEST)
    if len(visitor_id) > 64:
        return _error('invalid_visitor_id', status.HTTP_400_BAD_REQUEST)

    conn, err = resolve_widget_connection(token)
    if err:
        code_map = {'missing_token': 400, 'not_found': 404, 'disabled': 403}
        return _error(err, code_map[err])
    if conn.allowed_origins and not check_origin_allowed(conn, request):
        return _error('origin_not_allowed', status.HTTP_403_FORBIDDEN)

    with schema_context(conn.tenant_schema):
        # Re-use recent session for the same visitor so a returning browser
        # keeps its conversation thread.
        cutoff = timezone.now() - SESSION_STALE_AFTER
        existing = (
            WidgetSession.objects
            .filter(connection_id=conn.id, visitor_id=visitor_id, last_seen_at__gte=cutoff)
            .order_by('-last_seen_at')
            .first()
        )
        if existing:
            existing.last_seen_at = timezone.now()
            existing.save(update_fields=['last_seen_at'])
            return Response({
                'session_id': existing.session_id,
                'is_new': False,
                'session': WidgetSessionSerializer(existing).data,
            })

        session = WidgetSession.objects.create(
            connection_id=conn.id,
            session_id=uuid.uuid4().hex,
            visitor_id=visitor_id,
            visitor_name=body.get('visitor_name', '')[:120],
            visitor_email=body.get('visitor_email', '')[:254],
            referrer_url=body.get('referrer', '')[:500],
            page_url=body.get('page_url', '')[:500],
            user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:500],
            ip_address=client_ip(request),
        )
        return Response(
            {
                'session_id': session.session_id,
                'is_new': True,
                'session': WidgetSessionSerializer(session).data,
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='60/h', block=True)
# TODO(PR 3): switch to a custom key function that hashes session_id so
# one noisy visitor can't block another on a shared NAT.
def widget_public_messages(request):
    """Visitor sends a message."""
    body = request.data or {}
    token = body.get('token')
    session_id = (body.get('session_id') or '').strip()
    message_text = (body.get('message_text') or '').strip()
    attachments = body.get('attachments') or []

    if not session_id:
        return _error('missing_session_id', status.HTTP_400_BAD_REQUEST)
    if not message_text and not attachments:
        return _error('empty_message', status.HTTP_400_BAD_REQUEST)
    if len(message_text) > 10_000:
        return _error('message_too_long', status.HTTP_400_BAD_REQUEST)

    conn, err = resolve_widget_connection(token)
    if err:
        code_map = {'missing_token': 400, 'not_found': 404, 'disabled': 403}
        return _error(err, code_map[err])
    if conn.allowed_origins and not check_origin_allowed(conn, request):
        return _error('origin_not_allowed', status.HTTP_403_FORBIDDEN)

    with schema_context(conn.tenant_schema):
        try:
            session = WidgetSession.objects.get(session_id=session_id, connection_id=conn.id)
        except WidgetSession.DoesNotExist:
            return _error('session_not_found', status.HTTP_404_NOT_FOUND)

        if timezone.now() - session.last_seen_at > SESSION_STALE_AFTER:
            return _error('session_expired', status.HTTP_410_GONE)

        now = timezone.now()
        msg = WidgetMessage.objects.create(
            session=session,
            message_id=uuid.uuid4().hex,
            message_text=message_text,
            attachments=attachments if isinstance(attachments, list) else [],
            is_from_visitor=True,
            is_delivered=True,
            delivered_at=now,
            timestamp=now,
        )
        session.last_seen_at = now
        session.save(update_fields=['last_seen_at'])
        response_data = WidgetMessageSerializer(msg).data

    # PR 3: broadcast the new message so the agent's inbox and any other
    # widget tabs for this session update in real time.
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    if channel_layer:
        conversation_id = f"widget_{conn.id}_{session.session_id}"
        msg_payload = {
            'message_id': msg.message_id,
            'message_text': msg.message_text,
            'attachments': msg.attachments,
            'is_from_visitor': True,
            'timestamp': msg.timestamp.isoformat(),
            'session_id': session.session_id,
            'connection_id': conn.id,
            'platform': 'widget',
        }
        async_to_sync(channel_layer.group_send)(f'messages_{conn.tenant_schema}', {
            'type': 'new_message',
            'message': msg_payload,
            'conversation_id': conversation_id,
            'timestamp': msg_payload['timestamp'],
        })
        async_to_sync(channel_layer.group_send)(f'widget_visitor_{session.session_id}', {
            'type': 'new_message',
            'message': msg_payload,
            'conversation_id': conversation_id,
            'timestamp': msg_payload['timestamp'],
        })

    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='120/m', block=True)
def widget_public_messages_list(request):
    """Polling fallback — return session messages after `after` timestamp."""
    token = request.query_params.get('token')
    session_id = (request.query_params.get('session_id') or '').strip()
    after_raw = request.query_params.get('after')

    if not session_id:
        return _error('missing_session_id', status.HTTP_400_BAD_REQUEST)

    conn, err = resolve_widget_connection(token)
    if err:
        code_map = {'missing_token': 400, 'not_found': 404, 'disabled': 403}
        return _error(err, code_map[err])

    with schema_context(conn.tenant_schema):
        try:
            session = WidgetSession.objects.get(session_id=session_id, connection_id=conn.id)
        except WidgetSession.DoesNotExist:
            return _error('session_not_found', status.HTTP_404_NOT_FOUND)

        qs = WidgetMessage.objects.filter(session=session, is_deleted=False).order_by('timestamp')
        if after_raw:
            try:
                after_dt = timezone.datetime.fromisoformat(after_raw.replace('Z', '+00:00'))
                qs = qs.filter(timestamp__gt=after_dt)
            except (ValueError, TypeError):
                pass  # Ignore malformed timestamps — return everything.

        # Mark agent-sent messages as read now that visitor polled them.
        now = timezone.now()
        (
            qs.filter(is_from_visitor=False, is_read_by_visitor=False)
              .update(is_read_by_visitor=True)
        )

        return Response(WidgetMessageSerializer(qs, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def widget_admin_send_message(request):
    """Agent-side: send a reply into a widget conversation.

    Body: {connection_id: int, session_id: str, message_text: str, attachments?: list}
    """
    body = request.data or {}
    try:
        connection_id = int(body.get('connection_id'))
    except (TypeError, ValueError):
        return _error('invalid_connection_id', status.HTTP_400_BAD_REQUEST)
    session_id = (body.get('session_id') or '').strip()
    message_text = (body.get('message_text') or '').strip()
    attachments = body.get('attachments') or []
    if not session_id:
        return _error('missing_session_id', status.HTTP_400_BAD_REQUEST)
    if not message_text and not attachments:
        return _error('empty_message', status.HTTP_400_BAD_REQUEST)
    if len(message_text) > 10_000:
        return _error('message_too_long', status.HTTP_400_BAD_REQUEST)

    schema = getattr(request.tenant, 'schema_name', None)
    if not schema or schema == 'public':
        return _error('tenant_required', status.HTTP_400_BAD_REQUEST)

    # Verify tenant owns this connection.
    with schema_context('public'):
        try:
            conn = WidgetConnection.objects.get(id=connection_id, tenant_schema=schema)
        except WidgetConnection.DoesNotExist:
            return _error('not_found', status.HTTP_404_NOT_FOUND)

    with schema_context(schema):
        try:
            session = WidgetSession.objects.get(session_id=session_id, connection_id=connection_id)
        except WidgetSession.DoesNotExist:
            return _error('session_not_found', status.HTTP_404_NOT_FOUND)
        now = timezone.now()
        msg = WidgetMessage.objects.create(
            session=session,
            message_id=uuid.uuid4().hex,
            message_text=message_text,
            attachments=attachments if isinstance(attachments, list) else [],
            is_from_visitor=False,
            sent_by=request.user,
            is_delivered=True,
            delivered_at=now,
            timestamp=now,
        )
        payload_data = WidgetMessageSerializer(msg).data

    # Broadcast
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    if channel_layer:
        conversation_id = f"widget_{connection_id}_{session_id}"
        msg_payload = {
            'message_id': msg.message_id,
            'message_text': msg.message_text,
            'attachments': msg.attachments,
            'is_from_visitor': False,
            'sent_by': request.user.id,
            'timestamp': msg.timestamp.isoformat(),
            'session_id': session_id,
            'connection_id': connection_id,
            'platform': 'widget',
        }
        async_to_sync(channel_layer.group_send)(f'messages_{schema}', {
            'type': 'new_message',
            'message': msg_payload,
            'conversation_id': conversation_id,
            'timestamp': msg_payload['timestamp'],
        })
        async_to_sync(channel_layer.group_send)(f'widget_visitor_{session_id}', {
            'type': 'new_message',
            'message': msg_payload,
            'conversation_id': conversation_id,
            'timestamp': msg_payload['timestamp'],
        })

    return Response(payload_data, status=status.HTTP_201_CREATED)


class WidgetConnectionViewSet(viewsets.ModelViewSet):
    """Tenant-scoped admin CRUD for widget connections (lives in public schema)."""
    serializer_class = WidgetConnectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        schema = getattr(self.request.tenant, 'schema_name', None)
        if not schema or schema == 'public':
            return WidgetConnection.objects.none()
        with schema_context('public'):
            return WidgetConnection.objects.filter(tenant_schema=schema).order_by('-created_at')

    def perform_create(self, serializer):
        schema = self.request.tenant.schema_name
        with schema_context('public'):
            serializer.save(
                tenant_schema=schema,
                widget_token=WidgetConnection.generate_token(),
            )

    def perform_update(self, serializer):
        with schema_context('public'):
            serializer.save()

    def perform_destroy(self, instance):
        with schema_context('public'):
            instance.delete()


class WidgetMessageViewSet(viewsets.ReadOnlyModelViewSet):
    """Tenant-scoped read-only view of widget messages. Agents use this when
    surfing a single visitor's transcript."""
    serializer_class = WidgetMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        schema = getattr(self.request.tenant, 'schema_name', None)
        if not schema or schema == 'public':
            return WidgetMessage.objects.none()
        # WidgetMessage lives in the tenant schema already — the tenant middleware
        # set the connection. Filter by session_id query param when provided.
        qs = WidgetMessage.objects.filter(is_deleted=False).order_by('timestamp')
        session_id = self.request.query_params.get('session_id')
        if session_id:
            qs = qs.filter(session__session_id=session_id)
        return qs
