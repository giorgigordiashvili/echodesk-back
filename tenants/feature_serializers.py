"""
Serializers for Feature and Permission models
"""

from rest_framework import serializers
from django.contrib.auth.models import Permission
from .models import (
    Feature, FeaturePermission, PackageFeature,
    TenantFeature, TenantPermission
)


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Django's built-in Permission model"""
    app_label = serializers.CharField(source='content_type.app_label', read_only=True)
    model = serializers.CharField(source='content_type.model', read_only=True)

    class Meta:
        model = Permission
        fields = [
            'id', 'name', 'codename', 'app_label', 'model'
        ]


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
            'icon', 'price_per_user_gel', 'price_unlimited_gel', 'sort_order',
            'is_active', 'permissions', 'created_at', 'updated_at'
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


class FeatureCheckSerializer(serializers.Serializer):
    """Serializer for checking if a feature is available"""
    feature_key = serializers.CharField(required=True)
    is_available = serializers.BooleanField(read_only=True)


# Permission checking moved to users app
# Use existing user.has_permission() method with the User model's boolean fields
