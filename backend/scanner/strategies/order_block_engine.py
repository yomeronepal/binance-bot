"""4h order-block (ICT) entry rule: break of structure from the last opposing candle.

Single source of truth for the live scanner, mirroring the validated backtest
(backtest_ict order_block): on a break of the most recent confirmed swing, enter
in the break direction with the stop just beyond the order block (the last
opposing candle) and a fixed reward:risk target. Both directions, no filters.

Operates on CLOSED candles only — the caller must drop any forming candle, so
there is no look-ahead. Swing points use a k-bar confirmation lag.
"""
import numpy as np

from scanner.indicators.indicator_utils import calculate_atr


def _swing_levels(highs, lows, k):
    """Most-recent CONFIRMED swing high/low price at each index (k-bar lag)."""
    n = len(highs)
    last_sh = np.full(n, np.nan)
    last_sl = np.full(n, np.nan)
    sh = np.nan
    sl = np.nan
    for j in range(n):
        c = j - k
        if c - k >= 0:
            if highs[c] == highs[c - k:c + k + 1].max():
                sh = highs[c]
            if lows[c] == lows[c - k:c + k + 1].min():
                sl = lows[c]
        last_sh[j] = sh
        last_sl[j] = sl
    return last_sh, last_sl


def _structure_breaks(closes, last_sh, last_sl):
    """Classify each close's break as BOS (continuation) or CHoCH (reversal)."""
    n = len(closes)
    lbt = [''] * n
    sbt = [''] * n
    direction = ''
    for i in range(n):
        if not np.isnan(last_sh[i]) and closes[i] > last_sh[i]:
            lbt[i] = 'CHoCH' if direction == 'bear' else 'BOS'
            direction = 'bull'
        elif not np.isnan(last_sl[i]) and closes[i] < last_sl[i]:
            sbt[i] = 'CHoCH' if direction == 'bull' else 'BOS'
            direction = 'bear'
    return lbt, sbt


def _swept_recently(lows, highs, closes, last_sl, last_sh, i, look, direction):
    """True if a liquidity sweep of the opposing level happened in [i-look, i]."""
    for s in range(max(1, i - look), i + 1):
        if direction == 'LONG' and not np.isnan(last_sl[s]):
            if lows[s] < last_sl[s] and closes[s] > last_sl[s]:
                return True
        if direction == 'SHORT' and not np.isnan(last_sh[s]):
            if highs[s] > last_sh[s] and closes[s] < last_sh[s]:
                return True
    return False


def _order_block_stop(direction, i, opens, closes, highs, lows, last_sh, last_sl, atr_i, cfg):
    """Stop-loss from the order block for a break at candle i, or None if no setup."""
    look = cfg.lookback
    buf = cfg.sl_buffer_atr
    if direction == 'LONG' and not np.isnan(last_sh[i]) and closes[i] > last_sh[i]:
        blocks = [b for b in range(i - 1, max(i - look, 0) - 1, -1) if closes[b] < opens[b]]
        if blocks:
            return lows[blocks[0]] - buf * atr_i
    if direction == 'SHORT' and not np.isnan(last_sl[i]) and closes[i] < last_sl[i]:
        blocks = [b for b in range(i - 1, max(i - look, 0) - 1, -1) if closes[b] > opens[b]]
        if blocks:
            return highs[blocks[0]] + buf * atr_i
    return None


def _confidence(direction, i, closes, opens, highs, lows, vols, vol_sma, atr,
                last_sh, last_sl, lbt, sbt, look, pd_lb):
    """Confidence score (max 100) for the setup at candle i, per the hybrid weights."""
    a = atr[i]
    score = 15
    bt = lbt[i] if direction == 'LONG' else sbt[i]
    if bt == 'BOS':
        score += 20
    if abs(closes[i] - opens[i]) > 1.5 * a:
        score += 15
    if _swept_recently(lows, highs, closes, last_sl, last_sh, i, look, direction):
        score += 20
    if (direction == 'LONG' and lows[i] > highs[i - 2]) or (direction == 'SHORT' and highs[i] < lows[i - 2]):
        score += 10
    hi = highs[max(0, i - pd_lb):i + 1].max()
    lo = lows[max(0, i - pd_lb):i + 1].min()
    mid = (hi + lo) / 2.0
    if (direction == 'LONG' and closes[i] <= mid) or (direction == 'SHORT' and closes[i] >= mid):
        score += 10
    if not np.isnan(vol_sma[i]) and vols[i] > vol_sma[i]:
        score += 10
    return score


def _build_signal(direction, i, df, closes, opens, highs, lows, vols, vol_sma, atr, cfg, sl):
    """Assemble the signal dict for a validated setup, or None if risk is invalid."""
    entry = float(closes[i])
    risk = entry - sl if direction == 'LONG' else sl - entry
    if risk <= 0:
        return None
    tp = entry + cfg.rr * risk if direction == 'LONG' else entry - cfg.rr * risk
    last_sh, last_sl = _swing_levels(highs, lows, cfg.swing_k)
    lbt, sbt = _structure_breaks(closes, last_sh, last_sl)
    score = _confidence(direction, i, closes, opens, highs, lows, vols, vol_sma, atr,
                        last_sh, last_sl, lbt, sbt, cfg.lookback, 20)
    structure = (lbt[i] if direction == 'LONG' else sbt[i]) or ''
    return {
        'direction': direction,
        'entry': entry,
        'stop_loss': float(sl),
        'take_profit': float(tp),
        'atr': float(atr[i]),
        'confidence': int(score),
        'structure': structure,
    }


def evaluate_order_block(df_entry, config):
    """Return an order-block signal for the latest closed entry candle, or None.

    Args:
        df_entry: Closed entry-timeframe (4h) OHLCV frame.
        config: OrderBlockStrategyConfig (rr, swing_k, lookback, sl_buffer_atr).

    Returns:
        dict {direction, entry, stop_loss, take_profit, atr, confidence, structure} or None.
    """
    need = max(config.atr_period, config.lookback, config.swing_k * 2) + 5
    if len(df_entry) < need:
        return None
    highs = df_entry['high'].values
    lows = df_entry['low'].values
    closes = df_entry['close'].values
    opens = df_entry['open'].values
    vols = df_entry['volume'].values
    vol_sma = df_entry['volume'].rolling(20).mean().values
    atr = calculate_atr(df_entry, config.atr_period).values
    i = len(df_entry) - 1
    if np.isnan(atr[i]) or atr[i] <= 0:
        return None
    last_sh, last_sl = _swing_levels(highs, lows, config.swing_k)
    for direction in ('LONG', 'SHORT'):
        sl = _order_block_stop(direction, i, opens, closes, highs, lows, last_sh, last_sl, atr[i], config)
        if sl is None:
            continue
        signal = _build_signal(direction, i, df_entry, closes, opens, highs, lows, vols, vol_sma, atr, config, sl)
        if signal:
            return signal
    return None
