import secrets
from django.db import models


class WidgetConnection(models.Model):
    tenant_schema = models.CharField(max_length=63, db_index=True)
    widget_token = models.CharField(max_length=64, unique=True, db_index=True)
    label = models.CharField(max_length=80, default="Default widget")
    is_active = models.BooleanField(default=True, db_index=True)
    allowed_origins = models.JSONField(default=list)
    brand_color = models.CharField(max_length=7, default="#2A2B7D")
    position = models.CharField(
        max_length=16,
        default="bottom-right",
        choices=[("bottom-right", "Bottom right"), ("bottom-left", "Bottom left")],
    )
    welcome_message = models.JSONField(default=dict)
    pre_chat_form = models.JSONField(default=dict)
    offline_message = models.JSONField(default=dict)
    business_hours_schedule = models.JSONField(default=dict, blank=True)
    # Proactive messages — widget.js shows a preview bubble after the
    # visitor has been on the page for ``proactive_delay_seconds`` seconds.
    # Message is localized (e.g. {"en": "Need help?", "ka": "..."}).
    proactive_enabled = models.BooleanField(default=False)
    proactive_message = models.JSONField(default=dict, blank=True)
    proactive_delay_seconds = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.label} ({self.tenant_schema})"

    @staticmethod
    def generate_token():
        return 'wgt_live_' + secrets.token_urlsafe(24)
