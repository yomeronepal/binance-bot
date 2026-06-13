"""
Firebase Cloud Messaging push notification service.

Handles Firebase initialization, sending notifications to individual
users or broadcasting to all subscribers.
"""
import json
import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)

_firebase_app = None


def get_firebase_app():
    """
    Lazily initialize and return the Firebase Admin app singleton.

    Returns:
        firebase_admin.App or None if credentials not found.
    """
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred = _load_firebase_credentials()
        if cred is None:
            return None

        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully")
        return _firebase_app

    except Exception as e:
        logger.error("Failed to initialize Firebase: %s", e)
        return None


def _load_firebase_credentials():
    """
    Load Firebase credentials from env JSON string or file path.

    Returns:
        firebase_admin.credentials.Certificate or None.
    """
    from firebase_admin import credentials

    cred_json = os.getenv('FIREBASE_CREDENTIALS_JSON', '')
    if cred_json:
        try:
            cred_dict = json.loads(cred_json)
            logger.info("Firebase credentials loaded from FIREBASE_CREDENTIALS_JSON env var")
            return credentials.Certificate(cred_dict)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Invalid FIREBASE_CREDENTIALS_JSON: %s", e)

    cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', 'firebase-credentials.json')
    if not os.path.isabs(cred_path):
        cred_path = os.path.join(settings.BASE_DIR, cred_path)

    if os.path.exists(cred_path):
        logger.info("Firebase credentials loaded from file: %s", cred_path)
        return credentials.Certificate(cred_path)

    logger.warning("No Firebase credentials found (set FIREBASE_CREDENTIALS_JSON or FIREBASE_CREDENTIALS_PATH)")
    return None


def _deactivate_stale_tokens(token_list):
    """
    Mark tokens as inactive when Firebase reports them as unregistered.

    Args:
        token_list: List of FCM token strings to deactivate.
    """
    if not token_list:
        return
    from signals.models.push import PushSubscription
    count = PushSubscription.objects.filter(
        fcm_token__in=token_list, is_active=True
    ).update(is_active=False)
    if count:
        logger.info("Deactivated %d stale FCM tokens", count)


def send_to_user(user, title, body, data=None, signal_obj=None):
    """
    Send a push notification to all active devices of a specific user.

    Args:
        user: Django User instance.
        title: Notification title.
        body: Notification body text.
        data: Optional dict of extra data to include in the payload.
        signal_obj: Optional Signal model instance for audit logging.

    Returns:
        dict with keys: sent, failed, total.
    """
    from signals.models.push import PushSubscription, NotificationLog

    tokens = list(
        PushSubscription.objects.filter(user=user, is_active=True)
        .values_list('fcm_token', flat=True)
    )

    if not tokens:
        logger.debug("No active FCM tokens for user %s", user.username)
        return {'sent': 0, 'failed': 0, 'total': 0}

    result = _send_multicast(tokens, title, body, data)

    status = 'SENT' if result['failed'] == 0 else ('PARTIAL' if result['sent'] > 0 else 'FAILED')
    NotificationLog.objects.create(
        user=user,
        title=title,
        body=body,
        data=data or {},
        status=status,
        error_message=result.get('error', ''),
        signal=signal_obj,
        tokens_targeted=result['total'],
        tokens_succeeded=result['sent'],
    )

    return result


def broadcast(title, body, data=None, signal_obj=None):
    """
    Broadcast a push notification to all active subscribers.

    Args:
        title: Notification title.
        body: Notification body text.
        data: Optional dict of extra data to include in the payload.
        signal_obj: Optional Signal model instance for audit logging.

    Returns:
        dict with keys: sent, failed, total.
    """
    from signals.models.push import PushSubscription, NotificationLog

    tokens = list(
        PushSubscription.objects.filter(is_active=True)
        .values_list('fcm_token', flat=True)
    )

    if not tokens:
        logger.debug("No active FCM subscribers for broadcast")
        return {'sent': 0, 'failed': 0, 'total': 0}

    result = _send_multicast(tokens, title, body, data)

    status = 'SENT' if result['failed'] == 0 else ('PARTIAL' if result['sent'] > 0 else 'FAILED')
    NotificationLog.objects.create(
        title=title,
        body=body,
        data=data or {},
        status=status,
        error_message=result.get('error', ''),
        signal=signal_obj,
        tokens_targeted=result['total'],
        tokens_succeeded=result['sent'],
    )

    return result


def _send_multicast(tokens, title, body, data=None):
    """
    Send a multicast message to a list of tokens (FCM and native web push).

    Args:
        tokens: List of FCM or native push token strings.
        title: Notification title.
        body: Notification body text.
        data: Optional dict of string key-value pairs.

    Returns:
        dict with keys: sent, failed, total, error.
    """
    fcm_tokens = [t for t in tokens if not t.startswith('native:')]
    native_tokens = [t for t in tokens if t.startswith('native:')]

    total_sent = 0
    total_failed = 0
    errors = []

    if native_tokens:
        native_result = _send_native_webpush(native_tokens, title, body, data)
        total_sent += native_result['sent']
        total_failed += native_result['failed']
        if native_result.get('error'):
            errors.append(native_result['error'])

    if not fcm_tokens:
        return {'sent': total_sent, 'failed': total_failed, 'total': len(tokens), 'error': '; '.join(errors)}

    app = get_firebase_app()
    if app is None:
        return {'sent': total_sent, 'failed': total_failed + len(fcm_tokens), 'total': len(tokens), 'error': 'Firebase not initialized'}

    tokens = fcm_tokens

    try:
        from firebase_admin import messaging

        str_data = {str(k): str(v) for k, v in (data or {}).items()}

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=str_data,
            tokens=tokens,
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    title=title,
                    body=body,
                    icon='/icon-192x192.png',
                    badge='/icon-192x192.png',
                    vibrate=[200, 100, 200, 100, 200],
                ),
                headers={'Urgency': 'high'},
            ),
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default',
                    channel_id='trading_signals',
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound='default'),
                ),
            ),
        )

        response = messaging.send_each_for_multicast(message, app=app)

        stale_tokens = _collect_stale_tokens(response, tokens)
        _deactivate_stale_tokens(stale_tokens)

        logger.info(
            "Push sent: %d/%d succeeded, %d failed",
            response.success_count, len(tokens), response.failure_count
        )

        return {
            'sent': response.success_count + total_sent,
            'failed': response.failure_count + total_failed,
            'total': len(fcm_tokens) + len(native_tokens),
            'error': '; '.join(errors) if errors else '',
        }

    except Exception as e:
        logger.error("Failed to send push notification: %s", e)
        return {'sent': total_sent, 'failed': len(fcm_tokens) + total_failed, 'total': len(fcm_tokens) + len(native_tokens), 'error': str(e)}


def _send_native_webpush(native_tokens, title, body, data=None):
    """
    Send push notifications to native web push subscriptions (Safari/iOS).

    Args:
        native_tokens: List of tokens prefixed with 'native:'.
        title: Notification title.
        body: Notification body text.
        data: Optional dict of extra data.

    Returns:
        dict with keys: sent, failed, error.
    """
    try:
        from pywebpush import webpush, WebPushException
        import base64

        vapid_private_key = os.getenv('VAPID_PRIVATE_KEY', '')
        vapid_email = os.getenv('VAPID_EMAIL', 'mailto:admin@revxsys.com')

        if not vapid_private_key:
            logger.warning("VAPID_PRIVATE_KEY not set, cannot send native web push")
            return {'sent': 0, 'failed': len(native_tokens), 'error': 'VAPID_PRIVATE_KEY not configured'}

        payload = json.dumps({
            'notification': {'title': title, 'body': body},
            'data': data or {},
        })

        sent = 0
        failed = 0

        for token in native_tokens:
            try:
                sub_json = json.loads(base64.b64decode(token[7:]).decode('utf-8'))
                webpush(
                    subscription_info=sub_json,
                    data=payload,
                    vapid_private_key=vapid_private_key,
                    vapid_claims={'sub': vapid_email},
                )
                sent += 1
            except WebPushException as e:
                logger.warning("Native webpush failed: %s", e)
                if '410' in str(e) or '404' in str(e):
                    _deactivate_stale_tokens([token])
                failed += 1
            except Exception as e:
                logger.warning("Native webpush error: %s", e)
                failed += 1

        return {'sent': sent, 'failed': failed, 'error': ''}

    except ImportError:
        logger.warning("pywebpush not installed, cannot send native web push")
        return {'sent': 0, 'failed': len(native_tokens), 'error': 'pywebpush not installed'}


def _collect_stale_tokens(response, tokens):
    """
    Identify tokens that Firebase reports as unregistered.

    Args:
        response: Firebase BatchResponse object.
        tokens: Original list of tokens sent to.

    Returns:
        List of stale token strings.
    """
    from firebase_admin import messaging

    stale = []
    for idx, send_response in enumerate(response.responses):
        if send_response.exception is None:
            continue
        exc = send_response.exception
        if isinstance(exc, (messaging.UnregisteredError,)) or 'NOT_FOUND' in str(exc):
            stale.append(tokens[idx])
    return stale


def send_signal_notification(signal):
    """
    Build and broadcast a push notification for a new trading signal.

    Args:
        signal: Signal model instance.

    Returns:
        dict with broadcast result.
    """
    direction_emoji = "\U0001F7E2" if signal.direction == 'LONG' else "\U0001F534"
    is_priority = getattr(signal, 'is_priority', False)
    priority_tag = " [PRIORITY]" if is_priority else ""

    title = f"{direction_emoji} {signal.direction}{priority_tag} - {signal.symbol}"
    body = (
        f"Entry: ${float(signal.entry):,.2f} | "
        f"SL: ${float(signal.sl):,.2f} | "
        f"TP: ${float(signal.tp):,.2f} | "
        f"Conf: {float(signal.confidence) * 100:.0f}%"
    )

    data = {
        'type': 'NEW_SIGNAL',
        'signal_id': str(signal.id),
        'symbol': str(signal.symbol),
        'direction': signal.direction,
        'entry': str(float(signal.entry)),
        'sl': str(float(signal.sl)),
        'tp': str(float(signal.tp)),
        'is_priority': str(is_priority),
        'url': '/bot-performance',
    }

    return broadcast(title, body, data=data, signal_obj=signal)
