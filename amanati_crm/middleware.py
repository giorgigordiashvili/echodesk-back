"""
Custom middleware for EchoDesk multi-tenant routing
"""
from django.conf import settings
from django.http import Http404
from django.urls import reverse
from tenant_schemas.middleware import TenantMiddleware
from tenant_schemas.utils import get_public_schema_name


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
        
        # For subdomains, use the standard tenant lookup
        return super().get_tenant(domain_url, path)
    
    def process_request(self, request):
        """
        Process the request and set the appropriate tenant
        """
        # Get the hostname
        hostname = request.get_host().split(':')[0].lower()
        
        # Log the hostname for debugging
        if settings.DEBUG:
            print(f"[DEBUG] Hostname: {hostname}")
        
        # Use the parent class method to process the request
        # but override the tenant lookup logic
        domain_url = hostname
        path = request.get_full_path()
        
        try:
            tenant = self.get_tenant(domain_url, path)
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
        else:
            # Use default tenant URLs
            request.urlconf = getattr(settings, 'ROOT_URLCONF', None)
