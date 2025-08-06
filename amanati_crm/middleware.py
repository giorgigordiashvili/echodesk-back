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
    
    def get_tenant(self, domain_url, path):
        """
        Override to handle main domain routing
        """
        main_domain = getattr(settings, 'MAIN_DOMAIN', 'echodesk.ge')
        
        # If accessing main domain, use public schema
        if domain_url == main_domain:
            from tenants.models import Tenant
            # Create a fake tenant object for public schema
            public_tenant = Tenant()
            public_tenant.schema_name = get_public_schema_name()
            public_tenant.domain_url = main_domain
            return public_tenant
        
        # For subdomains, extract the subdomain and look up the tenant
        try:
            from tenants.models import Tenant
            # Look up tenant by domain_url
            tenant = Tenant.objects.get(domain_url=domain_url)
            return tenant
        except Tenant.DoesNotExist:
            # If tenant not found, raise exception to trigger fallback
            raise Exception(f"No tenant found for domain: {domain_url}")
    
    def process_request(self, request):
        """
        Process the request and set the appropriate tenant
        """
        # Get the hostname
        hostname = request.get_host().split(':')[0].lower()
        
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
        connection.set_tenant(request.tenant)
        
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
