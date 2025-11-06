"""
Technical indicator computation utilities.
Uses pandas and ta library for indicator calculations.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


def klines_to_dataframe(klines: List[List]) -> pd.DataFrame:
    """
    Convert Binance klines to pandas DataFrame.
    
    Args:
        klines: List of klines from Binance API
    
    Returns:
        DataFrame with OHLCV data
    """
    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    
    # Convert to appropriate types
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
    
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    
    df.set_index('open_time', inplace=True)
    return df


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (RSI)."""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_macd(
    df: pd.DataFrame,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD (Moving Average Convergence Divergence)."""
    exp1 = df['close'].ewm(span=fast_period, adjust=False).mean()
    exp2 = df['close'].ewm(span=slow_period, adjust=False).mean()
    
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def calculate_ema(df: pd.DataFrame, period: int) -> pd.Series:
    """Calculate Exponential Moving Average (EMA)."""
    return df['close'].ewm(span=period, adjust=False).mean()


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR)."""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()
    
    return atr


def calculate_adx(df: pd.DataFrame, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Average Directional Index (ADX) and DI lines."""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    plus_dm = df['high'].diff()
    minus_dm = -df['low'].diff()
    
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    atr = true_range.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    
    return adx, plus_di, minus_di


def calculate_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands."""
    middle_band = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    
    return upper_band, middle_band, lower_band


def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Heikin Ashi candles."""
    ha_df = df.copy()

    ha_df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4

    # Calculate ha_open using vectorized operations
    ha_open = [0.0] * len(ha_df)
    ha_open[0] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2

    for i in range(1, len(ha_df)):
        ha_open[i] = (ha_open[i-1] + ha_df['ha_close'].iloc[i-1]) / 2

    ha_df['ha_open'] = ha_open

    ha_df['ha_high'] = ha_df[['high', 'ha_open', 'ha_close']].max(axis=1)
    ha_df['ha_low'] = ha_df[['low', 'ha_open', 'ha_close']].min(axis=1)

    return ha_df


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all technical indicators for a DataFrame."""
    result_df = df.copy()

    try:
        result_df['rsi'] = calculate_rsi(df, period=14)

        macd, signal, hist = calculate_macd(df)
        result_df['macd'] = macd
        result_df['macd_signal'] = signal
        result_df['macd_hist'] = hist

        result_df['ema_9'] = calculate_ema(df, 9)
        result_df['ema_21'] = calculate_ema(df, 21)
        result_df['ema_50'] = calculate_ema(df, 50)
        result_df['ema_200'] = calculate_ema(df, 200)

        result_df['atr'] = calculate_atr(df, period=14)

        adx, plus_di, minus_di = calculate_adx(df, period=14)
        result_df['adx'] = adx
        result_df['plus_di'] = plus_di
        result_df['minus_di'] = minus_di

        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df, period=20, std_dev=2.0)
        result_df['bb_upper'] = bb_upper
        result_df['bb_middle'] = bb_middle
        result_df['bb_lower'] = bb_lower

        ha_df = calculate_heikin_ashi(df)
        result_df['ha_open'] = ha_df['ha_open']
        result_df['ha_high'] = ha_df['ha_high']
        result_df['ha_low'] = ha_df['ha_low']
        result_df['ha_close'] = ha_df['ha_close']
        result_df['ha_bullish'] = ha_df['ha_close'] > ha_df['ha_open']

        result_df['volume_trend'] = df['volume'] / df['volume'].rolling(window=20).mean()

        # NEW INDICATORS
        # SuperTrend
        supertrend, st_direction = calculate_supertrend(df, period=10, multiplier=3.0)
        result_df['supertrend'] = supertrend
        result_df['supertrend_direction'] = st_direction  # 1 = bullish, -1 = bearish

        # Money Flow Index (MFI)
        result_df['mfi'] = calculate_mfi(df, period=14)

        # Parabolic SAR
        result_df['psar'] = calculate_parabolic_sar(df, acceleration=0.02, maximum=0.2)
        result_df['psar_bullish'] = df['close'] > result_df['psar']  # Price above SAR = bullish

        logger.debug("Calculated all indicators successfully (including SuperTrend, MFI, PSAR)")

    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        raise

    return result_df


def calculate_supertrend(
    df: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0
) -> Tuple[pd.Series, pd.Series]:
    """
    Calculate SuperTrend indicator.

    Args:
        df: DataFrame with OHLC data
        period: ATR period (default 10)
        multiplier: ATR multiplier (default 3.0)

    Returns:
        Tuple of (supertrend, direction) where direction is 1 (bullish) or -1 (bearish)
    """
    hl2 = (df['high'] + df['low']) / 2
    atr = calculate_atr(df, period=period)

    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)

    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=float)

    # Initialize
    supertrend.iloc[0] = upper_band.iloc[0]
    direction.iloc[0] = 1

    for i in range(1, len(df)):
        # Calculate final bands
        if df['close'].iloc[i] > upper_band.iloc[i-1]:
            direction.iloc[i] = 1
        elif df['close'].iloc[i] < lower_band.iloc[i-1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i-1]

            # Adjust bands if direction hasn't changed
            if direction.iloc[i] == 1:
                lower_band.iloc[i] = max(lower_band.iloc[i], lower_band.iloc[i-1])
            else:
                upper_band.iloc[i] = min(upper_band.iloc[i], upper_band.iloc[i-1])

        # Set supertrend value
        if direction.iloc[i] == 1:
            supertrend.iloc[i] = lower_band.iloc[i]
        else:
            supertrend.iloc[i] = upper_band.iloc[i]

    return supertrend, direction


def calculate_mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Money Flow Index (MFI) - Volume-weighted RSI.

    Args:
        df: DataFrame with OHLCV data
        period: Lookback period (default 14)

    Returns:
        Series with MFI values (0-100)
    """
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['volume']

    # Identify positive and negative money flow
    positive_flow = pd.Series(0.0, index=df.index)
    negative_flow = pd.Series(0.0, index=df.index)

    for i in range(1, len(df)):
        if typical_price.iloc[i] > typical_price.iloc[i-1]:
            positive_flow.iloc[i] = money_flow.iloc[i]
        elif typical_price.iloc[i] < typical_price.iloc[i-1]:
            negative_flow.iloc[i] = money_flow.iloc[i]

    # Calculate money flow ratio
    positive_mf_sum = positive_flow.rolling(window=period).sum()
    negative_mf_sum = negative_flow.rolling(window=period).sum()

    mfi = 100 - (100 / (1 + (positive_mf_sum / negative_mf_sum.replace(0, 1e-10))))

    return mfi


def calculate_parabolic_sar(
    df: pd.DataFrame,
    acceleration: float = 0.02,
    maximum: float = 0.2
) -> pd.Series:
    """
    Calculate Parabolic SAR (Stop and Reverse).

    Args:
        df: DataFrame with OHLC data
        acceleration: Acceleration factor (default 0.02)
        maximum: Maximum acceleration (default 0.2)

    Returns:
        Series with SAR values
    """
    sar = pd.Series(index=df.index, dtype=float)
    trend = pd.Series(index=df.index, dtype=int)  # 1 for uptrend, -1 for downtrend
    ep = pd.Series(index=df.index, dtype=float)  # Extreme point
    af = pd.Series(index=df.index, dtype=float)  # Acceleration factor

    # Initialize
    sar.iloc[0] = df['low'].iloc[0]
    trend.iloc[0] = 1
    ep.iloc[0] = df['high'].iloc[0]
    af.iloc[0] = acceleration

    for i in range(1, len(df)):
        # Calculate SAR for current period
        sar.iloc[i] = sar.iloc[i-1] + af.iloc[i-1] * (ep.iloc[i-1] - sar.iloc[i-1])

        # Uptrend
        if trend.iloc[i-1] == 1:
            # Check for reversal
            if df['low'].iloc[i] < sar.iloc[i]:
                trend.iloc[i] = -1
                sar.iloc[i] = ep.iloc[i-1]
                ep.iloc[i] = df['low'].iloc[i]
                af.iloc[i] = acceleration
            else:
                trend.iloc[i] = 1
                # Update extreme point
                if df['high'].iloc[i] > ep.iloc[i-1]:
                    ep.iloc[i] = df['high'].iloc[i]
                    af.iloc[i] = min(af.iloc[i-1] + acceleration, maximum)
                else:
                    ep.iloc[i] = ep.iloc[i-1]
                    af.iloc[i] = af.iloc[i-1]

                # SAR should not be above prior two lows
                sar.iloc[i] = min(sar.iloc[i], df['low'].iloc[i-1])
                if i > 1:
                    sar.iloc[i] = min(sar.iloc[i], df['low'].iloc[i-2])

        # Downtrend
        else:
            # Check for reversal
            if df['high'].iloc[i] > sar.iloc[i]:
                trend.iloc[i] = 1
                sar.iloc[i] = ep.iloc[i-1]
                ep.iloc[i] = df['high'].iloc[i]
                af.iloc[i] = acceleration
            else:
                trend.iloc[i] = -1
                # Update extreme point
                if df['low'].iloc[i] < ep.iloc[i-1]:
                    ep.iloc[i] = df['low'].iloc[i]
                    af.iloc[i] = min(af.iloc[i-1] + acceleration, maximum)
                else:
                    ep.iloc[i] = ep.iloc[i-1]
                    af.iloc[i] = af.iloc[i-1]

                # SAR should not be below prior two highs
                sar.iloc[i] = max(sar.iloc[i], df['high'].iloc[i-1])
                if i > 1:
                    sar.iloc[i] = max(sar.iloc[i], df['high'].iloc[i-2])

    return sar


def detect_macd_crossover(df: pd.DataFrame) -> str:
    """Detect MACD crossover. Returns 'bullish', 'bearish', or 'none'."""
    if len(df) < 2:
        return 'none'

    current_hist = df['macd_hist'].iloc[-1]
    previous_hist = df['macd_hist'].iloc[-2]

    if previous_hist <= 0 and current_hist > 0:
        return 'bullish'
    elif previous_hist >= 0 and current_hist < 0:
        return 'bearish'

    return 'none'
