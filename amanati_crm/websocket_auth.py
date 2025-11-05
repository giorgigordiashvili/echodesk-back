"""
WebSocket Authentication Middleware for Django Channels
Supports both JWT and Django Token authentication
"""
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from urllib.parse import parse_qs
from users.models import User
from tenant_schemas.utils import schema_context

# Try to import JWT support
try:
    from rest_framework_simplejwt.tokens import AccessToken
    from rest_framework_simplejwt.exceptions import TokenError
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

# Try to import Django Token authentication
try:
    from rest_framework.authtoken.models import Token as DjangoToken
    DJANGO_TOKEN_AVAILABLE = True
except ImportError:
    DJANGO_TOKEN_AVAILABLE = False


@database_sync_to_async
def get_user_from_token(token_string, tenant_schema=None):
    """
    Get user from token - supports both JWT and Django Token authentication
    Queries within the tenant schema context for multi-tenant support
    """
    print(f"[WebSocket Auth] Authenticating token for tenant: {tenant_schema}")

    # If no tenant schema provided, cannot authenticate
    if not tenant_schema:
        print(f"[WebSocket Auth] No tenant schema provided")
        return AnonymousUser()

    # Query within tenant schema context
    with schema_context(tenant_schema):
        # Try JWT first if available
        if JWT_AVAILABLE:
            try:
                token = AccessToken(token_string)
                user_id = token.payload.get('user_id')
                if user_id:
                    user = User.objects.get(id=user_id)
                    print(f"[WebSocket Auth] JWT authentication successful for user: {user.email}")
                    return user
            except (TokenError, User.DoesNotExist, Exception) as e:
                print(f"[WebSocket Auth] JWT validation failed: {e}")

        # Try Django Token authentication if available
        if DJANGO_TOKEN_AVAILABLE:
            try:
                token_obj = DjangoToken.objects.select_related('user').get(key=token_string)
                user = token_obj.user
                print(f"[WebSocket Auth] Django Token authentication successful for user: {user.email}")
                return user
            except (DjangoToken.DoesNotExist, Exception) as e:
                print(f"[WebSocket Auth] Django Token validation failed: {e}")

        print(f"[WebSocket Auth] No valid authentication found for token")
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using JWT or Django Token authentication

    Token can be passed via:
    1. Query parameter: ?token=<token>
    2. Cookie: jwt_token=<token>

    Supports both:
    - JWT tokens (rest_framework_simplejwt)
    - Django Token authentication (rest_framework.authtoken)
    """

    async def __call__(self, scope, receive, send):
        # Get tenant schema from URL route kwargs
        tenant_schema = scope.get('url_route', {}).get('kwargs', {}).get('tenant_schema')

        # Fallback: Extract from path if url_route not available
        if not tenant_schema:
            path = scope.get('path', '')
            # Path format: /ws/messages/groot/ or /ws/typing/groot/conversation_id/
            path_parts = [p for p in path.split('/') if p]
            if len(path_parts) >= 2 and path_parts[0] in ['ws']:
                # path_parts[1] is 'messages' or 'typing', path_parts[2] is tenant_schema
                if len(path_parts) >= 3:
                    tenant_schema = path_parts[2]
                    print(f"[WebSocket Auth] Extracted tenant_schema from path: {tenant_schema}")

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

        # Authenticate user with token within tenant context
        if token and tenant_schema:
            scope['user'] = await get_user_from_token(token, tenant_schema)
        else:
            scope['user'] = AnonymousUser()
            if not tenant_schema:
                print(f"[WebSocket Auth] Warning: No tenant schema found. Path: {scope.get('path')}, URL route: {scope.get('url_route')}")

        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """
    Convenience function to wrap URLRouter with authentication middleware
    Supports both JWT and Django Token authentication
    """
    return JWTAuthMiddleware(inner)
