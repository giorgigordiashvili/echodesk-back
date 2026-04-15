from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import CallLog, Client, SipConfiguration, CallEvent, CallRecording, UserPhoneAssignment, PbxSettings


class UserPhoneAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for user phone number assignments"""
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = UserPhoneAssignment
        fields = [
            'id', 'user', 'user_name', 'user_email', 'sip_configuration',
            'extension', 'extension_password', 'phone_number', 'display_name',
            'is_primary', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.email

    def get_user_email(self, obj):
        return obj.user.email


class UserPhoneAssignmentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer including the full SIP config for the user's assignment"""
    sip_configuration = serializers.SerializerMethodField()

    class Meta:
        model = UserPhoneAssignment
        fields = [
            'id', 'user', 'sip_configuration', 'extension', 'extension_password',
            'phone_number', 'display_name', 'is_primary', 'is_active'
        ]

    def get_sip_configuration(self, obj):
        return SipConfigurationDetailSerializer(obj.sip_configuration).data


class SipConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for SIP configuration management"""
    user_assignments = UserPhoneAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = SipConfiguration
        fields = [
            'id', 'name', 'sip_server', 'sip_port', 'username', 'password',
            'realm', 'proxy', 'phone_number', 'websocket_path', 'stun_server', 'turn_server',
            'turn_username', 'turn_password', 'is_active', 'is_default',
            'max_concurrent_calls', 'created_at', 'updated_at', 'user_assignments'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': False},
        }
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class SipConfigurationListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing SIP configurations"""
    assignment_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = SipConfiguration
        fields = ['id', 'name', 'sip_server', 'phone_number', 'is_active', 'is_default', 'assignment_count']


class SipConfigurationDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer including sensitive fields for configuration"""
    user_assignments = UserPhoneAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = SipConfiguration
        fields = [
            'id', 'name', 'sip_server', 'sip_port', 'username', 'password',
            'realm', 'proxy', 'phone_number', 'websocket_path', 'stun_server', 'turn_server',
            'turn_username', 'turn_password', 'is_active', 'is_default',
            'max_concurrent_calls', 'user_assignments'
        ]


class CallLogSerializer(serializers.ModelSerializer):
    """Enhanced serializer for CallLog model with SIP support"""
    
    handled_by_name = serializers.SerializerMethodField()
    transferred_to_user_name = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    sip_config_name = serializers.CharField(source='sip_configuration.name', read_only=True)

    class Meta:
        model = CallLog
        fields = [
            'id', 'call_id', 'caller_number', 'recipient_number',
            'direction', 'call_type', 'started_at', 'answered_at',
            'ended_at', 'duration', 'duration_display', 'status',
            'notes', 'sip_call_id', 'client', 'social_client', 'client_name',
            'handled_by', 'handled_by_name', 'sip_configuration',
            'sip_config_name', 'recording_url', 'call_quality_score',
            'transferred_to', 'transferred_to_user', 'transferred_to_user_name',
            'transferred_at', 'parent_call', 'transfer_type',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'call_id', 'created_at', 'updated_at', 'client', 'social_client', 'parent_call']

    @extend_schema_field(serializers.CharField)
    def get_client_name(self, obj):
        """Get client name from social_client first, then CRM client"""
        if obj.social_client:
            return obj.social_client.name
        if obj.client:
            return obj.client.name
        return None

    @extend_schema_field(serializers.CharField)
    def get_handled_by_name(self, obj):
        """Get the name of the user who handled the call"""
        if obj.handled_by:
            return f"{obj.handled_by.first_name} {obj.handled_by.last_name}".strip()
        return None

    @extend_schema_field(serializers.CharField)
    def get_transferred_to_user_name(self, obj):
        if obj.transferred_to_user:
            return f"{obj.transferred_to_user.first_name} {obj.transferred_to_user.last_name}".strip()
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


class ConsultationInitiateSerializer(serializers.Serializer):
    """Serializer for initiating an attended transfer consultation call"""
    target_number = serializers.CharField(max_length=30)
    target_user_id = serializers.IntegerField(required=False)


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


class PbxSettingsSerializer(serializers.ModelSerializer):
    """Serializer for PBX working hours and sound management."""

    sound_greeting_url = serializers.SerializerMethodField()
    sound_after_hours_url = serializers.SerializerMethodField()
    sound_queue_hold_url = serializers.SerializerMethodField()
    sound_voicemail_prompt_url = serializers.SerializerMethodField()
    sound_thank_you_url = serializers.SerializerMethodField()
    sound_transfer_hold_url = serializers.SerializerMethodField()
    sound_review_prompt_url = serializers.SerializerMethodField()
    sound_review_invalid_url = serializers.SerializerMethodField()
    sound_review_thanks_url = serializers.SerializerMethodField()
    sound_queue_position_1_url = serializers.SerializerMethodField()
    sound_queue_position_2_url = serializers.SerializerMethodField()
    sound_queue_position_3_url = serializers.SerializerMethodField()
    sound_queue_position_4_url = serializers.SerializerMethodField()
    sound_queue_position_5_url = serializers.SerializerMethodField()
    sound_queue_position_6_url = serializers.SerializerMethodField()
    sound_queue_position_7_url = serializers.SerializerMethodField()
    sound_queue_position_8_url = serializers.SerializerMethodField()
    sound_queue_position_9_url = serializers.SerializerMethodField()
    sound_queue_position_10_url = serializers.SerializerMethodField()

    class Meta:
        model = PbxSettings
        fields = [
            'id', 'sip_configuration',
            'working_hours_enabled', 'working_hours_schedule', 'timezone', 'holidays',
            'after_hours_action', 'forward_number', 'voicemail_enabled',
            'sound_greeting', 'sound_after_hours', 'sound_queue_hold',
            'sound_voicemail_prompt', 'sound_thank_you', 'sound_transfer_hold',
            'sound_review_prompt', 'sound_review_invalid', 'sound_review_thanks',
            'sound_queue_position_1', 'sound_queue_position_2', 'sound_queue_position_3',
            'sound_queue_position_4', 'sound_queue_position_5', 'sound_queue_position_6',
            'sound_queue_position_7', 'sound_queue_position_8', 'sound_queue_position_9',
            'sound_queue_position_10',
            'sound_greeting_url', 'sound_after_hours_url', 'sound_queue_hold_url',
            'sound_voicemail_prompt_url', 'sound_thank_you_url', 'sound_transfer_hold_url',
            'sound_review_prompt_url', 'sound_review_invalid_url', 'sound_review_thanks_url',
            'sound_queue_position_1_url', 'sound_queue_position_2_url', 'sound_queue_position_3_url',
            'sound_queue_position_4_url', 'sound_queue_position_5_url', 'sound_queue_position_6_url',
            'sound_queue_position_7_url', 'sound_queue_position_8_url', 'sound_queue_position_9_url',
            'sound_queue_position_10_url',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'sip_configuration', 'created_at', 'updated_at']
        extra_kwargs = {
            'sound_greeting': {'write_only': True, 'required': False},
            'sound_after_hours': {'write_only': True, 'required': False},
            'sound_queue_hold': {'write_only': True, 'required': False},
            'sound_voicemail_prompt': {'write_only': True, 'required': False},
            'sound_thank_you': {'write_only': True, 'required': False},
            'sound_transfer_hold': {'write_only': True, 'required': False},
            'sound_review_prompt': {'write_only': True, 'required': False},
            'sound_review_invalid': {'write_only': True, 'required': False},
            'sound_review_thanks': {'write_only': True, 'required': False},
            'sound_queue_position_1': {'write_only': True, 'required': False},
            'sound_queue_position_2': {'write_only': True, 'required': False},
            'sound_queue_position_3': {'write_only': True, 'required': False},
            'sound_queue_position_4': {'write_only': True, 'required': False},
            'sound_queue_position_5': {'write_only': True, 'required': False},
            'sound_queue_position_6': {'write_only': True, 'required': False},
            'sound_queue_position_7': {'write_only': True, 'required': False},
            'sound_queue_position_8': {'write_only': True, 'required': False},
            'sound_queue_position_9': {'write_only': True, 'required': False},
            'sound_queue_position_10': {'write_only': True, 'required': False},
        }

    def _get_url(self, obj, field_name):
        f = getattr(obj, field_name)
        if f and f.name:
            return f.url
        return None

    def get_sound_greeting_url(self, obj):
        return self._get_url(obj, 'sound_greeting')

    def get_sound_after_hours_url(self, obj):
        return self._get_url(obj, 'sound_after_hours')

    def get_sound_queue_hold_url(self, obj):
        return self._get_url(obj, 'sound_queue_hold')

    def get_sound_voicemail_prompt_url(self, obj):
        return self._get_url(obj, 'sound_voicemail_prompt')

    def get_sound_thank_you_url(self, obj):
        return self._get_url(obj, 'sound_thank_you')

    def get_sound_transfer_hold_url(self, obj):
        return self._get_url(obj, 'sound_transfer_hold')

    def get_sound_review_prompt_url(self, obj):
        return self._get_url(obj, 'sound_review_prompt')

    def get_sound_review_invalid_url(self, obj):
        return self._get_url(obj, 'sound_review_invalid')

    def get_sound_review_thanks_url(self, obj):
        return self._get_url(obj, 'sound_review_thanks')

    def get_sound_queue_position_1_url(self, obj):
        return self._get_url(obj, 'sound_queue_position_1')

    def get_sound_queue_position_2_url(self, obj):
        return self._get_url(obj, 'sound_queue_position_2')

    def get_sound_queue_position_3_url(self, obj):
        return self._get_url(obj, 'sound_queue_position_3')

    def get_sound_queue_position_4_url(self, obj):
        return self._get_url(obj, 'sound_queue_position_4')

    def get_sound_queue_position_5_url(self, obj):
        return self._get_url(obj, 'sound_queue_position_5')

    def get_sound_queue_position_6_url(self, obj):
        return self._get_url(obj, 'sound_queue_position_6')

    def get_sound_queue_position_7_url(self, obj):
        return self._get_url(obj, 'sound_queue_position_7')

    def get_sound_queue_position_8_url(self, obj):
        return self._get_url(obj, 'sound_queue_position_8')

    def get_sound_queue_position_9_url(self, obj):
        return self._get_url(obj, 'sound_queue_position_9')

    def get_sound_queue_position_10_url(self, obj):
        return self._get_url(obj, 'sound_queue_position_10')
