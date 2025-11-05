"""
WebSocket JWT Authentication Middleware for Django Channels
"""
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from urllib.parse import parse_qs
from users.models import User


@database_sync_to_async
def get_user_from_token(token_string):
    """
    Get user from JWT access token
    """
    try:
        # Validate token
        token = AccessToken(token_string)
        user_id = token.payload.get('user_id')

        if user_id:
            user = User.objects.get(id=user_id)
            return user
    except (TokenError, User.DoesNotExist, Exception) as e:
        print(f"WebSocket auth error: {e}")
        pass

    return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using JWT tokens

    Token can be passed via:
    1. Query parameter: ?token=<jwt_token>
    2. Cookie: jwt_token=<jwt_token>
    """

    async def __call__(self, scope, receive, send):
        # Get token from query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        # If no token in query, try cookies
        if not token:
            headers = dict(scope.get('headers', []))
            cookie_header = headers.get(b'cookie', b'').decode()

            # Parse cookies
            for cookie in cookie_header.split(';'):
                cookie = cookie.strip()
                if cookie.startswith('jwt_token='):
                    token = cookie.split('=', 1)[1]
                    break

        # Authenticate user with token
        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """
    Convenience function to wrap URLRouter with JWT auth middleware
    """
    return JWTAuthMiddleware(inner)
