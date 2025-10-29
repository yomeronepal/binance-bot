"""Unit tests for technical indicators."""
import pytest
import pandas as pd
import numpy as np
from scanner.indicators.indicator_utils import (
    calculate_rsi,
    calculate_macd,
    calculate_ema,
    calculate_atr,
    calculate_adx,
    calculate_bollinger_bands,
    calculate_heikin_ashi,
    calculate_all_indicators,
    detect_macd_crossover
)


@pytest.fixture
def sample_df():
    """Create sample OHLCV DataFrame for testing."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='5min')

    # Generate realistic price data
    close_prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    open_prices = close_prices + np.random.randn(100) * 0.2
    high_prices = np.maximum(open_prices, close_prices) + np.abs(np.random.randn(100) * 0.3)
    low_prices = np.minimum(open_prices, close_prices) - np.abs(np.random.randn(100) * 0.3)
    volumes = np.random.randint(1000, 10000, 100)

    df = pd.DataFrame({
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes
    }, index=dates)

    return df


def test_calculate_rsi(sample_df):
    """Test RSI calculation."""
    rsi = calculate_rsi(sample_df, period=14)

    # RSI should be between 0 and 100
    assert (rsi >= 0).all() or rsi.isna().all()
    assert (rsi <= 100).all() or rsi.isna().all()

    # First 14 values should be NaN (warm-up period)
    assert rsi.iloc[:14].isna().sum() > 0


def test_calculate_macd(sample_df):
    """Test MACD calculation."""
    macd, signal, hist = calculate_macd(sample_df)

    # All series should have same length
    assert len(macd) == len(signal) == len(hist) == len(sample_df)

    # Histogram should be macd - signal
    np.testing.assert_array_almost_equal(
        macd.values - signal.values,
        hist.values,
        decimal=10
    )


def test_calculate_ema(sample_df):
    """Test EMA calculation."""
    ema_20 = calculate_ema(sample_df, 20)

    # EMA should have same length as input
    assert len(ema_20) == len(sample_df)

    # EMA should not have extreme jumps
    ema_diff = ema_20.diff().abs()
    assert ema_diff.max() < sample_df['close'].std() * 3


def test_calculate_atr(sample_df):
    """Test ATR calculation."""
    atr = calculate_atr(sample_df, period=14)

    # ATR should be positive
    assert (atr >= 0).all() or atr.isna().all()

    # ATR should be reasonable (less than price range)
    price_range = sample_df['high'].max() - sample_df['low'].min()
    assert atr.max() < price_range


def test_calculate_adx(sample_df):
    """Test ADX calculation."""
    adx, plus_di, minus_di = calculate_adx(sample_df, period=14)

    # ADX should be between 0 and 100
    assert (adx >= 0).all() or adx.isna().all()
    assert (adx <= 100).all() or adx.isna().all()

    # DI lines should also be between 0 and 100
    assert (plus_di >= 0).all() or plus_di.isna().all()
    assert (minus_di >= 0).all() or minus_di.isna().all()


def test_calculate_bollinger_bands(sample_df):
    """Test Bollinger Bands calculation."""
    upper, middle, lower = calculate_bollinger_bands(sample_df, period=20, std_dev=2.0)

    # Upper should be above middle, middle above lower
    assert (upper >= middle).all() or upper.isna().all()
    assert (middle >= lower).all() or middle.isna().all()

    # Middle band should be close to SMA
    sma = sample_df['close'].rolling(window=20).mean()
    np.testing.assert_array_almost_equal(
        middle.dropna().values,
        sma.dropna().values,
        decimal=10
    )


def test_calculate_heikin_ashi(sample_df):
    """Test Heikin Ashi calculation."""
    ha_df = calculate_heikin_ashi(sample_df)

    # Should have HA columns
    assert 'ha_open' in ha_df.columns
    assert 'ha_high' in ha_df.columns
    assert 'ha_low' in ha_df.columns
    assert 'ha_close' in ha_df.columns

    # HA high should be max of high, ha_open, ha_close
    for i in range(len(ha_df)):
        assert ha_df['ha_high'].iloc[i] >= ha_df['ha_open'].iloc[i]
        assert ha_df['ha_high'].iloc[i] >= ha_df['ha_close'].iloc[i]


def test_calculate_all_indicators(sample_df):
    """Test calculation of all indicators at once."""
    df_with_indicators = calculate_all_indicators(sample_df)

    # Check that all expected indicators are present
    expected_columns = [
        'rsi', 'macd', 'macd_signal', 'macd_hist',
        'ema_9', 'ema_21', 'ema_50', 'ema_200',
        'atr', 'adx', 'plus_di', 'minus_di',
        'bb_upper', 'bb_middle', 'bb_lower',
        'ha_open', 'ha_high', 'ha_low', 'ha_close', 'ha_bullish',
        'volume_trend'
    ]

    for col in expected_columns:
        assert col in df_with_indicators.columns, f"Missing column: {col}"


def test_detect_macd_crossover():
    """Test MACD crossover detection."""
    # Create test data with known crossover
    dates = pd.date_range('2024-01-01', periods=10, freq='5min')

    # Bullish crossover (hist goes from negative to positive)
    df_bullish = pd.DataFrame({
        'macd_hist': [-1, -0.5, -0.1, 0.1, 0.5]
    }, index=dates[:5])

    assert detect_macd_crossover(df_bullish) == 'bullish'

    # Bearish crossover (hist goes from positive to negative)
    df_bearish = pd.DataFrame({
        'macd_hist': [1, 0.5, 0.1, -0.1, -0.5]
    }, index=dates[:5])

    assert detect_macd_crossover(df_bearish) == 'bearish'

    # No crossover
    df_none = pd.DataFrame({
        'macd_hist': [1, 1.1, 1.2, 1.3, 1.4]
    }, index=dates[:5])

    assert detect_macd_crossover(df_none) == 'none'


def test_indicators_with_insufficient_data():
    """Test indicators with insufficient data."""
    # Create small DataFrame with only 10 rows
    small_df = pd.DataFrame({
        'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        'high': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
        'low': [99, 100, 101, 102, 103, 104, 105, 106, 107, 108],
        'close': [100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5, 107.5, 108.5, 109.5],
        'volume': [1000] * 10
    })

    # Should still work but with NaN values
    rsi = calculate_rsi(small_df, period=14)
    assert rsi.isna().sum() > 0  # Should have NaN values


def test_ema_200_with_insufficient_data():
    """Test EMA 200 with less than 200 data points."""
    small_df = pd.DataFrame({
        'close': np.random.randn(100) + 100
    })

    ema_200 = calculate_ema(small_df, 200)

    # Should have values but many will be NaN at the beginning
    assert len(ema_200) == 100
    assert ema_200.isna().sum() > 0
