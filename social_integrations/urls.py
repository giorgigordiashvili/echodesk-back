from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, admin_views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'facebook-pages', views.FacebookPageConnectionViewSet, basename='facebook_pages')
router.register(r'facebook-messages', views.FacebookMessageViewSet, basename='facebook_messages')
router.register(r'instagram-accounts', views.InstagramAccountConnectionViewSet, basename='instagram_accounts')
router.register(r'instagram-messages', views.InstagramMessageViewSet, basename='instagram_messages')
router.register(r'whatsapp-accounts', views.WhatsAppBusinessAccountViewSet, basename='whatsapp_accounts')
router.register(r'whatsapp-messages', views.WhatsAppMessageViewSet, basename='whatsapp_messages')
router.register(r'whatsapp-contacts', views.WhatsAppContactViewSet, basename='whatsapp_contacts')
router.register(r'email-messages', views.EmailMessageViewSet, basename='email_messages')
router.register(r'email-drafts', views.EmailDraftViewSet, basename='email_drafts')
router.register(r'tiktok-messages', views.TikTokMessageViewSet, basename='tiktok_messages')
router.register(r'quick-replies', views.QuickReplyViewSet, basename='quick_replies')
router.register(r'clients', views.SocialClientViewSet, basename='social_clients')
router.register(r'clients/custom-fields', views.SocialClientCustomFieldViewSet, basename='social_client_custom_fields')

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
    path('facebook/pages/<str:page_id>/disconnect/', views.facebook_page_disconnect, name='facebook_page_disconnect'),
    path('facebook/send-message/', views.facebook_send_message, name='facebook_send_message'),
    path('facebook/webhook/', views.facebook_webhook, name='facebook_webhook'),

    # Instagram endpoints
    path('instagram/status/', views.instagram_connection_status, name='instagram_status'),
    path('instagram/disconnect/', views.instagram_disconnect, name='instagram_disconnect'),
    path('instagram/send-message/', views.instagram_send_message, name='instagram_send_message'),
    path('instagram/webhook/', views.instagram_webhook, name='instagram_webhook'),

    # WhatsApp endpoints
    path('whatsapp/oauth/start/', views.whatsapp_oauth_start, name='whatsapp_oauth_start'),
    path('whatsapp/embedded-signup/callback/', views.whatsapp_embedded_signup_callback, name='whatsapp_embedded_signup_callback'),
    path('whatsapp/status/', views.whatsapp_connection_status, name='whatsapp_status'),
    path('whatsapp/disconnect/', views.whatsapp_disconnect, name='whatsapp_disconnect'),
    path('whatsapp/send-message/', views.whatsapp_send_message, name='whatsapp_send_message'),
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),

    # WhatsApp Template Management
    path('whatsapp/<str:waba_id>/templates/', views.whatsapp_list_templates, name='whatsapp_list_templates'),
    path('whatsapp/<str:waba_id>/templates/sync/', views.whatsapp_sync_templates, name='whatsapp_sync_templates'),
    path('whatsapp/templates/create/', views.whatsapp_create_template, name='whatsapp_create_template'),
    path('whatsapp/templates/<int:template_id>/delete/', views.whatsapp_delete_template, name='whatsapp_delete_template'),
    path('whatsapp/templates/send/', views.whatsapp_send_template_message, name='whatsapp_send_template_message'),

    # Email endpoints
    path('email/status/', views.email_connection_status, name='email_status'),
    path('email/connect/', views.email_connect, name='email_connect'),
    path('email/disconnect/', views.email_disconnect, name='email_disconnect'),
    path('email/update/', views.email_update_connection, name='email_update_connection'),
    path('email/send/', views.email_send, name='email_send'),
    path('email/action/', views.email_action, name='email_action'),
    path('email/folders/', views.email_folders, name='email_folders'),
    path('email/sync/', views.email_sync, name='email_sync'),
    path('email/sync/debug/', views.email_sync_debug, name='email_sync_debug'),
    path('email/sync/settings/', views.email_update_sync_days, name='email_update_sync_days'),
    path('email/signature/', views.email_signature_view, name='email_signature'),

    # TikTok endpoints
    path('tiktok/oauth/start/', views.tiktok_oauth_start, name='tiktok_oauth_start'),
    path('tiktok/oauth/callback/', views.tiktok_oauth_callback, name='tiktok_oauth_callback'),
    path('tiktok/webhook/', views.tiktok_webhook, name='tiktok_webhook'),
    path('tiktok/status/', views.tiktok_status, name='tiktok_status'),
    path('tiktok/disconnect/', views.tiktok_disconnect, name='tiktok_disconnect'),
    path('tiktok/send-message/', views.tiktok_send_message, name='tiktok_send_message'),

    # Webhook debugging endpoints
    path('webhook-status/', views.webhook_status, name='webhook_status'),
    path('webhook-logs/', views.webhook_debug_logs, name='webhook_debug_logs'),
    path('webhook-test/', views.webhook_test_receiver, name='webhook_test'),

    # Settings endpoint
    path('settings/', views.social_settings, name='social_settings'),

    # Chat Assignment endpoints
    path('assignments/', views.my_assignments, name='my_assignments'),
    path('assignments/all/', views.all_assignments, name='all_assignments'),
    path('assignments/assign/', views.assign_chat, name='assign_chat'),
    path('assignments/unassign/', views.unassign_chat, name='unassign_chat'),
    path('assignments/status/', views.get_assignment_status, name='assignment_status'),
    path('assignments/start-session/', views.start_session, name='start_session'),
    path('assignments/end-session/', views.end_session, name='end_session'),

    # Rating statistics endpoint (superadmin only)
    path('rating-statistics/', views.rating_statistics, name='rating_statistics'),
    path('rating-statistics/user/<int:user_id>/', views.user_chat_sessions, name='user_chat_sessions'),

    # Unread messages count endpoint
    path('unread-count/', views.unread_messages_count, name='unread_messages_count'),

    # Mark conversation as read endpoint
    path('mark-read/', views.mark_conversation_read, name='mark_conversation_read'),

    # Delete conversation endpoint (superadmin only)
    path('delete-conversation/', views.delete_conversation, name='delete_conversation'),

    # Social Sync endpoints (Facebook & Instagram message history sync)
    path('sync/status/', views.social_sync_status, name='social_sync_status'),
    path('sync/status/<str:platform>/', views.social_sync_status, name='social_sync_status_platform'),
    path('sync/trigger/', views.social_sync_trigger, name='social_sync_trigger'),
    path('sync/settings/', views.social_sync_settings, name='social_sync_settings'),

    # Admin OAuth endpoints
    path('admin/facebook/oauth/start/', admin_views.facebook_oauth_admin_start, name='admin_facebook_oauth_start'),
    path('admin/facebook/oauth/callback/', admin_views.facebook_oauth_admin_callback, name='admin_facebook_oauth_callback'),
]

app_name = 'social_integrations'
