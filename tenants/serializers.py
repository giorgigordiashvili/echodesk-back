from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Tenant

User = get_user_model()


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for Tenant model"""
    
    class Meta:
        model = Tenant
        fields = (
            'id', 'schema_name', 'domain_url', 'name', 'description', 'admin_email', 
            'admin_name', 'plan', 'max_users', 'max_storage', 'preferred_language',
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
            'plan', 'max_users', 'max_storage', 'preferred_language', 'domain'
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


class TenantRegistrationSerializer(serializers.Serializer):
    """
    Public serializer for tenant registration with admin user creation
    """
    # Tenant information
    company_name = serializers.CharField(max_length=100, help_text="Your company or organization name")
    domain = serializers.CharField(max_length=63, help_text="Subdomain for your tenant (e.g., 'acme' for acme.echodesk.ge)")
    description = serializers.CharField(max_length=500, required=False, help_text="Brief description of your organization")
    
    # Admin user information
    admin_email = serializers.EmailField(help_text="Email address for the admin user")
    admin_password = serializers.CharField(min_length=8, write_only=True, help_text="Password for the admin user")
    admin_first_name = serializers.CharField(max_length=30, help_text="Admin's first name")
    admin_last_name = serializers.CharField(max_length=30, help_text="Admin's last name")
    
    # Language preference
    preferred_language = serializers.ChoiceField(
        choices=[
            ('en', 'English'),
            ('ru', 'Russian'), 
            ('ka', 'Georgian'),
        ],
        default='en',
        help_text="Preferred language for the frontend dashboard"
    )
    
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
        reserved = ['www', 'api', 'admin', 'mail', 'ftp', 'public', 'app', 'support', 'help']
        if value.lower() in reserved:
            raise serializers.ValidationError(
                f"'{value}' is a reserved subdomain."
            )
        
        return value
    
    def validate_admin_password(self, value):
        """Validate password strength"""
        import re
        
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter.")
        
        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one number.")
        
        return value
