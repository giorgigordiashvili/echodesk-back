from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from rest_framework.authtoken.models import Token
from .models import Tenant

User = get_user_model()


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for Tenant model"""
    
    class Meta:
        model = Tenant
        fields = (
            'id', 'schema_name', 'domain_url', 'name', 'description', 'admin_email',
            'admin_name', 'plan', 'max_users', 'max_storage', 'preferred_language',
            'frontend_url', 'deployment_status', 'is_active', 'created_on',
            'min_users_per_ticket', 'only_superadmin_can_delete_tickets'
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
    
    # Package selection
    package_id = serializers.IntegerField(help_text="Selected package ID")
    pricing_model = serializers.ChoiceField(
        choices=[('agent', 'Agent-based'), ('crm', 'CRM-based')],
        help_text="Pricing model preference"
    )
    agent_count = serializers.IntegerField(
        default=1, 
        min_value=1, 
        help_text="Number of agents (required for agent-based pricing)"
    )
    
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
    
    def validate_package_id(self, value):
        """Validate that package exists and is active"""
        from .models import Package
        try:
            package = Package.objects.get(id=value, is_active=True)
            return value
        except Package.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive package selected")
    
    def validate(self, attrs):
        """Cross-field validation"""
        from .models import Package, PricingModel
        
        package_id = attrs.get('package_id')
        pricing_model = attrs.get('pricing_model')
        agent_count = attrs.get('agent_count', 1)
        
        # Validate package matches pricing model
        try:
            package = Package.objects.get(id=package_id, is_active=True)
            if package.pricing_model != pricing_model:
                raise serializers.ValidationError(
                    f"Selected package uses {package.get_pricing_model_display()} pricing, "
                    f"but you selected {dict(self.fields['pricing_model'].choices)[pricing_model]} pricing"
                )
            
            # For agent-based pricing, validate agent count
            if pricing_model == 'agent' and agent_count < 1:
                raise serializers.ValidationError("Agent count must be at least 1 for agent-based pricing")
            
            # For CRM-based pricing, agent_count is not used
            if pricing_model == 'crm':
                attrs['agent_count'] = 1  # Set default for CRM-based
                
        except Package.DoesNotExist:
            raise serializers.ValidationError("Invalid package selected")
        
        return attrs
    
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


class TenantLoginSerializer(serializers.Serializer):
    """
    Serializer for tenant-specific login
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            # Get the current tenant from the request context
            request = self.context.get('request')
            if not hasattr(request, 'tenant'):
                raise serializers.ValidationError('This endpoint is only available from tenant subdomains')
            
            user = authenticate(request=request, username=email, password=password)
            
            if not user:
                raise serializers.ValidationError('Invalid email or password')
            
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Must include email and password')
        
        return attrs


class TenantDashboardDataSerializer(serializers.Serializer):
    """
    Serializer for tenant dashboard data
    """
    tenant_info = serializers.SerializerMethodField()
    user_info = serializers.SerializerMethodField()
    statistics = serializers.SerializerMethodField()
    
    def get_tenant_info(self, obj):
        """Get tenant information"""
        request = self.context.get('request')
        tenant = request.tenant
        
        return {
            'id': tenant.id,
            'name': tenant.name,
            'description': tenant.description,
            'domain_url': tenant.domain_url,
            'preferred_language': tenant.preferred_language,
            'plan': tenant.plan,
            'frontend_url': tenant.frontend_url,
            'deployment_status': tenant.deployment_status,
            'created_on': tenant.created_on,
            'is_active': tenant.is_active
        }
    
    def get_user_info(self, obj):
        """Get current user information"""
        user = obj
        return {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'date_joined': user.date_joined
        }
    
    def get_statistics(self, obj):
        """Get tenant statistics including SIP functionality"""
        from django.contrib.auth import get_user_model
        from tickets.models import Ticket
        from crm.models import Client, CallLog, SipConfiguration
        from django.utils import timezone
        
        User = get_user_model()
        
        try:
            # Count users in current tenant
            total_users = User.objects.count()
            active_users = User.objects.filter(is_active=True).count()
            
            # Count tickets if tickets app exists
            try:
                total_tickets = Ticket.objects.count()
                open_tickets = Ticket.objects.filter(status__in=['open', 'in_progress']).count()
            except:
                total_tickets = 0
                open_tickets = 0
            
            # Count clients if CRM app exists
            try:
                total_clients = Client.objects.count()
                active_clients = Client.objects.filter(is_active=True).count()
            except:
                total_clients = 0
                active_clients = 0
            
            # SIP and call statistics
            try:
                # SIP configurations
                sip_configs = SipConfiguration.objects.filter(created_by__tenant=self.context['request'].tenant)
                active_sip_configs = sip_configs.filter(is_active=True)
                default_sip_config = sip_configs.filter(is_default=True, is_active=True).first()
                
                # Call statistics (today)
                today = timezone.now().date()
                calls_today = CallLog.objects.filter(started_at__date=today)
                
                # Call statistics (this week)
                week_start = timezone.now().date() - timezone.timedelta(days=7)
                calls_week = CallLog.objects.filter(started_at__date__gte=week_start)
                
                sip_stats = {
                    'configurations': {
                        'total': sip_configs.count(),
                        'active': active_sip_configs.count(),
                        'has_default': default_sip_config is not None
                    },
                    'calls_today': {
                        'total': calls_today.count(),
                        'answered': calls_today.filter(status='answered').count(),
                        'missed': calls_today.filter(status='missed').count(),
                        'inbound': calls_today.filter(direction='inbound').count(),
                        'outbound': calls_today.filter(direction='outbound').count()
                    },
                    'calls_week': {
                        'total': calls_week.count(),
                        'answered': calls_week.filter(status='answered').count(),
                        'missed': calls_week.filter(status='missed').count()
                    },
                    'default_config': {
                        'id': default_sip_config.id if default_sip_config else None,
                        'name': default_sip_config.name if default_sip_config else None,
                        'server': default_sip_config.sip_server if default_sip_config else None
                    } if default_sip_config else None
                }
            except:
                sip_stats = {
                    'configurations': {'total': 0, 'active': 0, 'has_default': False},
                    'calls_today': {'total': 0, 'answered': 0, 'missed': 0, 'inbound': 0, 'outbound': 0},
                    'calls_week': {'total': 0, 'answered': 0, 'missed': 0},
                    'default_config': None
                }
            
            return {
                'users': {
                    'total': total_users,
                    'active': active_users
                },
                'tickets': {
                    'total': total_tickets,
                    'open': open_tickets
                },
                'clients': {
                    'total': total_clients,
                    'active': active_clients
                },
                'sip': sip_stats
            }
        except Exception as e:
            return {
                'error': f'Could not fetch statistics: {str(e)}'
            }
