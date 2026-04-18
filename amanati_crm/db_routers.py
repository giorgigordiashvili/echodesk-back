"""Database routers for EchoDesk.

We keep Django's tenant-schemas router for the default DB (public + tenant
schemas on the ``default`` alias) and layer the Asterisk realtime DB on top
via :class:`AsteriskStateRouter`.

The Asterisk router only claims models whose app label is ``asterisk_state``.
Everything else falls through (return ``None``) so the tenant-schemas router
registered after this one keeps handling the default DB as before.
"""
from __future__ import annotations

ASTERISK_APP_LABEL = "asterisk_state"
ASTERISK_DB_ALIAS = "asterisk"


class AsteriskStateRouter:
    """Routes ``asterisk_state`` app models to the ``asterisk`` DB alias.

    Behaviour:
    - Reads/writes for ``asterisk_state.*`` models go to the ``asterisk`` DB.
    - Relations across DBs are disallowed (but same-DB relations are allowed
      to avoid tripping up the default tenant-schemas flow).
    - Migrations for the ``asterisk_state`` app run *only* on the ``asterisk``
      DB alias; migrations for every other app run only on ``default``.

    If ``settings.ASTERISK_SYNC_ENABLED`` is ``False`` and the ``asterisk`` DB
    alias is unconfigured, Django will still discover this router but no
    asterisk-state write will ever reach the DB — the sync service itself
    no-ops upstream of the ORM.
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label == ASTERISK_APP_LABEL:
            return ASTERISK_DB_ALIAS
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == ASTERISK_APP_LABEL:
            return ASTERISK_DB_ALIAS
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
        if app_label == ASTERISK_APP_LABEL:
            # Only migrate asterisk_state models on the asterisk DB alias.
            return db == ASTERISK_DB_ALIAS
        if db == ASTERISK_DB_ALIAS:
            # Never migrate non-asterisk_state apps into the asterisk DB.
            return False
        # Default DB migrations for everything else: defer to next router.
        return None
