"""Marketing models.

Public marketing-site helpers — testimonials for social proof,
contact-form submissions (sales leads), and newsletter subscribers.
All live in the public schema via SHARED_APPS (mirrors ``blog`` and
``landing_pages``) so the main echodesk.ge marketing site can read
and write without going through a tenant subdomain.
"""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


LANGUAGE_CHOICES = [
    ("ka", "Georgian"),
    ("en", "English"),
]


class Testimonial(models.Model):
    """Public social-proof item rendered on the marketing site.

    Frontend pulls ``is_active=True`` rows sorted by ``position`` and
    resolves ``role`` / ``quote`` against the ``?lang=`` query param.
    """

    slug = models.CharField(
        max_length=60, unique=True,
        help_text="Stable ID — admin can leave blank for auto-slug.",
    )
    position = models.PositiveSmallIntegerField(
        default=0,
        help_text="Sort order; lower values render first.",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    author_name = models.CharField(max_length=80)
    author_role_ka = models.CharField(max_length=120, blank=True)
    author_role_en = models.CharField(max_length=120, blank=True)
    company_name = models.CharField(max_length=80, blank=True)
    logo_url = models.URLField(
        blank=True,
        help_text="Optional customer logo for the logo bar.",
    )
    avatar_url = models.URLField(
        blank=True,
        help_text="Optional avatar; frontend falls back to initials.",
    )
    quote_ka = models.TextField(help_text="Georgian quote — 120-350 chars ideal.")
    quote_en = models.TextField(
        blank=True,
        help_text="English quote — falls back to KA when empty.",
    )
    rating = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "-created_at"]
        verbose_name = "Testimonial"
        verbose_name_plural = "Testimonials"

    def __str__(self):
        if self.company_name:
            return f"{self.author_name} ({self.company_name})"
        return self.author_name

    # Helpers used by the locale-aware public serializer.
    def get_role(self, language: str = "ka") -> str:
        if language == "en":
            return self.author_role_en or self.author_role_ka
        return self.author_role_ka or self.author_role_en

    def get_quote(self, language: str = "ka") -> str:
        if language == "en":
            return self.quote_en or self.quote_ka
        return self.quote_ka or self.quote_en


class ContactSubmission(models.Model):
    """Lead capture from the public marketing site contact form."""

    SUBJECT_CHOICES = [
        ("sales", "Sales"),
        ("demo", "Demo"),
        ("support", "Support"),
        ("partnership", "Partnership"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("closed_won", "Closed — Won"),
        ("closed_lost", "Closed — Lost"),
    ]

    name = models.CharField(max_length=120)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=40, blank=True)
    company = models.CharField(max_length=120, blank=True)
    subject = models.CharField(
        max_length=20, choices=SUBJECT_CHOICES, default="sales",
    )
    message = models.TextField()
    preferred_language = models.CharField(
        max_length=4, default="ka", choices=LANGUAGE_CHOICES,
    )

    # Server-captured audit context (not sent by the client directly —
    # views pull these from request headers before saving).
    referrer_url = models.CharField(max_length=500, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="new", db_index=True,
    )
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    internal_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Contact Submission"
        verbose_name_plural = "Contact Submissions"

    def __str__(self):
        return f"{self.name} <{self.email}> [{self.status}]"


class NewsletterSubscriber(models.Model):
    """Email-list subscriber.

    A single unique row per email — resubscribes flip ``is_active``
    back to True instead of creating duplicates. ``unsubscribe_token``
    is embedded in the welcome email so one-click unsubscribe works
    without requiring a login.
    """

    email = models.EmailField(unique=True)
    locale = models.CharField(
        max_length=4, default="ka", choices=LANGUAGE_CHOICES,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    source = models.CharField(
        max_length=40, default="footer", blank=True,
        help_text='Origin, e.g. "footer", "blog", "landing:<slug>".',
    )
    unsubscribe_token = models.CharField(
        max_length=64, unique=True,
        help_text="Auto-generated (uuid4 hex) on first save.",
    )
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Newsletter Subscriber"
        verbose_name_plural = "Newsletter Subscribers"

    def __str__(self):
        return f"{self.email} [{'active' if self.is_active else 'inactive'}]"

    def save(self, *args, **kwargs):
        if not self.unsubscribe_token:
            self.unsubscribe_token = uuid.uuid4().hex
        super().save(*args, **kwargs)
