"""DRF serializers for the marketing app.

Three pairs:
  * **Public** — the read-only, locale-resolved ``TestimonialSerializer``
    and the write-only ``ContactSubmissionCreateSerializer`` /
    ``NewsletterSubscribeSerializer`` used by the marketing site.
  * **Admin** — raw model fields for the admin API, letting internal
    staff manage testimonials, triage contact submissions, and export
    newsletter subscribers.

Locale resolution uses the ``_lang_from_context`` pattern from
``blog/serializers.py``. Default locale is ``ka`` (the marketing site
is Georgian-first).
"""

from rest_framework import serializers

from .models import ContactSubmission, NewsletterSubscriber, Testimonial


def _lang_from_context(context) -> str:
    request = context.get("request")
    if request is not None and hasattr(request, "query_params"):
        lang = request.query_params.get("lang")
        if lang in {"en", "ka"}:
            return lang
    return "ka"


# ---------------------------------------------------------------------------
# Public (read-only, locale-resolved)
# ---------------------------------------------------------------------------

class TestimonialSerializer(serializers.ModelSerializer):
    """Locale-aware, read-only testimonial for the public marketing site."""

    role = serializers.SerializerMethodField()
    quote = serializers.SerializerMethodField()

    class Meta:
        model = Testimonial
        fields = [
            "slug",
            "author_name",
            "role",
            "company_name",
            "logo_url",
            "avatar_url",
            "quote",
            "rating",
            "position",
        ]

    def get_role(self, obj):
        return obj.get_role(_lang_from_context(self.context))

    def get_quote(self, obj):
        return obj.get_quote(_lang_from_context(self.context))


# ---------------------------------------------------------------------------
# Public (write-only)
# ---------------------------------------------------------------------------

class ContactSubmissionCreateSerializer(serializers.ModelSerializer):
    """Write-only payload for the marketing-site contact form.

    Audit fields (``referrer_url``, ``user_agent``, ``status``, etc.)
    are filled in by the view, not the client.
    """

    class Meta:
        model = ContactSubmission
        fields = [
            "name",
            "email",
            "phone",
            "company",
            "subject",
            "message",
            "preferred_language",
        ]
        extra_kwargs = {
            "name": {"max_length": 120},
            "email": {"max_length": 254},
            "phone": {"required": False, "allow_blank": True, "max_length": 40},
            "company": {"required": False, "allow_blank": True, "max_length": 120},
            "subject": {"required": False},
            "preferred_language": {"required": False},
        }


class NewsletterSubscribeSerializer(serializers.Serializer):
    """Minimal payload for the newsletter signup form."""

    email = serializers.EmailField()
    locale = serializers.ChoiceField(
        choices=[("ka", "Georgian"), ("en", "English")],
        required=False,
        default="ka",
    )
    source = serializers.CharField(
        required=False, allow_blank=True, default="footer", max_length=40,
    )


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

class TestimonialAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class ContactSubmissionAdminSerializer(serializers.ModelSerializer):
    """Admin view: original submission fields are read-only (user data
    shouldn't be edited after the fact), but triage fields — status,
    handled_by, handled_at, internal_notes — are writable.
    """

    class Meta:
        model = ContactSubmission
        fields = "__all__"
        read_only_fields = (
            "name", "email", "phone", "company",
            "subject", "message", "preferred_language",
            "referrer_url", "user_agent",
            "created_at", "updated_at",
        )


class NewsletterSubscriberAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = "__all__"
        read_only_fields = (
            "unsubscribe_token",
            "created_at", "updated_at",
        )
