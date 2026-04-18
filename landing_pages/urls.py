from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    LandingPageAdminViewSet,
    LandingPageRunAdminViewSet,
    LandingTopicAdminViewSet,
    PublicLandingPageViewSet,
)

# Public router — no auth, what the marketing site hits.
public_router = DefaultRouter()
public_router.register(r"pages", PublicLandingPageViewSet, basename="public-landing-page")

# Admin router — IsAdminUser gated.
admin_router = DefaultRouter()
admin_router.register(r"pages", LandingPageAdminViewSet, basename="admin-landing-page")
admin_router.register(r"topics", LandingTopicAdminViewSet, basename="admin-landing-topic")
admin_router.register(r"runs", LandingPageRunAdminViewSet, basename="admin-landing-run")


urlpatterns = [
    path("public/", include(public_router.urls)),
    path("admin/", include(admin_router.urls)),
]
