from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crm'

    def ready(self):
        # Wire post_save / post_delete / m2m_changed handlers that keep the
        # Asterisk realtime DB in sync with product-model mutations. Import
        # is guarded so that a missing migration during collectstatic or
        # similar management commands doesn't spray import-time warnings.
        from . import signals  # noqa: F401

        # The ManyToMany `through` for ``User.tenant_groups`` is only
        # importable after the users app has loaded, so attach it here
        # rather than at module top level.
        try:
            signals.register_group_membership_signal()
        except Exception:  # noqa: BLE001
            # Don't break app init if the users model isn't installed
            # in some odd manage.py check scenario — the signal is an
            # enhancement, not a requirement for the product API.
            import logging

            logging.getLogger(__name__).exception(
                "Failed to register tenant_groups m2m_changed signal"
            )
