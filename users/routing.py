"""
WebSocket routing for user notifications real-time updates
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Notifications WebSocket for receiving notifications in real-time
    re_path(r'ws/notifications/(?P<tenant_schema>\w+)/$', consumers.NotificationConsumer.as_asgi()),
]
