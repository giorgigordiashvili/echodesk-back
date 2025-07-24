from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from tenant_schemas.utils import get_public_schema_name, schema_context
from django.contrib.auth import get_user_model
from .models import Tenant
from .serializers import TenantSerializer, TenantCreateSerializer

User = get_user_model()


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
