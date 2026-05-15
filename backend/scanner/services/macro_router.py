"""
Asset-class-aware macro filter router.

Trading signals fall into three asset classes (CRYPTO / STOCK /
COMMODITY) and each has its own regime proxy:

  CRYPTO     → BTCUSDT          (macro_filter / btc_trend)
  STOCK      → SPYUSDT          (equity_filter / equity_trend)
  COMMODITY  → XAUUSDT          (commodity_filter / commodity_trend)

Both the signal-creation tagger and the trade-boundary gate need to
pick the correct proxy at runtime. Centralising that here keeps the
two call sites identical, prevents drift if a new asset class ever
gets added, and gives the meta payload a uniform shape so analytics
queries on ``signal.meta.macro_at_signal`` don't have to branch on
asset_class.

Pure dispatch — no DB writes, no Celery. Snapshot fetch failures
return ``ALLOW`` + ``snapshot_unavailable_*`` reason so a transient
network blip never pauses the bot.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from .asset_classifier import classify_symbol

logger = logging.getLogger(__name__)


def _meta_payload(asset_class, regime_symbol, decision, reason, leg, snap):
    """
    Build the ``macro_at_signal`` meta dict in a uniform shape.

    ``leg`` is the per-symbol snapshot (BTCSnapshot, EquityLeg, or
    CommodityLeg). For BTC the leg and the parent snapshot are the
    same object; for equity/commodity ``leg`` is the gating sub-leg
    (SPY for equity, XAU for commodity).
    """
    return {
        'asset_class': asset_class,
        'regime_symbol': regime_symbol,
        'decision': decision,
        'reason': reason,
        'above_ema7': bool(leg.above_ema7) if leg is not None else None,
        'above_ema20': bool(leg.above_ema20) if leg is not None else None,
        'ret_3d': float(leg.ret_3d) if leg is not None else None,
        'ret_7d': float(leg.ret_7d) if leg is not None else None,
        'regime_close': float(leg.close) if leg is not None else None,
        'fetched_at': snap.fetched_at.isoformat() if snap is not None else None,
    }


def evaluate_for_symbol(
    symbol: str,
    direction: str,
    asset_class: Optional[str] = None,
) -> Tuple[str, str, dict]:
    """
    Pick the correct macro filter for ``symbol`` and evaluate
    ``direction``.

    Args:
        symbol: Trading-pair string. Used to classify when
            ``asset_class`` is not supplied.
        direction: 'LONG' or 'SHORT'.
        asset_class: Optional pre-resolved asset class. Pass this when
            you already know it (e.g. from a Signal row) to skip the
            classifier round-trip.

    Returns:
        ``(decision, reason, meta_payload)``. ``decision`` is 'ALLOW'
        or 'BLOCK'. ``meta_payload`` is suitable for stamping into
        ``signal.meta.macro_at_signal``.
    """
    asset_class = (asset_class or classify_symbol(symbol)).upper()

    if asset_class == 'STOCK':
        from .equity_trend import get_equity_snapshot
        from .equity_filter import evaluate_equity_filter
        snap = get_equity_snapshot()
        decision, reason = evaluate_equity_filter(direction, snapshot=snap)
        leg = snap.spy if snap else None
        meta = _meta_payload('STOCK', 'SPYUSDT', decision, reason, leg, snap)
        return decision, reason, meta

    if asset_class == 'COMMODITY':
        from .commodity_trend import get_commodity_snapshot
        from .commodity_filter import evaluate_commodity_filter
        snap = get_commodity_snapshot()
        decision, reason = evaluate_commodity_filter(direction, snapshot=snap)
        leg = snap.gold if snap else None
        meta = _meta_payload('COMMODITY', 'XAUUSDT', decision, reason, leg, snap)
        return decision, reason, meta

    from .btc_trend import get_btc_snapshot
    from .macro_filter import evaluate_macro_filter
    snap = get_btc_snapshot()
    decision, reason = evaluate_macro_filter(direction, snapshot=snap)
    meta = _meta_payload('CRYPTO', 'BTCUSDT', decision, reason, snap, snap)
    if snap is not None:
        meta['btc_close'] = float(snap.close)
    return decision, reason, meta
