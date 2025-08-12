from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, admin_views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'facebook-pages', views.FacebookPageConnectionViewSet, basename='facebook_pages')
router.register(r'facebook-messages', views.FacebookMessageViewSet, basename='facebook_messages')
router.register(r'instagram-accounts', views.InstagramAccountConnectionViewSet, basename='instagram_accounts')
router.register(r'instagram-messages', views.InstagramMessageViewSet, basename='instagram_messages')
router.register(r'whatsapp-connections', views.WhatsAppBusinessConnectionViewSet, basename='whatsapp_connections')
router.register(r'whatsapp-messages', views.WhatsAppMessageViewSet, basename='whatsapp_messages')

# URL patterns for the social integrations app
urlpatterns = [
    # Include router URLs for ViewSets
    path('', include(router.urls)),
    
    # Facebook OAuth endpoints
    path('facebook/oauth/start/', views.facebook_oauth_start, name='facebook_oauth_start'),
    path('facebook/oauth/callback/', views.facebook_oauth_callback, name='facebook_oauth_callback'),
    path('facebook/oauth/debug/', views.facebook_debug_callback, name='facebook_debug_callback'),
    path('facebook/api/test/', views.test_facebook_api_access, name='facebook_api_test'),
    path('facebook/webhook/test/', views.webhook_test_endpoint, name='webhook_test'),
    path('facebook/database/test/', views.test_database_save, name='database_test'),
    path('facebook/database/debug/', views.debug_database_status, name='database_debug'),
    path('facebook/pages/debug/', views.debug_facebook_pages, name='facebook_pages_debug'),
    path('facebook/status/', views.facebook_connection_status, name='facebook_status'),
    path('facebook/disconnect/', views.facebook_disconnect, name='facebook_disconnect'),
    path('facebook/send-message/', views.facebook_send_message, name='facebook_send_message'),
    path('facebook/webhook/', views.facebook_webhook, name='facebook_webhook'),
    
    # Instagram OAuth endpoints
    path('instagram/oauth/start/', views.instagram_oauth_start, name='instagram_oauth_start'),
    path('instagram/oauth/callback/', views.instagram_oauth_callback, name='instagram_oauth_callback'),
    path('instagram/status/', views.instagram_connection_status, name='instagram_status'),
    path('instagram/disconnect/', views.instagram_disconnect, name='instagram_disconnect'),
    path('instagram/send-message/', views.instagram_send_message, name='instagram_send_message'),
    path('instagram/conversations/', views.instagram_conversations, name='instagram_conversations'),
    path('instagram/conversations/<str:conversation_id>/messages/', views.instagram_conversation_messages, name='instagram_conversation_messages'),
    path('instagram/webhook/', views.instagram_webhook, name='instagram_webhook'),
    
    # WhatsApp Business API endpoints
    path('whatsapp/setup/', views.whatsapp_connection_setup, name='whatsapp_setup'),
    path('whatsapp/connect/', views.whatsapp_connect_account, name='whatsapp_connect'),
    path('whatsapp/status/', views.whatsapp_connection_status, name='whatsapp_status'),
    path('whatsapp/disconnect/', views.whatsapp_disconnect, name='whatsapp_disconnect'),
    path('whatsapp/send-message/', views.whatsapp_send_message, name='whatsapp_send_message'),
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
    
    # Admin OAuth endpoints
    path('admin/facebook/oauth/start/', admin_views.facebook_oauth_admin_start, name='admin_facebook_oauth_start'),
    path('admin/facebook/oauth/callback/', admin_views.facebook_oauth_admin_callback, name='admin_facebook_oauth_callback'),
]

app_name = 'social_integrations'
