"""
API views for Feature and Permission management
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import (
    Feature, Permission, TenantFeature, TenantPermission
)
from .feature_serializers import (
    FeatureSerializer, PermissionSerializer,
    TenantFeatureSerializer, TenantPermissionSerializer,
    FeatureCheckSerializer
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
    ViewSet for viewing Django's built-in permissions

    list: Get all permissions
    retrieve: Get a specific permission
    """
    queryset = Permission.objects.all().select_related('content_type').order_by('content_type__app_label', 'codename')
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter permissions by app_label if provided"""
        queryset = super().get_queryset()
        app_label = self.request.query_params.get('app_label', None)
        if app_label:
            queryset = queryset.filter(content_type__app_label=app_label)
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


# UserPermission ViewSet removed
# User permissions are managed via the existing User model fields (can_view_all_tickets, etc.)
# Tenant admins grant these permissions through the users app
# TenantPermission (above) shows which permissions are available to grant based on package features
