from django.contrib import admin
from .models import Client, CallLog, SipConfiguration, CallEvent, CallRecording


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
