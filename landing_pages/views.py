"""Viewsets for the landing_pages app.

Public endpoints sit under ``/api/landing/public/`` with ``AllowAny``;
admin endpoints under ``/api/landing/admin/`` require ``IsAdminUser``.
Separation keeps the drf-spectacular schema clean: public schema
surfaces only the locale-resolved shapes, the admin surfaces raw
JSONField columns.
"""

from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import LandingPage, LandingPageRun, LandingTopic
from .serializers import (
    LandingPageAdminSerializer,
    LandingPageRunAdminSerializer,
    LandingTopicAdminSerializer,
    LandingTopicSeedItemSerializer,
    PublicLandingPageDetailSerializer,
    PublicLandingPageListSerializer,
)


# ---------------------------------------------------------------------------
# Public (no auth)
# ---------------------------------------------------------------------------

LANG_PARAM = OpenApiParameter(
    name="lang",
    description='Locale for text fields — "ka" or "en" (defaults to "en").',
    required=False,
    type=str,
    enum=["en", "ka"],
)

PAGE_TYPE_PARAM = OpenApiParameter(
    name="page_type",
    description='Filter by page type: "feature", "vertical", or "comparison".',
    required=False,
    type=str,
    enum=["feature", "vertical", "comparison"],
)


@extend_schema_view(
    list=extend_schema(
        summary="List published landing pages",
        description=(
            "Returns landing pages with ``status='published'``, newest first. "
            "Supports optional filters for page_type and competitor."
        ),
        parameters=[LANG_PARAM, PAGE_TYPE_PARAM],
    ),
    retrieve=extend_schema(
        summary="Retrieve a landing page by slug",
        description="Returns the full landing page including content blocks and FAQ.",
        parameters=[LANG_PARAM],
    ),
)
class PublicLandingPageViewSet(viewsets.ReadOnlyModelViewSet):
    """Public landing pages — only ``status='published'`` rows surface here.

    Filter params:
      ``?page_type=feature|vertical|comparison``,
      ``?competitor=<name>``, ``?lang=ka|en`` (locale negotiation).
    Ordering: newest published first (``-published_at``).
    """

    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["published_at", "created_at"]
    ordering = ["-published_at", "-created_at"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PublicLandingPageDetailSerializer
        return PublicLandingPageListSerializer

    def get_queryset(self):
        qs = LandingPage.objects.filter(status="published")

        params = self.request.query_params
        if ptype := params.get("page_type"):
            qs = qs.filter(page_type=ptype)
        if competitor := params.get("competitor"):
            qs = qs.filter(competitor_name__iexact=competitor)

        return qs


# ---------------------------------------------------------------------------
# Admin (is_staff)
# ---------------------------------------------------------------------------

class LandingPageAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = LandingPageAdminSerializer
    queryset = LandingPage.objects.all().select_related("source_topic")
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["slug", "title", "competitor_name"]
    ordering_fields = ["published_at", "created_at", "status"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @extend_schema(
        summary="Approve and publish a landing page",
        description=(
            "Flips the page to ``published``, stamps reviewer fields, and "
            "marks the source topic as ``published`` if one is linked."
        ),
        responses={200: LandingPageAdminSerializer},
    )
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """Flip the page to ``published`` and stamp reviewer fields.

        If the page has a linked LandingTopic, its status is also flipped
        to ``published`` so the queue reflects reality.
        """
        page = self.get_object()
        if page.status == "published":
            return Response(
                {"detail": "Already published."},
                status=status.HTTP_200_OK,
            )

        now = timezone.now()
        page.status = "published"
        page.published_at = page.published_at or now
        page.reviewed_by = request.user
        page.reviewed_at = now
        page.save()

        if page.source_topic and page.source_topic.status != "published":
            page.source_topic.status = "published"
            page.source_topic.save(update_fields=["status", "updated_at"])

        return Response(LandingPageAdminSerializer(page).data)

    @extend_schema(
        summary="Archive a landing page",
        responses={200: LandingPageAdminSerializer},
    )
    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        page = self.get_object()
        page.status = "archived"
        page.save(update_fields=["status", "updated_at"])
        return Response(LandingPageAdminSerializer(page).data)


class LandingTopicAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = LandingTopicAdminSerializer
    queryset = LandingTopic.objects.all().select_related("generated_page")
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["slug", "title_hint", "competitor_name", "angle_hint"]
    ordering_fields = ["priority", "created_at", "status"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(
        summary="Bulk-seed landing topics",
        description=(
            "Accepts a list (or ``{topics: [...]}``) of seed items and "
            "creates topics for any slug that doesn't already exist."
        ),
        request=LandingTopicSeedItemSerializer(many=True),
        responses={200: OpenApiResponse(
            description="Created + skipped slug lists.",
        )},
    )
    @action(detail=False, methods=["post"], url_path="seed")
    def seed(self, request):
        """Bulk-create pending topics. Skips any slug that already exists.

        Payload: ``[{"slug": "...", "page_type": "...", ...}, ...]``
        """
        payload = request.data if isinstance(request.data, list) else request.data.get("topics", [])
        created, skipped = [], []
        for item in payload:
            serializer = LandingTopicSeedItemSerializer(data=item)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            if LandingTopic.objects.filter(slug=data["slug"]).exists():
                skipped.append(data["slug"])
                continue
            topic = LandingTopic.objects.create(created_by=request.user, **data)
            created.append(topic.slug)
        return Response({"created": created, "skipped": skipped})


class LandingPageRunAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only audit log of AI-generation runs."""

    permission_classes = [permissions.IsAdminUser]
    serializer_class = LandingPageRunAdminSerializer
    queryset = LandingPageRun.objects.all().select_related("topic", "resulting_page")
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["started_at"]
