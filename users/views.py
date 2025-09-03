from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from .models import Department, TenantGroup
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    GroupSerializer, GroupCreateSerializer, PermissionSerializer,
    BulkUserActionSerializer, PasswordChangeSerializer, DepartmentSerializer,
    TenantGroupSerializer, TenantGroupCreateSerializer
)

User = get_user_model()


class DepartmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing departments"""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Only show active departments by default, unless explicitly requested
        if self.request.query_params.get('include_inactive') == 'true':
            return Department.objects.all()
        return Department.objects.filter(is_active=True)


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing Django permissions"""
    queryset = Permission.objects.all().order_by('content_type__app_label', 'content_type__model', 'codename')
    serializer_class = PermissionSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Django Groups with permissions"""
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return GroupCreateSerializer
        return GroupSerializer
    
    def perform_create(self, serializer):
        # Check if user has permission to manage groups
        if not self.request.user.has_permission('can_manage_groups') and not self.request.user.is_staff:
            raise permissions.PermissionDenied("You don't have permission to manage groups")
        serializer.save()
    
    def perform_update(self, serializer):
        # Check if user has permission to manage groups
        if not self.request.user.has_permission('can_manage_groups') and not self.request.user.is_staff:
            raise permissions.PermissionDenied("You don't have permission to manage groups")
        serializer.save()
    
    def perform_destroy(self, instance):
        # Check if user has permission to manage groups
        if not self.request.user.has_permission('can_manage_groups') and not self.request.user.is_staff:
            raise permissions.PermissionDenied("You don't have permission to manage groups")
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def add_users(self, request, pk=None):
        """Add users to this group"""
        if not request.user.has_permission('can_manage_groups') and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to manage groups'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        group = self.get_object()
        user_ids = request.data.get('user_ids', [])
        
        if not user_ids:
            return Response(
                {'error': 'user_ids is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        users = User.objects.filter(id__in=user_ids)
        for user in users:
            user.groups.add(group)
        
        return Response({
            'message': f'Added {len(users)} users to group {group.name}',
            'added_users': [user.email for user in users]
        })
    
    @action(detail=True, methods=['post'])
    def remove_users(self, request, pk=None):
        """Remove users from this group"""
        if not request.user.has_permission('can_manage_groups') and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to manage groups'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        group = self.get_object()
        user_ids = request.data.get('user_ids', [])
        
        if not user_ids:
            return Response(
                {'error': 'user_ids is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        users = User.objects.filter(id__in=user_ids)
        for user in users:
            user.groups.remove(group)
        
        return Response({
            'message': f'Removed {len(users)} users from group {group.name}',
            'removed_users': [user.email for user in users]
        })
    
    @action(detail=False, methods=['get'])
    def available_permissions(self, request):
        """Get available permissions for groups"""
        # Get permissions from the User model's Meta.permissions
        user_content_type = ContentType.objects.get_for_model(User)
        user_permissions = Permission.objects.filter(content_type=user_content_type)
        
        # Also include some common auth permissions
        auth_content_type = ContentType.objects.get(app_label='auth', model='permission')
        
        all_permissions = user_permissions
        serializer = PermissionSerializer(all_permissions, many=True)
        return Response(serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for managing users"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer
    
    def get_queryset(self):
        queryset = User.objects.all()
        
        # Filter by role if specified
        role = self.request.query_params.get('role', None)
        if role is not None:
            queryset = queryset.filter(role=role)
        
        # Filter by status if specified
        status_filter = self.request.query_params.get('status', None)
        if status_filter is not None:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by group if specified
        group_id = self.request.query_params.get('group', None)
        if group_id is not None:
            queryset = queryset.filter(groups__id=group_id)
        
        return queryset.distinct()
    
    def perform_create(self, serializer):
        # Check if user has permission to manage users
        if not self.request.user.has_permission('can_manage_users') and not self.request.user.is_staff:
            raise permissions.PermissionDenied("You don't have permission to manage users")
        
        # Set invited_by to current user
        serializer.save(invited_by=self.request.user, invitation_sent_at=timezone.now())
    
    def perform_update(self, serializer):
        # Check if user has permission to manage users or is updating their own profile
        user_being_updated = self.get_object()
        if (not self.request.user.has_permission('can_manage_users') and 
            not self.request.user.is_staff and 
            user_being_updated != self.request.user):
            raise permissions.PermissionDenied("You don't have permission to manage users")
        
        serializer.save()
    
    def perform_destroy(self, instance):
        # Check if user has permission to manage users
        if not self.request.user.has_permission('can_manage_users') and not self.request.user.is_staff:
            raise permissions.PermissionDenied("You don't have permission to manage users")
        
        # Don't allow users to delete themselves
        if instance == self.request.user:
            raise permissions.PermissionDenied("You cannot delete your own account")
        
        instance.delete()
    
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Perform bulk actions on users"""
        if not request.user.has_permission('can_manage_users') and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to manage users'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = BulkUserActionSerializer(data=request.data)
        if serializer.is_valid():
            user_ids = serializer.validated_data['user_ids']
            action_type = serializer.validated_data['action']
            
            users = User.objects.filter(id__in=user_ids)
            
            if action_type == 'activate':
                users.update(is_active=True, status='active')
                message = f'Activated {len(users)} users'
            
            elif action_type == 'deactivate':
                users.update(is_active=False, status='inactive')
                message = f'Deactivated {len(users)} users'
            
            elif action_type == 'delete':
                # Don't allow deletion of current user
                users = users.exclude(id=request.user.id)
                count = users.count()
                users.delete()
                message = f'Deleted {count} users'
            
            elif action_type == 'change_role':
                role = serializer.validated_data.get('role')
                if role:
                    users.update(role=role)
                    message = f'Changed role to {role} for {len(users)} users'
                else:
                    return Response(
                        {'error': 'Role is required for change_role action'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            elif action_type == 'add_to_group':
                group_id = serializer.validated_data.get('group_id')
                if group_id:
                    try:
                        group = Group.objects.get(id=group_id)
                        for user in users:
                            user.groups.add(group)
                        message = f'Added {len(users)} users to group {group.name}'
                    except Group.DoesNotExist:
                        return Response(
                            {'error': 'Group not found'},
                            status=status.HTTP_404_NOT_FOUND
                        )
                else:
                    return Response(
                        {'error': 'group_id is required for add_to_group action'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            elif action_type == 'remove_from_group':
                group_id = serializer.validated_data.get('group_id')
                if group_id:
                    try:
                        group = Group.objects.get(id=group_id)
                        for user in users:
                            user.groups.remove(group)
                        message = f'Removed {len(users)} users from group {group.name}'
                    except Group.DoesNotExist:
                        return Response(
                            {'error': 'Group not found'},
                            status=status.HTTP_404_NOT_FOUND
                        )
                else:
                    return Response(
                        {'error': 'group_id is required for remove_from_group action'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            return Response({'message': message})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def change_password(self, request, pk=None):
        """Change user password"""
        user = self.get_object()
        
        # Users can only change their own password unless they have manage_users permission
        if (user != request.user and 
            not request.user.has_permission('can_manage_users') and 
            not request.user.is_staff):
            return Response(
                {'error': 'You can only change your own password'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'message': 'Password changed successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TenantGroupViewSet(viewsets.ModelViewSet):
    """ViewSet for managing TenantGroups with custom permissions"""
    queryset = TenantGroup.objects.all()
    serializer_class = TenantGroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TenantGroupCreateSerializer
        return TenantGroupSerializer
    
    def perform_create(self, serializer):
        # Check if user has permission to manage groups
        if not self.request.user.has_permission('manage_groups') and not self.request.user.is_staff:
            raise permissions.PermissionDenied("You don't have permission to manage groups")
        serializer.save()
    
    def perform_update(self, serializer):
        # Check if user has permission to manage groups
        if not self.request.user.has_permission('manage_groups') and not self.request.user.is_staff:
            raise permissions.PermissionDenied("You don't have permission to manage groups")
        serializer.save()
    
    def perform_destroy(self, instance):
        # Check if user has permission to manage groups
        if not self.request.user.has_permission('manage_groups') and not self.request.user.is_staff:
            raise permissions.PermissionDenied("You don't have permission to manage groups")
        instance.delete()


def tenant_homepage(request):
    """Simple homepage view for tenants"""
    from django.http import JsonResponse
    return JsonResponse({
        'message': 'Welcome to EchoDesk API',
        'tenant': getattr(request, 'tenant', None),
        'version': '1.0.0'
    })
