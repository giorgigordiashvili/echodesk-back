"""
WebSocket routing for real-time updates (notifications and ticket boards)
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Notifications WebSocket for receiving notifications in real-time
    re_path(r'ws/notifications/(?P<tenant_schema>\w+)/$', consumers.NotificationConsumer.as_asgi()),

    # Ticket Board WebSocket for real-time collaboration on Kanban boards
    re_path(r'ws/boards/(?P<tenant_schema>\w+)/(?P<board_id>\w+)/$', consumers.TicketBoardConsumer.as_asgi()),
]
