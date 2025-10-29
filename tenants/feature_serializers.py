"""
Serializers for Feature and Permission models
"""

from rest_framework import serializers
from .models import (
    Feature, Permission, FeaturePermission, PackageFeature,
    TenantFeature, TenantPermission, UserPermission
)


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Permission model"""

    class Meta:
        model = Permission
        fields = [
            'id', 'key', 'name', 'description', 'module',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class FeaturePermissionSerializer(serializers.ModelSerializer):
    """Serializer for FeaturePermission with nested permission details"""
    permission = PermissionSerializer(read_only=True)

    class Meta:
        model = FeaturePermission
        fields = ['id', 'permission', 'is_required']


class FeatureSerializer(serializers.ModelSerializer):
    """Serializer for Feature model with permissions"""
    permissions = FeaturePermissionSerializer(many=True, read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = Feature
        fields = [
            'id', 'key', 'name', 'description', 'category', 'category_display',
            'icon', 'sort_order', 'is_active', 'permissions',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PackageFeatureSerializer(serializers.ModelSerializer):
    """Serializer for PackageFeature with feature details"""
    feature = FeatureSerializer(read_only=True)
    feature_id = serializers.PrimaryKeyRelatedField(
        queryset=Feature.objects.all(),
        source='feature',
        write_only=True
    )

    class Meta:
        model = PackageFeature
        fields = [
            'id', 'feature', 'feature_id', 'custom_value',
            'is_highlighted', 'sort_order'
        ]


class TenantFeatureSerializer(serializers.ModelSerializer):
    """Serializer for TenantFeature"""
    feature = FeatureSerializer(read_only=True)

    class Meta:
        model = TenantFeature
        fields = [
            'id', 'feature', 'is_active', 'enabled_at',
            'disabled_at', 'custom_value'
        ]
        read_only_fields = ['enabled_at']


class TenantPermissionSerializer(serializers.ModelSerializer):
    """Serializer for TenantPermission"""
    permission = PermissionSerializer(read_only=True)
    granted_by_feature = FeatureSerializer(read_only=True)

    class Meta:
        model = TenantPermission
        fields = [
            'id', 'permission', 'granted_by_feature', 'is_active',
            'granted_at', 'revoked_at'
        ]
        read_only_fields = ['granted_at']


class UserPermissionSerializer(serializers.ModelSerializer):
    """Serializer for UserPermission"""
    permission = PermissionSerializer(read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    granted_by_email = serializers.EmailField(source='granted_by.email', read_only=True, allow_null=True)

    class Meta:
        model = UserPermission
        fields = [
            'id', 'user', 'user_email', 'permission', 'granted_by',
            'granted_by_email', 'is_active', 'granted_at', 'revoked_at'
        ]
        read_only_fields = ['granted_at', 'granted_by']


class FeatureCheckSerializer(serializers.Serializer):
    """Serializer for checking if a feature is available"""
    feature_key = serializers.CharField(required=True)
    is_available = serializers.BooleanField(read_only=True)


class PermissionCheckSerializer(serializers.Serializer):
    """Serializer for checking if a user has a permission"""
    permission_key = serializers.CharField(required=True)
    has_permission = serializers.BooleanField(read_only=True)
