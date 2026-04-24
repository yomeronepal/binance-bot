"""
Shared helpers for multi-timeframe Celery scanners.

Consolidates pieces that were duplicated across
multi_timeframe_scanner.py and futures_multi_timeframe_scanner.py.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


TIMEFRAME_PRIORITY = {
    '1d': 6,
    '4h': 5,
    '1h': 4,
    '30m': 3,
    '15m': 2,
    '5m': 1,
}
"""
Relative priority for timeframe-based signal deduplication.

Higher values win when two signals on the same symbol collide; absolute
values are meaningless — only ordering is compared. Superset of both
scanners; SPOT only ever looks up keys it uses, FUTURES uses the full set.
"""


def run_timeframe_scan_task(self_task, timeframe, async_fn, label):
    """
    Drive a single-timeframe async scan from inside a bound Celery task.

    Eliminates ~12 near-identical try/except/retry blocks between the SPOT
    and FUTURES scanners. Caller passes its own ``self`` so retries stay
    attached to the right task instance.

    Args:
        self_task: The bound Celery task (pass ``self``).
        timeframe: Timeframe label like ``"1h"`` or ``"4h"``.
        async_fn: Async callable taking ``(timeframe)`` and returning
            a JSON-serialisable result dict.
        label: Human label (e.g. ``"Spot multi-TF"``, ``"Futures"``) used
            only for log formatting.

    Returns:
        Whatever ``async_fn`` returned.

    Raises:
        celery.exceptions.Retry: Wrapped from any exception raised by
            ``async_fn``; Celery will reschedule per the task's
            ``max_retries`` / ``default_retry_delay``.
    """
    logger.info(f"Starting {label} {timeframe} scan...")
    try:
        result = asyncio.run(async_fn(timeframe))
        logger.info(f"{label} {timeframe} scan completed: {result}")
        return result
    except Exception as exc:
        logger.error(f"{label} {timeframe} scan failed: {exc}", exc_info=True)
        raise self_task.retry(exc=exc)
