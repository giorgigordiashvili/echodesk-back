from django.contrib import admin
from django.utils.html import format_html
from .models import HelpCategory, HelpArticle


@admin.register(HelpCategory)
class HelpCategoryAdmin(admin.ModelAdmin):
    list_display = [
        'get_name_display', 'slug', 'icon_display', 'position', 'is_active',
        'show_on_public', 'show_in_dashboard', 'article_count'
    ]
    list_filter = ['is_active', 'show_on_public', 'show_in_dashboard']
    search_fields = ['name', 'slug', 'description']
    ordering = ['position', 'created_at']
    list_editable = ['position', 'is_active']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'icon')
        }),
        ('Display Settings', {
            'fields': ('position', 'is_active')
        }),
        ('Visibility', {
            'fields': ('show_on_public', 'show_in_dashboard', 'required_feature_key'),
            'description': 'Control where this category appears'
        }),
    )

    @admin.display(description='Name')
    def get_name_display(self, obj):
        return obj.get_name('en')

    @admin.display(description='Icon')
    def icon_display(self, obj):
        if obj.icon:
            return format_html(
                '<span style="background-color: #f3f4f6; padding: 2px 8px; border-radius: 4px; font-family: monospace;">{}</span>',
                obj.icon
            )
        return '-'

    @admin.display(description='Articles')
    def article_count(self, obj):
        count = obj.articles.count()
        active_count = obj.articles.filter(is_active=True).count()
        if count == active_count:
            return count
        return format_html(
            '{} <span style="color: #9ca3af;">({} active)</span>',
            count, active_count
        )


@admin.register(HelpArticle)
class HelpArticleAdmin(admin.ModelAdmin):
    list_display = [
        'get_title_display', 'category', 'content_type_badge',
        'is_active', 'is_featured', 'position', 'updated_at'
    ]
    list_filter = ['content_type', 'category', 'is_active', 'is_featured', 'show_on_public', 'show_in_dashboard']
    search_fields = ['title', 'slug', 'content', 'summary']
    ordering = ['category__position', 'position', '-created_at']
    date_hierarchy = 'created_at'
    list_editable = ['position', 'is_active', 'is_featured']
    raw_id_fields = ['created_by', 'updated_by']

    fieldsets = (
        ('Basic Information', {
            'fields': ('category', 'title', 'slug', 'summary', 'content_type')
        }),
        ('Article Content', {
            'fields': ('content',),
            'classes': ('collapse',),
            'description': 'Rich HTML content. Use JSON format: {"en": "<p>Content here...</p>", "ka": "<p>შინაარსი...</p>", "ru": "<p>Контент...</p>"}'
        }),
        ('Video Content', {
            'fields': ('video_url', 'video_thumbnail', 'video_duration'),
            'classes': ('collapse',),
            'description': 'For video tutorials. Paste YouTube URL (e.g., https://www.youtube.com/watch?v=VIDEO_ID)'
        }),
        ('Guide Steps', {
            'fields': ('guide_steps',),
            'classes': ('collapse',),
            'description': '''JSON array of step objects. Example:
[
  {"step": 1, "title": {"en": "Create Account", "ka": "შექმენით ანგარიში"}, "content": {"en": "Go to...", "ka": "გადადით..."}, "image": "https://..."},
  {"step": 2, "title": {"en": "Configure Settings", "ka": "დააკონფიგურირეთ"}, "content": {"en": "Click on...", "ka": "დააჭირეთ..."}, "image": ""}
]'''
        }),
        ('FAQ Items', {
            'fields': ('faq_items',),
            'classes': ('collapse',),
            'description': '''JSON array of Q&A objects. Example:
[
  {"question": {"en": "How do I reset my password?", "ka": "როგორ შევცვალო პაროლი?"}, "answer": {"en": "Click on...", "ka": "დააჭირეთ..."}},
  {"question": {"en": "What payment methods do you accept?", "ka": "რა გადახდის მეთოდებს იღებთ?"}, "answer": {"en": "We accept...", "ka": "ჩვენ ვიღებთ..."}}
]'''
        }),
        ('Display Settings', {
            'fields': ('position', 'is_active', 'is_featured')
        }),
        ('Visibility', {
            'fields': ('show_on_public', 'show_in_dashboard')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Publishing', {
            'fields': ('published_at',),
            'classes': ('collapse',)
        }),
        ('Tracking', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['created_at', 'updated_at']

    @admin.display(description='Title')
    def get_title_display(self, obj):
        title = obj.get_title('en')
        if len(title) > 50:
            return title[:50] + '...'
        return title

    @admin.display(description='Type')
    def content_type_badge(self, obj):
        colors = {
            'video': ('#FF0000', '#FFFFFF'),      # Red bg, white text
            'article': ('#007BFF', '#FFFFFF'),    # Blue bg, white text
            'guide': ('#28A745', '#FFFFFF'),      # Green bg, white text
            'faq': ('#FFC107', '#000000'),        # Yellow bg, black text
        }
        bg_color, text_color = colors.get(obj.content_type, ('#6C757D', '#FFFFFF'))
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: 500;">{}</span>',
            bg_color, text_color, obj.get_content_type_display()
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
