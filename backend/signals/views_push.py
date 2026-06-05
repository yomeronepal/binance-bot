"""
API views for push notification subscription management.
"""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from signals.models_push import PushSubscription

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscribe_push(request):
    """
    Subscribe a device for push notifications.

    Args:
        request: Must contain 'fcm_token' and optional 'device_name'.

    Returns:
        201 on new subscription, 200 if reactivated.
    """
    fcm_token = request.data.get('fcm_token')
    device_name = request.data.get('device_name', '')

    if not fcm_token:
        return Response({'error': 'fcm_token is required'}, status=status.HTTP_400_BAD_REQUEST)

    sub, created = PushSubscription.objects.update_or_create(
        fcm_token=fcm_token,
        defaults={
            'user': request.user,
            'device_name': device_name,
            'is_active': True,
        }
    )

    action = 'subscribed' if created else 'reactivated'
    logger.info("Push %s for user %s (device: %s)", action, request.user.username, device_name)

    return Response(
        {'status': action, 'id': sub.id},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unsubscribe_push(request):
    """
    Unsubscribe a device from push notifications.

    Args:
        request: Must contain 'fcm_token'.

    Returns:
        200 on success, 404 if token not found.
    """
    fcm_token = request.data.get('fcm_token')

    if not fcm_token:
        return Response({'error': 'fcm_token is required'}, status=status.HTTP_400_BAD_REQUEST)

    updated = PushSubscription.objects.filter(
        fcm_token=fcm_token, user=request.user
    ).update(is_active=False)

    if not updated:
        return Response({'error': 'Subscription not found'}, status=status.HTTP_404_NOT_FOUND)

    logger.info("Push unsubscribed for user %s", request.user.username)
    return Response({'status': 'unsubscribed'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def push_status(request):
    """
    Check if the current user has active push subscriptions.

    Returns:
        JSON with subscription count and device list.
    """
    subs = PushSubscription.objects.filter(user=request.user, is_active=True)
    return Response({
        'subscribed': subs.exists(),
        'device_count': subs.count(),
        'devices': [
            {'id': s.id, 'device_name': s.device_name or 'Unknown', 'created_at': s.created_at}
            for s in subs[:10]
        ],
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def subscribe_push_public(request):
    """
    Subscribe an anonymous device for push notifications (no auth required).
    Uses a system user or stores without user association.

    Args:
        request: Must contain 'fcm_token' and optional 'device_name'.

    Returns:
        201 on new subscription, 200 if reactivated.
    """
    fcm_token = request.data.get('fcm_token')
    device_name = request.data.get('device_name', '')

    if not fcm_token:
        return Response({'error': 'fcm_token is required'}, status=status.HTTP_400_BAD_REQUEST)

    from django.contrib.auth import get_user_model
    User = get_user_model()
    system_user = User.objects.filter(is_superuser=True).first()

    if not system_user:
        return Response({'error': 'No admin user found'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    user = request.user if request.user.is_authenticated else system_user

    existing = PushSubscription.objects.filter(fcm_token=fcm_token).first()
    if existing and existing.user_id not in (user.id, system_user.id):
        existing.is_active = True
        if device_name:
            existing.device_name = device_name
        existing.save(update_fields=['is_active', 'device_name'])
        logger.info("Push reactivated (public) for existing owner, device: %s", device_name)
        return Response({'status': 'reactivated', 'id': existing.id}, status=status.HTTP_200_OK)

    sub, created = PushSubscription.objects.update_or_create(
        fcm_token=fcm_token,
        defaults={
            'user': user,
            'device_name': device_name,
            'is_active': True,
        }
    )

    action = 'subscribed' if created else 'reactivated'
    logger.info("Push %s (public) device: %s", action, device_name)

    return Response(
        {'status': action, 'id': sub.id},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )
