"""Viewsets + function views for the marketing app.

Public endpoints sit under ``/api/marketing/public/`` with
``AllowAny``; admin endpoints under ``/api/marketing/admin/`` require
``IsAdminUser``. Public form-submission endpoints (contact + newsletter)
are rate-limited per IP to blunt spam.
"""

import csv

from django.http import StreamingHttpResponse
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import filters, mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from .models import ContactSubmission, NewsletterSubscriber, Testimonial
from .serializers import (
    ContactSubmissionAdminSerializer,
    ContactSubmissionCreateSerializer,
    NewsletterSubscribeSerializer,
    NewsletterSubscriberAdminSerializer,
    TestimonialAdminSerializer,
    TestimonialSerializer,
)
from .services.notifications import notify_sales_team, send_subscriber_welcome


LANG_PARAM = OpenApiParameter(
    name="lang",
    description='Locale for text fields — "ka" or "en" (defaults to "ka").',
    required=False,
    type=str,
    enum=["en", "ka"],
)


# ---------------------------------------------------------------------------
# Public — testimonials
# ---------------------------------------------------------------------------

@extend_schema_view(
    list=extend_schema(
        summary="List active testimonials",
        description=(
            "Returns testimonials with ``is_active=True``, sorted by "
            "``position``. Locale-aware fields (``role``, ``quote``) "
            "are resolved via ``?lang=ka|en``."
        ),
        parameters=[LANG_PARAM],
    ),
    retrieve=extend_schema(
        summary="Retrieve a testimonial by slug",
        parameters=[LANG_PARAM],
    ),
)
class PublicTestimonialViewSet(viewsets.ReadOnlyModelViewSet):
    """Public testimonials — only ``is_active=True`` rows surface here."""

    permission_classes = [permissions.AllowAny]
    serializer_class = TestimonialSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return Testimonial.objects.filter(is_active=True).order_by(
            "position", "-created_at"
        )


# ---------------------------------------------------------------------------
# Public — contact form
# ---------------------------------------------------------------------------

@extend_schema(
    summary="Submit the marketing-site contact form",
    description=(
        "Creates a ContactSubmission, captures referrer + user-agent "
        "server-side, and emails the sales inbox. Rate-limited to "
        "5 submissions per hour per IP."
    ),
    request=ContactSubmissionCreateSerializer,
    responses={
        201: OpenApiResponse(
            response=inline_serializer(
                name="ContactSubmitResponse",
                fields={
                    "status": serializers.CharField(),
                    "id": serializers.IntegerField(),
                },
            ),
            description="Submission stored; sales team notified.",
        ),
        429: OpenApiResponse(description="Rate limit exceeded (5/hour per IP)."),
    },
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@ratelimit(key="ip", rate="5/h", block=True)
def contact_submit(request):
    """Store a new contact submission + notify sales."""
    serializer = ContactSubmissionCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    submission = serializer.save(
        referrer_url=request.META.get("HTTP_REFERER", "")[:500],
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
    )
    notify_sales_team(submission)
    return Response(
        {"status": "received", "id": submission.id},
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# Public — newsletter subscribe
# ---------------------------------------------------------------------------

@extend_schema(
    summary="Subscribe an email to the EchoDesk newsletter",
    description=(
        "Idempotent: resubscribing an existing inactive email "
        "reactivates the row rather than creating a duplicate. "
        "Rate-limited to 10/hour per IP."
    ),
    request=NewsletterSubscribeSerializer,
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="NewsletterSubscribeResponse",
                fields={"status": serializers.CharField()},
            ),
            description="Subscribed (or already subscribed).",
        ),
        429: OpenApiResponse(description="Rate limit exceeded (10/hour per IP)."),
    },
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@ratelimit(key="ip", rate="10/h", block=True)
def newsletter_subscribe(request):
    """Create-or-reactivate a newsletter subscriber."""
    serializer = NewsletterSubscribeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    sub, created = NewsletterSubscriber.objects.get_or_create(
        email=data["email"],
        defaults={
            "locale": data.get("locale", "ka"),
            "source": data.get("source") or "footer",
        },
    )
    send_welcome = created
    if not created and not sub.is_active:
        sub.is_active = True
        sub.unsubscribed_at = None
        # Let an explicit locale/source on re-subscribe overwrite the old ones.
        sub.locale = data.get("locale", sub.locale)
        if data.get("source"):
            sub.source = data["source"]
        sub.save(update_fields=["is_active", "unsubscribed_at", "locale", "source", "updated_at"])
        send_welcome = True

    if send_welcome:
        send_subscriber_welcome(sub)

    return Response({"status": "subscribed"}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Public — newsletter unsubscribe (link from the welcome email)
# ---------------------------------------------------------------------------

@extend_schema(
    summary="One-click unsubscribe via email token",
    description=(
        "Called from the unsubscribe link in the welcome email. Looks "
        "up the subscriber by ``unsubscribe_token`` and flips "
        "``is_active=False``. Safe to hit repeatedly (idempotent)."
    ),
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="NewsletterUnsubscribeResponse",
                fields={
                    "status": serializers.CharField(),
                    "email": serializers.EmailField(),
                },
            ),
        ),
        404: OpenApiResponse(description="Token not recognized."),
    },
)
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def newsletter_unsubscribe(request, token):
    """Token-based, non-authenticated unsubscribe endpoint."""
    try:
        sub = NewsletterSubscriber.objects.get(unsubscribe_token=token)
    except NewsletterSubscriber.DoesNotExist:
        return Response(
            {"detail": "Unknown token."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if sub.is_active:
        sub.is_active = False
        sub.unsubscribed_at = timezone.now()
        sub.save(update_fields=["is_active", "unsubscribed_at", "updated_at"])

    return Response({"status": "unsubscribed", "email": sub.email})


# ---------------------------------------------------------------------------
# Admin — testimonials (full CRUD)
# ---------------------------------------------------------------------------

class TestimonialAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = TestimonialAdminSerializer
    queryset = Testimonial.objects.all()
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["slug", "author_name", "company_name", "quote_ka", "quote_en"]
    ordering_fields = ["position", "created_at", "rating"]


# ---------------------------------------------------------------------------
# Admin — contact submissions (list + retrieve + triage updates)
# ---------------------------------------------------------------------------

class ContactSubmissionAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Read + partial-update contact submissions.

    Submission data (name, email, message, etc.) is locked read-only
    via the serializer — only triage fields (status, handled_by,
    internal_notes) accept PATCH writes.
    """

    permission_classes = [permissions.IsAdminUser]
    serializer_class = ContactSubmissionAdminSerializer
    queryset = ContactSubmission.objects.all().select_related("handled_by")
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["name", "email", "company", "message"]
    ordering_fields = ["created_at", "status"]

    def perform_update(self, serializer):
        # Auto-stamp handled_at/handled_by the first time a submission
        # leaves the 'new' state, so admins don't have to remember.
        instance = serializer.instance
        updated = serializer.save()
        if (
            instance.status == "new"
            and updated.status != "new"
            and updated.handled_at is None
        ):
            updated.handled_at = timezone.now()
            updated.handled_by = updated.handled_by or self.request.user
            updated.save(update_fields=["handled_at", "handled_by", "updated_at"])


# ---------------------------------------------------------------------------
# Admin — newsletter subscribers (list + retrieve + CSV export)
# ---------------------------------------------------------------------------

class _EchoBuffer:
    """Minimal file-like object that StreamingHttpResponse can write to."""

    def write(self, value):  # noqa: D401
        return value


class NewsletterSubscriberAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = NewsletterSubscriberAdminSerializer
    queryset = NewsletterSubscriber.objects.all()
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["email", "source"]
    ordering_fields = ["created_at", "is_active"]

    @extend_schema(
        summary="Export subscribers as CSV",
        description=(
            "Streams a CSV of ``email,locale,source,is_active,"
            "created_at`` for every subscriber in the current queryset. "
            "Applies the same ``?is_active=``/``?locale=`` filters as the "
            "list endpoint."
        ),
        responses={200: OpenApiResponse(description="text/csv stream")},
    )
    @action(detail=False, methods=["get"], url_path="export")
    def export_csv(self, request):
        """Stream a CSV of the current filtered queryset."""
        qs = self.filter_queryset(self.get_queryset())

        params = request.query_params
        if (is_active := params.get("is_active")) in {"true", "1", "false", "0"}:
            qs = qs.filter(is_active=is_active in {"true", "1"})
        if locale := params.get("locale"):
            qs = qs.filter(locale=locale)
        if source := params.get("source"):
            qs = qs.filter(source=source)

        writer = csv.writer(_EchoBuffer())
        header = ["email", "locale", "source", "is_active", "created_at"]

        def rows():
            yield writer.writerow(header)
            for sub in qs.iterator(chunk_size=500):
                yield writer.writerow([
                    sub.email,
                    sub.locale,
                    sub.source,
                    "1" if sub.is_active else "0",
                    sub.created_at.isoformat(),
                ])

        response = StreamingHttpResponse(rows(), content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="newsletter-subscribers.csv"'
        )
        return response
