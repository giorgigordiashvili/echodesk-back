"""
Debug middleware to catch transaction errors early
"""
import logging
from django.db import connection

logger = logging.getLogger('django.request')


class TransactionDebugMiddleware:
    """Middleware to debug transaction state throughout request lifecycle"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check transaction state at the start of the request
        if request.path.startswith('/admin/tenants/feature/'):
            logger.info(f"🔍 Transaction Debug - START of request: {request.path}")
            if hasattr(request, 'tenant'):
                logger.info(f"   Tenant: {request.tenant.schema_name}")
            else:
                logger.info(f"   No tenant set yet")
            self.check_transaction_state("START OF REQUEST")

        # Process the request
        response = self.get_response(request)

        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Called just before Django calls the view"""
        if request.path.startswith('/admin/tenants/feature/'):
            logger.info(f"🔍 Transaction Debug - BEFORE VIEW: {view_func.__name__}")

            # Force establish connection and rollback any transaction to start fresh
            from django.db import connection
            try:
                # Force connection to be established
                connection.ensure_connection()
                logger.info(f"   Ensured database connection exists")

                if connection.connection:
                    status = connection.connection.get_transaction_status()
                    logger.info(f"   Transaction status before rollback: {status}")

                    # Always rollback to ensure clean state
                    connection.rollback()
                    logger.info(f"   Forced rollback to start fresh")

                    # Verify status after rollback
                    new_status = connection.connection.get_transaction_status()
                    logger.info(f"   Transaction status after rollback: {new_status}")
            except Exception as e:
                logger.error(f"   Error during forced rollback: {e}", exc_info=True)

            self.check_transaction_state(f"BEFORE VIEW {view_func.__name__}")
        return None

    def process_template_response(self, request, response):
        """Called after view returns a TemplateResponse"""
        if request.path.startswith('/admin/tenants/feature/'):
            logger.info(f"🔍 Transaction Debug - TEMPLATE RESPONSE")
            self.check_transaction_state("TEMPLATE RESPONSE")
        return response

    def process_exception(self, request, exception):
        """Called when view raises an exception"""
        if request.path.startswith('/admin/tenants/feature/'):
            logger.error(f"🔍 Transaction Debug - EXCEPTION: {exception}")
            self.check_transaction_state(f"AFTER EXCEPTION: {exception}")
        return None

    def check_transaction_state(self, label):
        """Check and log the current transaction state"""
        if not connection.connection:
            logger.info(f"   [{label}] No database connection yet")
            return

        try:
            # PostgreSQL transaction status codes:
            # 0 = IDLE
            # 1 = ACTIVE
            # 2 = IN_TRANSACTION
            # 3 = IN_ERROR
            # 4 = UNKNOWN
            status = connection.connection.get_transaction_status()
            status_names = {
                0: "IDLE",
                1: "ACTIVE",
                2: "IN_TRANSACTION",
                3: "IN_ERROR ❌",
                4: "UNKNOWN"
            }
            status_name = status_names.get(status, f"UNKNOWN({status})")

            if status == 3:  # IN_ERROR
                logger.error(f"   [{label}] Transaction status: {status_name} - POISONED!")
                logger.error(f"   [{label}] Rolling back poisoned transaction...")
                connection.rollback()
                logger.info(f"   [{label}] Transaction rolled back, status now: {status_names.get(connection.connection.get_transaction_status(), 'UNKNOWN')}")
            else:
                logger.info(f"   [{label}] Transaction status: {status_name}")
        except Exception as e:
            logger.error(f"   [{label}] Error checking transaction state: {e}")
