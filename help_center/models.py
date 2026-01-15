from django.db import models
from django.conf import settings


class HelpCategory(models.Model):
    """
    Categories for organizing help content.
    Uses JSONField for multi-language support.
    """
    name = models.JSONField(
        help_text='Category name: {"en": "Getting Started", "ka": "დაწყება", "ru": "Начало"}'
    )
    slug = models.SlugField(max_length=100, unique=True)
    description = models.JSONField(
        blank=True,
        default=dict,
        help_text='Category description in different languages'
    )
    icon = models.CharField(
        max_length=100,
        blank=True,
        help_text='Lucide icon name (e.g., "book-open", "video", "help-circle")'
    )
    position = models.PositiveIntegerField(
        default=0,
        help_text='Display order (lower numbers first)'
    )
    is_active = models.BooleanField(default=True)

    # Visibility controls
    show_on_public = models.BooleanField(
        default=True,
        help_text='Show on public landing page (/docs)'
    )
    show_in_dashboard = models.BooleanField(
        default=True,
        help_text='Show in tenant dashboard help center'
    )

    # Feature association (optional)
    required_feature_key = models.CharField(
        max_length=100,
        blank=True,
        help_text='Feature key required to view this category in dashboard (e.g., "ecommerce", "whatsapp")'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'created_at']
        verbose_name = 'Help Category'
        verbose_name_plural = 'Help Categories'

    def __str__(self):
        if isinstance(self.name, dict):
            return self.name.get('en', list(self.name.values())[0] if self.name else 'Unnamed')
        return str(self.name)

    def get_name(self, language='en'):
        if isinstance(self.name, dict):
            return self.name.get(language, self.name.get('en', ''))
        return str(self.name)

    def get_description(self, language='en'):
        if isinstance(self.description, dict):
            return self.description.get(language, self.description.get('en', ''))
        return str(self.description) if self.description else ''


class HelpArticle(models.Model):
    """
    Main article model supporting different content types:
    - Video tutorials (YouTube embeds)
    - Text articles (rich HTML)
    - Step-by-step guides
    - FAQ sections
    """
    CONTENT_TYPE_CHOICES = [
        ('video', 'Video Tutorial'),
        ('article', 'Text Article'),
        ('guide', 'Step-by-Step Guide'),
        ('faq', 'FAQ Section'),
    ]

    category = models.ForeignKey(
        HelpCategory,
        on_delete=models.CASCADE,
        related_name='articles'
    )

    # Multi-language fields
    title = models.JSONField(
        help_text='Article title: {"en": "How to...", "ka": "როგორ...", "ru": "Как..."}'
    )
    slug = models.SlugField(max_length=200, unique=True)
    summary = models.JSONField(
        blank=True,
        default=dict,
        help_text='Short summary for listing pages'
    )

    content_type = models.CharField(
        max_length=20,
        choices=CONTENT_TYPE_CHOICES,
        default='article'
    )

    # Rich text content (for articles)
    content = models.JSONField(
        blank=True,
        default=dict,
        help_text='Rich HTML content: {"en": "<p>...</p>", "ka": "<p>...</p>"}'
    )

    # Video-specific fields
    video_url = models.URLField(
        blank=True,
        help_text='YouTube or Vimeo URL for video tutorials'
    )
    video_thumbnail = models.URLField(
        blank=True,
        help_text='Thumbnail image URL for video'
    )
    video_duration = models.CharField(
        max_length=20,
        blank=True,
        help_text='Duration string (e.g., "5:30")'
    )

    # Guide-specific fields (stored as JSON for step-by-step format)
    guide_steps = models.JSONField(
        blank=True,
        default=list,
        help_text='''Steps for guides: [
            {"step": 1, "title": {"en": "Step 1", "ka": "ნაბიჯი 1"}, "content": {"en": "...", "ka": "..."}, "image": "url"},
            ...
        ]'''
    )

    # FAQ-specific fields (Q&A pairs)
    faq_items = models.JSONField(
        blank=True,
        default=list,
        help_text='''FAQ items: [
            {"question": {"en": "Q?", "ka": "კ?"}, "answer": {"en": "A", "ka": "პ"}},
            ...
        ]'''
    )

    # Metadata
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(
        default=False,
        help_text='Show in featured/highlighted section'
    )

    # Visibility controls
    show_on_public = models.BooleanField(
        default=True,
        help_text='Show on public landing page'
    )
    show_in_dashboard = models.BooleanField(
        default=True,
        help_text='Show in tenant dashboard'
    )

    # SEO
    meta_title = models.JSONField(blank=True, default=dict)
    meta_description = models.JSONField(blank=True, default=dict)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # Author tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_help_articles'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_help_articles'
    )

    class Meta:
        ordering = ['category__position', 'position', '-created_at']
        verbose_name = 'Help Article'
        verbose_name_plural = 'Help Articles'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['content_type', 'is_active']),
            models.Index(fields=['is_featured', 'is_active']),
        ]

    def __str__(self):
        if isinstance(self.title, dict):
            return self.title.get('en', list(self.title.values())[0] if self.title else 'Unnamed')
        return str(self.title)

    def get_title(self, language='en'):
        if isinstance(self.title, dict):
            return self.title.get(language, self.title.get('en', ''))
        return str(self.title)

    def get_summary(self, language='en'):
        if isinstance(self.summary, dict):
            return self.summary.get(language, self.summary.get('en', ''))
        return str(self.summary) if self.summary else ''

    def get_content(self, language='en'):
        if isinstance(self.content, dict):
            return self.content.get(language, self.content.get('en', ''))
        return str(self.content) if self.content else ''
