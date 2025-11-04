from django.apps import AppConfig


class LeaveManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'leave_management'
    verbose_name = 'Leave Management'

    def ready(self):
        """
        Import signal handlers when app is ready
        """
        # Import signals here if needed in future
        pass
