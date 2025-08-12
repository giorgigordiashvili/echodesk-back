from rest_framework import serializers
from .models import (
    FacebookPageConnection, FacebookMessage, 
    InstagramAccountConnection, InstagramMessage,
    WhatsAppBusinessConnection, WhatsAppMessage
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


class InstagramAccountConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstagramAccountConnection
        fields = ['id', 'instagram_account_id', 'username', 'name', 'profile_picture_url', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class InstagramMessageSerializer(serializers.ModelSerializer):
    account_username = serializers.CharField(source='account_connection.username', read_only=True)
    
    class Meta:
        model = InstagramMessage
        fields = [
            'id', 'message_id', 'conversation_id', 'sender_id', 'sender_username', 
            'message_text', 'message_type', 'attachment_url', 'timestamp', 
            'is_from_business', 'account_username', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class WhatsAppBusinessConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppBusinessConnection
        fields = [
            'id', 'business_account_id', 'phone_number_id', 'phone_number', 
            'display_phone_number', 'verified_name', 'webhook_url', 'is_active', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class WhatsAppMessageSerializer(serializers.ModelSerializer):
    connection_phone = serializers.CharField(source='connection.display_phone_number', read_only=True)
    connection_name = serializers.CharField(source='connection.verified_name', read_only=True)
    
    class Meta:
        model = WhatsAppMessage
        fields = [
            'id', 'message_id', 'from_number', 'to_number', 'contact_name', 
            'message_text', 'message_type', 'media_url', 'media_mime_type', 
            'timestamp', 'is_from_business', 'is_read', 'delivery_status',
            'connection_phone', 'connection_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
