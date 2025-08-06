"""
WebSocket routing for social integrations real-time messaging
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Messages WebSocket for receiving new messages in real-time
    re_path(r'ws/messages/(?P<tenant_schema>\w+)/$', consumers.MessagesConsumer.as_asgi()),
    
    # Typing indicators WebSocket for specific conversations
    re_path(r'ws/typing/(?P<tenant_schema>\w+)/(?P<conversation_id>\w+)/$', consumers.TypingConsumer.as_asgi()),
]
