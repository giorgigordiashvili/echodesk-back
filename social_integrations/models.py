from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class FacebookPageConnection(models.Model):
    """Stores Facebook page connection details for a tenant"""

    DEACTIVATION_REASONS = [
        ('manual', 'Manually Disconnected'),
        ('token_expired', 'Access Token Expired'),
        ('permission_revoked', 'Permissions Revoked'),
        ('oauth_error', 'OAuth Error'),
        ('api_error', 'API Error'),
    ]

    page_id = models.CharField(max_length=100, unique=True)  # Make unique directly
    page_name = models.CharField(max_length=200)
    page_access_token = models.TextField()
    is_active = models.BooleanField(default=True)

    # Deactivation tracking
    deactivated_at = models.DateTimeField(null=True, blank=True, help_text='When the page was deactivated')
    deactivation_reason = models.CharField(
        max_length=50,
        choices=DEACTIVATION_REASONS,
        null=True,
        blank=True,
        help_text='Reason why the page was deactivated'
    )
    deactivation_error_code = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text='Facebook error code if deactivated due to error'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.page_name} - Tenant Page"


class FacebookMessage(models.Model):
    """Stores Facebook page messages"""
    ATTACHMENT_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('file', 'File'),
        ('location', 'Location'),
        ('fallback', 'Fallback'),
    ]

    page_connection = models.ForeignKey(FacebookPageConnection, on_delete=models.CASCADE, related_name='messages')
    message_id = models.CharField(max_length=100, unique=True)
    sender_id = models.CharField(max_length=100)
    sender_name = models.CharField(max_length=200, blank=True)
    profile_pic_url = models.URLField(max_length=500, blank=True, null=True)  # User's profile picture
    message_text = models.TextField(blank=True)  # Can be empty for attachment-only messages
    # Attachment fields
    attachment_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPE_CHOICES, blank=True)
    attachment_url = models.URLField(max_length=1000, blank=True, null=True)  # URL for media attachments
    attachments = models.JSONField(default=list, blank=True)  # Array for multiple attachments
    timestamp = models.DateTimeField()
    is_from_page = models.BooleanField(default=False)  # True if message is from page to user
    is_delivered = models.BooleanField(default=False)  # True if message was delivered to customer
    delivered_at = models.DateTimeField(null=True, blank=True)  # When the message was delivered
    is_read = models.BooleanField(default=False)  # True if customer has read the message
    read_at = models.DateTimeField(null=True, blank=True)  # When the message was read
    is_read_by_staff = models.BooleanField(default=False)  # True if staff has read this incoming message
    read_by_staff_at = models.DateTimeField(null=True, blank=True)  # When staff read the message
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        if self.message_text:
            return f"Message from {self.sender_name} - {self.message_text[:50]}"
        elif self.attachment_type:
            return f"Message from {self.sender_name} - [{self.attachment_type}]"
        return f"Message from {self.sender_name}"


class OrphanedFacebookMessage(models.Model):
    """
    Stores Facebook messages that couldn't be matched to any tenant.
    This happens when:
    1. A page is deactivated but still receives messages
    2. A webhook is received for an unknown page_id
    3. The tenant connection was deleted

    These messages are saved in the PUBLIC schema for admin review.
    """
    page_id = models.CharField(max_length=100, db_index=True, help_text="Facebook page ID that sent the message")
    sender_id = models.CharField(max_length=100, help_text="ID of the person who sent the message")
    sender_name = models.CharField(max_length=200, blank=True, help_text="Name of the sender if available")
    message_id = models.CharField(max_length=100, blank=True, help_text="Facebook message ID if available")
    message_text = models.TextField(help_text="Content of the message")
    timestamp = models.DateTimeField(help_text="When the message was sent")
    raw_webhook_data = models.JSONField(help_text="Full webhook payload for debugging")
    error_reason = models.CharField(
        max_length=255,
        default='page_not_found',
        help_text="Why this message was orphaned"
    )
    reviewed = models.BooleanField(default=False, help_text="Whether an admin has reviewed this message")
    reviewed_at = models.DateTimeField(null=True, blank=True, help_text="When the message was reviewed")
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_orphaned_messages',
        help_text="Admin who reviewed this message"
    )
    notes = models.TextField(blank=True, help_text="Admin notes about this orphaned message")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this record was created")

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['page_id', 'timestamp']),
            models.Index(fields=['reviewed', 'created_at']),
        ]
        verbose_name = "Orphaned Facebook Message"
        verbose_name_plural = "Orphaned Facebook Messages"

    def __str__(self):
        return f"Orphaned message from {self.sender_name or self.sender_id} to page {self.page_id} - {self.message_text[:50]}"


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
    ATTACHMENT_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('file', 'File'),
        ('share', 'Share'),  # Instagram story/post shares
        ('story_mention', 'Story Mention'),
        ('story_reply', 'Story Reply'),
    ]

    account_connection = models.ForeignKey(
        InstagramAccountConnection,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    message_id = models.CharField(max_length=255, unique=True)  # Instagram IDs are base64 encoded, need more space
    sender_id = models.CharField(max_length=100)
    sender_username = models.CharField(max_length=200, blank=True)
    sender_profile_pic = models.URLField(max_length=500, blank=True, null=True)
    message_text = models.TextField(blank=True)  # Can be empty for media-only messages
    # Attachment fields
    attachment_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPE_CHOICES, blank=True)
    attachment_url = models.URLField(max_length=1000, blank=True, null=True)  # URL for media attachments
    attachments = models.JSONField(default=list, blank=True)  # Array for multiple attachments
    timestamp = models.DateTimeField()
    is_from_business = models.BooleanField(default=False)  # True if sent by business
    is_delivered = models.BooleanField(default=False)  # True if message was delivered to customer
    delivered_at = models.DateTimeField(null=True, blank=True)  # When the message was delivered
    is_read = models.BooleanField(default=False)  # True if customer has read the message
    read_at = models.DateTimeField(null=True, blank=True)  # When the message was read
    is_read_by_staff = models.BooleanField(default=False)  # True if staff has read this incoming message
    read_by_staff_at = models.DateTimeField(null=True, blank=True)  # When staff read the message
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        if self.message_text:
            return f"Instagram DM from @{self.sender_username} - {self.message_text[:50]}"
        elif self.attachment_type:
            return f"Instagram DM from @{self.sender_username} - [{self.attachment_type}]"
        return f"Instagram DM from @{self.sender_username}"


class WhatsAppBusinessAccount(models.Model):
    """Stores WhatsApp Business Account connection details for a tenant"""
    waba_id = models.CharField(max_length=100, unique=True)  # WhatsApp Business Account ID
    business_name = models.CharField(max_length=200)
    phone_number_id = models.CharField(max_length=100)  # Phone number ID for sending messages
    phone_number = models.CharField(max_length=20)  # Display phone number (e.g., +1234567890)
    display_phone_number = models.CharField(max_length=30, blank=True)  # Formatted display number
    access_token = models.TextField()  # Long-lived access token
    quality_rating = models.CharField(max_length=50, blank=True)  # Quality rating from WhatsApp
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.business_name} - {self.display_phone_number or self.phone_number}"


class WhatsAppMessageTemplate(models.Model):
    """Stores WhatsApp message templates for a business account"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    CATEGORY_CHOICES = [
        ('MARKETING', 'Marketing'),
        ('UTILITY', 'Utility'),
        ('AUTHENTICATION', 'Authentication'),
    ]

    business_account = models.ForeignKey(
        WhatsAppBusinessAccount,
        on_delete=models.CASCADE,
        related_name='templates'
    )
    template_id = models.CharField(max_length=100, blank=True)  # Meta's template ID (assigned after creation)
    name = models.CharField(max_length=512)  # Template name (lowercase, no spaces, underscores allowed)
    language = models.CharField(max_length=10, default='en')  # Language code (en, ka, ru, etc.)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='UTILITY')
    components = models.JSONField(default=list)  # Array of component objects (header, body, footer, buttons)
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_whatsapp_templates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [['business_account', 'name', 'language']]
        indexes = [
            models.Index(fields=['business_account', 'status']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f"{self.name} ({self.language}) - {self.status}"


class WhatsAppMessage(models.Model):
    """Stores WhatsApp messages"""
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('document', 'Document'),
        ('sticker', 'Sticker'),
        ('location', 'Location'),
        ('contacts', 'Contacts'),
        ('interactive', 'Interactive'),
    ]

    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
    ]

    business_account = models.ForeignKey(
        WhatsAppBusinessAccount,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    message_id = models.CharField(max_length=255, unique=True)  # WhatsApp message ID (wamid)
    from_number = models.CharField(max_length=20)  # Sender's phone number
    to_number = models.CharField(max_length=20)  # Recipient's phone number
    contact_name = models.CharField(max_length=200, blank=True)  # Contact name if available
    profile_pic_url = models.URLField(max_length=500, blank=True, null=True)  # Contact's profile picture
    message_text = models.TextField(blank=True)  # Message text content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='text')
    media_url = models.URLField(max_length=1000, blank=True, null=True)  # URL for media messages
    media_mime_type = models.CharField(max_length=100, blank=True)  # MIME type for media
    attachments = models.JSONField(default=list, blank=True)  # Array for multiple attachments
    # Template-related fields
    template = models.ForeignKey(
        WhatsAppMessageTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages'
    )  # Template used for this message (if template-based)
    template_parameters = models.JSONField(null=True, blank=True)  # Parameters used to fill template variables
    timestamp = models.DateTimeField()  # Message timestamp from WhatsApp
    is_from_business = models.BooleanField(default=False)  # True if sent by business
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    is_delivered = models.BooleanField(default=False)  # True if message was delivered
    delivered_at = models.DateTimeField(null=True, blank=True)  # When the message was delivered
    is_read = models.BooleanField(default=False)  # True if customer has read the message
    read_at = models.DateTimeField(null=True, blank=True)  # When the message was read
    is_read_by_staff = models.BooleanField(default=False)  # True if staff has read this incoming message
    read_by_staff_at = models.DateTimeField(null=True, blank=True)  # When staff read the message
    error_message = models.TextField(blank=True)  # Error message if failed
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['from_number', 'to_number']),
            models.Index(fields=['business_account', 'timestamp']),
        ]

    def __str__(self):
        direction = "to" if self.is_from_business else "from"
        contact = self.contact_name or self.from_number
        return f"WhatsApp {direction} {contact} - {self.message_text[:50]}"


class SocialIntegrationSettings(models.Model):
    """Stores tenant-specific settings for social integrations"""
    # Singleton pattern - only one settings object per tenant
    refresh_interval = models.IntegerField(
        default=5000,
        help_text="Auto-refresh interval in milliseconds for messages page (min: 1000, max: 60000)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Social Integration Settings"
        verbose_name_plural = "Social Integration Settings"

    def __str__(self):
        return f"Social Settings (Refresh: {self.refresh_interval}ms)"

    def save(self, *args, **kwargs):
        # Enforce min/max limits
        if self.refresh_interval < 1000:
            self.refresh_interval = 1000
        elif self.refresh_interval > 60000:
            self.refresh_interval = 60000
        super().save(*args, **kwargs)