from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.csrf import ensure_csrf_cookie
from tenant_schemas.utils import get_public_schema_name, schema_context
from django.contrib.auth import get_user_model
from .models import Tenant
from .serializers import TenantSerializer, TenantCreateSerializer, TenantRegistrationSerializer

User = get_user_model()


@api_view(['GET'])
@permission_classes([])  # No authentication required
def get_tenant_language(request):
    """
    Get the preferred language for the current tenant
    """
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    return Response({
        'preferred_language': request.tenant.preferred_language,
        'tenant_name': request.tenant.name,
        'schema_name': request.tenant.schema_name
    })


@api_view(['PUT', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def update_tenant_language(request):
    """
    Update the preferred language for the current tenant
    Only authenticated users can change the language
    """
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    language = request.data.get('preferred_language')
    
    # Validate language choice
    valid_languages = ['en', 'ru', 'ka']
    if language not in valid_languages:
        return Response(
            {'error': f'Invalid language. Must be one of: {", ".join(valid_languages)}'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Update tenant language
    request.tenant.preferred_language = language
    request.tenant.save()
    
    return Response({
        'message': 'Language preference updated successfully',
        'preferred_language': request.tenant.preferred_language,
        'tenant_name': request.tenant.name
    })


def public_homepage(request):
    """
    Homepage view for the public schema (main domain)
    Redirects directly to the admin panel
    """
    return redirect('/admin/')


@ensure_csrf_cookie
def register_tenant_form(request):
    """
    Serve the tenant registration form
    """
    # Only allow access from public schema
    if hasattr(request, 'tenant') and request.tenant.schema_name != get_public_schema_name():
        return JsonResponse(
            {'error': 'Registration is only available from the main domain'}, 
            status=403
        )
    
    return render(request, 'tenants/register.html')


@api_view(['POST'])
@permission_classes([])  # No authentication required
def register_tenant(request):
    """
    Public endpoint for tenant registration with admin user creation
    """
    # Only allow access from public schema
    if hasattr(request, 'tenant') and request.tenant.schema_name != get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from the main domain'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = TenantRegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    validated_data = serializer.validated_data
    
    try:
        with transaction.atomic():
            # Create tenant
            domain_name = validated_data['domain']
            schema_name = domain_name.lower().replace('-', '_')
            
            tenant = Tenant.objects.create(
                schema_name=schema_name,
                domain_url=f"{domain_name}.echodesk.ge",
                name=validated_data['company_name'],
                description=validated_data.get('description', ''),
                admin_email=validated_data['admin_email'],
                admin_name=f"{validated_data['admin_first_name']} {validated_data['admin_last_name']}",
                preferred_language=validated_data.get('preferred_language', 'en'),
                plan='basic',  # Default plan
                max_users=10,  # Default limits
                max_storage=1024  # 1GB default
            )
            
            # Create admin user in tenant schema
            with schema_context(tenant.schema_name):
                admin_user = User.objects.create_user(
                    email=validated_data['admin_email'],
                    password=validated_data['admin_password'],
                    first_name=validated_data['admin_first_name'],
                    last_name=validated_data['admin_last_name'],
                    is_staff=True,
                    is_superuser=True,
                    is_active=True
                )
            
            return Response({
                'message': 'Tenant created successfully!',
                'tenant': {
                    'id': tenant.id,
                    'name': tenant.name,
                    'domain_url': tenant.domain_url,  # This is what the form expects
                    'schema': tenant.schema_name,
                    'admin_email': tenant.admin_email,
                    'preferred_language': tenant.preferred_language
                },
                'domain_url': tenant.domain_url,  # Also at root level for easy access
                'admin_email': validated_data['admin_email'],
                'preferred_language': tenant.preferred_language,
                'login_url': f"https://{tenant.domain_url}/admin/",
                'api_url': f"https://{tenant.domain_url}/api/",
                'credentials': {
                    'email': validated_data['admin_email'],
                    'note': 'Use the password you provided to login'
                }
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response(
            {'error': f'Failed to create tenant: {str(e)}'}, 
            status=status.HTTP_400_BAD_REQUEST
        )


class TenantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenants.
    Only accessible from the public schema.
    """
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TenantCreateSerializer
        return TenantSerializer
    
    def get_queryset(self):
        # Only allow access from public schema
        if not hasattr(self.request, 'tenant') or self.request.tenant.schema_name != get_public_schema_name():
            return Tenant.objects.none()
        return super().get_queryset()
    
    @action(detail=True, methods=['post'])
    def create_admin_user(self, request, pk=None):
        """Create an admin user for a specific tenant"""
        tenant = self.get_object()
        
        # Get user data from request
        email = request.data.get('email')
        password = request.data.get('password')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        
        if not email or not password:
            return Response(
                {'error': 'Email and password are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create user in tenant's schema
        with schema_context(tenant.schema_name):
            try:
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    is_staff=True,
                    is_superuser=True
                )
                return Response({
                    'message': f'Admin user created successfully for tenant {tenant.name}',
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name
                    }
                })
            except Exception as e:
                return Response(
                    {'error': f'Failed to create user: {str(e)}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get all users for a specific tenant"""
        tenant = self.get_object()
        
        with schema_context(tenant.schema_name):
            users = User.objects.all()
            user_data = [{
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'date_joined': user.date_joined
            } for user in users]
            
        return Response({'users': user_data})
