from rest_framework import serializers
from .models import (
    FacebookPageConnection, FacebookMessage,
    InstagramAccountConnection, InstagramMessage,
    SocialIntegrationSettings
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
            'timestamp', 'is_from_page', 'page_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


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
            'id', 'message_id', 'sender_id', 'sender_username', 'sender_profile_pic',
            'message_text', 'timestamp', 'is_from_business', 'account_username', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class InstagramSendMessageSerializer(serializers.Serializer):
    recipient_id = serializers.CharField(max_length=255, help_text="Instagram user ID to send message to")
    message = serializers.CharField(help_text="Message text to send")
    instagram_account_id = serializers.CharField(max_length=255, help_text="Instagram account ID to send from")


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