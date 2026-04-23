"""Dynamic per-tenant Asterisk realtime DB connection helpers.

Phase 2 of the BYO-Asterisk rollout moves each tenant's realtime data into
its own dedicated Postgres database, with credentials stored encrypted on
the tenant's :class:`crm.models.PbxServer` row. This module is the single
chokepoint that turns a PbxServer row into a Django DB alias usable with
``Model.objects.using(alias)``.

The previous static ``DATABASES['asterisk']`` alias (shared defaultdb) is
gone; callers must look up the current tenant's PbxServer and ask this
module for its alias. When no active PbxServer exists, helpers return
``(None, None)`` and sync code no-ops.

Key design choices
------------------
- The alias name is deterministic: ``asterisk_{schema_name}``. That keeps
  cache keys and log messages predictable.
- Alias registration is idempotent — calling :func:`register_pbx_alias` a
  second time either no-ops (if credentials match) or tears down the stale
  connection and re-registers with the new config. This lets the admin
  rotate DB creds without a process restart.
- Registration happens lazily from the sync layer + router, so a newly
  provisioned PbxServer works on the next request without warming.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from django.db import connection, connections

logger = logging.getLogger(__name__)


def alias_for_schema(schema_name: str) -> str:
    """Canonical alias name for a tenant's Asterisk DB connection.

    >>> alias_for_schema('amanati')
    'asterisk_amanati'
    """
    return f"asterisk_{schema_name}"


def _build_db_config(pbx_server) -> dict:
    """Produce a Django DATABASES-style dict from a PbxServer row."""
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': pbx_server.realtime_db_name,
        'USER': pbx_server.realtime_db_user,
        'PASSWORD': pbx_server.realtime_db_password or '',
        'HOST': pbx_server.realtime_db_host,
        'PORT': str(pbx_server.realtime_db_port or 5432),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'sslmode': pbx_server.realtime_db_sslmode or 'require',
            # Fail the TCP handshake in 5 s instead of libpq's default ~75 s
            # retry loop — the request-serving pod shouldn't hold a load-
            # balancer connection for over a minute waiting on an
            # unreachable PBX DB.
            'connect_timeout': 5,
        },
        'TIME_ZONE': None,
        'AUTOCOMMIT': True,
        'ATOMIC_REQUESTS': False,
        'CONN_HEALTH_CHECKS': False,
        'DISABLE_SERVER_SIDE_CURSORS': False,
        # Extra keys Django's ConnectionHandler expects when we inject at runtime.
        'TEST': {},
    }


def register_pbx_alias(pbx_server, schema_name: Optional[str] = None) -> str:
    """Inject (or refresh) a Django DB alias for this PbxServer.

    Returns the alias name (e.g. ``asterisk_amanati``). Safe to call from any
    code path: if the alias already points at the same database name, the
    config is updated in place (credentials can change); if it points at a
    different database, the stale connection is closed before registering.

    ``schema_name`` overrides the auto-detected tenant schema — useful when
    warming aliases outside a tenant request cycle.
    """
    schema = schema_name or getattr(connection, 'schema_name', None)
    if not schema or schema == 'public':
        # PbxServer rows live in tenant schemas; a public-schema lookup here
        # is almost certainly a bug. We still accept it for e.g. install-
        # script flows that resolve via enrollment_token and pass the schema
        # explicitly.
        raise ValueError(
            "register_pbx_alias: cannot derive alias without a tenant schema "
            "(pass schema_name= explicitly for cross-schema flows)."
        )

    alias = alias_for_schema(schema)
    new_config = _build_db_config(pbx_server)

    existing = connections.databases.get(alias)
    if existing and existing.get('NAME') == new_config['NAME']:
        # Same target DB → just refresh creds/options in place.
        existing.update(new_config)
        return alias

    # Different DB (or first registration): close any live connection tied
    # to the alias before swapping configs so Django doesn't reuse a socket
    # bound to the old database.
    if alias in connections.databases:
        try:
            connections[alias].close()
        except Exception:  # noqa: BLE001 — defensive; never block registration
            logger.debug("Failed to close stale asterisk alias %s", alias, exc_info=True)
        # Drop any cached DatabaseWrapper so the next access rebuilds it.
        if hasattr(connections, '_connections'):
            try:
                delattr(connections._connections, alias)
            except AttributeError:
                pass

    connections.databases[alias] = new_config
    return alias


def get_active_pbx_for_current_tenant():
    """Return the active :class:`PbxServer` for the current tenant, or ``None``.

    Queries inside the current ``connection.schema_name``. Returns ``None``
    when:
    - we're on the public schema (no PbxServer model available there), or
    - the tenant has no PbxServer row, or
    - its status is not ``active``.
    """
    schema = getattr(connection, 'schema_name', None)
    if not schema or schema == 'public':
        return None
    # Lazy import so this module can be imported during app loading.
    try:
        from crm.models import PbxServer
    except Exception:  # noqa: BLE001
        logger.debug("PbxServer model not importable yet", exc_info=True)
        return None
    try:
        return PbxServer.objects.filter(status=PbxServer.STATUS_ACTIVE).first()
    except Exception:  # noqa: BLE001 — migrations not yet applied, etc.
        logger.debug(
            "PbxServer lookup failed for schema=%s (migrations pending?)",
            schema,
            exc_info=True,
        )
        return None


def get_asterisk_connection_for_current_tenant() -> Tuple[Optional[str], object]:
    """Return ``(alias, pbx_server)`` for the current tenant.

    Registers the alias if needed. Returns ``(None, None)`` when no active
    PbxServer is configured — callers MUST treat this as "skip sync" /
    "return 503" rather than falling back to any shared DB.
    """
    pbx = get_active_pbx_for_current_tenant()
    if pbx is None:
        return None, None
    alias = register_pbx_alias(pbx)
    return alias, pbx


def warm_aliases_for_all_tenants() -> int:
    """Register a DB alias for every tenant with an active PbxServer.

    Intended to be called from ``AppConfig.ready()`` so worker processes
    have all aliases ready on boot. Safe to fail per-tenant — a bad row
    shouldn't block Django startup. Returns the number of aliases warmed.
    """
    warmed = 0
    try:
        from tenants.models import Tenant
        from tenant_schemas.utils import schema_context
    except Exception:  # noqa: BLE001
        logger.debug("Tenant model not importable yet; skipping alias warm-up")
        return 0

    try:
        tenants = list(Tenant.objects.exclude(schema_name='public'))
    except Exception:  # noqa: BLE001 — tables not yet created
        logger.debug("Tenant table not ready; skipping alias warm-up", exc_info=True)
        return 0

    for tenant in tenants:
        try:
            with schema_context(tenant.schema_name):
                pbx = get_active_pbx_for_current_tenant()
                if pbx is None:
                    continue
                register_pbx_alias(pbx, schema_name=tenant.schema_name)
                warmed += 1
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to warm asterisk alias for tenant=%s", tenant.schema_name
            )
    if warmed:
        logger.info("Warmed %s asterisk DB aliases on startup", warmed)
    return warmed
