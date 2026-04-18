"""Shadow models for the Asterisk realtime DB.

This app is a thin schema-only shim: it does not own any runtime logic and
lives exclusively to describe the Asterisk 18 realtime tables (``ps_endpoints``,
``ps_auths``, ``ps_aors``, ``ps_identifies``, ``queues``, ``queue_members``,
``ps_contacts``, ``ps_registrations``) to Django so we can read/write them via
the ORM.

All models are routed to the ``asterisk`` DB alias by
``amanati_crm.db_routers.AsteriskStateRouter``. Migrations for this app only
apply on that alias. When ``settings.ASTERISK_SYNC_ENABLED`` is ``False`` the
sync layer no-ops gracefully, so this app is safe to leave installed in dev
without an asterisk DB configured.
"""

default_app_config = "asterisk_state.apps.AsteriskStateConfig"
