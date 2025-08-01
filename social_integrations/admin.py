from django.contrib import admin
from .models import FacebookPageConnection, FacebookMessage


@admin.register(FacebookPageConnection)
class FacebookPageConnectionAdmin(admin.ModelAdmin):
    list_display = ['page_name', 'user', 'page_id', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['page_name', 'user__username', 'page_id']


@admin.register(FacebookMessage)
class FacebookMessageAdmin(admin.ModelAdmin):
    list_display = ['sender_name', 'page_connection', 'timestamp', 'is_from_page']
    list_filter = ['is_from_page', 'timestamp', 'page_connection']
    search_fields = ['sender_name', 'message_text', 'sender_id']
