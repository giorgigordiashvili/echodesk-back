from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HelpCategoryViewSet,
    HelpArticleViewSet,
    PublicHelpCategoryViewSet,
    PublicHelpArticleViewSet,
    search_help,
)

# Admin router - requires superuser authentication
admin_router = DefaultRouter()
admin_router.register(r'categories', HelpCategoryViewSet, basename='help-category')
admin_router.register(r'articles', HelpArticleViewSet, basename='help-article')

# Public router - no authentication required
public_router = DefaultRouter()
public_router.register(r'categories', PublicHelpCategoryViewSet, basename='public-help-category')
public_router.register(r'articles', PublicHelpArticleViewSet, basename='public-help-article')

urlpatterns = [
    # Admin endpoints (super admin only)
    path('admin/', include(admin_router.urls)),

    # Public endpoints (for landing page /docs and dashboard /help)
    path('public/', include(public_router.urls)),

    # Search endpoint (public)
    path('public/search/', search_help, name='help-search'),
]
