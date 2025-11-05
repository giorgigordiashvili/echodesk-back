"""
Custom admin site to debug transaction errors
"""
import logging
from django.contrib.admin import AdminSite
from django.db import connection

logger = logging.getLogger('django.request')


class DebugAdminSite(AdminSite):
    """Admin site with transaction debugging"""

    def admin_view(self, view, cacheable=False):
        """
        Decorator to create an admin view attached to this AdminSite.
        This wraps the view and provides auto-login and permission checking.
        """
        def inner(request, *args, **kwargs):
            logger.info(f"🔍 AdminSite.admin_view called for: {view.__name__}")
            logger.info(f"   Request path: {request.path}")
            logger.info(f"   User: {request.user if hasattr(request, 'user') else 'No user yet'}")

            # Check transaction state
            if connection.connection:
                status = connection.connection.get_transaction_status()
                status_names = {0: "IDLE", 1: "ACTIVE", 2: "IN_TRANSACTION", 3: "IN_ERROR", 4: "UNKNOWN"}
                logger.info(f"   Transaction status BEFORE has_permission check: {status_names.get(status, status)}")
            else:
                logger.info(f"   No DB connection yet before has_permission check")

            # This is where Django checks if user.has_permission()
            # which might trigger database queries
            if not self.has_permission(request):
                logger.info(f"   has_permission returned False, redirecting to login")
                return self.login(request)

            logger.info(f"   has_permission returned True, calling view")

            # Check transaction state after permission check
            if connection.connection:
                status = connection.connection.get_transaction_status()
                status_names = {0: "IDLE", 1: "ACTIVE", 2: "IN_TRANSACTION", 3: "IN_ERROR", 4: "UNKNOWN"}
                logger.info(f"   Transaction status AFTER has_permission check: {status_names.get(status, status)}")

                if status == 3:  # IN_ERROR
                    logger.error(f"   ❌ Transaction poisoned AFTER has_permission check!")
                    logger.error(f"   Rolling back...")
                    connection.rollback()

            return view(request, *args, **kwargs)

        # Call parent's wrapping logic
        return super().admin_view(inner, cacheable)
