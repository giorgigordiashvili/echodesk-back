from django.db import models
from tenant_schemas.models import TenantMixin


class Tenant(TenantMixin):
    """
    Tenant model for multi-tenancy support.
    Each tenant represents a separate organization/company.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # Owner/admin contact information
    admin_email = models.EmailField()
    admin_name = models.CharField(max_length=100)
    
    # Plan/subscription information (for future use)
    plan = models.CharField(
        max_length=50, 
        default='basic',
        choices=[
            ('basic', 'Basic'),
            ('premium', 'Premium'),
            ('enterprise', 'Enterprise'),
        ]
    )
    
    # Limits (for future use)
    max_users = models.IntegerField(default=10)
    max_storage = models.BigIntegerField(default=1073741824)  # 1GB in bytes
    
    # Language preference for tenant dashboard
    preferred_language = models.CharField(
        max_length=10,
        default='en',
        choices=[
            ('en', 'English'),
            ('ru', 'Russian'),
            ('ka', 'Georgian'),
        ],
        help_text='Preferred language for the frontend dashboard'
    )
    
    # Frontend deployment fields
    frontend_url = models.URLField(blank=True, null=True, help_text="URL of the deployed frontend")
    deployment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('deploying', 'Deploying'),
            ('deployed', 'Deployed'),
            ('failed', 'Failed'),
        ],
        default='pending',
        help_text="Status of the frontend deployment"
    )
    
    # Auto-created schema name is available as self.schema_name
    # domain_url inherited from TenantMixin
    
    auto_create_schema = True
    auto_drop_schema = False
    
    class Meta:
        db_table = 'tenants_tenant'
    
    def __str__(self):
        return f"{self.name} ({self.schema_name})"
    
    @property
    def is_public_schema(self):
        """Check if this is the public schema"""
        return self.schema_name == 'public'
