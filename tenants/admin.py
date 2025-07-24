from django.contrib import admin
from tenant_schemas.utils import get_public_schema_name
from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'schema_name', 'domain_url', 'admin_email', 'plan', 'is_active', 'created_on')
    list_filter = ('plan', 'is_active', 'created_on')
    search_fields = ('name', 'schema_name', 'domain_url', 'admin_email')
    readonly_fields = ('schema_name', 'created_on')
    
    def get_queryset(self, request):
        # Only show tenants in the public schema
        qs = super().get_queryset(request)
        if hasattr(request, 'tenant') and request.tenant.schema_name != get_public_schema_name():
            return qs.none()
        return qs
