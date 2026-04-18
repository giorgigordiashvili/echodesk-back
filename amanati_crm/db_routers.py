"""Database routers for EchoDesk.

We keep Django's tenant-schemas router for the default DB (public + tenant
schemas on the ``default`` alias) and layer the Asterisk realtime DB on top
via :class:`AsteriskStateRouter`.

**Phase 2 (BYO Asterisk).** There is no longer a single ``asterisk`` alias.
Each tenant has its own dedicated Postgres database whose connection info
lives encrypted on :class:`crm.models.PbxServer`. The router resolves the
current tenant's active PbxServer and returns ``asterisk_{schema_name}`` as
the alias — lazily registered via
:func:`crm.asterisk_db.get_asterisk_connection_for_current_tenant`.

If no active PbxServer exists for the current tenant, ``db_for_read`` /
``db_for_write`` return ``None`` so Django raises a clear error rather than
silently writing to the default DB. Sync code higher up should detect this
case (``get_active_pbx_for_current_tenant() is None``) and no-op cleanly.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

ASTERISK_APP_LABEL = "asterisk_state"
ASTERISK_ALIAS_PREFIX = "asterisk_"


def _resolve_alias():
    """Return the current tenant's dynamic asterisk alias, or ``None``."""
    # Imported lazily to avoid Django app-loading cycles.
    try:
        from crm.asterisk_db import get_asterisk_connection_for_current_tenant
    except Exception:  # noqa: BLE001
        return None
    try:
        alias, _pbx = get_asterisk_connection_for_current_tenant()
    except Exception:  # noqa: BLE001
        logger.debug("Asterisk alias resolution failed", exc_info=True)
        return None
    return alias


class AsteriskStateRouter:
    """Routes ``asterisk_state`` app models to the per-tenant asterisk DB alias.

    Behaviour:
    - Reads/writes for ``asterisk_state.*`` models go to the current tenant's
      ``asterisk_{schema}`` alias, resolved dynamically via the active
      ``PbxServer``.
    - When no active PbxServer exists, the router returns ``None`` → Django
      refuses the query rather than silently falling back. Higher-level sync
      code detects this earlier and skips.
    - Cross-DB relations are disallowed (but same-DB relations are allowed
      to avoid tripping up the default tenant-schemas flow).
    - Migrations for the ``asterisk_state`` app run *only* on ``asterisk_*``
      aliases; migrations for every other app run only on ``default``.
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label == ASTERISK_APP_LABEL:
            return _resolve_alias()
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == ASTERISK_APP_LABEL:
            return _resolve_alias()
        return None

    def allow_relation(self, obj1, obj2, **hints):
        label1 = obj1._meta.app_label
        label2 = obj2._meta.app_label
        # Both on the asterisk DB: fine.
        if label1 == ASTERISK_APP_LABEL and label2 == ASTERISK_APP_LABEL:
            return True
        # Cross-DB relations: block so Django raises at the ORM layer rather
        # than silently issuing cross-DB queries.
        if label1 == ASTERISK_APP_LABEL or label2 == ASTERISK_APP_LABEL:
            return False
        # Neither side is asterisk_state → let other routers decide.
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        is_asterisk_alias = db.startswith(ASTERISK_ALIAS_PREFIX)
        if app_label == ASTERISK_APP_LABEL:
            # Only migrate asterisk_state models on an asterisk_* alias.
            return is_asterisk_alias
        if is_asterisk_alias:
            # Never migrate non-asterisk_state apps into an asterisk DB.
            return False
        # Default DB migrations for everything else: defer to next router.
        return None
