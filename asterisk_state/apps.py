from django.apps import AppConfig


class AsteriskStateConfig(AppConfig):
    """App containing shadow models for the Asterisk realtime DB.

    All models live under ``app_label='asterisk_state'`` so the DB router
    (:class:`amanati_crm.db_routers.AsteriskStateRouter`) can match on it
    cleanly and keep migrations confined to the ``asterisk`` DB alias.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "asterisk_state"
    label = "asterisk_state"
    verbose_name = "Asterisk realtime state"
