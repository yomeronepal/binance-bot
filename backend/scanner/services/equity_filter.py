"""
Direction-aware equity macro filter — analog of macro_filter.py for
the TRADIFI lane. Gates stock/equity signals based on SPY's daily
trend.

Pure function: ``evaluate_equity_filter(direction, snapshot=None)``.
No DB access. No Celery. No retries.

Rules mirror the BTC filter, with SPY as the regime proxy:

  LONG  → SPY must be above both EMA7 and EMA20, AND 7d return >=
          LONG_RET_7D_MIN (-2.0 %). Allows mild weekly pullbacks
          while the daily trend is still up.
  SHORT → SPY must NOT be in a confirmed uptrend (defined as above
          both EMAs with positive 7d), AND SPY isn't outright
          crashing (3d return >= SHORT_RET_3D_MIN, -7 %).

QQQ data is fetched alongside SPY for the widget but isn't used by
the filter — broad-market (SPY) regime gates tech-heavy names just
as well, and adding a second AND-gate would over-constrain.

Reason strings are stable identifiers; do not rename without a
migration of historical signal meta.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from .equity_trend import EquitySnapshot, get_equity_snapshot

logger = logging.getLogger(__name__)


ALLOW_LONG = 'equity_long_ok'
BLOCK_LONG_NOT_UPTREND = 'equity_long_spy_not_uptrend'
BLOCK_LONG_7D_NEGATIVE = 'equity_long_spy_7d_too_negative'

ALLOW_SHORT = 'equity_short_ok'
BLOCK_SHORT_UPTREND = 'equity_short_spy_uptrend'
BLOCK_SHORT_CRASHING = 'equity_short_spy_crashing'

ALLOW_SNAPSHOT_UNAVAILABLE = 'equity_snapshot_unavailable_allow'

LONG_RET_7D_MIN = -2.0
SHORT_RET_3D_MIN = -7.0
SHORT_BLOCK_RET_7D_MIN = 0.0


def evaluate_equity_filter(
    direction: str,
    snapshot: Optional[EquitySnapshot] = None,
) -> Tuple[str, str]:
    """
    Decide whether a stock signal of ``direction`` should be allowed
    given SPY's current daily trend.

    Args:
        direction: 'LONG' or 'SHORT' (case-insensitive). Anything else
            returns ('ALLOW', 'unknown_direction').
        snapshot: Optional pre-fetched EquitySnapshot. If omitted, the
            cached value from get_equity_snapshot() is used.

    Returns:
        (decision, reason). decision is 'ALLOW' or 'BLOCK'.
    """
    direction = (direction or '').upper()

    if snapshot is None:
        snapshot = get_equity_snapshot()
    if snapshot is None or snapshot.spy is None:
        return 'ALLOW', ALLOW_SNAPSHOT_UNAVAILABLE

    spy = snapshot.spy

    if direction == 'LONG':
        if not (spy.above_ema7 and spy.above_ema20):
            return 'BLOCK', BLOCK_LONG_NOT_UPTREND
        if spy.ret_7d < LONG_RET_7D_MIN:
            return 'BLOCK', BLOCK_LONG_7D_NEGATIVE
        return 'ALLOW', ALLOW_LONG

    if direction == 'SHORT':
        in_uptrend = spy.above_ema7 and spy.above_ema20
        if in_uptrend and spy.ret_7d > SHORT_BLOCK_RET_7D_MIN:
            return 'BLOCK', BLOCK_SHORT_UPTREND
        if spy.ret_3d < SHORT_RET_3D_MIN:
            return 'BLOCK', BLOCK_SHORT_CRASHING
        return 'ALLOW', ALLOW_SHORT

    return 'ALLOW', 'unknown_direction'


def equity_macro_summary(snapshot: Optional[EquitySnapshot] = None) -> dict:
    """
    Self-contained dict summarising what the equity filter would do
    *right now* for both directions. Powers the public widget readout.
    """
    if snapshot is None:
        snapshot = get_equity_snapshot()
    long_decision, long_reason = evaluate_equity_filter('LONG', snapshot)
    short_decision, short_reason = evaluate_equity_filter('SHORT', snapshot)
    return {
        'snapshot': snapshot.to_dict() if snapshot else None,
        'long': {'decision': long_decision, 'reason': long_reason},
        'short': {'decision': short_decision, 'reason': short_reason},
        'thresholds': {
            'long_ret_7d_min': LONG_RET_7D_MIN,
            'short_ret_3d_min': SHORT_RET_3D_MIN,
            'short_block_ret_7d_min': SHORT_BLOCK_RET_7D_MIN,
        },
    }
