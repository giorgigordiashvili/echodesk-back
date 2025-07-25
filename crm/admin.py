from django.contrib import admin
from .models import Client, CallLog, SipConfiguration


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


@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = ('call_id', 'caller_number', 'recipient_number', 'direction', 'status', 'duration', 'started_at', 'handled_by')
    list_filter = ('status', 'direction', 'call_type', 'started_at')
    search_fields = ('caller_number', 'recipient_number', 'sip_call_id', 'notes')
    readonly_fields = ('call_id', 'created_at', 'updated_at')
    date_hierarchy = 'started_at'
    
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
