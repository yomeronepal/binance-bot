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


def _snap(
    *,
    above_ema7=True,
    above_ema20=True,
    ret_3d=0.0,
    ret_7d=0.0,
    close=100_000.0,
    ema7=99_500.0,
    ema20=99_000.0,
):
    """
    Snapshot factory used by the macro-filter branch tests.

    Defaults reflect a benign uptrend regime; each test overrides only
    the dimension(s) it cares about. The fast/slow EMA split mirrors
    BTCSnapshot — ``above_ema7`` is the *fast* leg, ``above_ema20`` is
    the *slow* leg.
    """
    return BTCSnapshot(
        close=close,
        ema7=ema7,
        ema20=ema20,
        above_ema7=above_ema7,
        above_ema20=above_ema20,
        ret_3d=ret_3d,
        ret_7d=ret_7d,
        fetched_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
    )


class TestEvaluateMacroFilterLong:
    """LONG branch: must be above both EMAs AND ret_7d >= 0."""

    def test_uptrend_with_positive_7d_allows(self):
        snap = _snap(above_ema7=True, above_ema20=True, ret_7d=4.2)
        decision, reason = evaluate_macro_filter('LONG', snap)
        assert decision == 'ALLOW'
        assert reason == ALLOW_LONG

    def test_uptrend_with_zero_7d_allows_at_boundary(self):
        snap = _snap(above_ema7=True, above_ema20=True, ret_7d=0.0)
        decision, _ = evaluate_macro_filter('LONG', snap)
        assert decision == 'ALLOW'

    def test_uptrend_with_negative_7d_blocks(self):
        snap = _snap(above_ema7=True, above_ema20=True, ret_7d=-0.01)
        decision, reason = evaluate_macro_filter('LONG', snap)
        assert decision == 'BLOCK'
        assert reason == BLOCK_LONG_7D_NEGATIVE

    def test_below_ema7_blocks(self):
        snap = _snap(above_ema7=False, above_ema20=True, ret_7d=5.0)
        decision, reason = evaluate_macro_filter('LONG', snap)
        assert decision == 'BLOCK'
        assert reason == BLOCK_LONG_NOT_UPTREND

    def test_below_ema20_blocks(self):
        snap = _snap(above_ema7=True, above_ema20=False, ret_7d=5.0)
        decision, reason = evaluate_macro_filter('LONG', snap)
        assert decision == 'BLOCK'
        assert reason == BLOCK_LONG_NOT_UPTREND

    def test_below_both_emas_blocks_with_uptrend_reason(self):
        snap = _snap(above_ema7=False, above_ema20=False, ret_7d=-5.0)
        decision, reason = evaluate_macro_filter('LONG', snap)
        assert decision == 'BLOCK'
        assert reason == BLOCK_LONG_NOT_UPTREND


class TestEvaluateMacroFilterShort:
    """SHORT branch: must NOT be in uptrend AND ret_3d >= -7."""

    def test_downtrend_with_mild_drop_allows(self):
        snap = _snap(above_ema7=False, above_ema20=False, ret_3d=-3.0)
        decision, reason = evaluate_macro_filter('SHORT', snap)
        assert decision == 'ALLOW'
        assert reason == ALLOW_SHORT

    def test_above_ema7_only_allows_short_if_below_ema20(self):
        snap = _snap(above_ema7=True, above_ema20=False, ret_3d=-2.0)
        decision, _ = evaluate_macro_filter('SHORT', snap)
        assert decision == 'ALLOW'

    def test_uptrend_blocks(self):
        snap = _snap(above_ema7=True, above_ema20=True, ret_3d=-3.0)
        decision, reason = evaluate_macro_filter('SHORT', snap)
        assert decision == 'BLOCK'
        assert reason == BLOCK_SHORT_UPTREND

    def test_3d_at_boundary_minus7_allows(self):
        snap = _snap(above_ema7=False, above_ema20=False, ret_3d=-7.0)
        decision, _ = evaluate_macro_filter('SHORT', snap)
        assert decision == 'ALLOW'

    def test_3d_below_minus7_blocks(self):
        snap = _snap(above_ema7=False, above_ema20=False, ret_3d=-7.01)
        decision, reason = evaluate_macro_filter('SHORT', snap)
        assert decision == 'BLOCK'
        assert reason == BLOCK_SHORT_CRASHING

    def test_uptrend_overrides_crashing_check(self):
        snap = _snap(above_ema7=True, above_ema20=True, ret_3d=-9.0)
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
        snap = _snap(above_ema7=True, above_ema20=True, ret_7d=1.0)
        decision, _ = evaluate_macro_filter('long', snap)
        assert decision == 'ALLOW'

    def test_none_direction_allows(self):
        decision, reason = evaluate_macro_filter(None, _snap())
        assert decision == 'ALLOW'
        assert reason == 'unknown_direction'

    @patch('scanner.services.macro_filter.get_btc_snapshot', return_value=None)
    def test_snapshot_unavailable_fails_open(self, _mock):
        decision, reason = evaluate_macro_filter('LONG', None)
        assert decision == 'ALLOW'
        assert reason == ALLOW_SNAPSHOT_UNAVAILABLE


class TestThresholdConstants:

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


class TestSnapshotComputation:

    def test_returns_btc_snapshot_with_all_fields(self):
        closes = [100.0 + i for i in range(60)]
        snap = _compute_snapshot_from_closes(closes)
        assert isinstance(snap, BTCSnapshot)
        assert snap.close == 159.0
        assert snap.ema7 < snap.close
        assert snap.ema20 < snap.ema7
        assert snap.above_ema7 is True
        assert snap.above_ema20 is True

    def test_uptrend_returns_positive_for_rising_series(self):
        closes = [100.0 + i for i in range(60)]
        snap = _compute_snapshot_from_closes(closes)
        assert snap.ret_3d == pytest.approx((159 / 156 - 1) * 100, rel=1e-3)
        assert snap.ret_7d == pytest.approx((159 / 152 - 1) * 100, rel=1e-3)

    def test_downtrend_returns_negative(self):
        closes = [200.0 - i for i in range(60)]
        snap = _compute_snapshot_from_closes(closes)
        assert snap.ret_3d < 0
        assert snap.ret_7d < 0
        assert snap.above_ema7 is False
        assert snap.above_ema20 is False

    def test_handles_below_ema_correctly(self):
        closes = [200.0] * 50 + [100.0] * 5
        snap = _compute_snapshot_from_closes(closes)
        assert snap.close == 100.0
        assert snap.ema7 > 100.0
        assert snap.ema20 > 100.0
        assert snap.above_ema7 is False
        assert snap.above_ema20 is False

    def test_short_history_returns_zero_when_lookback_unavailable(self):
        closes = [100.0, 101.0, 102.0, 103.0]
        snap = _compute_snapshot_from_closes(closes)
        assert snap.ret_7d == 0.0
        assert snap.ret_3d == pytest.approx((103 / 100 - 1) * 100, rel=1e-3)

    def test_zero_prior_close_returns_zero_safely(self):
        closes = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 100.0]
        snap = _compute_snapshot_from_closes(closes)
        assert snap.ret_7d == 0.0


class TestMacroSummary:

    def test_summary_includes_both_directions_and_thresholds(self):
        snap = _snap(above_ema7=True, above_ema20=True, ret_7d=2.0, ret_3d=-1.0)
        summary = macro_summary(snap)
        assert 'snapshot' in summary
        assert summary['long']['decision'] == 'ALLOW'
        assert summary['short']['decision'] == 'BLOCK'
        assert summary['short']['reason'] == BLOCK_SHORT_UPTREND
        assert summary['thresholds']['long_ret_7d_min'] == 0.0
        assert summary['thresholds']['short_ret_3d_min'] == -7.0

    @patch('scanner.services.macro_filter.get_btc_snapshot', return_value=None)
    def test_summary_handles_unavailable_snapshot(self, _mock):
        summary = macro_summary()
        assert summary['snapshot'] is None
        assert summary['long']['decision'] == 'ALLOW'
        assert summary['long']['reason'] == ALLOW_SNAPSHOT_UNAVAILABLE


class _FakeSettings:
    def __init__(self, enabled=True):
        self.macro_filter_enabled = enabled


class TestTradeGateRespectsToggle:
    """``FuturesTradingSettings.macro_filter_enabled`` controls whether the
    strict trade-time gate runs. When OFF, _check_macro_filter must
    short-circuit to True without consulting the BTC snapshot."""

    def _log_ctx(self, direction='LONG'):
        return {'signal': None, 'symbol': 'X', 'direction': direction,
                'is_priority': True, 'force_execute': True}

    def _signal_stub(self):
        class _S:
            id = 0
        return _S()

    def test_gate_bypasses_when_disabled(self):
        from signals.services.futures_trader import futures_trading_service

        with patch.object(
            type(futures_trading_service), '_log', return_value=None,
        ), patch(
            'signals.services.futures_trader.FuturesTradingSettings.get_settings',
            return_value=_FakeSettings(enabled=False),
        ), patch(
            'scanner.services.macro_filter.evaluate_macro_filter',
            return_value=('BLOCK', 'long_btc_not_uptrend'),
        ) as eval_mock:
            ok = futures_trading_service._check_macro_filter(
                self._signal_stub(), 'LONG', self._log_ctx(),
            )
        assert ok is True
        assert eval_mock.called is False, (
            "Toggle off must short-circuit before evaluate_macro_filter runs"
        )

    def test_gate_evaluates_when_enabled_and_allow(self):
        from signals.services.futures_trader import futures_trading_service

        with patch(
            'signals.services.futures_trader.FuturesTradingSettings.get_settings',
            return_value=_FakeSettings(enabled=True),
        ), patch(
            'scanner.services.macro_filter.evaluate_macro_filter',
            return_value=('ALLOW', 'long_ok'),
        ) as eval_mock:
            ok = futures_trading_service._check_macro_filter(
                self._signal_stub(), 'LONG', self._log_ctx(),
            )
        assert ok is True
        assert eval_mock.called is True

    def test_gate_blocks_when_enabled_and_filter_blocks(self):
        from signals.services.futures_trader import futures_trading_service

        with patch.object(
            type(futures_trading_service), '_log', return_value=None,
        ), patch(
            'signals.services.futures_trader.FuturesTradingSettings.get_settings',
            return_value=_FakeSettings(enabled=True),
        ), patch(
            'scanner.services.macro_filter.evaluate_macro_filter',
            return_value=('BLOCK', 'long_btc_7d_negative'),
        ):
            ok = futures_trading_service._check_macro_filter(
                self._signal_stub(), 'LONG', self._log_ctx(),
            )
        assert ok is False

    def test_gate_fails_open_on_settings_lookup_error(self):
        """A DB hiccup on settings lookup must not pause trading."""
        from signals.services.futures_trader import futures_trading_service

        with patch(
            'signals.services.futures_trader.FuturesTradingSettings.get_settings',
            side_effect=RuntimeError('DB down'),
        ), patch(
            'scanner.services.macro_filter.evaluate_macro_filter',
            return_value=('BLOCK', 'long_btc_not_uptrend'),
        ) as eval_mock:
            ok = futures_trading_service._check_macro_filter(
                self._signal_stub(), 'LONG', self._log_ctx(),
            )
        assert ok is True
        assert eval_mock.called is False


@pytest.fixture(autouse=True)
def _bust_cache_around_each_test():
    invalidate_btc_snapshot_cache()
    yield
    invalidate_btc_snapshot_cache()
