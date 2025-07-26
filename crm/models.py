from django.db import models
from django.conf import settings
import uuid


class SipConfiguration(models.Model):
    """SIP configuration for tenant-specific calling"""
    
    name = models.CharField(max_length=100, help_text="Configuration name")
    sip_server = models.CharField(max_length=255, help_text="SIP server hostname/IP")
    sip_port = models.IntegerField(default=5060, help_text="SIP server port")
    username = models.CharField(max_length=100, help_text="SIP username")
    password = models.CharField(max_length=255, help_text="SIP password")
    realm = models.CharField(max_length=255, blank=True, help_text="SIP realm/domain")
    proxy = models.CharField(max_length=255, blank=True, help_text="Outbound proxy")
    
    # WebRTC/STUN/TURN settings
    stun_server = models.CharField(
        max_length=255, 
        blank=True, 
        default="stun:stun.l.google.com:19302",
        help_text="STUN server for NAT traversal"
    )
    turn_server = models.CharField(max_length=255, blank=True, help_text="TURN server")
    turn_username = models.CharField(max_length=100, blank=True)
    turn_password = models.CharField(max_length=255, blank=True)
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    max_concurrent_calls = models.IntegerField(default=5)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_sip_configs'
    )
    
    class Meta:
        ordering = ['-is_default', 'name']
        
    def __str__(self):
        return f"{self.name} ({self.sip_server})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default configuration per tenant
        if self.is_default:
            SipConfiguration.objects.filter(is_default=True).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)


class Client(models.Model):
    """Client/Customer model"""
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    company = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.email})"


class CallLog(models.Model):
    """Enhanced call log model for tracking phone calls with SIP integration"""
    
    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('ringing', 'Ringing'),
        ('answered', 'Answered'),
        ('missed', 'Missed'), 
        ('busy', 'Busy'),
        ('no_answer', 'No Answer'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('transferred', 'Transferred'),
        ('ended', 'Ended'),
        ('recording', 'Recording'),
        ('on_hold', 'On Hold'),
    ]
    
    DIRECTION_CHOICES = [
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
    ]
    
    CALL_TYPE_CHOICES = [
        ('voice', 'Voice Call'),
        ('video', 'Video Call'),
        ('conference', 'Conference Call'),
    ]
    
    # Basic call information
    call_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    caller_number = models.CharField(max_length=20)
    recipient_number = models.CharField(max_length=20)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default='inbound')
    call_type = models.CharField(max_length=15, choices=CALL_TYPE_CHOICES, default='voice')
    
    # Call timing
    started_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    
    # Call status and metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ringing')
    notes = models.TextField(blank=True)
    
    # SIP-specific fields
    sip_call_id = models.CharField(max_length=255, blank=True, help_text="SIP Call-ID header")
    sip_configuration = models.ForeignKey(
        SipConfiguration, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="SIP configuration used for this call"
    )
    
    # User and client relationships
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='handled_calls'
    )
    client = models.ForeignKey(
        Client, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='calls',
        help_text="Associated client (auto-detected by phone number)"
    )
    
    # Recording and quality
    recording_url = models.URLField(blank=True, help_text="Call recording file URL")
    call_quality_score = models.FloatField(null=True, blank=True, help_text="Call quality (0-5)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['caller_number']),
            models.Index(fields=['recipient_number']),
            models.Index(fields=['status']),
            models.Index(fields=['direction']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        direction_symbol = "→" if self.direction == "outbound" else "←"
        return f"{self.caller_number} {direction_symbol} {self.recipient_number} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Auto-associate with client based on phone number
        if not self.client and (self.caller_number or self.recipient_number):
            phone_to_check = self.caller_number if self.direction == 'inbound' else self.recipient_number
            try:
                # Clean phone number for matching
                clean_phone = phone_to_check.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
                self.client = Client.objects.filter(
                    phone__icontains=clean_phone[-7:]  # Match last 7 digits
                ).first()
            except:
                pass
        super().save(*args, **kwargs)


class CallEvent(models.Model):
    """Track detailed events during a call"""
    
    EVENT_TYPES = [
        ('initiated', 'Call Initiated'),
        ('ringing', 'Ringing Started'),
        ('answered', 'Call Answered'),
        ('hold', 'Call On Hold'),
        ('unhold', 'Call Resumed'),
        ('transfer_initiated', 'Transfer Initiated'),
        ('transfer_completed', 'Transfer Completed'),
        ('recording_started', 'Recording Started'),
        ('recording_stopped', 'Recording Stopped'),
        ('muted', 'Call Muted'),
        ('unmuted', 'Call Unmuted'),
        ('dtmf', 'DTMF Pressed'),
        ('quality_change', 'Call Quality Changed'),
        ('ended', 'Call Ended'),
        ('failed', 'Call Failed'),
        ('error', 'Error Occurred'),
    ]
    
    call_log = models.ForeignKey(CallLog, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(blank=True, default=dict, help_text="Additional event data")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="User who triggered this event"
    )
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['call_log', 'event_type']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.call_log.call_id} - {self.event_type} at {self.timestamp}"


class CallRecording(models.Model):
    """Track call recordings separately for better management"""
    
    RECORDING_STATUS = [
        ('pending', 'Pending'),
        ('recording', 'Recording'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('deleted', 'Deleted'),
    ]
    
    call_log = models.OneToOneField(CallLog, on_delete=models.CASCADE, related_name='recording')
    recording_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    file_path = models.CharField(max_length=500, blank=True, help_text="Local file path")
    file_url = models.URLField(blank=True, help_text="External URL for recording")
    file_size = models.BigIntegerField(null=True, blank=True, help_text="File size in bytes")
    duration = models.DurationField(null=True, blank=True, help_text="Recording duration")
    format = models.CharField(max_length=10, default='wav', help_text="Audio format")
    status = models.CharField(max_length=15, choices=RECORDING_STATUS, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Transcription
    transcript = models.TextField(blank=True, help_text="Call transcript")
    transcript_confidence = models.FloatField(null=True, blank=True, help_text="Transcript confidence (0-1)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Recording for {self.call_log.call_id} ({self.status})"
