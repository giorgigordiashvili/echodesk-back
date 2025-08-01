from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'facebook-pages', views.FacebookPageConnectionViewSet, basename='facebook-pages')
router.register(r'facebook-messages', views.FacebookMessageViewSet, basename='facebook-messages')

# URL patterns for the social integrations app
urlpatterns = [
    # Include router URLs for ViewSets
    path('', include(router.urls)),
    
    # Facebook OAuth endpoints
    path('facebook/oauth/start/', views.facebook_oauth_start, name='facebook-oauth-start'),
    path('facebook/oauth/callback/', views.facebook_oauth_callback, name='facebook-oauth-callback'),
    path('facebook/status/', views.facebook_connection_status, name='facebook-status'),
    path('facebook/disconnect/', views.facebook_disconnect, name='facebook-disconnect'),
    path('facebook/webhook/', views.facebook_webhook, name='facebook-webhook'),
]

app_name = 'social_integrations'
