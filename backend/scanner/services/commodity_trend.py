"""
Cached XAU + CL daily trend snapshot for the commodity macro filter.

Mirrors equity_trend.py. XAU (gold spot, ``XAUUSDT``) anchors the
regime — it tracks broad commodity sentiment, real yields, and
dollar strength better than any single energy or agricultural
ticker. CL (WTI crude, ``CLUSDT``) is reported alongside for
energy-name context but isn't used by the filter at this stage.

Both are listed on Binance Futures as TRADIFI_PERPETUAL contracts.
If a leg is missing or returns insufficient history, that leg is
set to None and the filter falls back to "snapshot unavailable,
fail open" — same policy as the BTC/equity filters.
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
_SYMBOLS = ('XAUUSDT', 'CLUSDT')


@dataclass(frozen=True)
class CommodityLeg:
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
class CommoditySnapshot:
    gold: Optional[CommodityLeg]
    oil: Optional[CommodityLeg]
    fetched_at: datetime

    def to_dict(self) -> dict:
        return {
            'gold': self.gold.to_dict() if self.gold else None,
            'oil': self.oil.to_dict() if self.oil else None,
            'fetched_at': self.fetched_at.isoformat(),
        }


_state = {
    'snapshot': None,
    'expires_at': 0.0,
}
_lock = threading.Lock()


def _compute_leg(symbol: str, closes: list[float]) -> CommodityLeg:
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

    return CommodityLeg(
        symbol=symbol,
        close=close,
        ema7=ema7,
        ema20=ema20,
        above_ema7=close > ema7,
        above_ema20=close > ema20,
        ret_3d=_ret(3),
        ret_7d=_ret(7),
    )


def _fetch_sync() -> CommoditySnapshot:
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

    return CommoditySnapshot(
        gold=legs.get('XAUUSDT'),
        oil=legs.get('CLUSDT'),
        fetched_at=datetime.now(timezone.utc),
    )


def get_commodity_snapshot(force_refresh: bool = False) -> Optional[CommoditySnapshot]:
    """
    Return the cached commodity (GLD+CL) snapshot. ``None`` only when the
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

        if snap.gold:
            logger.info(
                "Commodity snapshot refreshed: XAU close=%.2f above_ema20=%s "
                "ret_7d=%+.2f%% | CL %s",
                snap.gold.close, snap.gold.above_ema20, snap.gold.ret_7d,
                f"close={snap.oil.close:.2f}" if snap.oil else "leg=missing",
            )
        return snap
    except Exception as exc:
        logger.warning("Commodity snapshot fetch failed: %s", exc)
        with _lock:
            _state['expires_at'] = time.time() + _FAILURE_TTL_SECONDS
            return _state['snapshot']


def invalidate_commodity_snapshot_cache() -> None:
    """Drop the cached snapshot. Primarily for tests / forced reload."""
    with _lock:
        _state['snapshot'] = None
        _state['expires_at'] = 0.0
