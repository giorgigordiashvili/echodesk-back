from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import authenticate
from django.http import JsonResponse
from rest_framework.authtoken.models import Token
from .models import User
from .serializers import UserSerializer, UserCreateSerializer


def tenant_homepage(request):
    """
    Homepage view for tenant schemas (subdomains)
    """
    tenant = getattr(request, 'tenant', None)
    user_count = User.objects.count()
    
    return JsonResponse({
        'message': f'Welcome to {tenant.name if tenant else "Your Tenant"}',
        'domain': request.get_host(),
        'schema': tenant.schema_name if tenant else 'unknown',
        'tenant_name': tenant.name if tenant else 'Unknown',
        'user_count': user_count,
        'endpoints': {
            'admin': '/admin/',
            'api_docs': '/api/docs/',
            'api_schema': '/api/schema/',
            'users_api': '/api/users/',
            'login': '/api/users/login/',
            'current_user': '/api/users/me/'
        }
    })


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User model with tenant-specific user management"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer
    
    def get_permissions(self):
        """
        Different permissions for different actions
        """
        if self.action == 'create':
            # Only staff can create users
            permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
        elif self.action in ['update', 'partial_update', 'destroy']:
            # Only staff can modify other users, users can modify themselves
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter users based on permissions"""
        user = self.request.user
        if user.is_staff:
            return User.objects.all()
        else:
            # Regular users can only see themselves
            return User.objects.filter(id=user.id)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user info"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], permission_classes=[])
    def login(self, request):
        """Login endpoint that returns a token"""
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response(
                {'error': 'Email and password required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(request, username=email, password=password)
        if user:
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            })
        else:
            return Response(
                {'error': 'Invalid credentials'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
    
    @action(detail=False, methods=['post'])
    def logout(self, request):
        """Logout endpoint that deletes the token"""
        try:
            request.user.auth_token.delete()
            return Response({'message': 'Successfully logged out'})
        except:
            return Response(
                {'error': 'Error logging out'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change password for current user"""
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not old_password or not new_password:
            return Response(
                {'error': 'Both old and new passwords required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not request.user.check_password(old_password):
            return Response(
                {'error': 'Invalid old password'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        request.user.set_password(new_password)
        request.user.save()
        
        return Response({'message': 'Password changed successfully'})
