from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, GroupViewSet, PermissionViewSet, DepartmentViewSet,
    TenantGroupViewSet, NotificationViewSet, tenant_homepage,
    TeamChatUserListView, TeamChatConversationViewSet, TeamChatMessageViewSet,
    upload_team_chat_file, team_chat_unread_count
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'groups', GroupViewSet)
router.register(r'tenant-groups', TenantGroupViewSet)
router.register(r'permissions', PermissionViewSet)
router.register(r'departments', DepartmentViewSet)
router.register(r'notifications', NotificationViewSet, basename='notification')

# Team Chat routes
router.register(r'team-chat/conversations', TeamChatConversationViewSet, basename='team-chat-conversation')
router.register(r'team-chat/messages', TeamChatMessageViewSet, basename='team-chat-message')

urlpatterns = [
    path('', tenant_homepage, name='tenant_homepage'),
    path('api/', include(router.urls)),

    # Team Chat endpoints
    path('api/team-chat/users/', TeamChatUserListView.as_view(), name='team-chat-users'),
    path('api/team-chat/upload/', upload_team_chat_file, name='team-chat-upload'),
    path('api/team-chat/unread-count/', team_chat_unread_count, name='team-chat-unread-count'),
]
