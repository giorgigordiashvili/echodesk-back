from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.db.models import Q
from .models import HelpCategory, HelpArticle
from .serializers import (
    HelpCategoryListSerializer,
    HelpCategoryDetailSerializer,
    HelpCategoryAdminSerializer,
    HelpArticleListSerializer,
    HelpArticleDetailSerializer,
    HelpArticleAdminSerializer,
)


# =============================================================================
# Public ViewSets (No Authentication Required)
# =============================================================================

class PublicHelpCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only ViewSet for help categories.
    Accessible without authentication.
    """
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = HelpCategory.objects.filter(is_active=True)

        # Filter by visibility
        for_public = self.request.query_params.get('for_public')
        for_dashboard = self.request.query_params.get('for_dashboard')

        if for_public == 'true':
            queryset = queryset.filter(show_on_public=True)
        elif for_dashboard == 'true':
            queryset = queryset.filter(show_in_dashboard=True)

        return queryset.order_by('position', 'created_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return HelpCategoryDetailSerializer
        return HelpCategoryListSerializer


class PublicHelpArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only ViewSet for help articles.
    Accessible without authentication.
    """
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['position', 'created_at', 'updated_at']
    ordering = ['category__position', 'position', '-created_at']

    def get_queryset(self):
        queryset = HelpArticle.objects.filter(
            is_active=True,
            category__is_active=True
        ).select_related('category')

        # Filter by visibility
        for_public = self.request.query_params.get('for_public')
        for_dashboard = self.request.query_params.get('for_dashboard')

        if for_public == 'true':
            queryset = queryset.filter(show_on_public=True, category__show_on_public=True)
        elif for_dashboard == 'true':
            queryset = queryset.filter(show_in_dashboard=True, category__show_in_dashboard=True)

        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)

        # Filter by content type
        content_type = self.request.query_params.get('content_type')
        if content_type:
            queryset = queryset.filter(content_type=content_type)

        # Filter featured only
        featured = self.request.query_params.get('featured')
        if featured == 'true':
            queryset = queryset.filter(is_featured=True)

        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return HelpArticleDetailSerializer
        return HelpArticleListSerializer

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured articles"""
        queryset = self.get_queryset().filter(is_featured=True)[:6]
        serializer = HelpArticleListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


@api_view(['GET'])
def search_help(request):
    """
    Search help articles by query.
    Public endpoint - no authentication required.
    """
    query = request.query_params.get('q', '')
    lang = request.query_params.get('lang', 'en')
    for_public = request.query_params.get('for_public', 'true')
    for_dashboard = request.query_params.get('for_dashboard', 'false')

    if len(query) < 2:
        return Response([])

    queryset = HelpArticle.objects.filter(is_active=True, category__is_active=True)

    # Apply visibility filters
    if for_public == 'true':
        queryset = queryset.filter(show_on_public=True)
    elif for_dashboard == 'true':
        queryset = queryset.filter(show_in_dashboard=True)

    # Search in title, summary, and content (JSON fields contain the search term)
    queryset = queryset.filter(
        Q(title__icontains=query) |
        Q(summary__icontains=query) |
        Q(content__icontains=query) |
        Q(faq_items__icontains=query)
    ).select_related('category')[:20]

    serializer = HelpArticleListSerializer(queryset, many=True, context={'request': request})
    return Response(serializer.data)


# =============================================================================
# Admin ViewSets (Superuser Required)
# =============================================================================

class HelpCategoryViewSet(viewsets.ModelViewSet):
    """
    Admin ViewSet for managing help categories.
    Requires superuser authentication.
    """
    queryset = HelpCategory.objects.all()
    serializer_class = HelpCategoryAdminSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'slug', 'description']
    ordering_fields = ['position', 'created_at', 'updated_at']
    ordering = ['position', 'created_at']
    lookup_field = 'slug'


class HelpArticleViewSet(viewsets.ModelViewSet):
    """
    Admin ViewSet for managing help articles.
    Requires superuser authentication.
    """
    queryset = HelpArticle.objects.all().select_related('category')
    serializer_class = HelpArticleAdminSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'slug', 'summary', 'content']
    ordering_fields = ['position', 'created_at', 'updated_at']
    ordering = ['category__position', 'position', '-created_at']
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)

        # Filter by content type
        content_type = self.request.query_params.get('content_type')
        if content_type:
            queryset = queryset.filter(content_type=content_type)

        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
