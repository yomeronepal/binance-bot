"""WebSocket JWT authentication for Django Channels.

Populates ``scope['user']`` from a SimpleJWT access token supplied as a
``token`` query-string parameter on the WebSocket handshake. Browsers cannot
attach Authorization headers to a WebSocket connection, and the SPA uses JWT
rather than Django sessions, so the token is passed via the query string.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


def _extract_token(scope):
    """Return the ``token`` query-string value, or None if absent.

    Args:
        scope: The Channels connection scope.

    Returns:
        The token string when present, otherwise None.
    """
    query_string = scope.get('query_string', b'').decode()
    tokens = parse_qs(query_string).get('token')
    return tokens[0] if tokens else None


@database_sync_to_async
def _get_user(token):
    """Resolve a validated access token to its user.

    Args:
        token: The raw JWT access token string.

    Returns:
        The matching user instance, or AnonymousUser if the token is
        invalid, expired, or references a missing user.
    """
    try:
        access = AccessToken(token)
    except TokenError:
        return AnonymousUser()

    user_id = access.get('user_id')
    if not user_id:
        return AnonymousUser()

    user_model = get_user_model()
    try:
        return user_model.objects.get(id=user_id)
    except user_model.DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Set ``scope['user']`` from a JWT access token query parameter.

    When no token is supplied the existing scope user (e.g. one set by an
    outer session-based middleware) is preserved as a fallback.
    """

    async def __call__(self, scope, receive, send):
        token = _extract_token(scope)
        if token:
            scope['user'] = await _get_user(token)
        else:
            scope.setdefault('user', AnonymousUser())
        return await super().__call__(scope, receive, send)
