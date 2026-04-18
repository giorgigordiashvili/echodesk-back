from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BlogCategoryAdminViewSet,
    BlogPostAdminViewSet,
    BlogPostRunAdminViewSet,
    BlogTopicAdminViewSet,
    PublicBlogCategoryViewSet,
    PublicBlogPostViewSet,
    public_blog_search,
)

# Public router — no auth, what the marketing site hits.
public_router = DefaultRouter()
public_router.register(r"posts", PublicBlogPostViewSet, basename="public-blog-post")
public_router.register(r"categories", PublicBlogCategoryViewSet, basename="public-blog-category")

# Admin router — IsAdminUser gated.
admin_router = DefaultRouter()
admin_router.register(r"posts", BlogPostAdminViewSet, basename="admin-blog-post")
admin_router.register(r"categories", BlogCategoryAdminViewSet, basename="admin-blog-category")
admin_router.register(r"topics", BlogTopicAdminViewSet, basename="admin-blog-topic")
admin_router.register(r"runs", BlogPostRunAdminViewSet, basename="admin-blog-run")


urlpatterns = [
    path("public/", include(public_router.urls)),
    path("public/search/", public_blog_search, name="public-blog-search"),
    path("admin/", include(admin_router.urls)),
]
