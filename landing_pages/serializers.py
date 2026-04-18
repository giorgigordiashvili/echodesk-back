"""DRF serializers for the landing_pages app.

Two pairs: **Public** (used by ``/api/landing/public/*``, returns
locale-resolved scalar fields based on the ``?lang=`` query param) and
**Admin** (raw JSONField contents, full CRUD, shown in the Django admin
+ the admin API).

``content_blocks`` and ``faq_items`` are returned RAW on the public
endpoint so the frontend can handle per-locale logic per-block — this
mirrors how the blog returns ``faq_items`` as raw JSON.
"""

from rest_framework import serializers

from .models import LandingPage, LandingPageRun, LandingTopic


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

class PublicLandingPageListSerializer(serializers.ModelSerializer):
    """Lightweight page representation for the /landing list view."""

    title = serializers.SerializerMethodField()
    hero_subtitle = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta:
        model = LandingPage
        fields = [
            "id", "slug", "page_type", "title", "hero_subtitle", "summary",
            "og_tag", "competitor_name", "highlighted_feature_slugs",
            "published_at", "updated_at",
        ]

    def get_title(self, obj) -> str:
        return obj.get_title(_lang_from_context(self.context))

    def get_hero_subtitle(self, obj) -> str:
        return obj.get_hero_subtitle(_lang_from_context(self.context))

    def get_summary(self, obj) -> str:
        return obj.get_summary(_lang_from_context(self.context))


class PublicLandingPageDetailSerializer(PublicLandingPageListSerializer):
    """Full landing page — list fields plus content_blocks, meta, FAQ, comparison matrix.

    ``content_blocks`` and ``faq_items`` come back RAW (as stored in the DB)
    so the frontend can resolve per-block locale fields on its own.
    """

    meta_title = serializers.SerializerMethodField()
    meta_description = serializers.SerializerMethodField()

    class Meta(PublicLandingPageListSerializer.Meta):
        fields = PublicLandingPageListSerializer.Meta.fields + [
            "meta_title", "meta_description", "keywords",
            "content_blocks", "faq_items", "comparison_matrix",
            "created_at",
        ]

    def get_meta_title(self, obj) -> str:
        return obj.get_meta_title(_lang_from_context(self.context))

    def get_meta_description(self, obj) -> str:
        return obj.get_meta_description(_lang_from_context(self.context))


# ---------------------------------------------------------------------------
# Admin (raw JSONField access, full CRUD)
# ---------------------------------------------------------------------------

class LandingPageAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = LandingPage
        fields = "__all__"
        read_only_fields = (
            "source_topic", "generated_by_ai",
            "ai_model", "ai_prompt_tokens", "ai_completion_tokens", "ai_generated_at",
            "reviewed_by", "reviewed_at",
            "created_by", "updated_by",
            "created_at", "updated_at",
        )


class LandingTopicAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = LandingTopic
        fields = "__all__"
        read_only_fields = (
            "processed_at", "generated_page", "retry_count",
            "created_by", "created_at", "updated_at",
        )


class LandingTopicSeedItemSerializer(serializers.Serializer):
    """Payload for bulk-seeding topics via POST /topics/seed/."""
    slug = serializers.CharField(max_length=120)
    page_type = serializers.ChoiceField(
        choices=[c[0] for c in LandingTopic._meta.get_field("page_type").choices]
    )
    title_hint = serializers.JSONField(required=False)
    angle_hint = serializers.CharField(required=False, allow_blank=True)
    target_keywords = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    primary_language = serializers.ChoiceField(
        choices=[c[0] for c in LandingTopic._meta.get_field("primary_language").choices],
        default="ka",
    )
    highlighted_feature_slugs = serializers.ListField(
        child=serializers.CharField(), required=False, default=list,
    )
    competitor_name = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.IntegerField(required=False, default=50)
    notes = serializers.CharField(required=False, allow_blank=True)


class LandingPageRunAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = LandingPageRun
        fields = "__all__"
        read_only_fields = [f.name for f in LandingPageRun._meta.fields]
