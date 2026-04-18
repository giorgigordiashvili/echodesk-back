from django.contrib import admin, messages
from django.db import connection

from .asterisk_sync import AsteriskStateSync
from .models import (
    Client, CallLog, SipConfiguration, CallEvent, CallRecording,
    Trunk, Queue, QueueMember, InboundRoute, UserPhoneAssignment, PbxServer,
)


def _resync_objs(modeladmin, request, queryset, sync_method_name: str):
    """Shared implementation for the "Resync to Asterisk" admin action.

    Iterates the selected queryset, calls the matching ``AsteriskStateSync``
    method for each row, and reports counts via the Django messages framework.
    Errors inside the service are swallowed/logged, so this surfaces a coarse
    success count rather than a per-row status.
    """
    schema = getattr(connection, "schema_name", None)
    if not schema or schema == "public":
        modeladmin.message_user(
            request,
            "Asterisk resync requires a tenant context; run this from a tenant admin.",
            level=messages.ERROR,
        )
        return

    sync = AsteriskStateSync(schema)
    method = getattr(sync, sync_method_name)
    count = 0
    for obj in queryset:
        method(obj)
        count += 1
    modeladmin.message_user(
        request,
        f"Queued Asterisk resync for {count} row(s) (tenant={schema}).",
        level=messages.SUCCESS,
    )


@admin.action(description="Resync selected trunk(s) to Asterisk realtime DB")
def resync_trunks_to_asterisk(modeladmin, request, queryset):
    _resync_objs(modeladmin, request, queryset, "sync_trunk")


@admin.action(description="Resync selected queue(s) to Asterisk realtime DB")
def resync_queues_to_asterisk(modeladmin, request, queryset):
    _resync_objs(modeladmin, request, queryset, "sync_queue")


@admin.action(description="Resync selected extension(s) to Asterisk realtime DB")
def resync_extensions_to_asterisk(modeladmin, request, queryset):
    _resync_objs(modeladmin, request, queryset, "sync_endpoint")


@admin.register(SipConfiguration)
class SipConfigurationAdmin(admin.ModelAdmin):
    list_display = ('name', 'sip_server', 'sip_port', 'username', 'is_active', 'is_default', 'created_by', 'created_at')
    list_filter = ('is_active', 'is_default', 'created_at')
    search_fields = ('name', 'sip_server', 'username', 'realm')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'is_active', 'is_default', 'max_concurrent_calls')
        }),
        ('SIP Server Settings', {
            'fields': ('sip_server', 'sip_port', 'username', 'password', 'realm', 'proxy')
        }),
        ('WebRTC Settings', {
            'fields': ('stun_server', 'turn_server', 'turn_username', 'turn_password'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class CallEventInline(admin.TabularInline):
    model = CallEvent
    extra = 0
    readonly_fields = ('timestamp',)
    fields = ('event_type', 'timestamp', 'user', 'metadata')


class CallRecordingInline(admin.StackedInline):
    model = CallRecording
    extra = 0
    readonly_fields = ('recording_id', 'created_at', 'updated_at')


@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = ('call_id', 'caller_number', 'recipient_number', 'direction', 'status', 'duration_display', 'started_at', 'handled_by')
    list_filter = ('status', 'direction', 'call_type', 'started_at')
    search_fields = ('caller_number', 'recipient_number', 'sip_call_id', 'notes')
    readonly_fields = ('call_id', 'created_at', 'updated_at')
    date_hierarchy = 'started_at'
    inlines = [CallEventInline, CallRecordingInline]
    
    def duration_display(self, obj):
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            if hours > 0:
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes}:{seconds:02d}"
        return "-"
    duration_display.short_description = "Duration"
    
    fieldsets = (
        ('Call Information', {
            'fields': ('call_id', 'caller_number', 'recipient_number', 'direction', 'call_type')
        }),
        ('Timing', {
            'fields': ('started_at', 'answered_at', 'ended_at', 'duration')
        }),
        ('Status & Quality', {
            'fields': ('status', 'call_quality_score', 'recording_url')
        }),
        ('SIP Details', {
            'fields': ('sip_call_id', 'sip_configuration'),
            'classes': ('collapse',)
        }),
        ('Relationships', {
            'fields': ('client', 'handled_by')
        }),
        ('Additional Information', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(CallEvent)
class CallEventAdmin(admin.ModelAdmin):
    list_display = ('call_log', 'event_type', 'timestamp', 'user')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('call_log__caller_number', 'call_log__recipient_number', 'event_type')
    readonly_fields = ('timestamp',)
    raw_id_fields = ('call_log', 'user')
    
    fieldsets = (
        ('Event Information', {
            'fields': ('call_log', 'event_type', 'timestamp', 'user')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        })
    )


@admin.register(CallRecording)
class CallRecordingAdmin(admin.ModelAdmin):
    list_display = ('recording_id', 'call_log', 'status', 'duration_display', 'file_size_display', 'created_at')
    list_filter = ('status', 'format', 'created_at')
    search_fields = ('recording_id', 'call_log__caller_number', 'call_log__recipient_number')
    readonly_fields = ('recording_id', 'created_at', 'updated_at')
    raw_id_fields = ('call_log',)
    
    def duration_display(self, obj):
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            if hours > 0:
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes}:{seconds:02d}"
        return "-"
    duration_display.short_description = "Duration"
    
    def file_size_display(self, obj):
        if obj.file_size:
            size_mb = obj.file_size / (1024 * 1024)
            if size_mb < 1:
                size_kb = obj.file_size / 1024
                return f"{size_kb:.1f} KB"
            else:
                return f"{size_mb:.1f} MB"
        return "-"
    file_size_display.short_description = "File Size"
    
    fieldsets = (
        ('Recording Information', {
            'fields': ('recording_id', 'call_log', 'status', 'format')
        }),
        ('File Details', {
            'fields': ('file_path', 'file_url', 'file_size', 'duration')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at')
        }),
        ('Transcription', {
            'fields': ('transcript', 'transcript_confidence'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'company', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at', 'company')
    search_fields = ('name', 'email', 'phone', 'company')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'email', 'phone', 'company')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(UserPhoneAssignment)
class UserPhoneAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'extension', 'phone_number', 'sip_configuration',
        'is_primary', 'is_active', 'created_at',
    )
    list_filter = ('is_active', 'is_primary', 'sip_configuration', 'created_at')
    search_fields = (
        'user__email', 'extension', 'phone_number', 'display_name',
    )
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('user', 'sip_configuration')
    actions = [resync_extensions_to_asterisk]


@admin.register(Trunk)
class TrunkAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'provider', 'sip_server', 'sip_port', 'username',
        'register', 'is_active', 'is_default', 'created_at',
    )
    list_filter = ('is_active', 'is_default', 'register', 'provider', 'created_at')
    search_fields = ('name', 'provider', 'sip_server', 'username', 'realm')
    readonly_fields = ('created_at', 'updated_at')
    actions = [resync_trunks_to_asterisk]

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'provider', 'is_active', 'is_default', 'register')
        }),
        ('SIP Server Settings', {
            'fields': ('sip_server', 'sip_port', 'username', 'password', 'realm', 'proxy')
        }),
        ('Outbound / DID', {
            'fields': ('caller_id_number', 'codecs', 'phone_numbers')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


class QueueMemberInline(admin.TabularInline):
    model = QueueMember
    extra = 0
    readonly_fields = ('queue', 'user_phone_assignment', 'penalty', 'paused', 'is_active', 'synced_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'slug', 'strategy', 'group', 'timeout_seconds',
        'max_wait_seconds', 'is_active', 'is_default', 'created_at',
    )
    list_filter = ('is_active', 'is_default', 'strategy', 'created_at')
    search_fields = ('name', 'slug', 'group__name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [QueueMemberInline]
    actions = [resync_queues_to_asterisk]

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'group', 'is_active', 'is_default')
        }),
        ('Ring Strategy', {
            'fields': ('strategy', 'timeout_seconds', 'max_wait_seconds', 'max_len', 'wrapup_time')
        }),
        ('Announcements', {
            'fields': ('music_on_hold', 'announce_position', 'announce_holdtime')
        }),
        ('Edge-case behaviour', {
            'fields': ('joinempty', 'leavewhenempty'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(QueueMember)
class QueueMemberAdmin(admin.ModelAdmin):
    """Read-only in admin — rows are materialised by the sync layer."""

    list_display = (
        'queue', 'user_phone_assignment', 'penalty', 'paused', 'is_active', 'synced_at',
    )
    list_filter = ('paused', 'is_active', 'queue')
    search_fields = (
        'queue__name', 'queue__slug',
        'user_phone_assignment__extension', 'user_phone_assignment__phone_number',
        'user_phone_assignment__user__email',
    )
    readonly_fields = (
        'queue', 'user_phone_assignment', 'penalty', 'paused', 'is_active', 'synced_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(InboundRoute)
class InboundRouteAdmin(admin.ModelAdmin):
    list_display = (
        'did', 'trunk', 'destination_type', 'destination_queue',
        'destination_extension', 'priority', 'is_active', 'created_at',
    )
    list_filter = ('destination_type', 'is_active', 'trunk', 'created_at')
    search_fields = ('did', 'ivr_custom_context', 'trunk__name', 'destination_queue__slug')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('DID Matching', {
            'fields': ('did', 'trunk', 'priority', 'is_active')
        }),
        ('Destination', {
            'fields': (
                'destination_type', 'destination_queue', 'destination_extension',
                'ivr_custom_context',
            )
        }),
        ('Overrides', {
            'fields': ('working_hours_override',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(PbxServer)
class PbxServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'fqdn', 'status', 'use_tenant_prefix', 'last_seen_at', 'created_at')
    list_filter = ('status', 'use_tenant_prefix')
    search_fields = ('name', 'fqdn', 'realtime_db_name', 'ami_username')
    readonly_fields = (
        'enrollment_token', 'enrollment_expires_at', 'asterisk_version',
        'last_seen_at', 'created_at', 'updated_at',
    )
    fieldsets = (
        ('Identity', {'fields': ('name', 'fqdn', 'public_ip', 'status')}),
        ('Realtime DB', {
            'fields': (
                'realtime_db_host', 'realtime_db_port', 'realtime_db_name',
                'realtime_db_user', 'realtime_db_password', 'realtime_db_sslmode',
            ),
        }),
        ('AMI', {
            'fields': ('ami_host', 'ami_port', 'ami_username', 'ami_password'),
        }),
        ('Transport endpoints', {
            'fields': ('wss_url', 'recording_base_url'),
        }),
        ('Enrollment', {
            'fields': (
                'enrollment_token', 'enrollment_expires_at',
                'asterisk_version', 'last_seen_at',
            ),
            'classes': ('collapse',),
        }),
        ('Naming', {'fields': ('use_tenant_prefix', 'notes')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
