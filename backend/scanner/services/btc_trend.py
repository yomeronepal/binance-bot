"""
Cached BTC daily trend snapshot for the macro filter.

The macro filter (``scanner/services/macro_filter.py``) gates Binance
order placement based on BTC's regime — trades that align with BTC's
daily trend tend to win more often than those that fight it. Computing
the snapshot per signal is wasteful: BTC's daily EMAs and 3/7-day
returns don't change between two scan cycles. We pull once and cache
``_TTL_SECONDS`` (5 minutes by default).

Snapshot contents:
  close          last daily close
  ema20, ema50   trend gates
  above_ema20    bool
  above_ema50    bool
  ret_3d         3-day percent change (%, signed)
  ret_7d         7-day percent change (%, signed)
  fetched_at     UTC datetime — for staleness debugging
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import pandas as pd

logger = logging.getLogger(__name__)


# 5-minute cache. BTC's 1-day EMAs/returns barely move in 5 min, and at
# this rate the bot makes 12 BTC kline calls per hour total — far below
# Binance's free-tier rate budget.
_TTL_SECONDS = 300

# On a fetch failure we cache an empty (None) snapshot for a shorter
# window so transient network blips are recoverable inside a minute.
_FAILURE_TTL_SECONDS = 30

# Pull 90 daily candles. Plenty to settle EMA50 (needs ~150 weighted
# inputs but pandas EWM converges effectively at ~3x span) and to read
# a 7-day return.
_KLINE_LIMIT = 90


@dataclass(frozen=True)
class BTCSnapshot:
    close: float
    ema20: float
    ema50: float
    above_ema20: bool
    above_ema50: bool
    ret_3d: float
    ret_7d: float
    fetched_at: datetime

    def to_dict(self) -> dict:
        d = asdict(self)
        d['fetched_at'] = self.fetched_at.isoformat()
        return d


_state = {
    'snapshot': None,    # type: BTCSnapshot | None
    'expires_at': 0.0,
}
_lock = threading.Lock()


def _compute_snapshot_from_closes(closes: list[float]) -> BTCSnapshot:
    """Pure helper — testable without the network."""
    s = pd.Series(closes, dtype='float64')
    ema20 = float(s.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(s.ewm(span=50, adjust=False).mean().iloc[-1])
    close = float(s.iloc[-1])

    # Returns are computed on close-to-close, not intraday, so 3d return
    # = today vs the close 3 trading days ago (= index -4).
    def _ret(n_back: int) -> float:
        if len(s) < n_back + 1:
            return 0.0
        prev = float(s.iloc[-(n_back + 1)])
        if prev == 0:
            return 0.0
        return (close / prev - 1.0) * 100.0

    return BTCSnapshot(
        close=close,
        ema20=ema20,
        ema50=ema50,
        above_ema20=close > ema20,
        above_ema50=close > ema50,
        ret_3d=_ret(3),
        ret_7d=_ret(7),
        fetched_at=datetime.now(timezone.utc),
    )


def _fetch_sync() -> BTCSnapshot:
    """Run the async client call from sync code on a fresh event loop."""
    from .binance_client import BinanceClient

    async def _go():
        async with BinanceClient() as c:
            klines = await c.get_klines('BTCUSDT', interval='1d', limit=_KLINE_LIMIT)
            return [float(k[4]) for k in klines]   # k[4] = close price

    loop = asyncio.new_event_loop()
    try:
        closes = loop.run_until_complete(_go())
    finally:
        loop.close()

    if len(closes) < 51:
        raise RuntimeError(
            f"BTCUSDT klines returned only {len(closes)} candles, need >= 51 for EMA50"
        )
    return _compute_snapshot_from_closes(closes)


def get_btc_snapshot(force_refresh: bool = False) -> BTCSnapshot | None:
    """
    Return the cached BTC trend snapshot.

    Returns ``None`` only when the very first fetch has failed and there
    is no prior cached value to fall back on. Callers should treat
    ``None`` as "macro filter cannot decide; fail open or fail closed
    according to local policy" — typically allow the trade rather than
    block on a transient network issue.
    """
    now = time.time()
    with _lock:
        if (
            not force_refresh
            and _state['snapshot'] is not None
            and now < _state['expires_at']
        ):
            return _state['snapshot']

    try:
        snap = _fetch_sync()
        with _lock:
            _state['snapshot'] = snap
            _state['expires_at'] = time.time() + _TTL_SECONDS
        logger.info(
            "BTC snapshot refreshed: close=%.2f ema20=%.2f ema50=%.2f "
            "above_ema20=%s above_ema50=%s ret_3d=%+.2f%% ret_7d=%+.2f%%",
            snap.close, snap.ema20, snap.ema50, snap.above_ema20, snap.above_ema50,
            snap.ret_3d, snap.ret_7d,
        )
        return snap
    except Exception as exc:
        logger.warning("BTC snapshot fetch failed: %s", exc)
        with _lock:
            # Don't overwrite a previously-good snapshot on a transient
            # failure — keep what we have, just shorten the TTL so we
            # retry sooner. If we never had one, store None and try
            # again in 30s.
            _state['expires_at'] = time.time() + _FAILURE_TTL_SECONDS
            return _state['snapshot']


def invalidate_btc_snapshot_cache() -> None:
    """Drop the cached snapshot. Primarily for tests / forced reload."""
    with _lock:
        _state['snapshot'] = None
        _state['expires_at'] = 0.0
