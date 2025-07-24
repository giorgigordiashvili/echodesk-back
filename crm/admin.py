from django.contrib import admin
from .models import Client, CallLog


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'company', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at', 'company')
    search_fields = ('name', 'email', 'phone', 'company')
    ordering = ('-created_at',)


@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = ('caller_number', 'recipient_number', 'status', 'duration', 'handled_by', 'created_at')
    list_filter = ('status', 'created_at', 'handled_by')
    search_fields = ('caller_number', 'recipient_number', 'notes')
    ordering = ('-created_at',)
    raw_id_fields = ('handled_by',)
