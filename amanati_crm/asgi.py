"""
ASGI config for amanati_crm project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
from django.urls import path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Import consumers AFTER Django initialization to avoid AppRegistry errors
from social_integrations import consumers

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter([
            path('ws/messages/<str:tenant_schema>/', consumers.MessagesConsumer.as_asgi()),
            path('ws/typing/<str:tenant_schema>/<str:conversation_id>/', consumers.TypingConsumer.as_asgi()),
        ])
    ),
})
