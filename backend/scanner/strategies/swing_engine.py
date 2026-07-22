"""4h swing entry rule: breakout gated by the 1D trend + ADX.

Single source of truth shared by the live scanner and (conceptually) the
backtest. Operates on CLOSED candles only — the caller must drop any forming
candle from both frames before calling, so there is no look-ahead.
"""
import pandas as pd

from scanner.indicators.indicator_utils import calculate_ema, calculate_atr, calculate_adx


def _trend_label(df_trend, adx_min):
    """UP / DOWN / None from the last closed trend candle (EMA50 vs EMA200 + ADX)."""
    ema50 = calculate_ema(df_trend, 50).iloc[-1]
    ema200 = calculate_ema(df_trend, 200).iloc[-1]
    adx = calculate_adx(df_trend, 14)[0].iloc[-1]
    if pd.isna(ema50) or pd.isna(ema200) or pd.isna(adx) or adx < adx_min:
        return None
    if ema50 > ema200:
        return 'UP'
    if ema50 < ema200:
        return 'DOWN'
    return None


def evaluate_swing(df_entry, df_trend, config):
    """Return a swing signal for the latest closed entry candle, or None.

    Args:
        df_entry: Closed entry-timeframe (4h) OHLCV frame.
        df_trend: Closed trend-timeframe (1D) OHLCV frame.
        config: SwingStrategyConfig (adx_min, breakout_lookback, sl/tp mults).

    Returns:
        dict {direction, entry, stop_loss, take_profit, atr} or None.
    """
    look = config.breakout_lookback
    if len(df_entry) < look + 2 or len(df_trend) < 205:
        return None

    atr = calculate_atr(df_entry, 14).iloc[-1]
    if pd.isna(atr) or atr <= 0:
        return None

    trend = _trend_label(df_trend, config.adx_min)
    if trend is None:
        return None

    close = float(df_entry['close'].iloc[-1])
    prior_high = float(df_entry['high'].iloc[-1 - look:-1].max())
    prior_low = float(df_entry['low'].iloc[-1 - look:-1].min())

    if trend == 'UP' and close > prior_high:
        direction = 'LONG'
    elif trend == 'DOWN' and close < prior_low:
        direction = 'SHORT'
    else:
        return None

    atr = float(atr)
    if direction == 'LONG':
        stop_loss = close - config.sl_atr_mult * atr
        take_profit = close + config.tp_atr_mult * atr
    else:
        stop_loss = close + config.sl_atr_mult * atr
        take_profit = close - config.tp_atr_mult * atr

    return {
        'direction': direction,
        'entry': close,
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'atr': atr,
    }
