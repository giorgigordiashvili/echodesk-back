"""
Custom database backend that logs all queries for debugging
"""
import logging
from tenant_schemas.postgresql_backend.base import DatabaseWrapper as TenantDatabaseWrapper

logger = logging.getLogger('django.db.backends')


class DatabaseWrapper(TenantDatabaseWrapper):
    """Database wrapper with query logging for debugging"""

    def _execute_wrapper(self, method, query, params):
        """Wrap query execution with logging"""
        # Only log for feature admin URLs
        try:
            from django.core.handlers.wsgi import WSGIRequest
            import threading
            request = getattr(threading.current_thread(), 'request', None)
            if request and hasattr(request, 'path') and '/admin/tenants/feature/' in request.path:
                logger.info(f"🔍 SQL Query: {query[:200]}...")
                if params:
                    logger.info(f"   Params: {params}")
        except:
            pass

        try:
            result = method(query, params)
            return result
        except Exception as e:
            logger.error(f"❌ SQL Query FAILED: {query[:200]}...")
            logger.error(f"   Error: {e}")
            raise
