from django.db import models
from django.conf import settings


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
    """Call log model for tracking phone calls"""
    
    STATUS_CHOICES = [
        ('answered', 'Answered'),
        ('missed', 'Missed'),
        ('busy', 'Busy'),
        ('no_answer', 'No Answer'),
        ('failed', 'Failed'),
    ]
    
    caller_number = models.CharField(max_length=20)
    recipient_number = models.CharField(max_length=20)
    duration = models.DurationField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='handled_calls'
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.caller_number} -> {self.recipient_number} ({self.status})"
