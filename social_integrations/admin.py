from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib import messages
import requests
from .models import FacebookPageConnection, FacebookMessage


@admin.register(FacebookPageConnection)
class FacebookPageConnectionAdmin(admin.ModelAdmin):
    list_display = ['page_name', 'page_id', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['page_name', 'page_id']
    fields = ['page_name', 'page_id', 'page_access_token', 'is_active']
    
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
    
    def save_model(self, request, obj, form, change):
        # If page_access_token was manually entered, validate it
        if 'page_access_token' in form.changed_data and obj.page_access_token:
            try:
                # Validate the token by making a request to Facebook API
                response = requests.get(
                    f"https://graph.facebook.com/v23.0/me?access_token={obj.page_access_token}"
                )
                if response.status_code == 200:
                    data = response.json()
                    # If page_id is not set, try to get it from the API response
                    if not obj.page_id and 'id' in data:
                        obj.page_id = data['id']
                    # If page_name is not set, try to get it from the API response
                    if not obj.page_name and 'name' in data:
                        obj.page_name = data['name']
                    messages.success(request, f"Facebook token validated successfully for page: {data.get('name', 'Unknown')}")
                else:
                    messages.error(request, f"Invalid Facebook token. API returned: {response.status_code}")
            except Exception as e:
                messages.error(request, f"Error validating Facebook token: {str(e)}")
        
        super().save_model(request, obj, form, change)


@admin.register(FacebookMessage)
class FacebookMessageAdmin(admin.ModelAdmin):
    list_display = ['sender_name', 'page_connection', 'timestamp', 'is_from_page']
    list_filter = ['is_from_page', 'timestamp', 'page_connection']
    search_fields = ['sender_name', 'message_text', 'sender_id']