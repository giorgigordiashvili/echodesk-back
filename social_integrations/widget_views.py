"""HTTP views for the embeddable chat widget.

Public endpoints (AllowAny, rate-limited) accept a widget token in the
request body or query string; the token resolves the tenant schema so
visitors never need to know the tenant's subdomain. Authenticated
endpoints are for tenant admins/agents to manage connections and read
conversation transcripts.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import timedelta

from django.conf import settings as django_settings
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
        'voice_enabled': getattr(conn, 'voice_enabled', False),
        # Fields added in migration 0002 — defensive getattr keeps the
        # endpoint responding even if a pod still has the pre-migration
        # model imported (DO rolling restart window).
        'proactive_enabled': getattr(conn, 'proactive_enabled', False),
        'proactive_message': getattr(conn, 'proactive_message', None) or {},
        'proactive_delay_seconds': getattr(conn, 'proactive_delay_seconds', 30),
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

    # Single broadcast to the tenant group — agents AND visitor iframes
    # both listen there. Frontend dedupes by message_id if the same frame
    # arrives twice (which happens when an agent is in both the tenant and
    # a conversation-specific group).
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


WIDGET_UPLOAD_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
WIDGET_UPLOAD_ALLOWED_PREFIXES = (
    'image/',
    'audio/',
    'video/',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'text/plain',
    'text/csv',
)


def _is_allowed_upload_type(content_type: str) -> bool:
    if not content_type:
        return False
    content_type = content_type.lower()
    return any(content_type.startswith(p) for p in WIDGET_UPLOAD_ALLOWED_PREFIXES)


@api_view(['POST'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='30/h', block=True)
def widget_public_upload(request):
    """Visitor-side attachment upload.

    Body (multipart/form-data):
        token:       widget token
        session_id:  active session id
        file:        the file (<=10 MB, allowed content-type)
    Returns {url, filename, size, content_type}.

    We trust the DO Spaces UUID path to keep the URL unguessable; the
    attachment only becomes reachable once the visitor references it
    from a WidgetMessage, which is tied to their session.
    """
    token = request.data.get('token') or request.query_params.get('token')
    session_id = (request.data.get('session_id') or '').strip()
    upload = request.FILES.get('file')

    if not upload:
        return _error('missing_file', status.HTTP_400_BAD_REQUEST)
    if not session_id:
        return _error('missing_session_id', status.HTTP_400_BAD_REQUEST)
    if upload.size > WIDGET_UPLOAD_MAX_BYTES:
        return _error('file_too_large', status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                      detail=f'Max {WIDGET_UPLOAD_MAX_BYTES // (1024 * 1024)} MB.')
    if not _is_allowed_upload_type(upload.content_type or ''):
        return _error('unsupported_type', status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                      detail=f'Content-Type {upload.content_type!r} not allowed.')

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

    # Save to Spaces. Keep filename but prefix with a UUID so the URL can't be
    # enumerated and two visitors uploading "receipt.pdf" don't collide.
    from django.core.files.storage import default_storage
    safe_name = (upload.name or 'file').replace('/', '_').replace('\\', '_')[:120]
    storage_path = (
        f'widget/{conn.tenant_schema}/{session.session_id}/'
        f'{uuid.uuid4().hex}-{safe_name}'
    )
    saved_path = default_storage.save(storage_path, upload)
    url = default_storage.url(saved_path)
    return Response({
        'url': url,
        'filename': safe_name,
        'size': upload.size,
        'content_type': upload.content_type,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='60/h', block=True)
def widget_public_call_credentials(request):
    """Issue short-lived SIP creds for a widget voice call.

    Visitor → POST /api/widget/public/call/credentials/
    Body: {token, session_id}
    Returns (on success):
        {
            sip_uri: "sip:widget_<sid>@pbx2.echodesk.cloud",
            sip_username: "widget_<sid>",
            sip_password: "...",       # ephemeral, 4h TTL
            sip_server_wss: "wss://pbx2.echodesk.cloud:8089/ws",
            destination_extension: "support",
            ice_servers: [{urls: "stun:stun.l.google.com:19302"}],
        }
    Errors: 403 voice_disabled / outside_hours / origin_not_allowed,
            404 not_found / session_not_found.

    Security:
    - Voice is gated behind the tenant's ``voice_enabled`` toggle AND
      (implicitly) their having an enrolled PbxServer.
    - The visitor side doesn't re-check the tenant's ``ip_calling``
      subscription feature — that gate lives on the admin side that
      toggles ``voice_enabled``. If no PbxServer exists we 503.
    """
    # Top-level bulletproof guard so we NEVER let an exception escape to
    # the worker level. A Python exception at this layer would normally be
    # caught by DRF, but if asterisk_db imports or a C extension
    # (psycopg2 SSL handshake) misbehaves, the worker can die without DRF
    # ever seeing the error. Catch EVERYTHING so we always return JSON.
    try:
        body = request.data or {}
        token = body.get('token')
        session_id = (body.get('session_id') or '').strip()
        if not session_id:
            return _error('missing_session_id', status.HTTP_400_BAD_REQUEST)

        conn, err = resolve_widget_connection(token)
        if err:
            code_map = {'missing_token': 400, 'not_found': 404, 'disabled': 403}
            return _error(err, code_map[err])
        if conn.allowed_origins and not check_origin_allowed(conn, request):
            return _error('origin_not_allowed', status.HTTP_403_FORBIDDEN)

        if not conn.voice_enabled:
            return _error('voice_disabled', status.HTTP_403_FORBIDDEN)

        endpoint_id: str | None = None
        sip_password = secrets.token_urlsafe(18)
        with schema_context(conn.tenant_schema):
            try:
                session = WidgetSession.objects.get(
                    session_id=session_id, connection_id=conn.id
                )
            except WidgetSession.DoesNotExist:
                return _error('session_not_found', status.HTTP_404_NOT_FOUND)
            if timezone.now() - session.last_seen_at > SESSION_STALE_AFTER:
                return _error('session_expired', status.HTTP_410_GONE)

            if conn.voice_working_hours_only and not is_tenant_online(conn.tenant_schema):
                return _error('outside_hours', status.HTTP_403_FORBIDDEN)

            # Resolve the tenant's PBX and provision the ephemeral endpoint.
            from crm.asterisk_db import get_active_pbx_for_current_tenant
            from crm.asterisk_sync import AsteriskStateSync
            pbx = get_active_pbx_for_current_tenant()
            if pbx is None:
                return _error('pbx_unavailable', status.HTTP_503_SERVICE_UNAVAILABLE)

            logger.info(
                "widget_public_call_credentials: provisioning endpoint "
                "tenant=%s session=%s pbx_fqdn=%s db=%s",
                conn.tenant_schema, session_id, pbx.fqdn, pbx.realtime_db_name,
            )

            sync = AsteriskStateSync(conn.tenant_schema, pbx=pbx)
            try:
                endpoint_id = sync._sync_widget_guest_endpoint_impl(
                    session_id=session_id,
                    password=sip_password,
                    queue=conn.voice_queue or 'support',
                    ttl_hours=4,
                )
            except Exception as e:
                logger.exception(
                    "widget_public_call_credentials: sync_widget_guest_endpoint "
                    "failed tenant=%s session=%s pbx=%s",
                    conn.tenant_schema, session_id, getattr(pbx, 'fqdn', None),
                )
                return _error(
                    'provision_failed', status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f'{type(e).__name__}: {e}',
                )
            if not endpoint_id:
                return _error('provision_failed', status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:  # noqa: BLE001 -- bulletproof guard
        logger.exception(
            "widget_public_call_credentials: unexpected top-level exception"
        )
        return _error(
            'internal_error', status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'{type(e).__name__}: {e}',
        )

    # Prefer the tenant's own PbxServer config (wss_url + fqdn) so each
    # tenant uses their own PBX; fall back to the globals only if the
    # tenant hasn't filled them in yet.
    sip_domain = pbx.fqdn or getattr(
        django_settings, 'WIDGET_SIP_DOMAIN', 'pbx2.echodesk.cloud'
    )
    sip_server_wss = pbx.wss_url or getattr(
        django_settings, 'WIDGET_SIP_WSS_URL', f'wss://{sip_domain}:8089/ws'
    )
    ice_servers = getattr(
        django_settings, 'WIDGET_SIP_ICE_SERVERS',
        [{'urls': 'stun:stun.l.google.com:19302'}],
    )

    return Response({
        'sip_uri': f'sip:{endpoint_id}@{sip_domain}',
        'sip_username': endpoint_id,
        'sip_password': sip_password,
        'sip_server_wss': sip_server_wss,
        'sip_domain': sip_domain,
        'destination_extension': conn.voice_queue or 'support',
        'ice_servers': ice_servers,
    }, status=status.HTTP_201_CREATED)


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
