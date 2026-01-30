"""
Fibonacci Pullback Utility Module

Provides swing detection, Fibonacci retracement level calculation,
and pullback zone validation for trading signals.
"""
import logging
from typing import Dict, Tuple, Optional
import pandas as pd
from decimal import Decimal

logger = logging.getLogger(__name__)


def find_recent_swing_high_low(
    df: pd.DataFrame,
    lookback: int = 50,
    direction: str = 'LONG'
) -> Tuple[Optional[float], Optional[float]]:
    """
    Find the most recent swing high and swing low within lookback period.

    A swing high is a local maximum (peak) where the price is higher than
    both adjacent candles. A swing low is a local minimum (valley).

    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        lookback: Number of candles to search back
        direction: 'LONG' or 'SHORT' (determines which swing is more recent)

    Returns:
        (swing_high, swing_low) tuple, or (None, None) if not found
    """
    if len(df) < 5:
        logger.warning(f"Not enough candles ({len(df)}) to detect swings")
        return None, None

    recent_df = df.tail(lookback).copy()

    swing_high = None
    swing_low = None

    for i in range(1, len(recent_df) - 1):
        current_high = recent_df.iloc[i]['high']
        current_low = recent_df.iloc[i]['low']

        prev_high = recent_df.iloc[i - 1]['high']
        next_high = recent_df.iloc[i + 1]['high']

        prev_low = recent_df.iloc[i - 1]['low']
        next_low = recent_df.iloc[i + 1]['low']

        if current_high > prev_high and current_high > next_high:
            swing_high = float(current_high)

        if current_low < prev_low and current_low < next_low:
            swing_low = float(current_low)

    if swing_high is None or swing_low is None:
        logger.debug(f"Could not find swing high/low in {lookback} candles")
        return None, None

    logger.debug(f"Found swings - High: {swing_high}, Low: {swing_low}")
    return swing_high, swing_low


def compute_fib_levels(
    swing_high: float,
    swing_low: float,
    direction: str = 'LONG'
) -> Dict[str, float]:
    """
    Calculate Fibonacci retracement levels.

    For LONG (bullish retracement):
    - Swing: From swing_low → swing_high (uptrend)
    - Retracement: Price pulls back from swing_high toward swing_low
    - Levels calculated from swing_high downward

    For SHORT (bearish retracement):
    - Swing: From swing_high → swing_low (downtrend)
    - Retracement: Price bounces from swing_low toward swing_high
    - Levels calculated from swing_low upward

    Args:
        swing_high: Recent swing high price
        swing_low: Recent swing low price
        direction: 'LONG' or 'SHORT'

    Returns:
        Dictionary with Fibonacci levels:
        {
            'level_0': ...,      # 0% (swing high/low)
            'level_23_6': ...,   # 23.6%
            'level_38_2': ...,   # 38.2%
            'level_50': ...,     # 50%
            'level_61_8': ...,   # 61.8% (Golden Ratio)
            'level_78_6': ...,   # 78.6%
            'level_100': ...,    # 100% (opposite swing)
            'swing_high': ...,
            'swing_low': ...,
            'direction': ...
        }
    """
    swing_range = swing_high - swing_low

    if direction == 'LONG':
        levels = {
            'level_0': swing_high,
            'level_23_6': swing_high - (swing_range * 0.236),
            'level_38_2': swing_high - (swing_range * 0.382),
            'level_50': swing_high - (swing_range * 0.5),
            'level_61_8': swing_high - (swing_range * 0.618),
            'level_78_6': swing_high - (swing_range * 0.786),
            'level_100': swing_low,
        }
    else:
        levels = {
            'level_0': swing_low,
            'level_23_6': swing_low + (swing_range * 0.236),
            'level_38_2': swing_low + (swing_range * 0.382),
            'level_50': swing_low + (swing_range * 0.5),
            'level_61_8': swing_low + (swing_range * 0.618),
            'level_78_6': swing_low + (swing_range * 0.786),
            'level_100': swing_high,
        }

    levels.update({
        'swing_high': swing_high,
        'swing_low': swing_low,
        'direction': direction,
        'swing_range': swing_range
    })

    return levels


def check_fibonacci_pullback(
    df: pd.DataFrame,
    current: pd.Series,
    direction: str,
    lookback: int = 50,
    entry_zone_min: float = 0.5,
    entry_zone_max: float = 0.618,
    symbol: str = None
) -> Tuple[bool, Dict]:
    """
    Check if current price is in Fibonacci pullback entry zone.

    Entry Zone (Golden Ratio): Between 50% and 61.8% retracement levels.

    Args:
        df: Historical price DataFrame
        current: Current candle (latest row)
        direction: 'LONG' or 'SHORT'
        lookback: Candles to search for swing high/low
        entry_zone_min: Minimum Fib level for entry (0.5 = 50%)
        entry_zone_max: Maximum Fib level for entry (0.618 = 61.8%)
        symbol: Symbol name for logging

    Returns:
        (valid: bool, fib_data: Dict) tuple
        - valid: True if price is in entry zone
        - fib_data: Fibonacci levels and metadata
    """
    swing_high, swing_low = find_recent_swing_high_low(df, lookback, direction)

    if swing_high is None or swing_low is None:
        return False, {}

    if swing_high <= swing_low:
        logger.warning(f"{symbol or 'Unknown'}: Invalid swings - high={swing_high} <= low={swing_low}")
        return False, {}

    fib_levels = compute_fib_levels(swing_high, swing_low, direction)

    current_price = float(current['close'])

    fib_50 = fib_levels['level_50']
    fib_618 = fib_levels['level_61_8']
    fib_786 = fib_levels['level_78_6']

    in_entry_zone = False
    pullback_depth = 0.0

    if direction == 'LONG':
        if fib_618 <= current_price <= fib_50:
            in_entry_zone = True

        if swing_high != current_price:
            pullback_depth = ((swing_high - current_price) / (swing_high - swing_low)) * 100

    else:
        if fib_50 <= current_price <= fib_618:
            in_entry_zone = True

        if current_price != swing_low:
            pullback_depth = ((current_price - swing_low) / (swing_high - swing_low)) * 100

    fib_data = {
        'swing_high': swing_high,
        'swing_low': swing_low,
        'fib_23_6': fib_levels['level_23_6'],
        'fib_38_2': fib_levels['level_38_2'],
        'fib_50': fib_50,
        'fib_61_8': fib_618,
        'fib_78_6': fib_786,
        'current_price': current_price,
        'in_entry_zone': in_entry_zone,
        'pullback_depth': round(pullback_depth, 2),
        'entry_zone': 'golden_ratio' if in_entry_zone else 'outside_zone',
        'direction': direction
    }

    if in_entry_zone:
        logger.info(
            f"✅ Fibonacci pullback detected ({direction}): "
            f"Price {current_price:.2f} in zone [{fib_618:.2f} - {fib_50:.2f}], "
            f"Pullback depth: {pullback_depth:.1f}%"
        )
    else:
        logger.debug(
            f"Price {current_price:.2f} outside entry zone "
            f"[{fib_618:.2f} - {fib_50:.2f}]"
        )

    return in_entry_zone, fib_data


def calculate_fib_extension_targets(
    swing_high: float,
    swing_low: float,
    direction: str
) -> Dict[str, float]:
    """
    Calculate Fibonacci extension levels for take-profit targets.

    Extension levels project beyond the swing range to estimate
    where the price might reach after breaking out.

    Args:
        swing_high: Recent swing high
        swing_low: Recent swing low
        direction: 'LONG' or 'SHORT'

    Returns:
        Dictionary with extension levels:
        {
            'ext_1_0': 100% extension
            'ext_1_272': 127.2% extension
            'ext_1_618': 161.8% extension (golden ratio)
            'ext_2_0': 200% extension
        }
    """
    swing_range = swing_high - swing_low

    if direction == 'LONG':
        return {
            'ext_1_0': swing_high + (swing_range * 1.0),
            'ext_1_272': swing_high + (swing_range * 1.272),
            'ext_1_618': swing_high + (swing_range * 1.618),
            'ext_2_0': swing_high + (swing_range * 2.0),
        }
    else:
        return {
            'ext_1_0': swing_low - (swing_range * 1.0),
            'ext_1_272': swing_low - (swing_range * 1.272),
            'ext_1_618': swing_low - (swing_range * 1.618),
            'ext_2_0': swing_low - (swing_range * 2.0),
        }


def validate_fibonacci_signal(
    fib_data: Dict,
    current: pd.Series,
    direction: str,
    rsi_threshold_long: Tuple[float, float] = (25, 50),
    rsi_threshold_short: Tuple[float, float] = (50, 75)
) -> Tuple[bool, str]:
    """
    Validate Fibonacci pullback with additional confirmations.

    Checks:
    1. Price is in golden ratio zone (50-61.8%)
    2. RSI alignment (not overbought for LONG, not oversold for SHORT)
    3. Volume confirmation (above average)

    Args:
        fib_data: Fibonacci levels from check_fibonacci_pullback()
        current: Current candle data
        direction: 'LONG' or 'SHORT'
        rsi_threshold_long: (min, max) RSI range for LONG
        rsi_threshold_short: (min, max) RSI range for SHORT

    Returns:
        (valid: bool, reason: str) tuple
    """
    if not fib_data.get('in_entry_zone', False):
        return False, "Not in golden ratio entry zone"

    rsi = current.get('rsi')
    if rsi is None:
        return True, "No RSI data, accepting pullback"

    if direction == 'LONG':
        if not (rsi_threshold_long[0] <= rsi <= rsi_threshold_long[1]):
            return False, f"RSI {rsi:.1f} outside LONG range {rsi_threshold_long}"
    else:
        if not (rsi_threshold_short[0] <= rsi <= rsi_threshold_short[1]):
            return False, f"RSI {rsi:.1f} outside SHORT range {rsi_threshold_short}"

    volume_trend = current.get('volume_trend', 1.0)
    if volume_trend < 0.8:
        return False, f"Low volume ({volume_trend:.2f}x)"

    return True, "All confirmations met"
