from rest_framework import serializers
from .models import Tenant


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for Tenant model"""
    
    class Meta:
        model = Tenant
        fields = (
            'id', 'schema_name', 'domain_url', 'name', 'description', 'admin_email', 
            'admin_name', 'plan', 'max_users', 'max_storage', 
            'is_active', 'created_on'
        )
        read_only_fields = ('id', 'schema_name', 'created_on')


class TenantCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new tenants"""
    
    domain = serializers.CharField(write_only=True, help_text="Subdomain for the tenant (e.g., 'acme' for acme.echodesk.ge)")
    
    class Meta:
        model = Tenant
        fields = (
            'name', 'description', 'admin_email', 'admin_name', 
            'plan', 'max_users', 'max_storage', 'domain'
        )
    
    def create(self, validated_data):
        domain_name = validated_data.pop('domain')
        schema_name = domain_name.lower().replace('-', '_')
        
        # Create the tenant with domain_url
        tenant = Tenant.objects.create(
            domain_url=f"{domain_name}.echodesk.ge",
            schema_name=schema_name,
            **validated_data
        )
        
        return tenant
    
    def validate_domain(self, value):
        """Validate that the domain is unique and follows naming conventions"""
        import re
        
        # Check format (only lowercase letters, numbers, and hyphens)
        if not re.match(r'^[a-z0-9-]+$', value):
            raise serializers.ValidationError(
                "Domain can only contain lowercase letters, numbers, and hyphens."
            )
        
        # Check if domain already exists
        full_domain = f"{value}.echodesk.ge"
        if Tenant.objects.filter(domain_url=full_domain).exists():
            raise serializers.ValidationError(
                f"Domain '{full_domain}' is already taken."
            )
        
        # Reserved subdomains
        reserved = ['www', 'api', 'admin', 'mail', 'ftp', 'public', 'app']
        if value.lower() in reserved:
            raise serializers.ValidationError(
                f"'{value}' is a reserved subdomain."
            )
        
        return value
