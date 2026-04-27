"""
Periodic health check for per-user Binance API connections.

Runs every 30 minutes via Celery Beat. Exercises the user's API key
against ``GET /fapi/v2/account`` (the same call the connect-wizard uses)
and updates the row's status. Pushes a notification on state changes
that need user attention (BROKEN, REVOKED), so the user can re-enter
their key without waiting to discover that auto-trading silently
stopped.
"""
import logging

from celery import shared_task

from .models_user_connection import UserBinanceConnection
from .services.user_connection_validator import validate_connection

logger = logging.getLogger(__name__)


_NEEDS_ATTENTION = {
    UserBinanceConnection.STATUS_BROKEN,
    UserBinanceConnection.STATUS_REVOKED,
}


def _push_state_change(connection, prev_status):
    """Notify the user when the connection becomes unhealthy."""
    try:
        from .services.push_notification import send_to_user
    except Exception:
        logger.warning("push_notification import failed; skipping state-change push")
        return

    if connection.status not in _NEEDS_ATTENTION:
        return
    if prev_status == connection.status:
        return  # already notified on the prior run

    title_map = {
        UserBinanceConnection.STATUS_REVOKED: "Binance API key revoked",
        UserBinanceConnection.STATUS_BROKEN: "Binance API connection broken",
    }
    body_map = {
        'invalid_key': "Your API key is invalid or revoked. Re-create it on Binance and reconnect.",
        'bad_secret': "Your API secret is wrong. Reconnect with the original secret you saved.",
        'ip_blocked': "Our server IP is no longer allowlisted on your Binance API key. Update the allowlist and reconnect.",
        'no_futures': "Futures trading is not enabled on this key. Enable it on Binance and reconnect.",
    }
    last_error = (connection.last_error or '').split(':', 1)[0]
    body = body_map.get(last_error, "Your Binance connection needs attention. Open the app to reconnect.")
    title = title_map[connection.status]

    try:
        send_to_user(connection.user, title=title, body=body, data={
            'type': 'binance_connection_state',
            'status': connection.status,
            'code': last_error,
        })
    except Exception as exc:
        logger.error("Failed to push state-change for user %s: %s", connection.user_id, exc)


@shared_task(name='signals.health_check_user_connections', bind=True, max_retries=0)
def health_check_user_connections(self):
    """
    For every connection in ACTIVE or PAUSED status, re-run validation.

    BROKEN/REVOKED rows are intentionally skipped — they require explicit
    user action via the wizard. Re-validating them every 30 minutes burns
    rate limit and produces no new information.
    """
    qs = UserBinanceConnection.objects.filter(
        status__in=[
            UserBinanceConnection.STATUS_ACTIVE,
            UserBinanceConnection.STATUS_PAUSED,
        ],
    )
    total = qs.count()
    flipped = 0
    for connection in qs.iterator():
        prev_status = connection.status
        try:
            validate_connection(connection)
        except Exception as exc:
            logger.exception("Health check raised for connection %s: %s",
                             connection.pk, exc)
            continue
        connection.refresh_from_db(fields=['status', 'last_error'])
        if connection.status != prev_status:
            flipped += 1
            _push_state_change(connection, prev_status)
    logger.info("health_check_user_connections done: total=%s state_changes=%s",
                total, flipped)
    return {'total': total, 'state_changes': flipped}
