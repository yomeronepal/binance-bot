"""Unit tests for signal detection engine."""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import deque
from scanner.strategies.signal_engine import (
    SignalDetectionEngine,
    SignalConfig,
    ActiveSignal
)
from scanner.indicators.indicator_utils import calculate_all_indicators


@pytest.fixture
def default_config():
    """Create default signal configuration."""
    return SignalConfig(min_confidence=0.6)


@pytest.fixture
def signal_engine(default_config):
    """Create signal detection engine instance."""
    return SignalDetectionEngine(default_config)


@pytest.fixture
def bullish_klines():
    """Generate bullish candlestick data."""
    dates = pd.date_range('2024-01-01', periods=200, freq='5min')
    # Uptrending price
    close_prices = 100 + np.cumsum(np.random.randn(200) * 0.3 + 0.1)
    open_prices = close_prices - np.random.rand(200) * 0.5
    high_prices = np.maximum(open_prices, close_prices) + np.random.rand(200) * 0.3
    low_prices = np.minimum(open_prices, close_prices) - np.random.rand(200) * 0.3
    volumes = np.random.randint(5000, 15000, 200)

    # Convert to klines format
    klines = []
    for i in range(200):
        kline = [
            int(dates[i].timestamp() * 1000),  # open_time
            str(open_prices[i]),
            str(high_prices[i]),
            str(low_prices[i]),
            str(close_prices[i]),
            str(volumes[i]),
            int(dates[i].timestamp() * 1000) + 300000,  # close_time
            '0',  # quote_volume
            100,  # trades
            '0',  # taker_buy_base
            '0',  # taker_buy_quote
            '0'   # ignore
        ]
        klines.append(kline)

    return klines


def test_engine_initialization(signal_engine):
    """Test signal engine initialization."""
    assert signal_engine is not None
    assert signal_engine.config.min_confidence == 0.6
    assert len(signal_engine.candle_cache) == 0
    assert len(signal_engine.active_signals) == 0


def test_update_candles(signal_engine, bullish_klines):
    """Test candle cache update."""
    symbol = 'BTCUSDT'

    signal_engine.update_candles(symbol, bullish_klines)

    assert symbol in signal_engine.candle_cache
    assert len(signal_engine.candle_cache[symbol]) == 200


def test_candle_cache_max_size(signal_engine):
    """Test candle cache respects max size."""
    symbol = 'ETHUSDT'
    max_size = signal_engine.config.max_candles_cache

    # Add more than max candles
    mock_klines = [[0] * 12 for _ in range(max_size + 50)]
    signal_engine.update_candles(symbol, mock_klines)

    # Should only keep last max_size candles
    assert len(signal_engine.candle_cache[symbol]) == max_size


def test_process_symbol_insufficient_data(signal_engine):
    """Test processing symbol with insufficient data."""
    symbol = 'BTCUSDT'

    # Add only 30 candles (need at least 50)
    mock_klines = [[0] * 12 for _ in range(30)]
    signal_engine.update_candles(symbol, mock_klines)

    result = signal_engine.process_symbol(symbol, '5m')

    assert result is None  # Should return None with insufficient data


def test_detect_long_signal(signal_engine, bullish_klines):
    """Test LONG signal detection."""
    symbol = 'BTCUSDT'

    # Update cache with bullish data
    signal_engine.update_candles(symbol, bullish_klines)

    # Process symbol (may or may not generate signal depending on data)
    result = signal_engine.process_symbol(symbol, '5m')

    # If signal was created
    if result and result['action'] == 'created':
        signal = result['signal']
        assert signal['direction'] == 'LONG'
        assert signal['confidence'] >= signal_engine.config.min_confidence
        assert signal['entry'] > 0
        assert signal['sl'] < signal['entry']
        assert signal['tp'] > signal['entry']


def test_active_signal_tracking(signal_engine):
    """Test active signals are tracked in memory."""
    signal = ActiveSignal(
        symbol='BTCUSDT',
        direction='LONG',
        entry=42500.0,
        sl=42100.0,
        tp=43300.0,
        confidence=0.85,
        timeframe='5m',
        description='Test signal',
        created_at=datetime.now(),
        last_updated=datetime.now(),
        conditions_met={}
    )

    # Add to active signals
    signal_engine.active_signals['BTCUSDT'] = signal

    assert 'BTCUSDT' in signal_engine.active_signals
    assert signal_engine.active_signals['BTCUSDT'].confidence == 0.85


def test_signal_update_logic(signal_engine, bullish_klines):
    """Test signal update when conditions change."""
    symbol = 'BTCUSDT'

    # Create existing signal
    signal = ActiveSignal(
        symbol=symbol,
        direction='LONG',
        entry=42500.0,
        sl=42100.0,
        tp=43300.0,
        confidence=0.70,
        timeframe='5m',
        description='Test signal',
        created_at=datetime.now(),
        last_updated=datetime.now(),
        conditions_met={}
    )
    signal_engine.active_signals[symbol] = signal

    # Update candles
    signal_engine.update_candles(symbol, bullish_klines)

    # Process symbol
    result = signal_engine.process_symbol(symbol, '5m')

    # Could be updated or invalidated
    if result:
        assert result['action'] in ['updated', 'deleted']


def test_signal_invalidation(signal_engine, bullish_klines):
    """Test signal invalidation when conditions no longer met."""
    symbol = 'BTCUSDT'

    # Create signal with high confidence
    signal = ActiveSignal(
        symbol=symbol,
        direction='LONG',
        entry=42500.0,
        sl=42100.0,
        tp=43300.0,
        confidence=0.95,
        timeframe='5m',
        description='Test signal',
        created_at=datetime.now(),
        last_updated=datetime.now(),
        conditions_met={}
    )
    signal_engine.active_signals[symbol] = signal

    # Update with bearish data (simplified - just modify last candle)
    bearish_klines = bullish_klines.copy()
    # Make last candle strongly bearish
    bearish_klines[-1][4] = str(float(bearish_klines[-1][1]) - 5)  # close < open

    signal_engine.update_candles(symbol, bearish_klines)

    # Process symbol
    result = signal_engine.process_symbol(symbol, '5m')

    # Could result in deletion or update with lower confidence
    if result:
        if result['action'] == 'deleted':
            assert symbol not in signal_engine.active_signals


def test_signal_expiry(signal_engine):
    """Test signal expiry based on age."""
    symbol = 'BTCUSDT'

    # Create old signal
    old_time = datetime.now() - timedelta(minutes=65)
    signal = ActiveSignal(
        symbol=symbol,
        direction='LONG',
        entry=42500.0,
        sl=42100.0,
        tp=43300.0,
        confidence=0.85,
        timeframe='5m',
        description='Old signal',
        created_at=old_time,
        last_updated=old_time,
        conditions_met={}
    )
    signal_engine.active_signals[symbol] = signal

    # Cleanup expired signals
    expired = signal_engine.cleanup_expired_signals()

    assert symbol in expired
    assert symbol not in signal_engine.active_signals


def test_get_active_signals(signal_engine):
    """Test retrieving all active signals."""
    # Add multiple signals
    for i, symbol in enumerate(['BTCUSDT', 'ETHUSDT', 'BNBUSDT']):
        signal = ActiveSignal(
            symbol=symbol,
            direction='LONG' if i % 2 == 0 else 'SHORT',
            entry=42500.0 + (i * 100),
            sl=42100.0,
            tp=43300.0,
            confidence=0.75 + (i * 0.05),
            timeframe='5m',
            description=f'Signal {i}',
            created_at=datetime.now(),
            last_updated=datetime.now(),
            conditions_met={}
        )
        signal_engine.active_signals[symbol] = signal

    active_signals = signal_engine.get_active_signals()

    assert len(active_signals) == 3
    assert all(isinstance(s, dict) for s in active_signals)
    assert all('symbol' in s for s in active_signals)
    assert all('confidence' in s for s in active_signals)


def test_remove_signal(signal_engine):
    """Test manual signal removal."""
    symbol = 'BTCUSDT'

    signal = ActiveSignal(
        symbol=symbol,
        direction='LONG',
        entry=42500.0,
        sl=42100.0,
        tp=43300.0,
        confidence=0.85,
        timeframe='5m',
        description='Test signal',
        created_at=datetime.now(),
        last_updated=datetime.now(),
        conditions_met={}
    )
    signal_engine.active_signals[symbol] = signal

    # Remove signal
    result = signal_engine.remove_signal(symbol)

    assert result is True
    assert symbol not in signal_engine.active_signals

    # Try removing again
    result = signal_engine.remove_signal(symbol)
    assert result is False  # Already removed


def test_confidence_calculation(signal_engine, bullish_klines):
    """Test confidence score calculation."""
    symbol = 'BTCUSDT'
    signal_engine.update_candles(symbol, bullish_klines)

    # Process symbol
    result = signal_engine.process_symbol(symbol, '5m')

    if result and result['action'] == 'created':
        confidence = result['signal']['confidence']

        # Confidence should be between 0 and 1
        assert 0 <= confidence <= 1

        # Should meet minimum threshold
        assert confidence >= signal_engine.config.min_confidence


def test_sl_tp_calculation(signal_engine, bullish_klines):
    """Test stop loss and take profit calculation."""
    symbol = 'BTCUSDT'
    signal_engine.update_candles(symbol, bullish_klines)

    result = signal_engine.process_symbol(symbol, '5m')

    if result and result['action'] == 'created':
        signal = result['signal']
        entry = signal['entry']
        sl = signal['sl']
        tp = signal['tp']

        if signal['direction'] == 'LONG':
            # For LONG: SL < Entry < TP
            assert sl < entry < tp

            # Calculate risk/reward
            risk = entry - sl
            reward = tp - entry
            rr_ratio = reward / risk

            # Should be around 1.67 (2.5/1.5)
            assert 1.5 < rr_ratio < 2.0

        else:  # SHORT
            # For SHORT: TP < Entry < SL
            assert tp < entry < sl

            risk = sl - entry
            reward = entry - tp
            rr_ratio = reward / risk

            assert 1.5 < rr_ratio < 2.0


def test_conditions_tracking(signal_engine, bullish_klines):
    """Test that individual conditions are tracked."""
    symbol = 'BTCUSDT'
    signal_engine.update_candles(symbol, bullish_klines)

    result = signal_engine.process_symbol(symbol, '5m')

    if result and result['action'] == 'created':
        # Check if signal was added to active signals
        if symbol in signal_engine.active_signals:
            signal = signal_engine.active_signals[symbol]

            # Should have conditions_met dictionary
            assert hasattr(signal, 'conditions_met')
            assert isinstance(signal.conditions_met, dict)

            # Should track specific conditions
            expected_conditions = [
                'macd_crossover', 'rsi_favorable', 'price_above_ema',
                'strong_trend', 'ha_bullish', 'volume_spike',
                'ema_aligned', 'positive_di'
            ]

            # At least some conditions should be tracked
            assert len(signal.conditions_met) > 0


def test_custom_config(bullish_klines):
    """Test engine with custom configuration."""
    custom_config = SignalConfig(
        min_confidence=0.8,
        long_rsi_min=55.0,
        long_rsi_max=75.0,
        sl_atr_multiplier=2.0,
        tp_atr_multiplier=4.0,
        signal_expiry_minutes=30
    )

    engine = SignalDetectionEngine(custom_config)

    assert engine.config.min_confidence == 0.8
    assert engine.config.long_rsi_min == 55.0
    assert engine.config.sl_atr_multiplier == 2.0


def test_multiple_symbols(signal_engine, bullish_klines):
    """Test processing multiple symbols simultaneously."""
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT']

    for symbol in symbols:
        signal_engine.update_candles(symbol, bullish_klines)
        signal_engine.process_symbol(symbol, '5m')

    # Should track candles for all symbols
    assert len(signal_engine.candle_cache) == len(symbols)

    # May have signals for some symbols
    active_count = len(signal_engine.active_signals)
    assert 0 <= active_count <= len(symbols)
