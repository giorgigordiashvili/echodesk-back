from rest_framework import serializers
from .models import FacebookPageConnection, FacebookMessage


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