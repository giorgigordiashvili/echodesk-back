from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class FacebookPageConnection(models.Model):
    """Stores Facebook page connection details for a tenant"""
    page_id = models.CharField(max_length=100, unique=True)  # Make unique directly
    page_name = models.CharField(max_length=200)
    page_access_token = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.page_name} - Tenant Page"


class FacebookMessage(models.Model):
    """Stores Facebook page messages"""
    page_connection = models.ForeignKey(FacebookPageConnection, on_delete=models.CASCADE, related_name='messages')
    message_id = models.CharField(max_length=100, unique=True)
    sender_id = models.CharField(max_length=100)
    sender_name = models.CharField(max_length=200, blank=True)
    profile_pic_url = models.URLField(max_length=500, blank=True, null=True)  # User's profile picture
    message_text = models.TextField()
    timestamp = models.DateTimeField()
    is_from_page = models.BooleanField(default=False)  # True if message is from page to user
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Message from {self.sender_name} - {self.message_text[:50]}"