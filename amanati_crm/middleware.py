"""
Custom middleware for EchoDesk multi-tenant routing
"""
import logging
import time
import json
from django.conf import settings
from django.http import Http404
from django.urls import reverse
from tenant_schemas.middleware import TenantMiddleware
from tenant_schemas.utils import get_public_schema_name

# Set up logger for request logging
logger = logging.getLogger('django.request')


class EchoDeskTenantMiddleware(TenantMiddleware):
    """
    Custom tenant middleware that handles:
    - Main domain (echodesk.ge) -> Public schema (tenant management)
    - Subdomains (*.echodesk.ge) -> Tenant schemas
    """
    
    def get_tenant(self, model, hostname, request):
        """
        Override to handle main domain routing
        Args:
            model: The Tenant model class
            hostname: The hostname from the request
            request: The HTTP request object
        """
        main_domain = getattr(settings, 'MAIN_DOMAIN', 'echodesk.ge')
        api_domain = getattr(settings, 'API_DOMAIN', 'api.echodesk.ge')

        # If accessing main domain or API domain, use public schema
        if hostname == main_domain or hostname == api_domain:
            # Create a fake tenant object for public schema
            public_tenant = model()
            public_tenant.schema_name = get_public_schema_name()
            public_tenant.domain_url = hostname
            return public_tenant

        # For subdomains (e.g., groot.api.echodesk.ge), extract subdomain and look up tenant
        # Check if it's a tenant subdomain of API domain
        if hostname.endswith(f'.{api_domain}'):
            # Extract subdomain (e.g., "groot" from "groot.api.echodesk.ge")
            subdomain = hostname.replace(f'.{api_domain}', '')
            try:
                tenant = model.objects.get(schema_name=subdomain)
                return tenant
            except model.DoesNotExist:
                # Silently return 404 for unknown subdomains (likely bots)
                logger.debug(f"Unknown subdomain: {subdomain}")
                raise Http404(f"Not found")

        # For main domain subdomains, look up by domain_url
        try:
            # Look up tenant by domain_url
            tenant = model.objects.get(domain_url=hostname)
            return tenant
        except model.DoesNotExist:
            # Silently return 404 for unknown domains (likely bots probing)
            logger.debug(f"Unknown domain: {hostname}")
            raise Http404(f"Not found")
    
    def process_request(self, request):
        """
        Process the request and set the appropriate tenant
        """
        # Get the hostname
        hostname = request.get_host().split(':')[0].lower()

        # Widget public endpoints carry their own token that resolves the tenant
        # internally (the view activates the tenant schema via schema_context
        # once the token is validated). Keep the public schema active so the
        # WidgetConnection lookup works, and skip the hostname-based lookup that
        # would 404 on the tenant subdomain lookup path.
        if request.path.startswith('/api/widget/public/'):
            from tenants.models import Tenant
            tenant = Tenant()
            tenant.schema_name = get_public_schema_name()
            tenant.domain_url = hostname
            request.tenant = tenant
            from django.db import connection
            try:
                connection.set_tenant(tenant)
            except Exception:
                pass
            request.urlconf = getattr(settings, 'PUBLIC_SCHEMA_URLCONF', None)
            return None

        # Log the hostname for debugging
        if settings.DEBUG:
            print(f"[DEBUG] Hostname: {hostname}")

        # Use our custom tenant lookup logic
        domain_url = hostname
        path = request.get_full_path()

        try:
            tenant = self.get_tenant(domain_url, path)
            if settings.DEBUG:
                print(f"[DEBUG] Found tenant: {tenant.schema_name} for domain: {domain_url}")
        except Exception as e:
            if settings.DEBUG:
                print(f"[DEBUG] Tenant lookup failed: {e}")
            # Fallback to public schema
            from tenants.models import Tenant
            tenant = Tenant()
            tenant.schema_name = get_public_schema_name()
            tenant.domain_url = hostname

        request.tenant = tenant

        # Use parent class method to set up the connection
        from django.db import connection
        try:
            connection.set_tenant(request.tenant)
        except Exception as e:
            # If setting tenant fails, log and rollback any poisoned transaction
            logger.error(f"Failed to set tenant {request.tenant.schema_name}: {e}")
            if connection.connection:
                status = connection.connection.get_transaction_status()
                if status == 3:  # IN_ERROR
                    logger.warning(f"Rolling back poisoned transaction from set_tenant failure")
                    connection.rollback()
            raise

        # Set URL routing based on tenant
        if tenant.schema_name == get_public_schema_name():
            # Use public schema URLs
            request.urlconf = getattr(settings, 'PUBLIC_SCHEMA_URLCONF', None)
            if settings.DEBUG:
                print(f"[DEBUG] Using public schema URLs: {request.urlconf}")
        else:
            # Use default tenant URLs
            request.urlconf = getattr(settings, 'ROOT_URLCONF', None)
            if settings.DEBUG:
                print(f"[DEBUG] Using tenant URLs: {request.urlconf}")


class WidgetPublicCorsMiddleware:
    """Open CORS for the embeddable-chat-widget public endpoints.

    These endpoints are called from arbitrary tenant websites (the whole
    point of the widget), so the global CORS allow-list on
    ``*.echodesk.ge`` doesn't apply. We echo the request's ``Origin``
    header back as ``Access-Control-Allow-Origin`` and short-circuit
    OPTIONS preflight so any origin can talk to the widget API. The
    real authorization happens inside the view via the widget token +
    the tenant's ``allowed_origins`` allowlist — this middleware only
    removes the browser-level CORS blocker so those view-level checks
    can even run.

    Runs before the tenant middleware because the preflight OPTIONS
    request won't carry the widget token and we want to short-circuit
    it without touching the schema.
    """

    WIDGET_PUBLIC_PREFIX = '/api/widget/public/'
    ALLOW_HEADERS = 'accept, accept-encoding, authorization, content-type, origin, user-agent, x-requested-with, cache-control'
    ALLOW_METHODS = 'GET, POST, OPTIONS'
    MAX_AGE = '86400'

    def __init__(self, get_response):
        self.get_response = get_response

    def _is_widget_public(self, request) -> bool:
        return request.path.startswith(self.WIDGET_PUBLIC_PREFIX)

    def __call__(self, request):
        if not self._is_widget_public(request):
            return self.get_response(request)

        origin = request.META.get('HTTP_ORIGIN', '')

        # Short-circuit preflight. We don't run the view — just return the
        # CORS headers so the browser lets the real request through.
        if request.method == 'OPTIONS':
            from django.http import HttpResponse
            response = HttpResponse(status=204)
            if origin:
                response['Access-Control-Allow-Origin'] = origin
                response['Vary'] = 'Origin'
                response['Access-Control-Allow-Methods'] = self.ALLOW_METHODS
                response['Access-Control-Allow-Headers'] = (
                    request.META.get('HTTP_ACCESS_CONTROL_REQUEST_HEADERS')
                    or self.ALLOW_HEADERS
                )
                response['Access-Control-Max-Age'] = self.MAX_AGE
                # Widget API is anonymous by design — never send cookies.
                response['Access-Control-Allow-Credentials'] = 'false'
            return response

        response = self.get_response(request)
        if origin:
            response['Access-Control-Allow-Origin'] = origin
            # Merge with any existing Vary header django-cors-headers may set.
            existing_vary = response.get('Vary', '')
            if 'Origin' not in existing_vary:
                response['Vary'] = (
                    f'{existing_vary}, Origin' if existing_vary else 'Origin'
                )
            response['Access-Control-Allow-Credentials'] = 'false'
        return response


class EcommerceClientCustomDomainCorsMiddleware:
    """Open CORS for ecommerce-client API endpoints when called from a
    tenant's verified custom domain (e.g. ``refurb.ge``).

    The static ``CORS_ALLOWED_ORIGIN_REGEXES`` list whitelists every
    ``*.echodesk.ge`` and ``*.api.echodesk.ge`` host, but custom domains
    registered through ``TenantDomain`` are dynamic and unknown at
    server boot. Without this middleware, a storefront on
    ``refurb.ge`` calling ``groot.api.echodesk.ge`` gets blocked by
    the browser's CORS preflight before any view runs — every product
    fetch / cart action / login fails silently.

    Runs before the tenant middleware so the preflight OPTIONS is
    short-circuited without needing tenant resolution. The hostname
    lookup against ``TenantDomain`` is one indexed query per request;
    the table is small and lives on the public schema.
    """

    ECOMMERCE_PREFIXES = ('/api/ecommerce/',)
    ALLOW_HEADERS = (
        'accept, accept-encoding, authorization, content-type, dnt, '
        'origin, user-agent, x-csrftoken, x-requested-with, '
        'x-tenant-subdomain, x-tenant-domain, cache-control'
    )
    ALLOW_METHODS = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
    MAX_AGE = '86400'

    def __init__(self, get_response):
        self.get_response = get_response

    def _is_ecommerce_client(self, request) -> bool:
        return any(request.path.startswith(p) for p in self.ECOMMERCE_PREFIXES)

    @staticmethod
    def _origin_host(origin: str) -> str:
        if not origin:
            return ''
        try:
            from urllib.parse import urlparse
            return (urlparse(origin).hostname or '').lower()
        except Exception:
            return ''

    @staticmethod
    def _is_verified_custom_domain(host: str) -> bool:
        if not host:
            return False
        from django.core.cache import cache
        cache_key = f'cors_custom_domain:{host}'
        cached = cache.get(cache_key)
        if cached is not None:
            return bool(cached)
        try:
            from tenants.models import TenantDomain
            ok = TenantDomain.objects.filter(
                domain__iexact=host, is_verified=True
            ).exists()
            # Also check EcommerceSettings.custom_domain on each tenant —
            # the resolve-domain endpoint supports both registries and we
            # need to mirror it. Iterating tenants is expensive, so we
            # cache the answer for 5 minutes (matches the resolve-domain
            # revalidate window).
            if not ok:
                from tenants.models import Tenant
                from tenant_schemas.utils import schema_context
                from ecommerce_crm.models import EcommerceSettings
                for t in Tenant.objects.filter(is_active=True).exclude(schema_name='public'):
                    try:
                        with schema_context(t.schema_name):
                            if EcommerceSettings.objects.filter(custom_domain__iexact=host).exists():
                                ok = True
                                break
                    except Exception:
                        continue
            cache.set(cache_key, 1 if ok else 0, 300)
            return ok
        except Exception:
            return False

    def __call__(self, request):
        if not self._is_ecommerce_client(request):
            return self.get_response(request)

        origin = request.META.get('HTTP_ORIGIN', '')
        host = self._origin_host(origin)
        is_custom_domain = self._is_verified_custom_domain(host)

        # Short-circuit the preflight OPTIONS for verified custom-domain
        # origins. The actual request that follows will hit the tenant
        # middleware which routes by the *destination* hostname (the
        # API subdomain), not the Origin.
        if is_custom_domain and request.method == 'OPTIONS':
            from django.http import HttpResponse
            response = HttpResponse(status=204)
            response['Access-Control-Allow-Origin'] = origin
            response['Vary'] = 'Origin'
            response['Access-Control-Allow-Methods'] = self.ALLOW_METHODS
            response['Access-Control-Allow-Headers'] = (
                request.META.get('HTTP_ACCESS_CONTROL_REQUEST_HEADERS')
                or self.ALLOW_HEADERS
            )
            response['Access-Control-Max-Age'] = self.MAX_AGE
            response['Access-Control-Allow-Credentials'] = 'true'
            return response

        response = self.get_response(request)

        if is_custom_domain and not response.has_header('Access-Control-Allow-Origin'):
            response['Access-Control-Allow-Origin'] = origin
            existing_vary = response.get('Vary', '')
            if 'Origin' not in existing_vary:
                response['Vary'] = (
                    f'{existing_vary}, Origin' if existing_vary else 'Origin'
                )
            response['Access-Control-Allow-Credentials'] = 'true'

        return response


class BotBlockerMiddleware:
    """
    Middleware to block suspicious bot requests early before URL routing.
    Returns 404 for:
    - Requests to unknown file types (.php, .asp, .jsp, etc.)
    - Requests to common attack paths
    - Requests to /api without trailing slash (prevents APPEND_SLASH errors)
    """

    BLOCKED_EXTENSIONS = {'.php', '.asp', '.aspx', '.jsp', '.cgi', '.pl', '.sh', '.exe', '.dll'}
    BLOCKED_PATHS = {
        '/wp-admin', '/wp-content', '/wp-includes', '/wordpress',
        '/admin.php', '/xmlrpc.php', '/wp-login.php',
        '/.env', '/.git', '/.svn', '/.htaccess',
        '/phpmyadmin', '/pma', '/mysql', '/myadmin',
        '/shell', '/cmd', '/command', '/eval',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path.lower()

        # Block /api without trailing slash (causes APPEND_SLASH errors on POST)
        if path == '/api':
            from django.http import JsonResponse
            return JsonResponse(
                {'error': 'Not found. API endpoints are under /api/'},
                status=404
            )

        # Block requests to suspicious file extensions
        for ext in self.BLOCKED_EXTENSIONS:
            if path.endswith(ext):
                raise Http404("Not found")

        # Block requests to common attack paths
        for blocked in self.BLOCKED_PATHS:
            if path.startswith(blocked):
                raise Http404("Not found")

        return self.get_response(request)


class RequestLoggingMiddleware:
    """
    Middleware to log every HTTP request when DEBUG=True
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if not settings.DEBUG:
            return self.get_response(request)
        
        # Record start time
        start_time = time.time()
        
        # Get request information
        method = request.method
        path = request.get_full_path()
        remote_addr = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Get request data (be careful with sensitive data)
        request_data = {}
        if method in ['POST', 'PUT', 'PATCH']:
            content_type = request.META.get('CONTENT_TYPE', '')
            if 'application/json' in content_type:
                try:
                    request_data = json.loads(request.body.decode('utf-8'))
                    # Remove sensitive fields
                    sensitive_fields = ['password', 'token', 'secret', 'key']
                    for field in sensitive_fields:
                        if field in request_data:
                            request_data[field] = '***REDACTED***'
                except (json.JSONDecodeError, UnicodeDecodeError):
                    request_data = {'body': 'Unable to parse JSON'}
            elif 'multipart/form-data' in content_type:
                request_data = {'type': 'multipart/form-data', 'note': 'File upload or form data'}
            elif request.POST:
                request_data = dict(request.POST)
                # Remove sensitive fields
                sensitive_fields = ['password', 'token', 'secret', 'key']
                for field in sensitive_fields:
                    if field in request_data:
                        request_data[field] = '***REDACTED***'
        
        # Log the incoming request
        logger.info(f"🔵 REQUEST START: {method} {path} from {remote_addr}")
        logger.info(f"   User-Agent: {user_agent}")
        if request_data:
            logger.info(f"   Request Data: {request_data}")
        
        # Process the request
        response = self.get_response(request)
        
        # Calculate response time
        end_time = time.time()
        duration = round((end_time - start_time) * 1000, 2)  # in milliseconds
        
        # Log the response
        status_code = response.status_code
        status_emoji = self.get_status_emoji(status_code)
        
        logger.info(f"{status_emoji} RESPONSE: {method} {path} -> {status_code} ({duration}ms)")
        
        # Log additional info for errors
        if status_code >= 400:
            logger.warning(f"   ⚠️  Error response for {method} {path}: {status_code}")
            
        return response
    
    def get_client_ip(self, request):
        """Get the real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'Unknown')
        return ip
    
    def get_status_emoji(self, status_code):
        """Get emoji based on status code"""
        if 200 <= status_code < 300:
            return "✅"
        elif 300 <= status_code < 400:
            return "🔄"
        elif 400 <= status_code < 500:
            return "❌"
        elif status_code >= 500:
            return "💥"
        else:
            return "❓"
