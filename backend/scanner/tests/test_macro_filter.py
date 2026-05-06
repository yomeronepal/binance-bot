"""
Unit tests for the BTC macro filter chain.

Two layers under test:

  1. ``btc_trend._compute_snapshot_from_closes`` — pure transform of a
     closes list into a BTCSnapshot. No network, no cache.
  2. ``macro_filter.evaluate_macro_filter`` — pure function from
     (direction, snapshot) -> (decision, reason). No network.

A third layer (the cached ``get_btc_snapshot()`` and the live BTC
fetch) is exercised end-to-end on the running server via a Django
shell smoke script — see the docstring at the bottom of this file.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from scanner.services.btc_trend import (
    BTCSnapshot,
    _compute_snapshot_from_closes,
    invalidate_btc_snapshot_cache,
)
from scanner.services.macro_filter import (
    ALLOW_LONG,
    ALLOW_SHORT,
    ALLOW_SNAPSHOT_UNAVAILABLE,
    BLOCK_LONG_NOT_UPTREND,
    BLOCK_LONG_7D_NEGATIVE,
    BLOCK_SHORT_CRASHING,
    BLOCK_SHORT_UPTREND,
    LONG_RET_7D_MIN,
    SHORT_RET_3D_MIN,
    evaluate_macro_filter,
    macro_summary,
)


# ---------------------------------------------------------------------------
# Snapshot-shape factory — keeps each test focused on the dimension it cares
# about by overriding only the fields under examination.
# ---------------------------------------------------------------------------

def _snap(
    *,
    above_ema20=True,
    above_ema50=True,
    ret_3d=0.0,
    ret_7d=0.0,
    close=100_000.0,
    ema20=99_000.0,
    ema50=95_000.0,
):
    return BTCSnapshot(
        close=close,
        ema20=ema20,
        ema50=ema50,
        above_ema20=above_ema20,
        above_ema50=above_ema50,
        ret_3d=ret_3d,
        ret_7d=ret_7d,
        fetched_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# evaluate_macro_filter — six branches
# ---------------------------------------------------------------------------

class TestEvaluateMacroFilterLong:
    """LONG branch: must be above both EMAs AND ret_7d >= 0."""

    def test_uptrend_with_positive_7d_allows(self):
        snap = _snap(above_ema20=True, above_ema50=True, ret_7d=4.2)
        decision, reason = evaluate_macro_filter('LONG', snap)
        assert decision == 'ALLOW'
        assert reason == ALLOW_LONG

    def test_uptrend_with_zero_7d_allows_at_boundary(self):
        # ret_7d == 0 is the boundary. Spec says ``>= 0`` allows.
        snap = _snap(above_ema20=True, above_ema50=True, ret_7d=0.0)
        decision, _ = evaluate_macro_filter('LONG', snap)
        assert decision == 'ALLOW'

    def test_uptrend_with_negative_7d_blocks(self):
        snap = _snap(above_ema20=True, above_ema50=True, ret_7d=-0.01)
        decision, reason = evaluate_macro_filter('LONG', snap)
        assert decision == 'BLOCK'
        assert reason == BLOCK_LONG_7D_NEGATIVE

    def test_below_ema20_blocks(self):
        snap = _snap(above_ema20=False, above_ema50=True, ret_7d=5.0)
        decision, reason = evaluate_macro_filter('LONG', snap)
        assert decision == 'BLOCK'
        assert reason == BLOCK_LONG_NOT_UPTREND

    def test_below_ema50_blocks(self):
        snap = _snap(above_ema20=True, above_ema50=False, ret_7d=5.0)
        decision, reason = evaluate_macro_filter('LONG', snap)
        assert decision == 'BLOCK'
        assert reason == BLOCK_LONG_NOT_UPTREND

    def test_below_both_emas_blocks_with_uptrend_reason(self):
        # Even when 7d return is also bad, the EMA gate fires first.
        # Reason should be 'long_btc_not_uptrend' for predictable
        # downstream analytics.
        snap = _snap(above_ema20=False, above_ema50=False, ret_7d=-5.0)
        decision, reason = evaluate_macro_filter('LONG', snap)
        assert decision == 'BLOCK'
        assert reason == BLOCK_LONG_NOT_UPTREND


class TestEvaluateMacroFilterShort:
    """SHORT branch: must NOT be in uptrend AND ret_3d >= -7."""

    def test_downtrend_with_mild_drop_allows(self):
        snap = _snap(above_ema20=False, above_ema50=False, ret_3d=-3.0)
        decision, reason = evaluate_macro_filter('SHORT', snap)
        assert decision == 'ALLOW'
        assert reason == ALLOW_SHORT

    def test_above_ema20_only_allows_short_if_below_ema50_block(self):
        # Mixed: above EMA20, below EMA50 — does NOT count as full uptrend
        # (uptrend requires BOTH). So SHORT is allowed if 3d return is OK.
        snap = _snap(above_ema20=True, above_ema50=False, ret_3d=-2.0)
        decision, _ = evaluate_macro_filter('SHORT', snap)
        assert decision == 'ALLOW'

    def test_uptrend_blocks(self):
        snap = _snap(above_ema20=True, above_ema50=True, ret_3d=-3.0)
        decision, reason = evaluate_macro_filter('SHORT', snap)
        assert decision == 'BLOCK'
        assert reason == BLOCK_SHORT_UPTREND

    def test_3d_at_boundary_minus7_allows(self):
        # ret_3d == -7 is the boundary. Spec ``>= -7`` allows.
        snap = _snap(above_ema20=False, above_ema50=False, ret_3d=-7.0)
        decision, _ = evaluate_macro_filter('SHORT', snap)
        assert decision == 'ALLOW'

    def test_3d_below_minus7_blocks(self):
        snap = _snap(above_ema20=False, above_ema50=False, ret_3d=-7.01)
        decision, reason = evaluate_macro_filter('SHORT', snap)
        assert decision == 'BLOCK'
        assert reason == BLOCK_SHORT_CRASHING

    def test_uptrend_overrides_crashing_check(self):
        # If uptrend is true, that's the BLOCK reason regardless of 3d.
        # (Wouldn't actually happen — uptrend with ret_3d=-9 is unlikely —
        # but the predicate must be deterministic.)
        snap = _snap(above_ema20=True, above_ema50=True, ret_3d=-9.0)
        decision, reason = evaluate_macro_filter('SHORT', snap)
        assert decision == 'BLOCK'
        assert reason == BLOCK_SHORT_UPTREND


class TestEvaluateMacroFilterFallbacks:

    def test_unknown_direction_allows(self):
        snap = _snap()
        decision, reason = evaluate_macro_filter('OTHER', snap)
        assert decision == 'ALLOW'
        assert reason == 'unknown_direction'

    def test_lowercase_direction_normalised(self):
        snap = _snap(above_ema20=True, above_ema50=True, ret_7d=1.0)
        decision, _ = evaluate_macro_filter('long', snap)
        assert decision == 'ALLOW'

    def test_none_direction_allows(self):
        decision, reason = evaluate_macro_filter(None, _snap())
        assert decision == 'ALLOW'
        assert reason == 'unknown_direction'

    @patch('scanner.services.macro_filter.get_btc_snapshot', return_value=None)
    def test_snapshot_unavailable_fails_open(self, _mock):
        # When the very first fetch fails and there's no cached value,
        # caller should treat as "allow rather than block silently".
        decision, reason = evaluate_macro_filter('LONG', None)
        assert decision == 'ALLOW'
        assert reason == ALLOW_SNAPSHOT_UNAVAILABLE


class TestThresholdConstants:
    """Reason codes and thresholds are part of the public contract — they
    appear in stored signal.meta and in FuturesTradeLog. Failing this test
    means downstream analytics/UI need updating in lockstep."""

    def test_threshold_values_match_spec(self):
        assert LONG_RET_7D_MIN == 0.0
        assert SHORT_RET_3D_MIN == -7.0

    def test_reason_codes_are_stable_strings(self):
        assert ALLOW_LONG == 'long_ok'
        assert BLOCK_LONG_NOT_UPTREND == 'long_btc_not_uptrend'
        assert BLOCK_LONG_7D_NEGATIVE == 'long_btc_7d_negative'
        assert ALLOW_SHORT == 'short_ok'
        assert BLOCK_SHORT_UPTREND == 'short_btc_uptrend'
        assert BLOCK_SHORT_CRASHING == 'short_btc_crashing'


# ---------------------------------------------------------------------------
# _compute_snapshot_from_closes — pure transform under test
# ---------------------------------------------------------------------------

class TestSnapshotComputation:

    def test_returns_btc_snapshot_with_all_fields(self):
        # 60 closes climbing linearly — easy to reason about.
        closes = [100.0 + i for i in range(60)]   # 100..159
        snap = _compute_snapshot_from_closes(closes)
        assert isinstance(snap, BTCSnapshot)
        assert snap.close == 159.0
        assert snap.ema20 < snap.close  # rising series, EMA lags
        assert snap.ema50 < snap.ema20
        assert snap.above_ema20 is True
        assert snap.above_ema50 is True

    def test_uptrend_returns_positive_for_rising_series(self):
        closes = [100.0 + i for i in range(60)]
        snap = _compute_snapshot_from_closes(closes)
        # ret_3d: 159 vs 156 (3 days back) -> +1.92%
        assert snap.ret_3d == pytest.approx((159 / 156 - 1) * 100, rel=1e-3)
        # ret_7d: 159 vs 152 -> +4.61%
        assert snap.ret_7d == pytest.approx((159 / 152 - 1) * 100, rel=1e-3)

    def test_downtrend_returns_negative(self):
        closes = [200.0 - i for i in range(60)]   # 200..141
        snap = _compute_snapshot_from_closes(closes)
        assert snap.ret_3d < 0
        assert snap.ret_7d < 0
        assert snap.above_ema20 is False
        assert snap.above_ema50 is False

    def test_handles_below_ema_correctly(self):
        # Series that drops sharply at the end — recent close below EMAs.
        closes = [200.0] * 50 + [100.0] * 5
        snap = _compute_snapshot_from_closes(closes)
        assert snap.close == 100.0
        assert snap.ema20 > 100.0  # EMA still elevated from prior 200s
        assert snap.ema50 > 100.0
        assert snap.above_ema20 is False
        assert snap.above_ema50 is False

    def test_short_history_returns_zero_when_lookback_unavailable(self):
        # Only 4 candles — ret_7d would need index -8 which doesn't exist.
        # Should not raise; return 0.0.
        closes = [100.0, 101.0, 102.0, 103.0]
        snap = _compute_snapshot_from_closes(closes)
        assert snap.ret_7d == 0.0
        assert snap.ret_3d == pytest.approx((103 / 100 - 1) * 100, rel=1e-3)

    def test_zero_prior_close_returns_zero_safely(self):
        # Edge: division by zero protection.
        closes = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 100.0]
        snap = _compute_snapshot_from_closes(closes)
        assert snap.ret_7d == 0.0   # would have divided by 0 otherwise


# ---------------------------------------------------------------------------
# macro_summary — feeds the live readout endpoint
# ---------------------------------------------------------------------------

class TestMacroSummary:

    def test_summary_includes_both_directions_and_thresholds(self):
        snap = _snap(above_ema20=True, above_ema50=True, ret_7d=2.0, ret_3d=-1.0)
        summary = macro_summary(snap)
        assert 'snapshot' in summary
        assert summary['long']['decision'] == 'ALLOW'
        assert summary['short']['decision'] == 'BLOCK'   # uptrend blocks SHORT
        assert summary['short']['reason'] == BLOCK_SHORT_UPTREND
        assert summary['thresholds']['long_ret_7d_min'] == 0.0
        assert summary['thresholds']['short_ret_3d_min'] == -7.0

    @patch('scanner.services.macro_filter.get_btc_snapshot', return_value=None)
    def test_summary_handles_unavailable_snapshot(self, _mock):
        summary = macro_summary()
        assert summary['snapshot'] is None
        assert summary['long']['decision'] == 'ALLOW'
        assert summary['long']['reason'] == ALLOW_SNAPSHOT_UNAVAILABLE


# ---------------------------------------------------------------------------
# Cache hygiene — keep tests order-independent.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _bust_cache_around_each_test():
    invalidate_btc_snapshot_cache()
    yield
    invalidate_btc_snapshot_cache()


# ---------------------------------------------------------------------------
# End-to-end smoke (live server). Run inside the prod web container:
#
#     docker exec binancebot_web_prod python manage.py shell -c "
#     from scanner.services.btc_trend import get_btc_snapshot, invalidate_btc_snapshot_cache
#     from scanner.services.macro_filter import evaluate_macro_filter, macro_summary
#     invalidate_btc_snapshot_cache()
#     snap = get_btc_snapshot(force_refresh=True)
#     assert snap is not None, 'BTC fetch returned None — network / Binance issue'
#     print('snapshot:', snap)
#     print('long:', evaluate_macro_filter('LONG'))
#     print('short:', evaluate_macro_filter('SHORT'))
#     print('summary:', macro_summary())
#     "
#
# Expect: snapshot is a BTCSnapshot dataclass with non-zero close, both
# decisions are ALLOW or BLOCK with stable reason codes, summary dict
# has snapshot/long/short/thresholds keys.
# ---------------------------------------------------------------------------
