from rest_framework import serializers
from .models import (
    FacebookPageConnection, FacebookMessage,
    InstagramAccountConnection, InstagramMessage,
    WhatsAppBusinessAccount, WhatsAppMessage, WhatsAppMessageTemplate,
    WhatsAppContact, SocialIntegrationSettings
)


class FacebookPageConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacebookPageConnection
        fields = ['id', 'page_id', 'page_name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class FacebookMessageSerializer(serializers.ModelSerializer):
    page_name = serializers.CharField(source='page_connection.page_name', read_only=True)

    class Meta:
        model = FacebookMessage
        fields = [
            'id', 'message_id', 'sender_id', 'sender_name', 'profile_pic_url', 'message_text',
            'attachment_type', 'attachment_url', 'attachments',
            'timestamp', 'is_from_page', 'is_delivered', 'delivered_at', 'is_read', 'read_at', 'page_name', 'created_at'
        ]
        read_only_fields = ['id', 'is_delivered', 'delivered_at', 'is_read', 'read_at', 'created_at']


class FacebookSendMessageSerializer(serializers.Serializer):
    recipient_id = serializers.CharField(max_length=255, help_text="Facebook user ID to send message to")
    message = serializers.CharField(help_text="Message text to send")
    page_id = serializers.CharField(max_length=255, help_text="Facebook page ID to send from")


class InstagramAccountConnectionSerializer(serializers.ModelSerializer):
    facebook_page_name = serializers.CharField(source='facebook_page.page_name', read_only=True)

    class Meta:
        model = InstagramAccountConnection
        fields = [
            'id', 'instagram_account_id', 'username', 'profile_picture_url',
            'is_active', 'facebook_page_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InstagramMessageSerializer(serializers.ModelSerializer):
    account_username = serializers.CharField(source='account_connection.username', read_only=True)

    class Meta:
        model = InstagramMessage
        fields = [
            'id', 'message_id', 'sender_id', 'sender_name', 'sender_username', 'sender_profile_pic',
            'message_text', 'attachment_type', 'attachment_url', 'attachments',
            'timestamp', 'is_from_business', 'is_delivered', 'delivered_at', 'is_read', 'read_at', 'account_username', 'created_at'
        ]
        read_only_fields = ['id', 'is_delivered', 'delivered_at', 'is_read', 'read_at', 'created_at']


class InstagramSendMessageSerializer(serializers.Serializer):
    recipient_id = serializers.CharField(max_length=255, help_text="Instagram user ID to send message to")
    message = serializers.CharField(help_text="Message text to send")
    instagram_account_id = serializers.CharField(max_length=255, help_text="Instagram account ID to send from")


class WhatsAppBusinessAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppBusinessAccount
        fields = [
            'id', 'waba_id', 'business_name', 'phone_number_id', 'phone_number',
            'display_phone_number', 'quality_rating', 'is_active',
            # Coexistence fields
            'coex_enabled', 'is_on_biz_app', 'platform_type', 'sync_status',
            'onboarded_at', 'contacts_synced_at', 'history_synced_at', 'throughput_limit',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'coex_enabled', 'is_on_biz_app', 'platform_type', 'sync_status',
            'onboarded_at', 'contacts_synced_at', 'history_synced_at', 'throughput_limit',
            'created_at', 'updated_at'
        ]


class WhatsAppMessageSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business_account.business_name', read_only=True)
    business_phone = serializers.CharField(source='business_account.display_phone_number', read_only=True)
    waba_id = serializers.CharField(source='business_account.waba_id', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True, allow_null=True)

    class Meta:
        model = WhatsAppMessage
        fields = [
            'id', 'message_id', 'from_number', 'to_number', 'contact_name', 'profile_pic_url',
            'message_text', 'message_type', 'media_url', 'media_mime_type', 'attachments', 'timestamp',
            'is_from_business', 'status', 'is_delivered', 'delivered_at', 'is_read', 'read_at',
            'error_message', 'business_name', 'business_phone', 'waba_id', 'template', 'template_name',
            'template_parameters',
            # Coexistence fields
            'source', 'is_echo', 'is_edited', 'edited_at', 'original_text', 'is_revoked', 'revoked_at',
            'created_at'
        ]
        read_only_fields = [
            'id', 'status', 'is_delivered', 'delivered_at', 'is_read', 'read_at',
            'source', 'is_echo', 'is_edited', 'edited_at', 'original_text', 'is_revoked', 'revoked_at',
            'created_at'
        ]


class WhatsAppSendMessageSerializer(serializers.Serializer):
    to_number = serializers.CharField(max_length=20, help_text="Recipient's phone number (E.164 format, e.g., +1234567890)")
    message = serializers.CharField(help_text="Message text to send")
    waba_id = serializers.CharField(max_length=100, help_text="WhatsApp Business Account ID to send from")

    def validate_to_number(self, value):
        """Ensure phone number starts with +"""
        if not value.startswith('+'):
            raise serializers.ValidationError("Phone number must be in E.164 format (start with +)")
        return value


class WhatsAppContactSerializer(serializers.ModelSerializer):
    """Serializer for WhatsApp contacts synced from Business App (Coexistence feature)"""
    account_phone = serializers.CharField(source='account.display_phone_number', read_only=True)
    account_name = serializers.CharField(source='account.business_name', read_only=True)

    class Meta:
        model = WhatsAppContact
        fields = [
            'id', 'account', 'wa_id', 'profile_name', 'is_business', 'contact_type',
            'synced_at', 'last_message_at', 'account_phone', 'account_name'
        ]
        read_only_fields = ['id', 'synced_at', 'account_phone', 'account_name']


class WhatsAppMessageTemplateSerializer(serializers.ModelSerializer):
    """Serializer for WhatsApp message templates"""
    business_name = serializers.CharField(source='business_account.business_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)

    class Meta:
        model = WhatsAppMessageTemplate
        fields = [
            'id', 'business_account', 'template_id', 'name', 'language', 'status',
            'category', 'components', 'created_by', 'created_by_name', 'business_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'template_id', 'created_at', 'updated_at', 'business_name', 'created_by_name']


class WhatsAppTemplateCreateSerializer(serializers.Serializer):
    """Serializer for creating WhatsApp message templates"""
    waba_id = serializers.CharField(max_length=100, help_text="WhatsApp Business Account ID")
    name = serializers.CharField(
        max_length=512,
        help_text="Template name (lowercase, no spaces, use underscores)"
    )
    language = serializers.CharField(max_length=10, default='en', help_text="Language code (e.g., en, ka, ru)")
    category = serializers.ChoiceField(
        choices=['MARKETING', 'UTILITY', 'AUTHENTICATION'],
        default='UTILITY',
        help_text="Template category"
    )
    components = serializers.ListField(
        child=serializers.DictField(),
        help_text="Array of component objects (header, body, footer, buttons)"
    )

    def validate_name(self, value):
        """Validate template name format"""
        import re
        if not re.match(r'^[a-z0-9_]+$', value):
            raise serializers.ValidationError(
                "Template name must be lowercase alphanumeric with underscores only (no spaces)"
            )
        if len(value) < 1 or len(value) > 512:
            raise serializers.ValidationError("Template name must be 1-512 characters")
        return value

    def validate_components(self, value):
        """Validate components structure"""
        if not value:
            raise serializers.ValidationError("At least one component is required")

        # Check that at least one component is BODY
        has_body = any(comp.get('type') == 'BODY' for comp in value)
        if not has_body:
            raise serializers.ValidationError("Template must have at least one BODY component")

        return value


class WhatsAppTemplateSendSerializer(serializers.Serializer):
    """Serializer for sending template-based WhatsApp messages"""
    waba_id = serializers.CharField(max_length=100, help_text="WhatsApp Business Account ID")
    template_id = serializers.IntegerField(help_text="Template ID from database")
    to_number = serializers.CharField(
        max_length=20,
        help_text="Recipient's phone number (E.164 format, e.g., +1234567890)"
    )
    parameters = serializers.DictField(
        child=serializers.CharField(),
        required=False,
        allow_null=True,
        help_text="Template parameters as key-value pairs (e.g., {'name': 'John', 'order_id': '12345'})"
    )

    def validate_to_number(self, value):
        """Ensure phone number starts with +"""
        if not value.startswith('+'):
            raise serializers.ValidationError("Phone number must be in E.164 format (start with +)")
        return value


class SocialIntegrationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialIntegrationSettings
        fields = ['id', 'refresh_interval', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_refresh_interval(self, value):
        """Ensure refresh interval is within acceptable range"""
        if value < 1000:
            raise serializers.ValidationError("Refresh interval must be at least 1000ms (1 second)")
        if value > 60000:
            raise serializers.ValidationError("Refresh interval must be at most 60000ms (60 seconds)")
        return value