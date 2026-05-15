"""
Cached SPY + QQQ daily trend snapshot for the equity macro filter.

Mirrors btc_trend.py but for the TRADIFI lane. SPY is the primary
gate (broad-market US equities); QQQ is reported alongside for
tech-heavy stocks but is informational only at the filter layer.

Snapshot contents:
  spy        per-symbol dict: close/ema7/ema20/above_*/ret_3d/ret_7d
  qqq        per-symbol dict: same shape (informational)
  fetched_at UTC datetime — for staleness debugging

The SPY/QQQ tickers on Binance are TRADIFI_PERPETUAL contracts —
24/7 perp pricing wrapped around the underlying cash-market hours.
We pull the daily candles directly from fapi.binance.com via the
same client used for BTC.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


_TTL_SECONDS = 300
_FAILURE_TTL_SECONDS = 30
_KLINE_LIMIT = 60
_SYMBOLS = ('SPYUSDT', 'QQQUSDT')


@dataclass(frozen=True)
class EquityLeg:
    symbol: str
    close: float
    ema7: float
    ema20: float
    above_ema7: bool
    above_ema20: bool
    ret_3d: float
    ret_7d: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EquitySnapshot:
    spy: Optional[EquityLeg]
    qqq: Optional[EquityLeg]
    fetched_at: datetime

    def to_dict(self) -> dict:
        return {
            'spy': self.spy.to_dict() if self.spy else None,
            'qqq': self.qqq.to_dict() if self.qqq else None,
            'fetched_at': self.fetched_at.isoformat(),
        }


_state = {
    'snapshot': None,
    'expires_at': 0.0,
}
_lock = threading.Lock()


def _compute_leg(symbol: str, closes: list[float]) -> EquityLeg:
    s = pd.Series(closes, dtype='float64')
    ema7 = float(s.ewm(span=7, adjust=False).mean().iloc[-1])
    ema20 = float(s.ewm(span=20, adjust=False).mean().iloc[-1])
    close = float(s.iloc[-1])

    def _ret(n_back: int) -> float:
        if len(s) < n_back + 1:
            return 0.0
        prev = float(s.iloc[-(n_back + 1)])
        if prev == 0:
            return 0.0
        return (close / prev - 1.0) * 100.0

    return EquityLeg(
        symbol=symbol,
        close=close,
        ema7=ema7,
        ema20=ema20,
        above_ema7=close > ema7,
        above_ema20=close > ema20,
        ret_3d=_ret(3),
        ret_7d=_ret(7),
    )


def _fetch_sync() -> EquitySnapshot:
    """
    Pull SPYUSDT and QQQUSDT daily klines from fapi.binance.com.

    A leg with insufficient data (e.g. listing too new for EMA20) is
    set to None rather than raising — the equity filter handles a
    missing leg as "snapshot unavailable, fail open".
    """
    from .binance_futures_client import BinanceFuturesClient

    async def _go():
        legs = {}
        async with BinanceFuturesClient() as c:
            for sym in _SYMBOLS:
                try:
                    klines = await c.get_klines(sym, interval='1d', limit=_KLINE_LIMIT)
                    closes = [float(k[4]) for k in klines]
                    if len(closes) >= 21:
                        legs[sym] = _compute_leg(sym, closes)
                    else:
                        legs[sym] = None
                        logger.warning(
                            "%s returned only %d candles, need >= 21 for EMA20",
                            sym, len(closes),
                        )
                except Exception as exc:
                    legs[sym] = None
                    logger.warning("Failed to fetch %s klines: %s", sym, exc)
        return legs

    loop = asyncio.new_event_loop()
    try:
        legs = loop.run_until_complete(_go())
    finally:
        loop.close()

    return EquitySnapshot(
        spy=legs.get('SPYUSDT'),
        qqq=legs.get('QQQUSDT'),
        fetched_at=datetime.now(timezone.utc),
    )


def get_equity_snapshot(force_refresh: bool = False) -> Optional[EquitySnapshot]:
    """
    Return the cached equity (SPY+QQQ) snapshot. ``None`` only when the
    very first fetch failed and there is no prior value to fall back on.
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

        if snap.spy:
            logger.info(
                "Equity snapshot refreshed: SPY close=%.2f above_ema20=%s "
                "ret_7d=%+.2f%% | QQQ %s",
                snap.spy.close, snap.spy.above_ema20, snap.spy.ret_7d,
                f"close={snap.qqq.close:.2f}" if snap.qqq else "leg=missing",
            )
        return snap
    except Exception as exc:
        logger.warning("Equity snapshot fetch failed: %s", exc)
        with _lock:
            _state['expires_at'] = time.time() + _FAILURE_TTL_SECONDS
            return _state['snapshot']


def invalidate_equity_snapshot_cache() -> None:
    """Drop the cached snapshot. Primarily for tests / forced reload."""
    with _lock:
        _state['snapshot'] = None
        _state['expires_at'] = 0.0
