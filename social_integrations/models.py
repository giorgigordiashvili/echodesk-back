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
        user_display = self.user.get_full_name() or self.user.email
        return f"{self.page_name} - {user_display}"


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


class WhatsAppBusinessConnection(models.Model):
    """Model to store WhatsApp Business API connections"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='whatsapp_connections')
    business_account_id = models.CharField(max_length=255)  # WhatsApp Business Account ID
    phone_number_id = models.CharField(max_length=255)  # WhatsApp Phone Number ID
    phone_number = models.CharField(max_length=20)  # The actual phone number (e.g., +1234567890)
    display_phone_number = models.CharField(max_length=20)  # Formatted display number
    verified_name = models.CharField(max_length=255)  # Business verified name
    access_token = models.TextField()  # WhatsApp access token
    webhook_url = models.URLField(blank=True)  # Webhook URL for this connection
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'phone_number_id']

    def __str__(self):
        return f"WhatsApp {self.display_phone_number} - {self.verified_name}"


class WhatsAppMessage(models.Model):
    """Model to store WhatsApp messages"""
    connection = models.ForeignKey(WhatsAppBusinessConnection, on_delete=models.CASCADE, related_name='messages')
    message_id = models.CharField(max_length=255, unique=True)  # WhatsApp message ID
    from_number = models.CharField(max_length=20)  # Sender's phone number
    to_number = models.CharField(max_length=20)  # Recipient's phone number
    contact_name = models.CharField(max_length=255, blank=True)  # Contact name if available
    message_text = models.TextField(blank=True)  # Message content
    message_type = models.CharField(max_length=50, default='text')  # text, image, document, location, etc.
    media_url = models.URLField(blank=True)  # URL to media if message contains media
    media_mime_type = models.CharField(max_length=100, blank=True)  # MIME type of media
    timestamp = models.DateTimeField()  # When the message was sent
    is_from_business = models.BooleanField(default=False)  # True if sent by business, False if from customer
    is_read = models.BooleanField(default=False)  # Message read status
    delivery_status = models.CharField(max_length=20, default='sent')  # sent, delivered, read, failed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        direction = "to" if self.is_from_business else "from"
        return f"WhatsApp message {direction} {self.from_number if not self.is_from_business else self.to_number}"
