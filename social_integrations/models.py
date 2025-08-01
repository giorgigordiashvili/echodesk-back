from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class FacebookPageConnection(models.Model):
    """Stores Facebook page connection details for a user"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='facebook_pages')
    page_id = models.CharField(max_length=100)
    page_name = models.CharField(max_length=200)
    page_access_token = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'page_id']
    
    def __str__(self):
        return f"{self.page_name} - {self.user.username}"


class FacebookMessage(models.Model):
    """Stores Facebook page messages"""
    page_connection = models.ForeignKey(FacebookPageConnection, on_delete=models.CASCADE, related_name='messages')
    message_id = models.CharField(max_length=100, unique=True)
    sender_id = models.CharField(max_length=100)
    sender_name = models.CharField(max_length=200, blank=True)
    message_text = models.TextField()
    timestamp = models.DateTimeField()
    is_from_page = models.BooleanField(default=False)  # True if message is from page to user
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Message from {self.sender_name} - {self.message_text[:50]}"


class InstagramAccountConnection(models.Model):
    """Stores Instagram business account connection details for a user"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='instagram_accounts')
    instagram_account_id = models.CharField(max_length=100)
    username = models.CharField(max_length=200)
    account_name = models.CharField(max_length=200, blank=True)
    access_token = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'instagram_account_id']
    
    def __str__(self):
        return f"@{self.username} - {self.user.username}"


class InstagramMessage(models.Model):
    """Stores Instagram direct messages"""
    account_connection = models.ForeignKey(InstagramAccountConnection, on_delete=models.CASCADE, related_name='messages')
    message_id = models.CharField(max_length=100, unique=True)
    conversation_id = models.CharField(max_length=100)
    sender_id = models.CharField(max_length=100)
    sender_username = models.CharField(max_length=200, blank=True)
    message_text = models.TextField(blank=True)
    message_type = models.CharField(max_length=50, default='text')  # text, image, video, etc.
    attachment_url = models.URLField(blank=True, null=True)
    timestamp = models.DateTimeField()
    is_from_business = models.BooleanField(default=False)  # True if message is from business account
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Instagram message from @{self.sender_username} - {self.message_text[:50]}"
