from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate
from tenant_schemas.utils import get_public_schema_name, schema_context
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes
from .models import Tenant
from .serializers import (
    TenantSerializer, TenantCreateSerializer, TenantRegistrationSerializer,
    TenantLoginSerializer, TenantDashboardDataSerializer
)
from .services import SingleFrontendDeploymentService, TenantConfigAPI
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@extend_schema(
    operation_id='tenant_login',
    summary='Tenant Login',
    description='Authenticate a user within a specific tenant and get dashboard data. This endpoint only works from tenant subdomains (*.api.echodesk.ge).',
    request=TenantLoginSerializer,
    responses={
        200: OpenApiResponse(
            description='Login successful',
            response={
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'token': {'type': 'string'},
                    'dashboard_data': {'type': 'object'}
                }
            }
        ),
        400: OpenApiResponse(description='Invalid credentials or validation errors'),
        403: OpenApiResponse(description='Not available from main domain')
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([])  # No authentication required for login
def tenant_login(request):
    """
    Tenant-specific login endpoint for dashboard access
    """
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = TenantLoginSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # Get or create token for the user
        token, created = Token.objects.get_or_create(user=user)
        
        # Get dashboard data
        dashboard_serializer = TenantDashboardDataSerializer(user, context={'request': request})
        
        return Response({
            'message': 'Login successful',
            'token': token.key,
            'dashboard_data': dashboard_serializer.data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='tenant_logout',
    summary='Tenant Logout',
    description='Logout the current user and invalidate their authentication token. This endpoint only works from tenant subdomains.',
    responses={
        200: OpenApiResponse(
            description='Logout successful',
            response={
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'}
                }
            }
        ),
        400: OpenApiResponse(description='Error during logout'),
        403: OpenApiResponse(description='Not available from main domain')
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def tenant_logout(request):
    """
    Tenant-specific logout endpoint
    """
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Delete the user's token
        request.user.auth_token.delete()
        return Response({
            'message': 'Successfully logged out'
        }, status=status.HTTP_200_OK)
    except:
        return Response(
            {'error': 'Error during logout'}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(
    operation_id='tenant_dashboard',
    summary='Get Tenant Dashboard Data',
    description='Get comprehensive dashboard data including tenant information, user details, and statistics. Requires authentication.',
    responses={
        200: TenantDashboardDataSerializer,
        403: OpenApiResponse(description='Not available from main domain')
    },
    tags=['Dashboard']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def tenant_dashboard(request):
    """
    Get tenant dashboard data for authenticated users
    """
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = TenantDashboardDataSerializer(request.user, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    operation_id='tenant_profile',
    summary='Get User Profile',
    description='Get current user profile information including groups and permissions within the tenant context.',
    responses={
        200: OpenApiResponse(
            description='User profile data with groups and permissions',
            response={
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'email': {'type': 'string'},
                    'first_name': {'type': 'string'},
                    'last_name': {'type': 'string'},
                    'is_staff': {'type': 'boolean'},
                    'is_superuser': {'type': 'boolean'},
                    'date_joined': {'type': 'string', 'format': 'date-time'},
                    'last_login': {'type': 'string', 'format': 'date-time'},
                    'is_active': {'type': 'boolean'},
                    'groups': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer'},
                                'name': {'type': 'string'},
                                'permissions': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'id': {'type': 'integer'},
                                            'codename': {'type': 'string'},
                                            'name': {'type': 'string'},
                                            'app_label': {'type': 'string'},
                                            'model': {'type': 'string'}
                                        }
                                    }
                                }
                            }
                        }
                    },
                    'all_permissions': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'List of all permission codenames user has'
                    }
                }
            }
        ),
        403: OpenApiResponse(description='Not available from main domain')
    },
    tags=['User Profile']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def tenant_profile(request):
    """
    Get current user profile information including groups and permissions
    """
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    user = request.user
    
    # Get user's groups with permissions
    groups_data = []
    for group in user.groups.all():
        permissions_data = []
        for permission in group.permissions.all():
            permissions_data.append({
                'id': permission.id,
                'codename': permission.codename,
                'name': permission.name,
                'app_label': permission.content_type.app_label,
                'model': permission.content_type.model
            })
        
        groups_data.append({
            'id': group.id,
            'name': group.name,
            'permissions': permissions_data
        })
    
    # Get all user permissions (both from groups and direct permissions)
    all_permissions = user.get_all_permissions()
    
    return Response({
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'date_joined': user.date_joined,
        'last_login': user.last_login,
        'is_active': user.is_active,
        'groups': groups_data,
        'all_permissions': list(all_permissions)
    }, status=status.HTTP_200_OK)


@extend_schema(
    operation_id='update_tenant_profile',
    summary='Update User Profile',
    description='Update current user profile information (first_name and last_name only).',
    request={
        'type': 'object',
        'properties': {
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'}
        }
    },
    responses={
        200: OpenApiResponse(
            description='Profile updated successfully',
            response={
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'user': {'type': 'object'}
                }
            }
        ),
        403: OpenApiResponse(description='Not available from main domain')
    },
    tags=['User Profile']
)
@api_view(['PUT', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def update_tenant_profile(request):
    """
    Update current user profile information
    """
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    user = request.user
    data = request.data
    
    # Update allowed fields
    if 'first_name' in data:
        user.first_name = data['first_name']
    if 'last_name' in data:
        user.last_name = data['last_name']
    
    user.save()
    
    return Response({
        'message': 'Profile updated successfully',
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser
        }
    }, status=status.HTTP_200_OK)


@extend_schema(
    operation_id='change_tenant_password',
    summary='Change User Password',
    description='Change password for the current user. Requires old password for verification. All existing tokens will be invalidated.',
    request={
        'type': 'object',
        'properties': {
            'old_password': {'type': 'string'},
            'new_password': {'type': 'string', 'minLength': 8}
        },
        'required': ['old_password', 'new_password']
    },
    responses={
        200: OpenApiResponse(
            description='Password changed successfully',
            response={
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'}
                }
            }
        ),
        400: OpenApiResponse(description='Invalid old password or validation errors'),
        403: OpenApiResponse(description='Not available from main domain')
    },
    tags=['User Profile']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def change_tenant_password(request):
    """
    Change password for current user in tenant
    """
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    
    if not old_password or not new_password:
        return Response(
            {'error': 'Both old_password and new_password are required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = request.user
    
    # Check old password
    if not user.check_password(old_password):
        return Response(
            {'error': 'Invalid old password'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate new password (basic validation)
    if len(new_password) < 8:
        return Response(
            {'error': 'New password must be at least 8 characters long'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Set new password
    user.set_password(new_password)
    user.save()
    
    # Delete all existing tokens to force re-login
    Token.objects.filter(user=user).delete()
    
    return Response({
        'message': 'Password changed successfully. Please login again.'
    }, status=status.HTTP_200_OK)


@extend_schema(
    operation_id='get_tenant_language',
    summary='Get Tenant Language',
    description='Get the preferred language setting for the current tenant.',
    responses={
        200: OpenApiResponse(
            description='Tenant language information',
            response={
                'type': 'object',
                'properties': {
                    'preferred_language': {'type': 'string'},
                    'tenant_name': {'type': 'string'},
                    'schema_name': {'type': 'string'}
                }
            }
        ),
        403: OpenApiResponse(description='Not available from main domain')
    },
    tags=['Tenant Configuration']
)
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


@extend_schema(
    operation_id='register_tenant',
    summary='Register New Tenant',
    description='Register a new tenant with admin user creation. Only available from the main domain.',
    request=TenantRegistrationSerializer,
    responses={
        201: OpenApiResponse(
            description='Tenant created successfully',
            response={
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'tenant': {'type': 'object'},
                    'frontend_url': {'type': 'string'},
                    'api_url': {'type': 'string'}
                }
            }
        ),
        400: OpenApiResponse(description='Validation errors'),
        403: OpenApiResponse(description='Only available from main domain')
    },
    tags=['Tenant Management']
)
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
                domain_url=f"{domain_name}.api.echodesk.ge",  # Backend API domain
                name=validated_data['company_name'],
                description=validated_data.get('description', ''),
                admin_email=validated_data['admin_email'],
                admin_name=f"{validated_data['admin_first_name']} {validated_data['admin_last_name']}",
                preferred_language=validated_data.get('preferred_language', 'en'),
                plan='basic',  # Default plan
                max_users=10,  # Default limits
                max_storage=1024,  # 1GB default
                deployment_status='deploying'  # Set initial status
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
            
            # Setup frontend access (immediate, no deployment needed)
            deployment_service = SingleFrontendDeploymentService()
            deployment_result = deployment_service.setup_tenant_frontend(tenant)
            
            if deployment_result:
                return Response({
                    'message': 'Tenant created successfully! Your frontend is ready.',
                    'tenant': {
                        'id': tenant.id,
                        'name': tenant.name,
                        'domain_url': tenant.domain_url,
                        'schema': tenant.schema_name,
                        'admin_email': tenant.admin_email,
                        'preferred_language': tenant.preferred_language,
                        'deployment_status': 'deployed',
                        'frontend_url': tenant.frontend_url
                    },
                    'domain_url': tenant.domain_url,
                    'admin_email': validated_data['admin_email'],
                    'preferred_language': tenant.preferred_language,
                    'login_url': f"https://{tenant.domain_url}/admin/",  # API domain admin
                    'api_url': f"https://{tenant.domain_url}/api/",      # API domain
                    'frontend_url': tenant.frontend_url,                 # Frontend domain
                    'deployment_status': 'deployed',
                    'credentials': {
                        'email': validated_data['admin_email'],
                        'note': 'Use the password you provided to login'
                    }
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'error': 'Tenant created but frontend setup failed'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        return Response(
            {'error': f'Failed to create tenant: {str(e)}'}, 
            status=status.HTTP_400_BAD_REQUEST
        )


# Add API endpoint for frontend to get tenant configuration
@api_view(['GET'])
@permission_classes([])
def get_tenant_config(request):
    """
    Get tenant configuration for frontend
    Can be called by subdomain or domain parameter
    """
    subdomain = request.GET.get('subdomain')
    domain = request.GET.get('domain')
    
    if subdomain:
        config = TenantConfigAPI.get_tenant_by_subdomain(subdomain)
    elif domain:
        config = TenantConfigAPI.get_tenant_by_domain(domain)
    else:
        return Response({'error': 'subdomain or domain parameter required'}, status=400)
    
    if config:
        return Response(config)
    else:
        return Response({'error': 'Tenant not found'}, status=404)


@api_view(['GET'])
@permission_classes([])
def get_all_tenants(request):
    """
    Get list of all active tenants for frontend routing
    """
    tenants = TenantConfigAPI.get_all_tenants()
    return Response({
        'tenants': tenants,
        'count': len(tenants)
    })


@api_view(['GET'])
@permission_classes([])
def check_deployment_status(request, tenant_id):
    """Check the deployment status of a tenant's frontend"""
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        return Response({
            'deployment_status': tenant.deployment_status,
            'frontend_url': tenant.frontend_url,
            'message': f'Deployment status: {tenant.get_deployment_status_display()}'
        })
    except Tenant.DoesNotExist:
        return Response({'error': 'Tenant not found'}, status=404)


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
