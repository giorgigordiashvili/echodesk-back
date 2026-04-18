"""Django admin registrations for the landing_pages app.

Review workflow lives here: AI drafts land in ``LandingPage`` with
``status='review'``, editors tweak the JSON translations inline, then
hit the "Approve & publish" bulk action to flip them live.
"""

import traceback
from io import StringIO

from django.contrib import admin, messages
from django.core.management import call_command
from django.utils import timezone

from .models import LandingPage, LandingPageRun, LandingTopic


# Cap "Draft now" bulk action to avoid runaway API cost.
DRAFT_NOW_LIMIT = 5


@admin.register(LandingPage)
class LandingPageAdmin(admin.ModelAdmin):
    list_display = (
        "slug", "_title_ka", "page_type", "status",
        "published_at", "ai_model", "competitor_name",
    )
    list_filter = ("status", "page_type", "competitor_name", "generated_by_ai")
    list_editable = ("status",)
    search_fields = ("slug", "title", "competitor_name")
    readonly_fields = (
        "source_topic", "generated_by_ai",
        "ai_model", "ai_prompt_tokens", "ai_completion_tokens", "ai_generated_at",
        "reviewed_by", "reviewed_at",
        "created_by", "updated_by", "created_at", "updated_at",
    )
    fieldsets = (
        (None, {
            "fields": ("slug", "page_type", "status"),
        }),
        ("Hero (multilingual JSON)", {
            "fields": ("title", "hero_subtitle", "summary", "og_tag"),
            "description": 'All JSON fields use locale keys: {"en": "...", "ka": "..."}.',
        }),
        ("SEO", {
            "fields": ("meta_title", "meta_description", "keywords"),
        }),
        ("Body blocks", {
            "fields": ("content_blocks",),
            "description": (
                "Typed array of blocks: benefit_grid, checklist, "
                "feature_showcase, quote, comparison_table."
            ),
        }),
        ("FAQ", {
            "fields": ("faq_items",),
            "classes": ("collapse",),
        }),
        ("Feature highlighting", {
            "fields": ("highlighted_feature_slugs",),
            "classes": ("collapse",),
        }),
        ("Comparison-only", {
            "fields": ("competitor_name", "comparison_matrix"),
            "classes": ("collapse",),
        }),
        ("Scheduling", {
            "fields": ("published_at",),
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

    @admin.display(description="Title (ka)")
    def _title_ka(self, obj):
        return obj.get_title("ka")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Approve & publish selected")
    def approve_and_publish(self, request, queryset):
        now = timezone.now()
        updated = 0
        for page in queryset.exclude(status="published"):
            page.status = "published"
            page.published_at = page.published_at or now
            page.reviewed_by = request.user
            page.reviewed_at = now
            page.save()
            # Also link the source topic's status if applicable
            topic = page.source_topic
            if topic and topic.status != "published":
                topic.status = "published"
                topic.save(update_fields=["status", "updated_at"])
            updated += 1
        self.message_user(
            request, f"Published {updated} page(s).", level=messages.SUCCESS,
        )

    @admin.action(description="Return to draft")
    def return_to_draft(self, request, queryset):
        updated = queryset.update(status="draft", published_at=None)
        self.message_user(
            request, f"Returned {updated} page(s) to draft.", level=messages.INFO,
        )

    @admin.action(description="Archive")
    def archive(self, request, queryset):
        updated = queryset.update(status="archived")
        self.message_user(
            request, f"Archived {updated} page(s).", level=messages.INFO,
        )


@admin.register(LandingTopic)
class LandingTopicAdmin(admin.ModelAdmin):
    list_display = (
        "slug", "page_type", "competitor_name", "primary_language",
        "priority", "status", "retry_count", "created_at",
    )
    list_filter = ("status", "page_type", "primary_language")
    list_editable = ("priority", "status")
    search_fields = ("slug", "title_hint", "competitor_name", "angle_hint")
    readonly_fields = ("processed_at", "generated_page", "retry_count", "created_at", "updated_at")
    fieldsets = (
        (None, {
            "fields": ("slug", "title_hint", "angle_hint", "page_type", "primary_language"),
        }),
        ("Feature bundling", {
            "fields": ("highlighted_feature_slugs",),
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
            "fields": ("generated_page", "processed_at"),
            "classes": ("collapse",),
        }),
        ("Admin", {
            "fields": ("notes", "created_by", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    actions = ("draft_now",)

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Draft now via Claude (max 5)")
    def draft_now(self, request, queryset):
        """Run generate_daily_landing_pages synchronously for each selected
        topic (capped to avoid runaway cost). Errors surface as admin messages.
        """
        topics = list(queryset[:DRAFT_NOW_LIMIT])
        if len(queryset) > DRAFT_NOW_LIMIT:
            self.message_user(
                request,
                f"Capped to {DRAFT_NOW_LIMIT} topics per action "
                f"(you selected {len(queryset)}).",
                level=messages.WARNING,
            )

        succeeded, failed = 0, 0
        for topic in topics:
            out = StringIO()
            err = StringIO()
            try:
                call_command(
                    "generate_daily_landing_pages",
                    topic_slug=topic.slug,
                    stdout=out, stderr=err,
                )
                succeeded += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                self.message_user(
                    request,
                    f"[{topic.slug}] FAILED: {exc}\n{traceback.format_exc()[-500:]}",
                    level=messages.ERROR,
                )
        if succeeded:
            self.message_user(
                request,
                f"Drafted {succeeded} topic(s) successfully.",
                level=messages.SUCCESS,
            )
        if failed == 0 and succeeded == 0:
            self.message_user(
                request, "No topics selected.", level=messages.INFO,
            )


@admin.register(LandingPageRun)
class LandingPageRunAdmin(admin.ModelAdmin):
    list_display = (
        "_topic_slug", "model", "success", "started_at", "completed_at",
        "prompt_tokens", "completion_tokens",
    )
    list_filter = ("success", "model")
    readonly_fields = [f.name for f in LandingPageRun._meta.fields]
    search_fields = ("topic__slug", "error_message")

    @admin.display(description="Topic", ordering="topic__slug")
    def _topic_slug(self, obj):
        return obj.topic.slug if obj.topic_id else "-"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
