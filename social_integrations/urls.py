from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, admin_views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'facebook-pages', views.FacebookPageConnectionViewSet, basename='facebook-pages')
router.register(r'facebook-messages', views.FacebookMessageViewSet, basename='facebook-messages')
router.register(r'instagram-accounts', views.InstagramAccountConnectionViewSet, basename='instagram-accounts')
router.register(r'instagram-messages', views.InstagramMessageViewSet, basename='instagram-messages')
router.register(r'whatsapp-connections', views.WhatsAppBusinessConnectionViewSet, basename='whatsapp-connections')
router.register(r'whatsapp-messages', views.WhatsAppMessageViewSet, basename='whatsapp-messages')

# URL patterns for the social integrations app
urlpatterns = [
    # Include router URLs for ViewSets
    path('', include(router.urls)),
    
    # Facebook OAuth endpoints
    path('facebook/oauth/start/', views.facebook_oauth_start, name='facebook-oauth-start'),
    path('facebook/oauth/callback/', views.facebook_oauth_callback, name='facebook-oauth-callback'),
    path('facebook/oauth/debug/', views.facebook_debug_callback, name='facebook-debug-callback'),
    path('facebook/webhook/test/', views.webhook_test_endpoint, name='webhook-test'),
    path('facebook/status/', views.facebook_connection_status, name='facebook-status'),
    path('facebook/disconnect/', views.facebook_disconnect, name='facebook-disconnect'),
    path('facebook/webhook/', views.facebook_webhook, name='facebook-webhook'),
    
    # Instagram OAuth endpoints
    path('instagram/oauth/start/', views.instagram_oauth_start, name='instagram-oauth-start'),
    path('instagram/oauth/callback/', views.instagram_oauth_callback, name='instagram-oauth-callback'),
    path('instagram/status/', views.instagram_connection_status, name='instagram-status'),
    path('instagram/disconnect/', views.instagram_disconnect, name='instagram-disconnect'),
    path('instagram/webhook/', views.instagram_webhook, name='instagram-webhook'),
    
    # WhatsApp Business API endpoints
    path('whatsapp/setup/', views.whatsapp_connection_setup, name='whatsapp-setup'),
    path('whatsapp/connect/', views.whatsapp_connect_account, name='whatsapp-connect'),
    path('whatsapp/status/', views.whatsapp_connection_status, name='whatsapp-status'),
    path('whatsapp/disconnect/', views.whatsapp_disconnect, name='whatsapp-disconnect'),
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp-webhook'),
    
    # Admin OAuth endpoints
    path('admin/facebook/oauth/start/', admin_views.facebook_oauth_admin_start, name='admin_facebook_oauth_start'),
    path('admin/facebook/oauth/callback/', admin_views.facebook_oauth_admin_callback, name='admin_facebook_oauth_callback'),
]

app_name = 'social_integrations'
