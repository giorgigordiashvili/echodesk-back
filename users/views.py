from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import redirect
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count
from rest_framework.authtoken.models import Token
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
import secrets

from .models import User
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    BulkUserActionSerializer, PasswordChangeSerializer
)

User = get_user_model()


def tenant_homepage(request):
    """
    Homepage view for tenant schemas (subdomains)
    Redirects directly to the admin panel
    """
    return redirect('/admin/')


class UserViewSet(viewsets.ModelViewSet):
    """Enhanced ViewSet for comprehensive tenant user management"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'status', 'department', 'is_active', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name', 'phone_number']
    ordering_fields = ['date_joined', 'last_login', 'email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        elif self.action == 'bulk_action':
            return BulkUserActionSerializer
        elif self.action == 'change_password':
            return PasswordChangeSerializer
        return UserSerializer
    
    def get_permissions(self):
        """Enhanced permissions for different actions"""
        if self.action == 'create':
            # Only users with manage_users permission can create
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy']:
            # Users can modify themselves, admins can modify others
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['bulk_action', 'reset_password']:
            # Only admins can perform bulk actions
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter users based on permissions"""
        user = self.request.user
        if user.is_superuser or user.has_permission('manage_users'):
            return User.objects.all()
        elif user.is_manager:
            # Managers can see all users but with limited actions
            return User.objects.all()
        else:
            # Regular users can only see themselves
            return User.objects.filter(id=user.id)
    
    def perform_create(self, serializer):
        """Custom create logic with permission check"""
        if not (self.request.user.is_superuser or self.request.user.has_permission('manage_users')):
            raise permissions.PermissionDenied("You do not have permission to create users")
        serializer.save()
    
    def perform_update(self, serializer):
        """Custom update logic with permission check"""
        user = self.request.user
        target_user = self.get_object()
        
        # Users can always update themselves
        if user == target_user:
            serializer.save()
            return
        
        # Only admins can update other users
        if not (user.is_superuser or user.has_permission('manage_users')):
            raise permissions.PermissionDenied("You do not have permission to modify other users")
        
        serializer.save()
    
    def perform_destroy(self, instance):
        """Custom delete logic with permission check"""
        user = self.request.user
        
        # Can't delete yourself
        if user == instance:
            raise permissions.PermissionDenied("You cannot delete your own account")
        
        # Only admins can delete users
        if not (user.is_superuser or user.has_permission('manage_users')):
            raise permissions.PermissionDenied("You do not have permission to delete users")
        
        # Can't delete other admins unless you're superuser
        if instance.is_admin and not user.is_superuser:
            raise permissions.PermissionDenied("Only superusers can delete admin accounts")
        
        instance.delete()
    
    @extend_schema(
        operation_id='users_me',
        summary='Get Current User Profile',
        description='Get current user profile information with permissions',
    )
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user info"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @extend_schema(
        operation_id='users_bulk_action',
        summary='Bulk User Actions',
        description='Perform bulk actions on multiple users (activate, deactivate, delete, change role, etc.)',
        request=BulkUserActionSerializer
    )
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Perform bulk actions on users"""
        if not (request.user.is_superuser or request.user.has_permission('manage_users')):
            return Response(
                {'error': 'You do not have permission to perform bulk actions'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = BulkUserActionSerializer(data=request.data)
        if serializer.is_valid():
            user_ids = serializer.validated_data['user_ids']
            action = serializer.validated_data['action']
            
            users = User.objects.filter(id__in=user_ids)
            if not users.exists():
                return Response({'error': 'No users found'}, status=status.HTTP_404_NOT_FOUND)
            
            results = []
            
            with transaction.atomic():
                for user in users:
                    try:
                        # Skip self for certain actions
                        if user == request.user and action in ['delete', 'deactivate']:
                            results.append(f"❌ Cannot {action} your own account: {user.email}")
                            continue
                        
                        if action == 'activate':
                            user.status = 'active'
                            user.is_active = True
                            user.save(update_fields=['status', 'is_active'])
                            results.append(f"✅ Activated {user.email}")
                            
                        elif action == 'deactivate':
                            user.status = 'inactive'
                            user.is_active = False
                            user.save(update_fields=['status', 'is_active'])
                            results.append(f"⏸️ Deactivated {user.email}")
                            
                        elif action == 'delete':
                            if user.is_superuser and not request.user.is_superuser:
                                results.append(f"❌ Cannot delete superuser {user.email}")
                                continue
                            email = user.email
                            user.delete()
                            results.append(f"🗑️ Deleted {email}")
                            
                        elif action == 'change_role':
                            old_role = user.role
                            new_role = serializer.validated_data['role']
                            user.role = new_role
                            user.save(update_fields=['role'])
                            results.append(f"👤 Changed {user.email} role: {old_role} → {new_role}")
                            
                        elif action == 'change_status':
                            old_status = user.status
                            new_status = serializer.validated_data['status']
                            user.status = new_status
                            user.is_active = new_status == 'active'
                            user.save(update_fields=['status', 'is_active'])
                            results.append(f"📊 Changed {user.email} status: {old_status} → {new_status}")
                        
                    except Exception as e:
                        results.append(f"❌ Error with {user.email}: {str(e)}")
            
            return Response({
                'message': f'Bulk action "{action}" completed',
                'results': results,
                'processed_count': len([r for r in results if not r.startswith('❌')]),
                'total_requested': len(user_ids)
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        operation_id='users_change_status',
        summary='Change User Status',
        description='Change user status (active, inactive, suspended, pending)',
    )
    @action(detail=True, methods=['patch'])
    def change_status(self, request, pk=None):
        """Change user status"""
        user = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in dict(User.STATUS_CHOICES):
            return Response(
                {'error': f'Invalid status. Choose from: {[choice[0] for choice in User.STATUS_CHOICES]}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_status = user.status
        user.status = new_status
        user.is_active = new_status == 'active'
        user.save(update_fields=['status', 'is_active'])
        
        return Response({
            'message': f'User status changed from {old_status} to {new_status}',
            'user': UserSerializer(user).data
        })
    
    @extend_schema(
        operation_id='users_reset_password',
        summary='Reset User Password',
        description='Reset password for a user (admin only) and generate temporary password',
    )
    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        """Reset user password (admin only)"""
        if not (request.user.is_superuser or request.user.has_permission('manage_users')):
            return Response(
                {'error': 'You do not have permission to reset passwords'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        user = self.get_object()
        
        # Generate new temporary password
        new_password = secrets.token_urlsafe(12)
        user.set_password(new_password)
        user.save(update_fields=['password'])
        
        return Response({
            'message': 'Password reset successfully',
            'temporary_password': new_password,  # In production, send via email
            'user': user.email
        })
    
    @extend_schema(
        operation_id='users_statistics',
        summary='Get User Statistics',
        description='Get statistics about users in the tenant',
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get user statistics"""
        if not (request.user.is_manager or request.user.has_permission('view_reports')):
            return Response(
                {'error': 'You do not have permission to view statistics'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        queryset = self.get_queryset()
        
        stats = {
            'total_users': queryset.count(),
            'active_users': queryset.filter(is_active=True).count(),
            'inactive_users': queryset.filter(is_active=False).count(),
            'by_role': {},
            'by_status': {},
            'recent_signups': queryset.filter(
                date_joined__gte=timezone.now() - timezone.timedelta(days=30)
            ).count(),
        }
        
        # Role breakdown
        for role_code, role_name in User.ROLE_CHOICES:
            stats['by_role'][role_name] = queryset.filter(role=role_code).count()
        
        # Status breakdown
        for status_code, status_name in User.STATUS_CHOICES:
            stats['by_status'][status_name] = queryset.filter(status=status_code).count()
        
        return Response(stats)
    
    @action(detail=False, methods=['post'], permission_classes=[])
    def login(self, request):
        """Enhanced login endpoint"""
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response(
                {'error': 'Email and password required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(request, username=email, password=password)
        if user:
            if not user.is_active:
                return Response(
                    {'error': 'Account is inactive'}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
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
        """Enhanced logout endpoint"""
        try:
            request.user.auth_token.delete()
            return Response({'message': 'Successfully logged out'})
        except Exception as e:
            return Response(
                {'error': 'Error logging out'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        operation_id='users_change_password',
        summary='Change Password',
        description='Change password for current user with old password verification',
        request=PasswordChangeSerializer
    )
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Enhanced change password with validation"""
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            new_password = serializer.validated_data['new_password']
            
            request.user.set_password(new_password)
            request.user.save(update_fields=['password'])
            
            return Response({'message': 'Password changed successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
