"""DRF serializers for the blog app.

Two pairs: **Public** (used by `/api/blog/public/*`, returns
locale-resolved strings based on the ``?lang=`` query param) and
**Admin** (raw JSONField contents, full CRUD, shown in the Django admin
+ the admin API).
"""

from rest_framework import serializers

from .models import BlogCategory, BlogPost, BlogPostRun, BlogTopic


def _lang_from_context(context) -> str:
    request = context.get("request")
    if request is not None and hasattr(request, "query_params"):
        lang = request.query_params.get("lang")
        if lang in {"en", "ka"}:
            return lang
    return "en"


# ---------------------------------------------------------------------------
# Public (read-only, locale-resolved)
# ---------------------------------------------------------------------------

class PublicBlogCategorySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    post_count = serializers.SerializerMethodField()

    class Meta:
        model = BlogCategory
        fields = [
            "id", "slug", "name", "description", "icon",
            "position", "is_featured", "post_count",
        ]

    def get_name(self, obj):
        return obj.get_name(_lang_from_context(self.context))

    def get_description(self, obj):
        return obj.get_description(_lang_from_context(self.context))

    def get_post_count(self, obj):
        return obj.posts.filter(status="published").count()


class PublicBlogPostListSerializer(serializers.ModelSerializer):
    """Lightweight post representation for the /blog list view."""

    title = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    category = PublicBlogCategorySerializer(read_only=True)

    class Meta:
        model = BlogPost
        fields = [
            "id", "slug", "post_type", "title", "summary",
            "category", "hero_image_url", "published_at",
            "reading_time_minutes", "is_featured",
            "competitor_name",
        ]

    def get_title(self, obj):
        return obj.get_title(_lang_from_context(self.context))

    def get_summary(self, obj):
        return obj.get_summary(_lang_from_context(self.context))


class PublicBlogPostDetailSerializer(PublicBlogPostListSerializer):
    """Full post — list fields plus content_html, meta, FAQ, comparison matrix."""

    content_html = serializers.SerializerMethodField()
    meta_title = serializers.SerializerMethodField()
    meta_description = serializers.SerializerMethodField()

    class Meta(PublicBlogPostListSerializer.Meta):
        fields = PublicBlogPostListSerializer.Meta.fields + [
            "content_html", "meta_title", "meta_description", "keywords",
            "faq_items", "comparison_matrix",
            "created_at", "updated_at",
        ]

    def get_content_html(self, obj):
        return obj.get_content_html(_lang_from_context(self.context))

    def get_meta_title(self, obj):
        return obj.get_meta_title(_lang_from_context(self.context))

    def get_meta_description(self, obj):
        return obj.get_meta_description(_lang_from_context(self.context))


# ---------------------------------------------------------------------------
# Admin (raw JSONField access, full CRUD)
# ---------------------------------------------------------------------------

class BlogCategoryAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogCategory
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class BlogPostAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogPost
        fields = "__all__"
        read_only_fields = (
            "reading_time_minutes",
            "source_topic", "generated_by_ai",
            "ai_model", "ai_prompt_tokens", "ai_completion_tokens", "ai_generated_at",
            "reviewed_by", "reviewed_at",
            "created_by", "updated_by",
            "created_at", "updated_at",
        )


class BlogTopicAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogTopic
        fields = "__all__"
        read_only_fields = (
            "processed_at", "generated_post", "retry_count",
            "created_by", "created_at", "updated_at",
        )


class BlogTopicSeedItemSerializer(serializers.Serializer):
    """Payload for bulk-seeding topics via POST /topics/seed/."""
    slug = serializers.SlugField(max_length=160)
    title_hint = serializers.JSONField(required=False)
    angle_hint = serializers.CharField(required=False, allow_blank=True)
    post_type = serializers.ChoiceField(
        choices=[c[0] for c in BlogTopic._meta.get_field("post_type").choices]
    )
    target_keywords = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    primary_language = serializers.ChoiceField(
        choices=[c[0] for c in BlogTopic._meta.get_field("primary_language").choices],
        default="ka",
    )
    competitor_name = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.IntegerField(required=False, default=50)
    notes = serializers.CharField(required=False, allow_blank=True)


class BlogPostRunAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogPostRun
        fields = "__all__"
        read_only_fields = [f.name for f in BlogPostRun._meta.fields]
