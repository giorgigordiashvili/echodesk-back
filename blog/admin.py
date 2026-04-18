"""Django admin registrations for the blog app.

Review workflow lives here: AI drafts land in ``BlogPost`` with
``status='review'``, editors tweak the JSON translations inline, then
hit the "Approve & publish" bulk action to flip them live.
"""

from django.contrib import admin, messages
from django.utils import timezone

from .models import BlogCategory, BlogPost, BlogPostRun, BlogTopic


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ("slug", "_name_en", "position", "is_active", "is_featured", "updated_at")
    list_editable = ("position", "is_active", "is_featured")
    search_fields = ("slug", "name")
    list_filter = ("is_active", "is_featured")
    prepopulated_fields = {"slug": ()}
    fieldsets = (
        (None, {
            "fields": ("slug", "name", "description", "icon", "position"),
        }),
        ("Visibility", {
            "fields": ("is_active", "is_featured"),
        }),
        ("SEO overrides", {
            "fields": ("seo_title", "seo_description"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Name (en)")
    def _name_en(self, obj):
        return obj.get_name("en")


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = (
        "slug", "_title_en", "post_type", "status",
        "is_featured", "published_at", "reading_time_minutes", "ai_model",
    )
    list_filter = (
        "status", "post_type", "is_featured", "generated_by_ai",
        "competitor_name", "category",
    )
    list_editable = ("status", "is_featured")
    search_fields = ("slug", "title", "summary", "competitor_name")
    readonly_fields = (
        "reading_time_minutes", "source_topic", "generated_by_ai",
        "ai_model", "ai_prompt_tokens", "ai_completion_tokens", "ai_generated_at",
        "reviewed_by", "reviewed_at",
        "created_by", "updated_by", "created_at", "updated_at",
    )
    fieldsets = (
        (None, {
            "fields": ("slug", "category", "post_type", "status", "is_featured"),
        }),
        ("Content (multilingual JSON)", {
            "fields": ("title", "summary", "content_html", "hero_image_url"),
            "description": 'All JSON fields use locale keys: {"en": "...", "ka": "..."}.',
        }),
        ("SEO", {
            "fields": ("meta_title", "meta_description", "keywords"),
        }),
        ("Structured data", {
            "fields": ("faq_items",),
            "classes": ("collapse",),
        }),
        ("Comparison-only", {
            "fields": ("competitor_name", "comparison_matrix"),
            "classes": ("collapse",),
        }),
        ("Scheduling", {
            "fields": ("published_at", "reading_time_minutes"),
        }),
        ("AI trace", {
            "fields": (
                "source_topic", "generated_by_ai", "ai_model",
                "ai_prompt_tokens", "ai_completion_tokens", "ai_generated_at",
            ),
            "classes": ("collapse",),
        }),
        ("Review", {
            "fields": ("reviewed_by", "reviewed_at", "review_notes"),
            "classes": ("collapse",),
        }),
        ("Audit", {
            "fields": ("created_by", "updated_by", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    actions = ("approve_and_publish", "return_to_draft", "archive")

    @admin.display(description="Title (en)")
    def _title_en(self, obj):
        return obj.get_title("en")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Approve & publish selected")
    def approve_and_publish(self, request, queryset):
        now = timezone.now()
        updated = 0
        for post in queryset.exclude(status="published"):
            post.status = "published"
            post.published_at = post.published_at or now
            post.reviewed_by = request.user
            post.reviewed_at = now
            post.save()
            # Also link the source topic's status if applicable
            topic = post.source_topic
            if topic and topic.status != "published":
                topic.status = "published"
                topic.save(update_fields=["status", "updated_at"])
            updated += 1
        self.message_user(
            request, f"Published {updated} post(s).", level=messages.SUCCESS,
        )

    @admin.action(description="Return to draft")
    def return_to_draft(self, request, queryset):
        updated = queryset.update(status="draft", published_at=None)
        self.message_user(
            request, f"Returned {updated} post(s) to draft.", level=messages.INFO,
        )

    @admin.action(description="Archive")
    def archive(self, request, queryset):
        updated = queryset.update(status="archived")
        self.message_user(
            request, f"Archived {updated} post(s).", level=messages.INFO,
        )


@admin.register(BlogTopic)
class BlogTopicAdmin(admin.ModelAdmin):
    list_display = (
        "slug", "post_type", "competitor_name", "primary_language",
        "priority", "status", "retry_count", "processed_at",
    )
    list_filter = ("status", "post_type", "primary_language")
    list_editable = ("priority", "status")
    search_fields = ("slug", "title_hint", "competitor_name", "angle_hint")
    readonly_fields = ("processed_at", "generated_post", "retry_count", "created_at", "updated_at")
    fieldsets = (
        (None, {
            "fields": ("slug", "title_hint", "angle_hint", "post_type", "primary_language"),
        }),
        ("Comparison metadata", {
            "fields": ("competitor_name",),
            "classes": ("collapse",),
        }),
        ("SEO", {
            "fields": ("target_keywords",),
        }),
        ("Queue", {
            "fields": ("priority", "status", "retry_count"),
        }),
        ("Result", {
            "fields": ("generated_post", "processed_at"),
            "classes": ("collapse",),
        }),
        ("Admin", {
            "fields": ("notes", "created_by", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(BlogPostRun)
class BlogPostRunAdmin(admin.ModelAdmin):
    list_display = ("topic", "model", "success", "started_at", "completed_at",
                    "prompt_tokens", "completion_tokens")
    list_filter = ("success", "model")
    readonly_fields = [f.name for f in BlogPostRun._meta.fields]
    search_fields = ("topic__slug", "error_message")
