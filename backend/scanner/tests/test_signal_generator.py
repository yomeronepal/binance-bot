"""Unit tests for signal generation strategy."""
import pytest
import pandas as pd
import numpy as np
from decimal import Decimal
from scanner.strategies.signal_generator import SignalGenerator
from scanner.indicators.indicator_utils import calculate_all_indicators


@pytest.fixture
def signal_generator():
    """Create signal generator instance."""
    return SignalGenerator(min_confidence=0.6)


@pytest.fixture
def bullish_setup_df():
    """Create DataFrame with bullish setup."""
    dates = pd.date_range('2024-01-01', periods=200, freq='5min')

    # Create uptrending price data
    close_prices = 100 + np.cumsum(np.random.randn(200) * 0.3 + 0.1)  # Upward bias
    open_prices = close_prices - np.random.rand(200) * 0.5
    high_prices = np.maximum(open_prices, close_prices) + np.random.rand(200) * 0.3
    low_prices = np.minimum(open_prices, close_prices) - np.random.rand(200) * 0.3
    volumes = np.random.randint(5000, 15000, 200)  # Higher volume

    df = pd.DataFrame({
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes
    }, index=dates)

    # Calculate all indicators
    df = calculate_all_indicators(df)

    # Manually set last row to have strong bullish signals
    df.loc[df.index[-1], 'rsi'] = 60  # Bullish RSI
    df.loc[df.index[-1], 'macd_hist'] = 0.5  # Positive MACD
    df.loc[df.index[-2], 'macd_hist'] = -0.1  # Previous negative (crossover)
    df.loc[df.index[-1], 'adx'] = 25  # Strong trend
    df.loc[df.index[-1], 'ha_bullish'] = True  # Heikin Ashi bullish
    df.loc[df.index[-1], 'volume_trend'] = 1.5  # High volume
    df.loc[df.index[-1], 'plus_di'] = 30
    df.loc[df.index[-1], 'minus_di'] = 15

    # Ensure price > EMA50
    df.loc[df.index[-1], 'close'] = df.loc[df.index[-1], 'ema_50'] + 5

    return df


@pytest.fixture
def bearish_setup_df():
    """Create DataFrame with bearish setup."""
    dates = pd.date_range('2024-01-01', periods=200, freq='5min')

    # Create downtrending price data
    close_prices = 100 - np.cumsum(np.random.randn(200) * 0.3 + 0.1)  # Downward bias
    open_prices = close_prices + np.random.rand(200) * 0.5
    high_prices = np.maximum(open_prices, close_prices) + np.random.rand(200) * 0.3
    low_prices = np.minimum(open_prices, close_prices) - np.random.rand(200) * 0.3
    volumes = np.random.randint(5000, 15000, 200)

    df = pd.DataFrame({
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes
    }, index=dates)

    # Calculate all indicators
    df = calculate_all_indicators(df)

    # Manually set last row to have strong bearish signals
    df.loc[df.index[-1], 'rsi'] = 40  # Bearish RSI
    df.loc[df.index[-1], 'macd_hist'] = -0.5  # Negative MACD
    df.loc[df.index[-2], 'macd_hist'] = 0.1  # Previous positive (crossover)
    df.loc[df.index[-1], 'adx'] = 25  # Strong trend
    df.loc[df.index[-1], 'ha_bullish'] = False  # Heikin Ashi bearish
    df.loc[df.index[-1], 'volume_trend'] = 1.5  # High volume
    df.loc[df.index[-1], 'plus_di'] = 15
    df.loc[df.index[-1], 'minus_di'] = 30

    # Ensure price < EMA50
    df.loc[df.index[-1], 'close'] = df.loc[df.index[-1], 'ema_50'] - 5

    return df


def test_generate_long_signal(signal_generator, bullish_setup_df):
    """Test LONG signal generation."""
    signal = signal_generator.generate_signal('BTCUSDT', bullish_setup_df, '5m')

    assert signal is not None
    assert signal['symbol'] == 'BTCUSDT'
    assert signal['direction'] == 'LONG'
    assert signal['timeframe'] == '5m'

    # Check price levels
    assert isinstance(signal['entry'], Decimal)
    assert isinstance(signal['sl'], Decimal)
    assert isinstance(signal['tp'], Decimal)

    # SL should be below entry, TP above entry
    assert signal['sl'] < signal['entry']
    assert signal['tp'] > signal['entry']

    # Confidence should be in valid range
    assert 0 <= signal['confidence'] <= 1
    assert signal['confidence'] >= signal_generator.min_confidence

    # Should have description
    assert 'description' in signal
    assert len(signal['description']) > 0


def test_generate_short_signal(signal_generator, bearish_setup_df):
    """Test SHORT signal generation."""
    signal = signal_generator.generate_signal('ETHUSDT', bearish_setup_df, '15m')

    assert signal is not None
    assert signal['symbol'] == 'ETHUSDT'
    assert signal['direction'] == 'SHORT'
    assert signal['timeframe'] == '15m'

    # Check price levels
    assert isinstance(signal['entry'], Decimal)
    assert isinstance(signal['sl'], Decimal)
    assert isinstance(signal['tp'], Decimal)

    # SL should be above entry, TP below entry
    assert signal['sl'] > signal['entry']
    assert signal['tp'] < signal['entry']

    # Confidence should be in valid range
    assert 0 <= signal['confidence'] <= 1
    assert signal['confidence'] >= signal_generator.min_confidence


def test_no_signal_with_weak_setup(signal_generator):
    """Test that no signal is generated with weak setup."""
    # Create neutral/weak setup
    dates = pd.date_range('2024-01-01', periods=200, freq='5min')
    close_prices = 100 + np.random.randn(200) * 0.1  # No clear trend

    df = pd.DataFrame({
        'open': close_prices,
        'high': close_prices + 0.5,
        'low': close_prices - 0.5,
        'close': close_prices,
        'volume': [5000] * 200
    }, index=dates)

    df = calculate_all_indicators(df)

    # Set neutral indicators
    df.loc[df.index[-1], 'rsi'] = 50
    df.loc[df.index[-1], 'macd_hist'] = 0
    df.loc[df.index[-1], 'adx'] = 15  # Weak trend
    df.loc[df.index[-1], 'volume_trend'] = 0.8  # Low volume

    signal = signal_generator.generate_signal('BTCUSDT', df, '5m')

    assert signal is None  # No signal should be generated


def test_confidence_threshold(bullish_setup_df):
    """Test that confidence threshold is respected."""
    # High threshold - should not generate signal
    high_threshold_gen = SignalGenerator(min_confidence=0.95)
    signal = high_threshold_gen.generate_signal('BTCUSDT', bullish_setup_df, '5m')

    # Might not generate signal with very high threshold
    if signal:
        assert signal['confidence'] >= 0.95

    # Low threshold - should generate signal
    low_threshold_gen = SignalGenerator(min_confidence=0.3)
    signal = low_threshold_gen.generate_signal('BTCUSDT', bullish_setup_df, '5m')

    assert signal is not None
    assert signal['confidence'] >= 0.3


def test_atr_based_levels(signal_generator, bullish_setup_df):
    """Test that SL and TP are based on ATR."""
    signal = signal_generator.generate_signal('BTCUSDT', bullish_setup_df, '5m')

    if signal:
        atr = float(bullish_setup_df.iloc[-1]['atr'])
        entry = float(signal['entry'])
        sl = float(signal['sl'])
        tp = float(signal['tp'])

        if signal['direction'] == 'LONG':
            # Check SL is ~1.5 ATR below entry
            sl_distance = entry - sl
            assert 0.5 * atr < sl_distance < 2.5 * atr

            # Check TP is ~2.5 ATR above entry
            tp_distance = tp - entry
            assert 1.5 * atr < tp_distance < 3.5 * atr


def test_signal_with_insufficient_data(signal_generator):
    """Test signal generation with insufficient data."""
    # Create very small DataFrame
    small_df = pd.DataFrame({
        'close': [100, 101]
    })

    signal = signal_generator.generate_signal('BTCUSDT', small_df, '5m')

    assert signal is None  # Should return None with insufficient data


def test_risk_reward_ratio(signal_generator, bullish_setup_df):
    """Test that risk/reward ratio is reasonable."""
    signal = signal_generator.generate_signal('BTCUSDT', bullish_setup_df, '5m')

    if signal:
        entry = float(signal['entry'])
        sl = float(signal['sl'])
        tp = float(signal['tp'])

        if signal['direction'] == 'LONG':
            risk = entry - sl
            reward = tp - entry
        else:
            risk = sl - entry
            reward = entry - tp

        # R:R should be positive and reasonable (should be ~1.67)
        rr_ratio = reward / risk if risk > 0 else 0
        assert rr_ratio > 0
        assert 1.0 < rr_ratio < 5.0  # Reasonable range


def test_signal_description_content(signal_generator, bullish_setup_df):
    """Test that signal description contains relevant info."""
    signal = signal_generator.generate_signal('BTCUSDT', bullish_setup_df, '5m')

    if signal:
        description = signal['description'].lower()

        # Should mention direction
        if signal['direction'] == 'LONG':
            assert 'bullish' in description or 'long' in description.lower()
        else:
            assert 'bearish' in description or 'short' in description.lower()


def test_multiple_signals_different_symbols(signal_generator, bullish_setup_df):
    """Test generating signals for multiple symbols."""
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    signals = []

    for symbol in symbols:
        signal = signal_generator.generate_signal(symbol, bullish_setup_df, '5m')
        if signal:
            signals.append(signal)

    # All signals should be for different symbols
    signal_symbols = [s['symbol'] for s in signals]
    assert len(set(signal_symbols)) == len(signals)
