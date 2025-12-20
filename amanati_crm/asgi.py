"""
ASGI config for amanati_crm project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Import consumers and custom auth middleware AFTER Django initialization
from social_integrations import consumers
from users import consumers as users_consumers
from amanati_crm.websocket_auth import JWTAuthMiddlewareStack

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter([
        path('ws/messages/<str:tenant_schema>/', JWTAuthMiddlewareStack(consumers.MessagesConsumer.as_asgi())),
        path('ws/typing/<str:tenant_schema>/<str:conversation_id>/', JWTAuthMiddlewareStack(consumers.TypingConsumer.as_asgi())),
        path('ws/notifications/<str:tenant_schema>/', JWTAuthMiddlewareStack(users_consumers.NotificationConsumer.as_asgi())),
        path('ws/boards/<str:tenant_schema>/<str:board_id>/', JWTAuthMiddlewareStack(users_consumers.TicketBoardConsumer.as_asgi())),
        path('ws/team-chat/<str:tenant_schema>/', JWTAuthMiddlewareStack(users_consumers.TeamChatConsumer.as_asgi())),
    ]),
})
