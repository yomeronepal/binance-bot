"""Unit tests for the 4h swing entry rule (evaluate_swing)."""
from types import SimpleNamespace

import numpy as np
import pandas as pd

from scanner.strategies.swing_engine import evaluate_swing

CONFIG = SimpleNamespace(adx_min=20.0, breakout_lookback=20, sl_atr_mult=1.5, tp_atr_mult=3.0)


def _df(closes, spread=1.0):
    idx = pd.date_range('2024-01-01', periods=len(closes), freq='h')
    return pd.DataFrame({
        'open': closes,
        'high': [c + spread for c in closes],
        'low': [c - spread for c in closes],
        'close': closes,
        'volume': [1.0] * len(closes),
    }, index=idx)


def _uptrend_trend():
    return _df(list(np.linspace(100, 300, 210)))


def _downtrend_trend():
    return _df(list(np.linspace(300, 100, 210)))


def _range_then(last_close, spread=0.5):
    base = [200 + (0.5 if i % 2 else -0.5) for i in range(59)]
    return _df(base + [last_close], spread=spread)


def test_long_breakout_in_uptrend():
    sig = evaluate_swing(_range_then(210), _uptrend_trend(), CONFIG)
    assert sig is not None
    assert sig['direction'] == 'LONG'
    assert sig['stop_loss'] < sig['entry'] < sig['take_profit']
    assert abs(sig['entry'] - 210) < 1e-6


def test_short_breakdown_in_downtrend():
    sig = evaluate_swing(_range_then(190), _downtrend_trend(), CONFIG)
    assert sig is not None
    assert sig['direction'] == 'SHORT'
    assert sig['take_profit'] < sig['entry'] < sig['stop_loss']


def test_no_signal_without_breakout():
    assert evaluate_swing(_range_then(200), _uptrend_trend(), CONFIG) is None


def test_no_signal_without_trend():
    flat = _df([200.0] * 210)
    assert evaluate_swing(_range_then(210), flat, CONFIG) is None


def test_rr_matches_multiples():
    sig = evaluate_swing(_range_then(210), _uptrend_trend(), CONFIG)
    risk = sig['entry'] - sig['stop_loss']
    reward = sig['take_profit'] - sig['entry']
    assert abs(reward / risk - 2.0) < 1e-6
