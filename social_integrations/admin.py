from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import (
    FacebookPageConnection, FacebookMessage, 
    InstagramAccountConnection, InstagramMessage,
    WhatsAppBusinessConnection, WhatsAppMessage
)


@admin.register(FacebookPageConnection)
class FacebookPageConnectionAdmin(admin.ModelAdmin):
    list_display = ['page_name', 'user', 'page_id', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['page_name', 'user__username', 'page_id']
    readonly_fields = ['page_access_token']
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        # Add "Connect to Facebook" button
        connect_url = reverse('social_integrations:admin_facebook_oauth_start')
        extra_context['connect_facebook_button'] = format_html(
            '<a class="button" href="{}" style="background-color: #1877f2; color: white; margin-bottom: 10px;">'
            'Connect to Facebook</a>',
            connect_url
        )
        
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(FacebookMessage)
class FacebookMessageAdmin(admin.ModelAdmin):
    list_display = ['sender_name', 'page_connection', 'timestamp', 'is_from_page']
    list_filter = ['is_from_page', 'timestamp', 'page_connection']
    search_fields = ['sender_name', 'message_text', 'sender_id']


@admin.register(InstagramAccountConnection)
class InstagramAccountConnectionAdmin(admin.ModelAdmin):
    list_display = ['username', 'account_name', 'user', 'instagram_account_id', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['username', 'account_name', 'user__username', 'instagram_account_id']


@admin.register(InstagramMessage)
class InstagramMessageAdmin(admin.ModelAdmin):
    list_display = ['sender_username', 'account_connection', 'message_type', 'timestamp', 'is_from_business']
    list_filter = ['is_from_business', 'message_type', 'timestamp', 'account_connection']
    search_fields = ['sender_username', 'message_text', 'sender_id']


@admin.register(WhatsAppBusinessConnection)
class WhatsAppBusinessConnectionAdmin(admin.ModelAdmin):
    list_display = ['verified_name', 'display_phone_number', 'user', 'business_account_id', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['verified_name', 'display_phone_number', 'user__username', 'business_account_id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ['contact_name', 'from_number', 'connection', 'message_type', 'timestamp', 'is_from_business', 'delivery_status']
    list_filter = ['is_from_business', 'message_type', 'delivery_status', 'timestamp', 'connection']
    search_fields = ['contact_name', 'message_text', 'from_number', 'to_number']
    readonly_fields = ['created_at', 'updated_at']
