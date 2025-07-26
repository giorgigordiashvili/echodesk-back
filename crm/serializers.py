from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import CallLog, Client, SipConfiguration, CallEvent, CallRecording


class SipConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for SIP configuration management"""
    
    class Meta:
        model = SipConfiguration
        fields = [
            'id', 'name', 'sip_server', 'sip_port', 'username', 
            'realm', 'proxy', 'stun_server', 'turn_server', 
            'turn_username', 'is_active', 'is_default', 
            'max_concurrent_calls', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class SipConfigurationListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing SIP configurations"""
    
    class Meta:
        model = SipConfiguration
        fields = ['id', 'name', 'sip_server', 'is_active', 'is_default']


class SipConfigurationDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer including sensitive fields for configuration"""
    
    class Meta:
        model = SipConfiguration
        fields = [
            'id', 'name', 'sip_server', 'sip_port', 'username', 'password',
            'realm', 'proxy', 'stun_server', 'turn_server', 
            'turn_username', 'turn_password', 'is_active', 'is_default',
            'max_concurrent_calls'
        ]


class CallLogSerializer(serializers.ModelSerializer):
    """Enhanced serializer for CallLog model with SIP support"""
    
    handled_by_name = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    client_name = serializers.CharField(source='client.name', read_only=True)
    sip_config_name = serializers.CharField(source='sip_configuration.name', read_only=True)
    
    class Meta:
        model = CallLog
        fields = [
            'id', 'call_id', 'caller_number', 'recipient_number', 
            'direction', 'call_type', 'started_at', 'answered_at', 
            'ended_at', 'duration', 'duration_display', 'status', 
            'notes', 'sip_call_id', 'client', 'client_name', 
            'handled_by', 'handled_by_name', 'sip_configuration', 
            'sip_config_name', 'recording_url', 'call_quality_score',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'call_id', 'created_at', 'updated_at', 'client']

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
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            if hours > 0:
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes}:{seconds:02d}"
        return None


class CallLogCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new call logs"""
    
    class Meta:
        model = CallLog
        fields = [
            'caller_number', 'recipient_number', 'direction', 
            'call_type', 'sip_call_id', 'sip_configuration', 'notes'
        ]


class CallInitiateSerializer(serializers.Serializer):
    """Serializer for initiating outbound calls"""
    recipient_number = serializers.CharField(max_length=20)
    call_type = serializers.ChoiceField(
        choices=CallLog.CALL_TYPE_CHOICES, 
        default='voice'
    )
    sip_configuration = serializers.IntegerField(required=False)
    
    def validate_recipient_number(self, value):
        """Validate phone number format"""
        # Remove common formatting characters
        clean_number = value.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        if not clean_number.isdigit() or len(clean_number) < 7:
            raise serializers.ValidationError("Please enter a valid phone number")
        return value


class CallStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating call status"""
    status = serializers.ChoiceField(choices=CallLog.STATUS_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)
    call_quality_score = serializers.FloatField(min_value=0, max_value=5, required=False)
    recording_url = serializers.URLField(required=False, allow_blank=True)


class ClientSerializer(serializers.ModelSerializer):
    """Serializer for Client model"""
    
    class Meta:
        model = Client
        fields = (
            'id', 'name', 'email', 'phone', 'company', 
            'created_at', 'updated_at', 'is_active'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class CallEventSerializer(serializers.ModelSerializer):
    """Serializer for call events"""
    
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = CallEvent
        fields = [
            'id', 'event_type', 'timestamp', 'metadata', 
            'user', 'user_name'
        ]
        read_only_fields = ['id', 'timestamp']
    
    @extend_schema_field(serializers.CharField)
    def get_user_name(self, obj):
        """Get the name of the user who triggered the event"""
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip()
        return None


class CallRecordingSerializer(serializers.ModelSerializer):
    """Serializer for call recordings"""
    
    duration_display = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()
    
    class Meta:
        model = CallRecording
        fields = [
            'id', 'recording_id', 'file_path', 'file_url', 
            'file_size', 'file_size_display', 'duration', 'duration_display',
            'format', 'status', 'started_at', 'completed_at',
            'transcript', 'transcript_confidence', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'recording_id', 'created_at', 'updated_at']
    
    @extend_schema_field(serializers.CharField)
    def get_duration_display(self, obj):
        """Display duration in human-readable format"""
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            if hours > 0:
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes}:{seconds:02d}"
        return None
    
    @extend_schema_field(serializers.CharField)
    def get_file_size_display(self, obj):
        """Display file size in human-readable format"""
        if obj.file_size:
            # Convert bytes to MB
            size_mb = obj.file_size / (1024 * 1024)
            if size_mb < 1:
                size_kb = obj.file_size / 1024
                return f"{size_kb:.1f} KB"
            else:
                return f"{size_mb:.1f} MB"
        return None


class CallLogDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for CallLog with events and recording"""
    
    handled_by_name = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    client_name = serializers.CharField(source='client.name', read_only=True)
    sip_config_name = serializers.CharField(source='sip_configuration.name', read_only=True)
    events = CallEventSerializer(many=True, read_only=True)
    recording = CallRecordingSerializer(read_only=True)
    
    class Meta:
        model = CallLog
        fields = [
            'id', 'call_id', 'caller_number', 'recipient_number', 
            'direction', 'call_type', 'started_at', 'answered_at', 
            'ended_at', 'duration', 'duration_display', 'status', 
            'notes', 'sip_call_id', 'client', 'client_name', 
            'handled_by', 'handled_by_name', 'sip_configuration', 
            'sip_config_name', 'recording_url', 'call_quality_score',
            'created_at', 'updated_at', 'events', 'recording'
        ]
        read_only_fields = ['id', 'call_id', 'created_at', 'updated_at', 'client']

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
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            if hours > 0:
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes}:{seconds:02d}"
        return None
