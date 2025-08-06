from rest_framework import serializers
from .models import Package, TenantSubscription, PricingModel


class PackageSerializer(serializers.ModelSerializer):
    """Serializer for Package model"""
    features_list = serializers.ReadOnlyField()
    
    class Meta:
        model = Package
        fields = [
            'id', 'name', 'display_name', 'description', 'pricing_model',
            'price_gel', 'billing_period', 'max_users', 'max_whatsapp_messages',
            'max_storage_gb', 'ticket_management', 'email_integration',
            'sip_calling', 'facebook_integration', 'instagram_integration',
            'whatsapp_integration', 'advanced_analytics', 'api_access',
            'custom_integrations', 'priority_support', 'dedicated_account_manager',
            'is_highlighted', 'is_active', 'sort_order', 'features_list'
        ]


class PackageListSerializer(serializers.ModelSerializer):
    """Simplified serializer for package listing"""
    features_list = serializers.ReadOnlyField()
    pricing_suffix = serializers.SerializerMethodField()
    
    class Meta:
        model = Package
        fields = [
            'id', 'name', 'display_name', 'description', 'pricing_model',
            'price_gel', 'max_users', 'max_whatsapp_messages', 'max_storage_gb',
            'is_highlighted', 'features_list', 'pricing_suffix'
        ]
    
    def get_pricing_suffix(self, obj):
        return "/agent/month" if obj.pricing_model == PricingModel.AGENT_BASED else "/month"


class TenantSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for TenantSubscription model"""
    package_details = PackageSerializer(source='package', read_only=True)
    monthly_cost = serializers.ReadOnlyField()
    is_over_user_limit = serializers.ReadOnlyField()
    is_over_whatsapp_limit = serializers.ReadOnlyField()
    is_over_storage_limit = serializers.ReadOnlyField()
    
    class Meta:
        model = TenantSubscription
        fields = [
            'id', 'package', 'package_details', 'is_active', 'starts_at',
            'expires_at', 'agent_count', 'current_users', 'whatsapp_messages_used',
            'storage_used_gb', 'last_billed_at', 'next_billing_date',
            'monthly_cost', 'is_over_user_limit', 'is_over_whatsapp_limit',
            'is_over_storage_limit', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
