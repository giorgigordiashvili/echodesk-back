from rest_framework import serializers
from .models import FacebookPageConnection, FacebookMessage, InstagramAccountConnection, InstagramMessage


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
            'id', 'message_id', 'sender_id', 'sender_name', 'message_text', 
            'timestamp', 'is_from_page', 'page_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class InstagramAccountConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstagramAccountConnection
        fields = ['id', 'instagram_account_id', 'username', 'account_name', 'is_active', 'created_at', 'updated_at']
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
