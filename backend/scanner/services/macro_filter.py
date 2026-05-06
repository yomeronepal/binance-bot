"""
Direction-aware macro filter — gates Binance order placement (and tags
signals at creation) based on BTC's daily trend.

Pure function: ``evaluate_macro_filter(direction, snapshot=None)``.
No DB access. No Celery. No retries. Take a direction, take (or fetch)
a BTC snapshot, return ``(decision, reason)``.

Rules (matches the spec exactly, no quality flag check):

  LONG  → BTC must be above both EMA20 and EMA50, and 7d return >= 0
  SHORT → BTC must NOT be in the LONG uptrend regime above, and 3d
          return >= -7 (i.e. BTC isn't outright crashing)

The reason strings are stable identifiers; UI / analytics filter on
them, so do not rename without a migration of historical signal meta.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from .btc_trend import BTCSnapshot, get_btc_snapshot

logger = logging.getLogger(__name__)


# Stable reason codes — used in signal.meta and FuturesTradeLog. Treat
# as part of the public surface.
ALLOW_LONG = 'long_ok'
BLOCK_LONG_NOT_UPTREND = 'long_btc_not_uptrend'
BLOCK_LONG_7D_NEGATIVE = 'long_btc_7d_negative'

ALLOW_SHORT = 'short_ok'
BLOCK_SHORT_UPTREND = 'short_btc_uptrend'
BLOCK_SHORT_CRASHING = 'short_btc_crashing'

# Snapshot unavailable on the first ever fetch. Default policy is to
# allow the trade so a transient outage doesn't pause the bot — risk
# is symmetrical (we'd block correct AND wrong trades equally), but
# allowing matches "no signal = current behaviour".
ALLOW_SNAPSHOT_UNAVAILABLE = 'snapshot_unavailable_allow'

# Threshold constants — single source of truth so analytics/admin can
# read the exact values that gated the trade.
LONG_RET_7D_MIN = 0.0    # ret_7d must be >= this to allow LONG
SHORT_RET_3D_MIN = -7.0  # ret_3d must be >= this to allow SHORT


def evaluate_macro_filter(
    direction: str,
    snapshot: Optional[BTCSnapshot] = None,
) -> Tuple[str, str]:
    """
    Decide whether a signal of ``direction`` should be allowed given the
    current BTC daily trend snapshot.

    Args:
        direction: 'LONG' or 'SHORT' (case-insensitive). Anything else
            is allowed with reason 'unknown_direction' — keeps callers
            from accidentally blocking SPOT-only or paper trades.
        snapshot: Optional pre-fetched ``BTCSnapshot``. If omitted, the
            cached value from ``get_btc_snapshot()`` is used. Pass an
            explicit snapshot when stamping signals at creation so the
            stored ``meta['macro_at_signal']`` matches the decision
            reason in the same record.

    Returns:
        ``(decision, reason)``. ``decision`` is ``'ALLOW'`` or
        ``'BLOCK'``. ``reason`` is one of the module constants above.
    """
    direction = (direction or '').upper()

    if snapshot is None:
        snapshot = get_btc_snapshot()
    if snapshot is None:
        # First-ever fetch failed. Allow rather than silently block.
        return 'ALLOW', ALLOW_SNAPSHOT_UNAVAILABLE

    if direction == 'LONG':
        if not (snapshot.above_ema20 and snapshot.above_ema50):
            return 'BLOCK', BLOCK_LONG_NOT_UPTREND
        if snapshot.ret_7d < LONG_RET_7D_MIN:
            return 'BLOCK', BLOCK_LONG_7D_NEGATIVE
        return 'ALLOW', ALLOW_LONG

    if direction == 'SHORT':
        if snapshot.above_ema20 and snapshot.above_ema50:
            return 'BLOCK', BLOCK_SHORT_UPTREND
        if snapshot.ret_3d < SHORT_RET_3D_MIN:
            return 'BLOCK', BLOCK_SHORT_CRASHING
        return 'ALLOW', ALLOW_SHORT

    return 'ALLOW', 'unknown_direction'


def macro_summary(snapshot: Optional[BTCSnapshot] = None) -> dict:
    """
    Self-contained dict summarising what the filter would do *right now*
    for both directions. Powers the live admin readout panel and is
    safe to embed in any API response.
    """
    if snapshot is None:
        snapshot = get_btc_snapshot()
    long_decision, long_reason = evaluate_macro_filter('LONG', snapshot)
    short_decision, short_reason = evaluate_macro_filter('SHORT', snapshot)
    return {
        'snapshot': snapshot.to_dict() if snapshot else None,
        'long': {'decision': long_decision, 'reason': long_reason},
        'short': {'decision': short_decision, 'reason': short_reason},
        'thresholds': {
            'long_ret_7d_min': LONG_RET_7D_MIN,
            'short_ret_3d_min': SHORT_RET_3D_MIN,
        },
    }
