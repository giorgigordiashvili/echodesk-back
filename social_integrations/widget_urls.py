from django.urls import path
from rest_framework.routers import DefaultRouter

from . import widget_views

router = DefaultRouter()
router.register(r'admin/connections', widget_views.WidgetConnectionViewSet, basename='widget_connections')
router.register(r'admin/messages', widget_views.WidgetMessageViewSet, basename='widget_messages')

urlpatterns = [
    *router.urls,
    path('public/config/', widget_views.widget_public_config, name='widget_public_config'),
    path('public/sessions/', widget_views.widget_public_sessions, name='widget_public_sessions'),
    path('public/messages/', widget_views.widget_public_messages, name='widget_public_messages'),
    path('public/messages/list/', widget_views.widget_public_messages_list, name='widget_public_messages_list'),
]
