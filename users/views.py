from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import secrets
import string
import logging
from tenants.email_service import email_service
from .models import Department, TenantGroup, Notification
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    GroupSerializer, GroupCreateSerializer, PermissionSerializer,
    BulkUserActionSerializer, PasswordChangeSerializer, DepartmentSerializer,
    TenantGroupSerializer, TenantGroupCreateSerializer, NotificationSerializer
)

logger = logging.getLogger(__name__)

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
        
        # Note: user.groups no longer exists (removed PermissionsMixin)
        # Use TenantGroupViewSet for managing user group memberships instead
        return Response({
            'error': 'Django auth groups are deprecated. Use TenantGroup instead.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
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
        
        # Note: user.groups no longer exists (removed PermissionsMixin)
        # Use TenantGroupViewSet for managing user group memberships instead
        return Response({
            'error': 'Django auth groups are deprecated. Use TenantGroup instead.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
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

        # Generate temporary password (12 characters: letters, digits, special chars)
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        temporary_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        # Save user with temporary password
        user = serializer.save(
            invited_by=self.request.user,
            invitation_sent_at=timezone.now(),
            temporary_password=temporary_password
        )

        # Set the password (hashed)
        user.set_password(temporary_password)
        user.save()

        # Send invitation email
        try:
            # Get tenant info
            tenant = self.request.tenant if hasattr(self.request, 'tenant') else None
            tenant_name = tenant.name if tenant else "EchoDesk"
            frontend_url = tenant.frontend_url if tenant else settings.MAIN_DOMAIN

            email_sent = email_service.send_user_invitation_email(
                user_email=user.email,
                user_name=user.get_full_name(),
                tenant_name=tenant_name,
                temporary_password=temporary_password,
                frontend_url=frontend_url,
                invited_by=self.request.user.get_full_name()
            )

            if email_sent:
                logger.info(f'Invitation email sent to {user.email}')
            else:
                logger.warning(f'Failed to send invitation email to {user.email}')
        except Exception as e:
            logger.error(f'Error sending invitation email to {user.email}: {str(e)}')
    
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
                # Note: user.groups no longer exists (removed PermissionsMixin)
                return Response(
                    {'error': 'Django auth groups are deprecated. Use TenantGroup instead.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            elif action_type == 'remove_from_group':
                # Note: user.groups no longer exists (removed PermissionsMixin)
                return Response(
                    {'error': 'Django auth groups are deprecated. Use TenantGroup instead.'},
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
        if self.action in ['create', 'update', 'partial_update']:
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
    
    @action(detail=True, methods=['post'])
    def add_users(self, request, pk=None):
        """Add users to this tenant group"""
        if not request.user.has_permission('manage_groups') and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to manage groups'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        tenant_group = self.get_object()
        user_ids = request.data.get('user_ids', [])
        
        if not user_ids:
            return Response(
                {'error': 'user_ids is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        users = User.objects.filter(id__in=user_ids)
        for user in users:
            user.tenant_groups.add(tenant_group)
        
        return Response({
            'message': f'Added {len(users)} users to tenant group {tenant_group.name}',
            'added_users': [user.email for user in users]
        })
    
    @action(detail=True, methods=['post'])
    def remove_users(self, request, pk=None):
        """Remove users from this tenant group"""
        if not request.user.has_permission('manage_groups') and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to manage groups'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        tenant_group = self.get_object()
        user_ids = request.data.get('user_ids', [])
        
        if not user_ids:
            return Response(
                {'error': 'user_ids is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        users = User.objects.filter(id__in=user_ids)
        for user in users:
            user.tenant_groups.remove(tenant_group)
        
        return Response({
            'message': f'Removed {len(users)} users from tenant group {tenant_group.name}',
            'removed_users': [user.email for user in users]
        })
    
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """Get all members of this tenant group"""
        tenant_group = self.get_object()
        members = tenant_group.members.all()

        # Use the UserSerializer to return user data
        from .serializers import UserSerializer
        serializer = UserSerializer(members, many=True)

        return Response({
            'count': len(members),
            'group': tenant_group.name,
            'members': serializer.data
        })

    @action(detail=False, methods=['get'])
    def available_features(self, request):
        """Get all available features that can be assigned to groups based on tenant's subscription"""
        from tenants.models import Tenant
        from tenants.feature_models import TenantFeature, Feature

        # Get current tenant's available features
        try:
            # Get tenant from request
            tenant = request.tenant if hasattr(request, 'tenant') else None
            # Get optional group_id to include features already assigned to that group
            group_id = request.query_params.get('group_id')

            if tenant and hasattr(tenant, 'schema_name') and tenant.schema_name != 'public':
                # Get features available to this tenant through their subscription
                tenant_features = TenantFeature.objects.filter(
                    tenant=tenant,
                    is_active=True
                ).select_related('feature').values_list('feature_id', flat=True)

                # Start with subscription features
                feature_ids = list(tenant_features)

                # If editing a group, also include features already assigned to it
                if group_id:
                    try:
                        group = TenantGroup.objects.get(id=group_id)
                        group_feature_ids = group.features.values_list('id', flat=True)
                        # Combine subscription features and group features (avoiding duplicates)
                        feature_ids = list(set(feature_ids) | set(group_feature_ids))
                    except TenantGroup.DoesNotExist:
                        pass

                # Return only the features this tenant has access to or already has in the group
                features = Feature.objects.filter(id__in=feature_ids, is_active=True)
            else:
                # For public schema or no tenant, return all active features
                features = Feature.objects.filter(is_active=True)

            # Group by category
            from tenants.feature_models import FeatureCategory
            categories_dict = {}

            for feature in features:
                if feature.category not in categories_dict:
                    categories_dict[feature.category] = {
                        'category': feature.category,
                        'category_display': feature.get_category_display(),
                        'features': []
                    }

                categories_dict[feature.category]['features'].append({
                    'id': feature.id,
                    'key': feature.key,
                    'name': feature.name,
                    'description': feature.description,
                    'icon': feature.icon,
                    'sort_order': feature.sort_order
                })

            categories_list = list(categories_dict.values())

            return Response({
                'categories': categories_list
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to fetch available features: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user notifications"""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Only show notifications for the current user"""
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications"""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'count': count})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a single notification as read"""
        notification = self.get_object()
        notification.mark_as_read()
        serializer = self.get_serializer(notification)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        updated = self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'updated': updated})

    @action(detail=False, methods=['delete'])
    def clear_all(self, request):
        """Clear all read notifications"""
        deleted_count, _ = self.get_queryset().filter(is_read=True).delete()
        return Response({'deleted': deleted_count})


def tenant_homepage(request):
    """Simple homepage view for tenants"""
    from django.http import JsonResponse
    return JsonResponse({
        'message': 'Welcome to EchoDesk API',
        'tenant': getattr(request, 'tenant', None),
        'version': '1.0.0'
    })
