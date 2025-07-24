from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import CallLog, Client


class CallLogSerializer(serializers.ModelSerializer):
    """Serializer for CallLog model"""
    
    handled_by_name = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    
    class Meta:
        model = CallLog
        fields = (
            'id', 'caller_number', 'recipient_number', 'duration', 
            'duration_display', 'status', 'created_at', 'notes', 
            'handled_by', 'handled_by_name'
        )
        read_only_fields = ('id', 'created_at', 'handled_by_name', 'duration_display')

    @extend_schema_field(serializers.CharField)
    def get_handled_by_name(self, obj):
        """Get the name of the user who handled the call"""
        if obj.handled_by:
            return f"{obj.handled_by.first_name} {obj.handled_by.last_name}".strip()
        return None

    @extend_schema_field(serializers.CharField)
    def get_duration_display(self, obj):
        """Display duration in human-readable format"""
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}:{seconds:02d}"
        return None


class ClientSerializer(serializers.ModelSerializer):
    """Serializer for Client model"""
    
    class Meta:
        model = Client
        fields = (
            'id', 'name', 'email', 'phone', 'company', 
            'created_at', 'updated_at', 'is_active'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
