"""
Fan a Signal out to every connected user account.

CONTRACT WITH THE CENTRAL ACCOUNT (do not break):

    The central bot account (env ``BINANCE_API_KEY``/``BINANCE_API_SECRET``)
    continues to trade through its own code path: the Signal post_save
    handler in ``signals_handlers`` and the periodic
    ``golden_window_trader.execute_futures_trade`` task. This dispatcher
    runs *additionally*, in a background thread, after those have done
    their work. The dispatcher MUST NOT:

      * Touch the central account's credentials or trader instance.
      * Block the caller (it runs async via the helper below).
      * Raise into the caller — every error is contained.
      * Mutate the central FuturesTrade row.

Failure isolation is non-negotiable: one user's broken key, exhausted
margin, or rate-limit MUST NOT block another user's trade nor the
central account's trade. Each user runs in its own worker thread, each
in its own try/except.

Trade size, leverage, max-concurrent etc come from the central
``FuturesTradingSettings`` (slice 2 will introduce per-user settings).
Connections in ``BROKEN``/``REVOKED`` status are skipped — they require
explicit user action and the 30-min health check transitions them back
when fixed.
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List

from django.db import close_old_connections

from .credential_crypto import decrypt
from ..models import Signal
from ..models_user_connection import UserBinanceConnection
from .futures_trader import futures_trading_service

logger = logging.getLogger(__name__)


# Connections in these statuses participate in fan-out. BROKEN/REVOKED do
# not — they need explicit user action and the periodic health check will
# transition them back when fixed.
_TRADABLE_STATUSES = (
    UserBinanceConnection.STATUS_ACTIVE,
    UserBinanceConnection.STATUS_PAUSED,
)

# Bound the parallel fan-out so a Signal that fires while we have many
# connections doesn't spawn unbounded threads. 8 in-flight per signal is
# plenty: each user trade is ~5 Binance API calls and 1-2 s wall, so
# ceiling is 8 trades / ~2 s = ~240 trades/min — well inside Binance's
# per-IP rate budget for a long while. Bump if you grow past ~100 users.
_FANOUT_MAX_WORKERS = 8

# Cap each user's trade flow at 2 minutes — covers entry-poll worst case
# (~3 s) plus SL/TP placement and the 0.3 s verification settle-time with
# generous headroom. Anything longer means the user's network is broken
# or the API is jammed; we'd rather skip than tie up the worker pool.
_PER_USER_TIMEOUT_S = 120


def _eligible_connections() -> List[UserBinanceConnection]:
    """
    Return the connections that should receive this signal.

    Selecting both ACTIVE and PAUSED is deliberate — UX is wired to
    "trade as soon as connected" rather than gating on an explicit
    enable toggle. Slice 2 may narrow this to ACTIVE only.
    """
    return list(
        UserBinanceConnection.objects
        .filter(status__in=_TRADABLE_STATUSES, ip_check_passed=True)
        .select_related('user')
    )


def _execute_for_user(signal_id: int, connection_id: int) -> None:
    """
    Worker: load fresh state, decrypt, place the trade.

    Re-fetches Signal and Connection inside the thread so we never share
    ORM objects across threads. Closes any leaked DB connection at the
    end — Django allocates connections per-thread and they outlive the
    thread otherwise, eventually exhausting the pool on long-lived
    workers.
    """
    api_key = None
    api_secret = None
    try:
        try:
            signal = Signal.objects.select_related('symbol').get(pk=signal_id)
        except Signal.DoesNotExist:
            logger.warning("dispatcher: signal %s vanished before fan-out", signal_id)
            return

        try:
            connection = (
                UserBinanceConnection.objects
                .select_related('user')
                .get(pk=connection_id)
            )
        except UserBinanceConnection.DoesNotExist:
            logger.warning("dispatcher: connection %s vanished before fan-out", connection_id)
            return

        # Re-check status inside the thread — the connection might have
        # been disconnected or moved to BROKEN between dispatch and run.
        if connection.status not in _TRADABLE_STATUSES:
            logger.info(
                "dispatcher: skipping signal %s for user %s (status=%s)",
                signal_id, connection.user_id, connection.status,
            )
            return

        try:
            api_key = decrypt(connection.api_key_enc)
            api_secret = decrypt(connection.api_secret_enc)
        except Exception:
            logger.exception(
                "dispatcher: cannot decrypt credentials for connection %s — "
                "rotation issue? user must reconnect.",
                connection_id,
            )
            return

        try:
            # ``execute_signal`` has its own try/except around the API
            # call, writes a per-account FuturesTradeLog row for both
            # success and failure, and returns None on any failure. We
            # layer one more try/except here so any unexpected error
            # (DB hiccup, etc.) is contained to this user's thread.
            futures_trading_service.execute_signal(
                signal,
                force_execute=True,    # users bypass the trading-window gate
                user=connection.user,
                api_key=api_key,
                api_secret=api_secret,
            )
        except Exception:
            logger.exception(
                "dispatcher: unexpected error executing signal %s for user %s",
                signal_id, connection.user_id,
            )
    finally:
        # Best-effort scrub of secret strings from this thread's locals.
        api_key = None
        api_secret = None
        # Release this thread's DB connection so Django can recycle it.
        # Without this, daemon threads hold open connections forever and
        # eventually exhaust the pool on long-lived Celery workers.
        close_old_connections()


def dispatch_signal_to_users(signal) -> dict:
    """
    Fan ``signal`` out to every eligible UserBinanceConnection.

    Blocks the caller until every user thread completes (or hits its
    timeout). Returns a summary dict suitable for logging. Use
    :func:`dispatch_signal_to_users_async` from non-blocking contexts.
    """
    try:
        connections = _eligible_connections()
    except Exception:
        logger.exception("dispatcher: failed to load eligible connections for signal %s", signal.id)
        return {'eligible': 0, 'dispatched': 0, 'error': 'load_failed'}

    if not connections:
        logger.debug("dispatcher: no eligible user connections for signal %s", signal.id)
        return {'eligible': 0, 'dispatched': 0}

    logger.info(
        "dispatcher: fanning signal %s out to %d user connection(s)",
        signal.id, len(connections),
    )

    with ThreadPoolExecutor(max_workers=_FANOUT_MAX_WORKERS,
                              thread_name_prefix='user-trade') as pool:
        futures = [
            pool.submit(_execute_for_user, signal.id, c.pk)
            for c in connections
        ]
        for f in futures:
            try:
                f.result(timeout=_PER_USER_TIMEOUT_S)
            except Exception:
                logger.exception("dispatcher: worker raised past its own try/except")

    return {'eligible': len(connections), 'dispatched': len(connections)}


def dispatch_signal_to_users_async(signal) -> threading.Thread:
    """
    Fire-and-forget version of :func:`dispatch_signal_to_users`.

    Returns the daemon thread handle so callers in test contexts can
    join() if they need to. Production callers should NOT join — the
    central account's caller has already returned to its work, and the
    user-side fan-out runs in the background.
    """
    thread = threading.Thread(
        target=dispatch_signal_to_users,
        args=(signal,),
        name=f'user-fanout-signal-{signal.id}',
        daemon=True,
    )
    thread.start()
    return thread


def safe_dispatch(signal, source: str = 'unknown') -> None:
    """
    Single-line entrypoint for both call sites (post_save and
    golden_window_trader). Wraps the spawn in try/except so a misuse or
    import error never bubbles into the central-account flow.
    """
    try:
        dispatch_signal_to_users_async(signal)
    except Exception:
        logger.exception(
            "safe_dispatch[%s]: failed to start user fan-out for signal %s",
            source, getattr(signal, 'id', '?'),
        )
