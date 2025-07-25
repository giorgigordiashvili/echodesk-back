import requests
import json
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class SingleFrontendDeploymentService:
    """Service to deploy tenant to a single Next.js frontend"""
    
    def __init__(self):
        self.frontend_base_url = getattr(settings, 'FRONTEND_BASE_URL', 'echodesk.ge')
        self.revalidation_secret = getattr(settings, 'REVALIDATION_SECRET', 'your-secret-key')
        
    def setup_tenant_frontend(self, tenant):
        """
        Setup tenant frontend configuration (no new deployment needed)
        Just register the tenant in our frontend routing system
        """
        try:
            logger.info(f"Setting up frontend access for tenant: {tenant.name}")
            
            # Create tenant-specific frontend URL using subdomain on main domain
            # Backend API: tenant.api.echodesk.ge
            # Frontend: tenant.echodesk.ge
            frontend_url = f"https://{tenant.schema_name}.{self.frontend_base_url}"
            
            # Update tenant with frontend URL
            tenant.frontend_url = frontend_url
            tenant.deployment_status = 'deployed'
            tenant.save()
            
            # Optionally trigger a revalidation/cache clear on the frontend
            self.notify_frontend_of_new_tenant(tenant)
            
            logger.info(f"Frontend setup complete for {tenant.name}: {tenant.frontend_url}")
            return {
                'url': tenant.frontend_url,
                'status': 'deployed',
                'message': 'Frontend configured successfully'
            }
                
        except Exception as e:
            logger.error(f"Frontend setup failed for tenant {tenant.name}: {str(e)}")
            tenant.deployment_status = 'failed'
            tenant.save()
            return None
    
    def notify_frontend_of_new_tenant(self, tenant):
        """
        Notify the frontend about the new tenant (optional)
        This can trigger cache invalidation or webhook calls
        """
        try:
            # Call a webhook on your frontend to clear cache
            webhook_url = f"https://{self.frontend_base_url}/api/revalidate"
            
            payload = {
                'tenant_id': tenant.id,
                'schema_name': tenant.schema_name,
                'domain_url': tenant.domain_url,
                'secret': self.revalidation_secret
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Successfully notified frontend about new tenant: {tenant.name}")
            else:
                logger.warning(f"Frontend notification failed: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Could not notify frontend: {str(e)}")
            # This is not critical, so we don't fail the deployment
    
    def get_tenant_frontend_config(self, tenant):
        """
        Generate configuration that the frontend will use for this tenant
        """
        return {
            'tenant_id': tenant.id,
            'tenant_name': tenant.name,
            'schema_name': tenant.schema_name,
            'domain_url': tenant.domain_url,  # API domain: tenant.api.echodesk.ge
            'api_url': f"https://{tenant.domain_url}/api",  # Full API URL
            'preferred_language': tenant.preferred_language,
            'admin_email': tenant.admin_email,
            'plan': tenant.plan,
            'frontend_url': tenant.frontend_url,  # Frontend domain: tenant.echodesk.ge
            'theme': {
                'primary_color': '#667eea',
                'secondary_color': '#764ba2',
                'company_name': tenant.name,
                'logo_url': f'/api/tenant/{tenant.id}/logo/' if hasattr(tenant, 'logo') else None
            },
            'features': {
                'max_users': tenant.max_users,
                'max_storage': tenant.max_storage,
                'analytics': tenant.plan in ['pro', 'enterprise'],
                'custom_branding': tenant.plan == 'enterprise',
                'api_access': True,
                'webhooks': tenant.plan != 'basic'
            },
            'localization': {
                'language': tenant.preferred_language,
                'timezone': getattr(tenant, 'timezone', 'UTC'),
                'date_format': 'DD/MM/YYYY' if tenant.preferred_language in ['ru', 'ka'] else 'MM/DD/YYYY'
            }
        }

class TenantConfigAPI:
    """API helper for frontend to get tenant configuration"""
    
    @staticmethod
    def get_tenant_by_subdomain(subdomain):
        """Get tenant configuration by subdomain for frontend"""
        from .models import Tenant
        
        try:
            # Try to find tenant by schema_name (subdomain)
            tenant = Tenant.objects.get(schema_name=subdomain)
            service = SingleFrontendDeploymentService()
            return service.get_tenant_frontend_config(tenant)
        except Tenant.DoesNotExist:
            return None
    
    @staticmethod
    def get_tenant_by_domain(domain):
        """Get tenant configuration by domain for frontend"""
        from .models import Tenant
        
        try:
            tenant = Tenant.objects.get(domain_url=domain)
            service = SingleFrontendDeploymentService()
            return service.get_tenant_frontend_config(tenant)
        except Tenant.DoesNotExist:
            return None
    
    @staticmethod
    def get_all_tenants():
        """Get list of all active tenants for frontend routing"""
        from .models import Tenant
        
        tenants = Tenant.objects.filter(is_active=True, deployment_status='deployed')
        return [{
            'schema_name': tenant.schema_name,
            'domain_url': tenant.domain_url,
            'frontend_url': tenant.frontend_url,
            'name': tenant.name
        } for tenant in tenants]
