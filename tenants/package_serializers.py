from rest_framework import serializers
from .models import Package, TenantSubscription, PricingModel
from .feature_serializers import FeatureSerializer


class PackageFeatureDetailSerializer(serializers.Serializer):
    """Serializer for package feature with price"""
    id = serializers.IntegerField()
    key = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    category = serializers.CharField()
    category_display = serializers.CharField()
    icon = serializers.CharField()
    price_gel = serializers.DecimalField(max_digits=10, decimal_places=2)
    sort_order = serializers.IntegerField()
    is_highlighted = serializers.BooleanField()


class PackageSerializer(serializers.ModelSerializer):
    """Serializer for Package model"""
    features_list = serializers.ReadOnlyField()
    dynamic_features = serializers.SerializerMethodField()
    calculated_price = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            'id', 'name', 'display_name', 'description', 'pricing_model',
            'price_gel', 'calculated_price', 'billing_period', 'max_users',
            'max_whatsapp_messages', 'max_storage_gb', 'ticket_management',
            'email_integration', 'sip_calling', 'facebook_integration',
            'instagram_integration', 'whatsapp_integration', 'advanced_analytics',
            'api_access', 'custom_integrations', 'priority_support',
            'dedicated_account_manager', 'is_highlighted', 'is_active',
            'is_custom', 'sort_order', 'features_list', 'dynamic_features'
        ]

    def get_dynamic_features(self, obj):
        """Get dynamic features with prices"""
        package_features = obj.package_features.select_related('feature').filter(
            feature__is_active=True
        )

        features = []
        for pf in package_features:
            features.append({
                'id': pf.feature.id,
                'key': pf.feature.key,
                'name': pf.feature.name,
                'description': pf.feature.description,
                'category': pf.feature.category,
                'category_display': pf.feature.get_category_display(),
                'icon': pf.feature.icon,
                'price_per_user_gel': str(pf.feature.price_per_user_gel),
                'price_unlimited_gel': str(pf.feature.price_unlimited_gel),
                'sort_order': pf.sort_order,
                'is_highlighted': pf.is_highlighted
            })

        return features

    def get_calculated_price(self, obj):
        """Get calculated price (for custom packages, sum of feature prices)"""
        return str(obj.calculate_custom_price())


class PackageListSerializer(serializers.ModelSerializer):
    """Simplified serializer for package listing"""
    features_list = serializers.ReadOnlyField()
    dynamic_features = serializers.SerializerMethodField()
    pricing_suffix = serializers.SerializerMethodField()
    calculated_price = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            'id', 'name', 'display_name', 'description', 'pricing_model',
            'price_gel', 'calculated_price', 'max_users', 'max_whatsapp_messages',
            'max_storage_gb', 'is_highlighted', 'is_custom', 'features_list',
            'dynamic_features', 'pricing_suffix'
        ]

    def get_pricing_suffix(self, obj):
        return "/agent/month" if obj.pricing_model == PricingModel.AGENT_BASED else "/month"

    def get_dynamic_features(self, obj):
        """Get dynamic features with prices"""
        package_features = obj.package_features.select_related('feature').filter(
            feature__is_active=True
        )

        features = []
        for pf in package_features:
            features.append({
                'id': pf.feature.id,
                'key': pf.feature.key,
                'name': pf.feature.name,
                'description': pf.feature.description,
                'category': pf.feature.category,
                'category_display': pf.feature.get_category_display(),
                'icon': pf.feature.icon,
                'price_per_user_gel': str(pf.feature.price_per_user_gel),
                'price_unlimited_gel': str(pf.feature.price_unlimited_gel),
                'sort_order': pf.sort_order,
                'is_highlighted': pf.is_highlighted
            })

        return features

    def get_calculated_price(self, obj):
        """Get calculated price (for custom packages, sum of feature prices)"""
        return str(obj.calculate_custom_price())


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
