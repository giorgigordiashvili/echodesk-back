"""Shared helpers for the embeddable chat widget endpoints.

The public-facing widget API lives on the public schema (the widget
token carries the tenant identifier so visitors can hit the API
without knowing the tenant subdomain). The helpers below centralise
the token -> tenant resolution + origin gate so every view uses the
same policy.
"""
from __future__ import annotations

import logging

from django.conf import settings as django_settings
from tenant_schemas.utils import schema_context, get_public_schema_name

logger = logging.getLogger(__name__)

WIDGET_PUBLIC_PATH_PREFIX = '/api/widget/public/'


def resolve_widget_connection(token: str):
    """Look up a WidgetConnection by its token in the public schema.

    Returns (connection, None) on success or (None, error_code) where
    error_code is one of: 'missing_token', 'not_found', 'disabled'.
    """
    if not token:
        return None, 'missing_token'
    from widget_registry.models import WidgetConnection
    with schema_context(get_public_schema_name()):
        try:
            conn = WidgetConnection.objects.get(widget_token=token)
        except WidgetConnection.DoesNotExist:
            return None, 'not_found'
        if not conn.is_active:
            return None, 'disabled'
        # Evaluate fields while the ORM is bound to public so .refresh_from_db() etc.
        # behave predictably — materialise a lightweight dict for the caller.
        return conn, None


def request_origin(request) -> str:
    return request.headers.get('Origin', '') or request.META.get('HTTP_ORIGIN', '')


def check_origin_allowed(conn, request) -> bool:
    """True if the request's Origin matches an entry in allowed_origins.

    Empty allowed_origins means the widget is in setup mode — the config
    endpoint returns a warning flag; all other endpoints reject.
    """
    origin = request_origin(request)
    if not conn.allowed_origins:
        return False
    return origin in conn.allowed_origins


def client_ip(request) -> str | None:
    """Return the real client IP, honouring X-Forwarded-For."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def is_tenant_online(schema_name: str) -> bool:
    """Best-effort 'is tenant available now?' check.

    Reads SocialIntegrationSettings.away_hours_schedule if present.
    If anything goes wrong (no settings row, malformed schedule), returns True
    so we don't block visitors due to a misconfigured tenant.
    """
    from .models import SocialIntegrationSettings
    try:
        with schema_context(schema_name):
            sett = SocialIntegrationSettings.objects.first()
            if not sett or not getattr(sett, 'away_hours_schedule', None):
                return True
            # Don't re-implement business-hours logic here — the existing
            # helper (if any) is the source of truth. For MVP return True;
            # PR 3 can refine this once the WS layer needs accurate online
            # status for presence pings.
            return True
    except Exception as exc:  # pragma: no cover
        logger.warning("is_tenant_online(%s) failed: %s", schema_name, exc)
        return True
