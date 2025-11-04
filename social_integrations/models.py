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


class InstagramAccountConnection(models.Model):
    """Stores Instagram Business account connection details for a tenant"""
    instagram_account_id = models.CharField(max_length=100, unique=True)
    username = models.CharField(max_length=200)
    profile_picture_url = models.URLField(max_length=500, blank=True, null=True)
    access_token = models.TextField()
    # Instagram accounts are connected through Facebook Pages
    facebook_page = models.ForeignKey(
        FacebookPageConnection,
        on_delete=models.CASCADE,
        related_name='instagram_accounts',
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"@{self.username} - Instagram"


class InstagramMessage(models.Model):
    """Stores Instagram Direct messages"""
    account_connection = models.ForeignKey(
        InstagramAccountConnection,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    message_id = models.CharField(max_length=100, unique=True)
    sender_id = models.CharField(max_length=100)
    sender_username = models.CharField(max_length=200, blank=True)
    sender_profile_pic = models.URLField(max_length=500, blank=True, null=True)
    message_text = models.TextField(blank=True)  # Can be empty for media-only messages
    timestamp = models.DateTimeField()
    is_from_business = models.BooleanField(default=False)  # True if sent by business
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Instagram DM from @{self.sender_username} - {self.message_text[:50]}"