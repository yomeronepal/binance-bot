"""
Per-user Binance API key connection endpoints.

Slice 1 scope: read-only validation against ``GET /fapi/v2/account``.
No trading is executed through these endpoints. Status transitions are
PAUSED on first connect / on health-check recovery, BROKEN on validation
failure, REVOKED on detected bad/invalid key.
"""
import logging

from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .models_user_connection import UserBinanceConnection
from .serializers_user_connection import (
    UserBinanceConnectInputSerializer,
    UserBinanceConnectionStateSerializer,
)
from .services.credential_crypto import encrypt, hint
from .services.user_connection_validator import validate_connection

logger = logging.getLogger(__name__)


class ConnectThrottle(UserRateThrottle):
    rate = '5/hour'


class RevalidateThrottle(UserRateThrottle):
    rate = '10/hour'


@api_view(['GET'])
@permission_classes([AllowAny])
def server_ip(request):
    """Return the IP a user must allowlist on their Binance API key."""
    return Response({'ip': settings.BINANCE_SERVER_IP})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_connection(request):
    """Return the current user's connection state, or 404 if none."""
    try:
        conn = request.user.binance_connection
    except UserBinanceConnection.DoesNotExist:
        return Response({'detail': 'No Binance connection.'},
                        status=status.HTTP_404_NOT_FOUND)
    return Response(UserBinanceConnectionStateSerializer(conn).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ConnectThrottle])
def connect(request):
    """
    Create or replace the current user's Binance connection.

    Validates the supplied credentials *before* persisting them. If
    validation fails the row is still saved so the UI can show a
    diagnostic ("ip_blocked", "invalid_key", etc.) and the user can
    retry from a pre-filled form. We never log the raw key/secret.
    """
    payload = UserBinanceConnectInputSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    api_key = payload.validated_data['api_key']
    api_secret = payload.validated_data['api_secret']

    with transaction.atomic():
        conn, _ = UserBinanceConnection.objects.update_or_create(
            user=request.user,
            defaults={
                'api_key_enc': encrypt(api_key),
                'api_secret_enc': encrypt(api_secret),
                'api_key_hint': hint(api_key),
                # Reset transient fields; status is set by validate_connection
                'status': UserBinanceConnection.STATUS_PAUSED,
                'permissions': {},
                'ip_check_passed': False,
                'last_error': '',
            },
        )

    result = validate_connection(conn)
    conn.refresh_from_db()

    body = UserBinanceConnectionStateSerializer(conn).data
    body['validation'] = {
        'ok': result.ok,
        'code': result.code,
        'message': result.message,
    }
    return Response(
        body,
        status=status.HTTP_200_OK if result.ok else status.HTTP_400_BAD_REQUEST,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([RevalidateThrottle])
def revalidate(request):
    """Manually re-run validation for the current user's connection."""
    try:
        conn = request.user.binance_connection
    except UserBinanceConnection.DoesNotExist:
        return Response({'detail': 'No Binance connection.'},
                        status=status.HTTP_404_NOT_FOUND)

    result = validate_connection(conn)
    conn.refresh_from_db()
    body = UserBinanceConnectionStateSerializer(conn).data
    body['validation'] = {
        'ok': result.ok,
        'code': result.code,
        'message': result.message,
    }
    return Response(body)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def disconnect(request):
    """Wipe the current user's connection row (and credentials with it)."""
    deleted, _ = UserBinanceConnection.objects.filter(user=request.user).delete()
    if not deleted:
        return Response({'detail': 'No Binance connection.'},
                        status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_204_NO_CONTENT)
