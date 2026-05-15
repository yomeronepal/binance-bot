"""
Direction-aware commodity macro filter — analog of macro_filter.py
for the COMMODITY asset class. Gates commodity signals based on
XAU (gold) daily trend.

Pure function: ``evaluate_commodity_filter(direction, snapshot=None)``.

Rules mirror the BTC and equity filters, with XAU as the regime proxy:

  LONG  → XAU must be above both EMA7 and EMA20, AND 7d return >=
          LONG_RET_7D_MIN (-2.0 %).
  SHORT → XAU must NOT be in a confirmed uptrend (above both EMAs
          with positive 7d), AND XAU isn't crashing (3d return >=
          SHORT_RET_3D_MIN, -7 %).

CL (WTI oil) data is fetched alongside XAU for the widget but isn't
used by the filter — gold leads broad commodity sentiment more
reliably than any single energy ticker, and an AND-gate on both
would over-constrain mixed-regime periods.

Reason strings are stable identifiers; do not rename without a
migration of historical signal meta.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from .commodity_trend import CommoditySnapshot, get_commodity_snapshot

logger = logging.getLogger(__name__)


ALLOW_LONG = 'commodity_long_ok'
BLOCK_LONG_NOT_UPTREND = 'commodity_long_xau_not_uptrend'
BLOCK_LONG_7D_NEGATIVE = 'commodity_long_xau_7d_too_negative'

ALLOW_SHORT = 'commodity_short_ok'
BLOCK_SHORT_UPTREND = 'commodity_short_xau_uptrend'
BLOCK_SHORT_CRASHING = 'commodity_short_xau_crashing'

ALLOW_SNAPSHOT_UNAVAILABLE = 'commodity_snapshot_unavailable_allow'

LONG_RET_7D_MIN = -2.0
SHORT_RET_3D_MIN = -7.0
SHORT_BLOCK_RET_7D_MIN = 0.0


def evaluate_commodity_filter(
    direction: str,
    snapshot: Optional[CommoditySnapshot] = None,
) -> Tuple[str, str]:
    """
    Decide whether a commodity signal of ``direction`` should be allowed
    given XAU's current daily trend.

    Returns:
        (decision, reason). decision is 'ALLOW' or 'BLOCK'.
    """
    direction = (direction or '').upper()

    if snapshot is None:
        snapshot = get_commodity_snapshot()
    if snapshot is None or snapshot.gold is None:
        return 'ALLOW', ALLOW_SNAPSHOT_UNAVAILABLE

    gold = snapshot.gold

    if direction == 'LONG':
        if not (gold.above_ema7 and gold.above_ema20):
            return 'BLOCK', BLOCK_LONG_NOT_UPTREND
        if gold.ret_7d < LONG_RET_7D_MIN:
            return 'BLOCK', BLOCK_LONG_7D_NEGATIVE
        return 'ALLOW', ALLOW_LONG

    if direction == 'SHORT':
        in_uptrend = gold.above_ema7 and gold.above_ema20
        if in_uptrend and gold.ret_7d > SHORT_BLOCK_RET_7D_MIN:
            return 'BLOCK', BLOCK_SHORT_UPTREND
        if gold.ret_3d < SHORT_RET_3D_MIN:
            return 'BLOCK', BLOCK_SHORT_CRASHING
        return 'ALLOW', ALLOW_SHORT

    return 'ALLOW', 'unknown_direction'


def commodity_macro_summary(snapshot: Optional[CommoditySnapshot] = None) -> dict:
    """
    Self-contained dict summarising what the commodity filter would do
    *right now* for both directions.
    """
    if snapshot is None:
        snapshot = get_commodity_snapshot()
    long_decision, long_reason = evaluate_commodity_filter('LONG', snapshot)
    short_decision, short_reason = evaluate_commodity_filter('SHORT', snapshot)
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
