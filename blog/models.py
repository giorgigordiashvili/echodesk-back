"""Blog models.

Public marketing-site blog — lives in the public schema via SHARED_APPS
(mirrors help_center). Content is multilingual via JSONField columns
keyed by locale (``"en"`` / ``"ka"``), same convention as HelpArticle
so the Django admin, serializers, and frontend renderer all feel
familiar.

AI-pipeline fields on BlogPost track which Claude call produced each
draft. Nothing on BlogPost is required for a human-authored post —
admins can create entries directly in the admin and never touch the AI.
"""

import re
from django.conf import settings
from django.db import models


POST_TYPE_CHOICES = [
    ("comparison", "Comparison"),       # EchoDesk vs <competitor>
    ("how_to", "How-To Guide"),         # Step-by-step tutorial
    ("use_case", "Use Case"),           # Scenario / customer-story style
    ("announcement", "Announcement"),   # Product news
    ("thought_leadership", "Thought Leadership"),  # Editorial / opinion
]

POST_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("review", "Needs Review"),         # AI-generated draft awaiting human review
    ("scheduled", "Scheduled"),         # Approved, publishes at published_at
    ("published", "Published"),
    ("archived", "Archived"),
]

TOPIC_STATUS_CHOICES = [
    ("pending", "Pending"),             # In queue, not yet drafted
    ("drafting", "Drafting"),           # Claude call in flight
    ("drafted", "Drafted"),             # BlogPost created, awaiting review
    ("published", "Published"),         # Source topic for a published post
    ("skipped", "Skipped"),             # Admin chose not to use
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


class BlogCategory(models.Model):
    """Top-level taxonomy for blog posts (e.g. "Product", "Guides",
    "Comparisons"). A post can belong to one category; posts without a
    category render under a generic "All posts" listing.
    """

    name = models.JSONField(
        help_text='Category name per locale: {"en": "Guides", "ka": "გზამკვლევები"}'
    )
    slug = models.SlugField(max_length=120, unique=True)
    description = models.JSONField(blank=True, default=dict)
    icon = models.CharField(
        max_length=64, blank=True,
        help_text='Lucide icon name (e.g. "book-open", "target"). Optional.',
    )
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(
        default=False,
        help_text="Featured categories render first on the blog index.",
    )

    # Per-category SEO overrides (fall back to site defaults if empty)
    seo_title = models.JSONField(blank=True, default=dict)
    seo_description = models.JSONField(blank=True, default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "-is_featured", "created_at"]
        verbose_name = "Blog Category"
        verbose_name_plural = "Blog Categories"

    def __str__(self):
        return _locale_get(self.name, "en") or self.slug

    def get_name(self, language: str = "en") -> str:
        return _locale_get(self.name, language)

    def get_description(self, language: str = "en") -> str:
        return _locale_get(self.description, language)


class BlogTopic(models.Model):
    """An idea in the AI generation queue.

    Admins seed these either through the Django admin or via the POST
    ``/api/blog/admin/topics/seed/`` endpoint. The daily Celery task
    picks the highest-priority ``pending`` topics, drafts posts via
    Claude, and flips them to ``drafted`` with a link to the generated
    BlogPost.
    """

    slug = models.SlugField(max_length=160, unique=True)
    title_hint = models.JSONField(
        blank=True, default=dict,
        help_text="Seed title per locale. AI may refine it.",
    )
    angle_hint = models.TextField(
        blank=True,
        help_text="1-3 sentences telling the AI what the unique angle is.",
    )
    post_type = models.CharField(max_length=32, choices=POST_TYPE_CHOICES)
    target_keywords = models.JSONField(
        blank=True, default=list,
        help_text='Keyword list for natural inclusion, e.g. ["WhatsApp helpdesk", "Kommo alternative Georgia"].',
    )
    primary_language = models.CharField(
        max_length=8, choices=LANGUAGE_CHOICES, default="ka",
    )

    # Comparison-only metadata
    competitor_name = models.CharField(
        max_length=80, blank=True,
        help_text="For post_type=comparison only (e.g. 'Kommo', 'Bitrix24').",
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

    generated_post = models.OneToOneField(
        "blog.BlogPost",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="source_topic_link",
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
            models.Index(fields=["post_type"]),
        ]
        verbose_name = "Blog Topic"
        verbose_name_plural = "Blog Topics"

    def __str__(self):
        return f"{self.slug} [{self.status}]"

    def get_title_hint(self, language: str = "en") -> str:
        return _locale_get(self.title_hint, language)


class BlogPost(models.Model):
    """A published (or to-be-published) article on the public blog.

    Most string-content fields are JSON maps keyed by locale so a single
    post holds both Georgian and English copies. The frontend reads the
    ``?lang=`` query parameter and returns the matching locale's strings.
    """

    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="posts",
    )
    slug = models.SlugField(max_length=160, unique=True, db_index=True)
    post_type = models.CharField(
        max_length=32, choices=POST_TYPE_CHOICES, default="how_to",
    )

    # Multilingual content
    title = models.JSONField(default=dict)
    summary = models.JSONField(default=dict, blank=True)
    content_html = models.JSONField(
        default=dict,
        help_text="HTML content per locale. Sanitized with DOMPurify on the frontend.",
    )

    # SEO
    meta_title = models.JSONField(default=dict, blank=True)
    meta_description = models.JSONField(default=dict, blank=True)
    keywords = models.JSONField(default=list, blank=True)

    hero_image_url = models.URLField(blank=True, default="")

    # Structured data
    faq_items = models.JSONField(
        default=list, blank=True,
        help_text="Array of {question_en, question_ka, answer_en, answer_ka} for FAQPage JSON-LD.",
    )

    # Comparison-specific fields
    competitor_name = models.CharField(max_length=80, blank=True, default="")
    comparison_matrix = models.JSONField(
        default=list, blank=True,
        help_text="Structured feature diff: [{feature, us, them, winner}] for table rendering.",
    )

    # Status + scheduling
    status = models.CharField(
        max_length=16, choices=POST_STATUS_CHOICES, default="draft",
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reading_time_minutes = models.PositiveSmallIntegerField(default=0)
    is_featured = models.BooleanField(default=False)

    # AI trace (nullable — empty for human-authored posts)
    source_topic = models.ForeignKey(
        BlogTopic,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="posts",
    )
    generated_by_ai = models.BooleanField(default=False)
    ai_model = models.CharField(max_length=80, blank=True, default="")
    ai_prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    ai_completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    ai_generated_at = models.DateTimeField(null=True, blank=True)

    # Review metadata
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="blog_posts_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, default="")

    # Authorship
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="blog_posts_created",
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
            models.Index(fields=["status", "-published_at"]),
            models.Index(fields=["post_type"]),
            models.Index(fields=["competitor_name"]),
        ]
        verbose_name = "Blog Post"
        verbose_name_plural = "Blog Posts"

    def __str__(self):
        return _locale_get(self.title, "en") or self.slug

    def save(self, *args, **kwargs):
        self.reading_time_minutes = self._compute_reading_time()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def get_title(self, language: str = "en") -> str:
        return _locale_get(self.title, language)

    def get_summary(self, language: str = "en") -> str:
        return _locale_get(self.summary, language)

    def get_content_html(self, language: str = "en") -> str:
        return _locale_get(self.content_html, language)

    def get_meta_title(self, language: str = "en") -> str:
        return _locale_get(self.meta_title, language) or self.get_title(language)

    def get_meta_description(self, language: str = "en") -> str:
        return _locale_get(self.meta_description, language) or self.get_summary(language)

    def _compute_reading_time(self) -> int:
        """~200 words/minute reading speed. Uses whichever locale has the
        most words (typically Georgian content is longer by glyph but
        similar by concept count)."""
        longest = 0
        if isinstance(self.content_html, dict):
            for html in self.content_html.values():
                text = re.sub(r"<[^>]+>", " ", html or "")
                words = len(text.split())
                if words > longest:
                    longest = words
        return max(1, round(longest / 200)) if longest else 0


class BlogPostRun(models.Model):
    """Audit log for AI generation calls.

    Written for every Claude invocation — success or failure — so ops
    can monitor token spend, error rates, and prompt drift. One topic
    can have many runs (retries after parse failures).
    """

    topic = models.ForeignKey(
        BlogTopic,
        on_delete=models.CASCADE,
        related_name="runs",
    )
    resulting_post = models.ForeignKey(
        BlogPost,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ai_runs",
    )
    model = models.CharField(max_length=80, blank=True, default="")
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, default="")
    raw_response = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["topic", "-started_at"]),
        ]
        verbose_name = "Blog Post Run"
        verbose_name_plural = "Blog Post Runs"

    def __str__(self):
        status = "OK" if self.success else "FAIL"
        return f"{self.topic.slug} [{status} @ {self.started_at:%Y-%m-%d %H:%M}]"
