from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import (
    CallLog, Client, SipConfiguration, CallEvent, CallRecording,
    UserPhoneAssignment, PbxSettings, CallRating,
    Trunk, Queue, QueueMember, InboundRoute,
)


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


def _is_admin_request(serializer):
    """Tenant admin = is_staff or is_superuser. Recordings + review ratings
    are gated to admins only — agents see neither the URL nor the score."""
    request = serializer.context.get('request')
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return False
    return bool(user.is_staff or user.is_superuser)


class CallLogSerializer(serializers.ModelSerializer):
    """Enhanced serializer for CallLog model with SIP support"""

    handled_by_name = serializers.SerializerMethodField()
    transferred_to_user_name = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    sip_config_name = serializers.CharField(source='sip_configuration.name', read_only=True)
    recording_url = serializers.SerializerMethodField()
    call_quality_score = serializers.SerializerMethodField()

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
    def get_recording_url(self, obj):
        """Return the recording URL, falling back to the related CallRecording.

        Historical recordings were written to CallLog.recording_url; the newer
        webhook pipeline writes to CallRecording.file_url instead and doesn't
        always backfill the legacy field. Restricted to tenant admins only —
        agents get an empty string so the recording UI hides itself.
        """
        if not _is_admin_request(self):
            return ''
        if obj.recording_url:
            return obj.recording_url
        # Reverse OneToOne raises RelatedObjectDoesNotExist when no recording
        # row exists — guard with try/except rather than hasattr so a
        # select_related hit doesn't spuriously fail.
        try:
            recording = obj.recording
        except CallRecording.DoesNotExist:
            return ''
        return recording.file_url or ''

    @extend_schema_field(serializers.FloatField)
    def get_call_quality_score(self, obj):
        """Customer review rating (1-5 from IVR). Admin-only — agents
        shouldn't see how individual customers rated them."""
        if not _is_admin_request(self):
            return None
        return obj.call_quality_score

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


class MergeConferenceSerializer(serializers.Serializer):
    """Serializer for merging an attended transfer into a 3-way conference"""
    consultation_log_id = serializers.IntegerField(help_text="ID of the consultation CallLog")


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
    recording = serializers.SerializerMethodField()
    recording_url = serializers.SerializerMethodField()
    call_quality_score = serializers.SerializerMethodField()

    @extend_schema_field(CallRecordingSerializer)
    def get_recording(self, obj):
        """Nested CallRecording — admin-only."""
        if not _is_admin_request(self):
            return None
        try:
            recording = obj.recording
        except CallRecording.DoesNotExist:
            return None
        return CallRecordingSerializer(recording, context=self.context).data

    @extend_schema_field(serializers.CharField)
    def get_recording_url(self, obj):
        """Fall back to CallRecording.file_url; admin-only."""
        if not _is_admin_request(self):
            return ''
        if obj.recording_url:
            return obj.recording_url
        try:
            recording = obj.recording
        except CallRecording.DoesNotExist:
            return ''
        return recording.file_url or ''

    @extend_schema_field(serializers.FloatField)
    def get_call_quality_score(self, obj):
        """Customer review rating (1-5 from IVR). Admin-only."""
        if not _is_admin_request(self):
            return None
        return obj.call_quality_score

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
            'review_method', 'sms_api_key', 'sms_rating_template_ka', 'sms_rating_template_en',
            'review_delay_hours', 'review_cooldown_hours',
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
            'sms_api_key': {'write_only': True},
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


class CallRatingSerializer(serializers.ModelSerializer):
    """Serializer for call ratings collected via SMS or phone callback."""

    rated_user_name = serializers.SerializerMethodField()

    class Meta:
        model = CallRating
        fields = [
            'id', 'call_log', 'caller_number', 'rated_user', 'rated_user_name',
            'rating', 'rating_token', 'token_expires_at', 'comment',
            'sms_message_id', 'review_method', 'sip_configuration',
            'created_at', 'rated_at',
        ]
        read_only_fields = ['id', 'created_at', 'rated_at']

    @extend_schema_field(serializers.CharField)
    def get_rated_user_name(self, obj):
        if obj.rated_user:
            return f"{obj.rated_user.first_name} {obj.rated_user.last_name}".strip()
        return None


# ---------------------------------------------------------------------------
# PBX management panel serializers
# ---------------------------------------------------------------------------


class TrunkSerializer(serializers.ModelSerializer):
    """Full serializer for ``Trunk`` — used on retrieve/create/update."""

    class Meta:
        model = Trunk
        fields = [
            'id', 'name', 'provider',
            'sip_server', 'sip_port', 'username', 'password',
            'realm', 'proxy', 'register',
            'codecs', 'caller_id_number', 'phone_numbers',
            'is_active', 'is_default',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            # Password is returned so admins can copy it back into provisioning
            # scripts; the viewset is already gated by sip_calling feature.
            'password': {'write_only': False},
        }


class TrunkListSerializer(serializers.ModelSerializer):
    """Lighter serializer for trunk lists."""

    class Meta:
        model = Trunk
        fields = ['id', 'name', 'provider', 'phone_numbers', 'is_active']


class QueueSerializer(serializers.ModelSerializer):
    """Full serializer for ``Queue`` — used on retrieve/create/update."""

    group_name = serializers.CharField(source='group.name', read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Queue
        fields = [
            'id', 'name', 'slug', 'strategy',
            'group', 'group_name',
            'timeout_seconds', 'max_wait_seconds', 'max_len', 'wrapup_time',
            'music_on_hold', 'announce_position', 'announce_holdtime',
            'joinempty', 'leavewhenempty',
            'is_active', 'is_default',
            'member_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    @extend_schema_field(serializers.IntegerField)
    def get_member_count(self, obj):
        """Active QueueMember rows for this queue (materialised by sync layer)."""
        return obj.members.filter(is_active=True).count()


class QueueListSerializer(serializers.ModelSerializer):
    """Lighter serializer for queue lists."""

    group_name = serializers.CharField(source='group.name', read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Queue
        fields = [
            'id', 'name', 'slug', 'strategy',
            'group', 'group_name', 'member_count',
            'is_active', 'is_default',
        ]

    @extend_schema_field(serializers.IntegerField)
    def get_member_count(self, obj):
        return obj.members.filter(is_active=True).count()


class QueueMemberSerializer(serializers.ModelSerializer):
    """Read-only serializer for QueueMember.

    Rows are materialised by the sync layer from ``Queue.group``'s members
    that have an active ``UserPhoneAssignment``.
    """

    queue_slug = serializers.CharField(source='queue.slug', read_only=True)
    queue_name = serializers.CharField(source='queue.name', read_only=True)
    extension = serializers.CharField(source='user_phone_assignment.extension', read_only=True)
    phone_number = serializers.CharField(source='user_phone_assignment.phone_number', read_only=True)
    user_id = serializers.IntegerField(source='user_phone_assignment.user_id', read_only=True)
    user_email = serializers.CharField(source='user_phone_assignment.user.email', read_only=True)
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = QueueMember
        fields = [
            'id', 'queue', 'queue_slug', 'queue_name',
            'user_phone_assignment', 'extension', 'phone_number',
            'user_id', 'user_email', 'user_name',
            'penalty', 'paused', 'is_active', 'synced_at',
        ]
        read_only_fields = fields  # Entire serializer is read-only.

    @extend_schema_field(serializers.CharField)
    def get_user_name(self, obj):
        user = obj.user_phone_assignment.user
        return f"{user.first_name} {user.last_name}".strip() or user.email


class InboundRouteSerializer(serializers.ModelSerializer):
    """Serializer for ``InboundRoute`` with destination-consistency validation."""

    trunk_name = serializers.CharField(source='trunk.name', read_only=True)
    destination_queue_slug = serializers.CharField(source='destination_queue.slug', read_only=True)
    destination_extension_display = serializers.SerializerMethodField()

    class Meta:
        model = InboundRoute
        fields = [
            'id', 'did',
            'trunk', 'trunk_name',
            'destination_type',
            'destination_queue', 'destination_queue_slug',
            'destination_extension', 'destination_extension_display',
            'ivr_custom_context', 'working_hours_override',
            'priority', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    @extend_schema_field(serializers.CharField)
    def get_destination_extension_display(self, obj):
        if obj.destination_extension:
            return f"ext {obj.destination_extension.extension} ({obj.destination_extension.phone_number})"
        return None

    def validate(self, attrs):
        """Mirror ``InboundRoute.clean()`` — DRF-side destination consistency."""
        # Merge incoming attrs with the instance's current values so partial
        # updates still get sensible validation.
        merged = {}
        if self.instance is not None:
            for field in ('destination_type', 'destination_queue', 'destination_extension', 'ivr_custom_context'):
                merged[field] = getattr(self.instance, field)
        merged.update(attrs)

        destination_type = merged.get('destination_type')
        errors = {}

        if destination_type == 'queue' and not merged.get('destination_queue'):
            errors['destination_queue'] = "destination_queue is required when destination_type='queue'."
        if destination_type == 'extension' and not merged.get('destination_extension'):
            errors['destination_extension'] = "destination_extension is required when destination_type='extension'."
        if destination_type == 'ivr_custom' and not merged.get('ivr_custom_context'):
            errors['ivr_custom_context'] = "ivr_custom_context is required when destination_type='ivr_custom'."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs
