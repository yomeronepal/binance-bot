"""
Redis-backed distributed lock for signal execution.

Replaces the per-process ``_futures_signal_lock = set()`` that only protected
against duplicates inside a single Python process. With multiple Celery workers
or an API server + worker, the old approach could let the same Signal fire
twice — opening two real positions with one set of SL/TP.

Uses ``redis-py``'s built-in :class:`redis.lock.Lock` which implements the
standard SET NX + Lua-release pattern: only the caller that set the key can
delete it, and the key auto-expires if the holder crashes.
"""
import logging
from contextlib import contextmanager

from django.conf import settings
from redis import Redis
from redis.exceptions import LockError, LockNotOwnedError, RedisError

logger = logging.getLogger(__name__)

_SIGNAL_LOCK_TTL_SECONDS = 60
_SIGNAL_LOCK_PREFIX = 'futures_signal_lock'

_redis_client = None


def _get_client():
    """
    Lazy-init a shared Redis client against settings.REDIS_URL.

    Returns:
        redis.Redis: Decoded-response client bound to the Celery broker
        Redis instance.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


@contextmanager
def signal_execution_lock(signal_id):
    """
    Acquire a distributed lock for executing a single Signal.

    Fail-open on Redis errors: if Redis is unreachable, we log a loud
    ERROR and yield True so trades are not silently dropped during an
    outage. A duplicate execution is worse than a missed one, but a
    completely silent failure is worse than either.

    Args:
        signal_id: Signal primary key.

    Yields:
        bool: True if the lock was acquired (or Redis is down — fail open);
        False if another worker already holds the lock.

    Example:
        with signal_execution_lock(signal.id) as acquired:
            if not acquired:
                return
            # ... execute trade
    """
    key = f"{_SIGNAL_LOCK_PREFIX}:{signal_id}"
    lock = None
    acquired = False

    try:
        lock = _get_client().lock(key, timeout=_SIGNAL_LOCK_TTL_SECONDS)
        acquired = lock.acquire(blocking=False)
    except RedisError as exc:
        logger.error(
            f"Redis unavailable for signal lock {key}: {exc} — "
            "FAIL-OPEN, trade will proceed without duplicate protection",
            exc_info=True,
        )
        yield True
        return

    try:
        yield acquired
    finally:
        if acquired and lock is not None:
            _release_lock(lock, key)


def _release_lock(lock, key):
    """
    Release a held lock, swallowing expected benign errors.

    :class:`LockNotOwnedError` means the TTL expired before we released —
    the lock is already gone, so this is not a real failure.

    Args:
        lock: The :class:`redis.lock.Lock` instance to release.
        key: Key name, for log context.
    """
    try:
        lock.release()
    except LockNotOwnedError:
        logger.warning(f"Signal lock {key} expired before release (TTL exceeded)")
    except (LockError, RedisError) as exc:
        logger.warning(f"Failed to release signal lock {key}: {exc}")
