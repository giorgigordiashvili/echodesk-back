from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        # Register signal handlers for optional modules (invoices, leave, bookings, calls)
        import users.module_signals  # noqa: F401
