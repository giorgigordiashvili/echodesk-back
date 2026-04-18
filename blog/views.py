"""Viewsets for the blog app.

Public endpoints sit under ``/api/blog/public/`` with ``AllowAny``; admin
endpoints under ``/api/blog/admin/`` require ``IsAdminUser``. Separation
keeps the drf-spectacular schema clean: public schema surfaces only the
locale-resolved shapes, the admin surfaces raw JSONField columns.
"""

from django.utils import timezone
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from .models import BlogCategory, BlogPost, BlogPostRun, BlogTopic
from .serializers import (
    BlogCategoryAdminSerializer,
    BlogPostAdminSerializer,
    BlogPostRunAdminSerializer,
    BlogTopicAdminSerializer,
    BlogTopicSeedItemSerializer,
    PublicBlogCategorySerializer,
    PublicBlogPostDetailSerializer,
    PublicBlogPostListSerializer,
)


# ---------------------------------------------------------------------------
# Public (no auth)
# ---------------------------------------------------------------------------

class PublicBlogCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Public blog categories (``is_active=True``)."""

    permission_classes = [permissions.AllowAny]
    serializer_class = PublicBlogCategorySerializer
    lookup_field = "slug"

    def get_queryset(self):
        qs = BlogCategory.objects.filter(is_active=True)
        if self.request.query_params.get("featured") in {"true", "1"}:
            qs = qs.filter(is_featured=True)
        return qs


class PublicBlogPostViewSet(viewsets.ReadOnlyModelViewSet):
    """Public blog posts — only ``status='published'`` rows surface here.

    Filter params:
      ``?category=<slug>``, ``?post_type=<type>``, ``?featured=true``,
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
            return PublicBlogPostDetailSerializer
        return PublicBlogPostListSerializer

    def get_queryset(self):
        qs = BlogPost.objects.filter(status="published").select_related("category")

        params = self.request.query_params
        if cat := params.get("category"):
            qs = qs.filter(category__slug=cat)
        if ptype := params.get("post_type"):
            qs = qs.filter(post_type=ptype)
        if params.get("featured") in {"true", "1"}:
            qs = qs.filter(is_featured=True)
        if competitor := params.get("competitor"):
            qs = qs.filter(competitor_name__iexact=competitor)

        return qs

    @action(detail=False, methods=["get"], url_path="featured")
    def featured(self, request):
        """Convenience: top 6 featured published posts."""
        qs = self.get_queryset().filter(is_featured=True)[:6]
        serializer = PublicBlogPostListSerializer(
            qs, many=True, context={"request": request}
        )
        return Response(serializer.data)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def public_blog_search(request):
    """Simple text search over title + summary + content_html across locales.

    Query params: ``?q=<term>``, optional ``?lang=ka|en`` (doesn't filter —
    just chooses which locale's text to return in the response).
    """
    q = (request.query_params.get("q") or "").strip()
    if not q:
        return Response({"count": 0, "results": []})

    qs = BlogPost.objects.filter(status="published")
    # Case-insensitive JSONField icontains works on Postgres by casting to text.
    qs = qs.filter(
        title__icontains=q,
    ) | qs.filter(summary__icontains=q) | qs.filter(content_html__icontains=q)
    qs = qs.distinct()[:20]

    serializer = PublicBlogPostListSerializer(qs, many=True, context={"request": request})
    return Response({"count": len(serializer.data), "results": serializer.data})


# ---------------------------------------------------------------------------
# Admin (is_staff)
# ---------------------------------------------------------------------------

class BlogCategoryAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = BlogCategoryAdminSerializer
    queryset = BlogCategory.objects.all()


class BlogPostAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = BlogPostAdminSerializer
    queryset = BlogPost.objects.all().select_related("category", "source_topic")
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["slug", "title", "competitor_name"]
    ordering_fields = ["published_at", "created_at", "status"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """Flip the post to ``published`` and stamp reviewer fields.

        If the post has a linked BlogTopic, its status is also flipped to
        ``published`` so the queue reflects reality.
        """
        post = self.get_object()
        if post.status == "published":
            return Response(
                {"detail": "Already published."},
                status=status.HTTP_200_OK,
            )

        now = timezone.now()
        post.status = "published"
        post.published_at = post.published_at or now
        post.reviewed_by = request.user
        post.reviewed_at = now
        post.save()

        if post.source_topic and post.source_topic.status != "published":
            post.source_topic.status = "published"
            post.source_topic.save(update_fields=["status", "updated_at"])

        return Response(BlogPostAdminSerializer(post).data)

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        post = self.get_object()
        post.status = "archived"
        post.save(update_fields=["status", "updated_at"])
        return Response(BlogPostAdminSerializer(post).data)


class BlogTopicAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = BlogTopicAdminSerializer
    queryset = BlogTopic.objects.all().select_related("generated_post")
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["slug", "title_hint", "competitor_name", "angle_hint"]
    ordering_fields = ["priority", "created_at", "status"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["post"], url_path="seed")
    def seed(self, request):
        """Bulk-create pending topics. Skips any slug that already exists.

        Payload: ``[{"slug": "...", "post_type": "...", ...}, ...]``
        """
        payload = request.data if isinstance(request.data, list) else request.data.get("topics", [])
        created, skipped = [], []
        for item in payload:
            serializer = BlogTopicSeedItemSerializer(data=item)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            if BlogTopic.objects.filter(slug=data["slug"]).exists():
                skipped.append(data["slug"])
                continue
            topic = BlogTopic.objects.create(created_by=request.user, **data)
            created.append(topic.slug)
        return Response({"created": created, "skipped": skipped})


class BlogPostRunAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only audit log of AI-generation runs."""

    permission_classes = [permissions.IsAdminUser]
    serializer_class = BlogPostRunAdminSerializer
    queryset = BlogPostRun.objects.all().select_related("topic", "resulting_post")
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["started_at"]
