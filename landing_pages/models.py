"""Landing-pages models.

Marketing-site landing pages — feature, vertical, and competitor-comparison
layouts. Lives in the public schema via SHARED_APPS (mirrors the blog app).
Content is multilingual via JSONField columns keyed by locale (``"en"`` /
``"ka"``) so the Django admin, serializers, and frontend renderer all feel
familiar.

AI-pipeline fields on LandingPage track which Claude call produced each
draft. Nothing on LandingPage is required for a human-authored page —
admins can create entries directly in the admin and never touch the AI.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


PAGE_TYPE_CHOICES = [
    ("feature", "Feature"),            # EchoDesk <module> deep-dive
    ("vertical", "Vertical"),          # EchoDesk for <industry>
    ("comparison", "Comparison"),      # EchoDesk vs <competitor>
]

PAGE_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("review", "Needs Review"),        # AI-generated draft awaiting human review
    ("scheduled", "Scheduled"),        # Approved, publishes at published_at
    ("published", "Published"),
    ("archived", "Archived"),
]

TOPIC_STATUS_CHOICES = [
    ("pending", "Pending"),            # In queue, not yet drafted
    ("drafting", "Drafting"),          # Claude call in flight
    ("drafted", "Drafted"),            # LandingPage created, awaiting review
    ("published", "Published"),        # Source topic for a published page
    ("skipped", "Skipped"),            # Admin chose not to use
]

LANGUAGE_CHOICES = [
    ("ka", "Georgian"),
    ("en", "English"),
]


def _locale_get(value, language: str = "en") -> str:
    """Safe reader for JSONField columns that hold ``{"en": ..., "ka": ...}``."""
    if not value:
        return ""
    if isinstance(value, dict):
        return value.get(language) or value.get("en") or next(iter(value.values()), "")
    return str(value)


class LandingTopic(models.Model):
    """An idea in the AI generation queue.

    Admins seed these either through the Django admin, via the POST
    ``/api/landing/admin/topics/seed/`` endpoint, or via the
    ``0002_seed_topics`` data migration. The daily Celery task picks the
    highest-priority ``pending`` topics, drafts pages via Claude, and
    flips them to ``drafted`` with a link to the generated LandingPage.
    """

    slug = models.CharField(max_length=120, unique=True)
    page_type = models.CharField(max_length=16, choices=PAGE_TYPE_CHOICES)
    title_hint = models.JSONField(
        blank=True, default=dict,
        help_text="Seed title per locale. AI may refine it.",
    )
    angle_hint = models.TextField(
        blank=True,
        help_text="1-2 sentences telling the AI what the specific angle is.",
    )
    target_keywords = models.JSONField(
        blank=True, default=list,
        help_text='Keyword list for natural inclusion, e.g. ["WhatsApp Business API Georgia", "CRM GEL"].',
    )
    primary_language = models.CharField(
        max_length=8, choices=LANGUAGE_CHOICES, default="ka",
    )
    highlighted_feature_slugs = models.JSONField(
        blank=True, default=list,
        help_text="Feature keys from tenants.Feature. Bundle for verticals; feature pages may have one.",
    )

    # Comparison-only metadata
    competitor_name = models.CharField(
        max_length=80, blank=True,
        help_text="For page_type=comparison only (e.g. 'Kommo', 'Bitrix24').",
    )

    priority = models.IntegerField(
        default=50,
        help_text="Higher drafts first (0-100 typical range).",
    )
    status = models.CharField(
        max_length=16, choices=TOPIC_STATUS_CHOICES, default="pending",
    )
    retry_count = models.PositiveSmallIntegerField(default=0)
    processed_at = models.DateTimeField(null=True, blank=True)

    generated_page = models.OneToOneField(
        "landing_pages.LandingPage",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="source_topic_back",
        help_text="Filled in once the AI creates a draft from this topic.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )
    notes = models.TextField(
        blank=True,
        help_text="Admin notes — NOT sent to the AI.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "created_at"]
        indexes = [
            models.Index(fields=["status", "-priority"]),
            models.Index(fields=["page_type"]),
        ]
        verbose_name = "Landing Topic"
        verbose_name_plural = "Landing Topics"

    def __str__(self):
        return f"{self.slug} [{self.status}]"

    def get_title_hint(self, language: str = "en") -> str:
        return _locale_get(self.title_hint, language)


class LandingPage(models.Model):
    """A published (or to-be-published) marketing landing page.

    Most string-content fields are JSON maps keyed by locale so a single
    page holds both Georgian and English copies. The frontend reads the
    ``?lang=`` query parameter and returns the matching locale's strings.

    Unlike blog posts (one HTML body), landing pages store structured
    ``content_blocks`` — a typed array of block dicts rendered per-block
    by the frontend (benefit_grid, checklist, feature_showcase, etc.).
    """

    slug = models.CharField(max_length=120, unique=True, db_index=True)
    page_type = models.CharField(max_length=16, choices=PAGE_TYPE_CHOICES)

    # Multilingual hero copy
    title = models.JSONField(default=dict)
    hero_subtitle = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)

    # SEO
    meta_title = models.JSONField(default=dict, blank=True)
    meta_description = models.JSONField(default=dict, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    og_tag = models.CharField(
        max_length=40, blank=True,
        help_text='Short chip for OG image (e.g. "WhatsApp", "Invoicing").',
    )

    # Body — structured blocks rendered per-type by the frontend
    content_blocks = models.JSONField(
        default=list, blank=True,
        help_text=(
            "Typed array of block dicts: benefit_grid, checklist, "
            "feature_showcase, quote, comparison_table."
        ),
    )

    # Structured data
    faq_items = models.JSONField(
        default=list, blank=True,
        help_text="Array of {question_en, question_ka, answer_en, answer_ka} for FAQPage JSON-LD.",
    )

    # Pricing section filters to these feature keys from tenants.Feature
    highlighted_feature_slugs = models.JSONField(
        default=list, blank=True,
        help_text="Array of feature keys used to filter the on-page pricing section.",
    )

    # Comparison-specific fields
    competitor_name = models.CharField(
        max_length=80, blank=True,
        help_text="For page_type=comparison only.",
    )
    comparison_matrix = models.JSONField(
        default=list, blank=True,
        help_text="Structured feature diff: [{feature, us, them, winner}] for table rendering.",
    )

    # Status + scheduling
    status = models.CharField(
        max_length=16, choices=PAGE_STATUS_CHOICES, default="draft",
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # AI trace (nullable — empty for human-authored pages)
    source_topic = models.ForeignKey(
        LandingTopic,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="generated_pages",
    )
    generated_by_ai = models.BooleanField(default=False)
    ai_model = models.CharField(max_length=80, blank=True, default="")
    ai_prompt_tokens = models.PositiveIntegerField(default=0)
    ai_completion_tokens = models.PositiveIntegerField(default=0)
    ai_generated_at = models.DateTimeField(null=True, blank=True)

    # Review metadata
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Authorship
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="landing_pages_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status", "-published_at"]),
            models.Index(fields=["page_type"]),
        ]
        verbose_name = "Landing Page"
        verbose_name_plural = "Landing Pages"

    def __str__(self):
        return _locale_get(self.title, "en") or self.slug

    def save(self, *args, **kwargs):
        # Editors sometimes flip status → 'published' via the field editor
        # without remembering to set published_at. Auto-stamp it so the
        # frontend sort-by-date + sitemap both work. (Phase 2 lesson.)
        if self.status == "published" and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def get_title(self, language: str = "en") -> str:
        return _locale_get(self.title, language)

    def get_hero_subtitle(self, language: str = "en") -> str:
        return _locale_get(self.hero_subtitle, language)

    def get_summary(self, language: str = "en") -> str:
        return _locale_get(self.summary, language)

    def get_meta_title(self, language: str = "en") -> str:
        return _locale_get(self.meta_title, language) or self.get_title(language)

    def get_meta_description(self, language: str = "en") -> str:
        return _locale_get(self.meta_description, language) or self.get_summary(language)


class LandingPageRun(models.Model):
    """Audit log for AI generation calls.

    Written for every Claude invocation — success or failure — so ops
    can monitor token spend, error rates, and prompt drift. One topic
    can have many runs (retries after parse failures).
    """

    topic = models.ForeignKey(
        LandingTopic,
        on_delete=models.CASCADE,
        related_name="runs",
    )
    resulting_page = models.ForeignKey(
        LandingPage,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ai_runs",
    )
    model = models.CharField(max_length=80, blank=True, default="")
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, default="")
    raw_response = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["topic", "-started_at"]),
        ]
        verbose_name = "Landing Page Run"
        verbose_name_plural = "Landing Page Runs"

    def __str__(self):
        status = "OK" if self.success else "FAIL"
        return f"{self.topic.slug} [{status} @ {self.started_at:%Y-%m-%d %H:%M}]"
