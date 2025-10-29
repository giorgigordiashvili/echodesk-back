"""
API views for Feature and Permission management
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import (
    Feature, Permission, TenantFeature, TenantPermission,
    UserPermission
)
from .feature_serializers import (
    FeatureSerializer, PermissionSerializer,
    TenantFeatureSerializer, TenantPermissionSerializer,
    UserPermissionSerializer, FeatureCheckSerializer,
    PermissionCheckSerializer
)
from .subscription_service import SubscriptionService


class FeatureViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing available features

    list: Get all active features
    retrieve: Get a specific feature with its permissions
    """
    queryset = Feature.objects.filter(is_active=True).prefetch_related('permissions__permission')
    serializer_class = FeatureSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter features by category if provided"""
        queryset = super().get_queryset()
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
        return queryset


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing available permissions

    list: Get all active permissions
    retrieve: Get a specific permission
    """
    queryset = Permission.objects.filter(is_active=True)
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter permissions by module if provided"""
        queryset = super().get_queryset()
        module = self.request.query_params.get('module', None)
        if module:
            queryset = queryset.filter(module=module)
        return queryset


class TenantFeatureViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing tenant's enabled features

    list: Get all features enabled for current tenant
    retrieve: Get details of a specific tenant feature
    check: Check if tenant has a specific feature
    """
    serializer_class = TenantFeatureSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get features for current tenant"""
        if not hasattr(self.request, 'tenant'):
            return TenantFeature.objects.none()

        return TenantFeature.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).select_related('feature')

    @action(detail=False, methods=['post'])
    def check(self, request):
        """
        Check if tenant has a specific feature

        POST /api/tenant-features/check/
        Body: {"feature_key": "whatsapp_integration"}
        """
        serializer = FeatureCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feature_key = serializer.validated_data['feature_key']
        is_available = SubscriptionService.check_tenant_feature(
            request.tenant, feature_key
        )

        return Response({
            'feature_key': feature_key,
            'is_available': is_available
        })


class TenantPermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing tenant's available permissions

    list: Get all permissions available to current tenant
    retrieve: Get details of a specific tenant permission
    """
    serializer_class = TenantPermissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get permissions for current tenant"""
        if not hasattr(self.request, 'tenant'):
            return TenantPermission.objects.none()

        return TenantPermission.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).select_related('permission', 'granted_by_feature')


class UserPermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing and checking user permissions

    list: Get all permissions for current user
    retrieve: Get details of a specific user permission
    check: Check if user has a specific permission
    my_permissions: Get all permission keys for current user
    """
    serializer_class = UserPermissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get permissions for current user"""
        return UserPermission.objects.filter(
            user=self.request.user,
            is_active=True
        ).select_related('permission', 'granted_by')

    @action(detail=False, methods=['post'])
    def check(self, request):
        """
        Check if user has a specific permission

        POST /api/user-permissions/check/
        Body: {"permission_key": "tickets.create"}
        """
        serializer = PermissionCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        permission_key = serializer.validated_data['permission_key']
        has_permission = SubscriptionService.check_user_permission(
            request.user, permission_key
        )

        return Response({
            'permission_key': permission_key,
            'has_permission': has_permission
        })

    @action(detail=False, methods=['get'])
    def my_permissions(self, request):
        """
        Get all permission keys for current user

        GET /api/user-permissions/my-permissions/

        Returns:
        {
            "permissions": ["tickets.create", "tickets.view", ...]
        }
        """
        # Get user's direct permissions
        user_permissions = UserPermission.objects.filter(
            user=request.user,
            is_active=True
        ).select_related('permission').values_list('permission__key', flat=True)

        # Get tenant's available permissions
        tenant_permissions = []
        if hasattr(request, 'tenant'):
            tenant_permissions = TenantPermission.objects.filter(
                tenant=request.tenant,
                is_active=True
            ).values_list('permission__key', flat=True)

        # Combine and deduplicate
        all_permissions = list(set(list(user_permissions) + list(tenant_permissions)))

        return Response({
            'permissions': sorted(all_permissions)
        })
