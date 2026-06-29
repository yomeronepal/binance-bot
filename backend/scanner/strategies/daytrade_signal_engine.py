"""Day-trade signal engine for the 15m Market Structure Pullback strategy.

Implements docs/15m_STRATEGY_V2.md: a 1H EMA trend filter and 15m market
structure are mandatory hard gates; pullback, volume, momentum, ADX and the
ATR regime feed a weighted score that must reach the configured minimum to
emit a signal. ATR-based stop and TP1/TP2 targets are attached. Parameters
are loaded from DayTradeStrategyConfig so the strategy is tunable from admin.

The engine is pure with respect to data: evaluate() takes prepared OHLCV
DataFrames and returns a result dict (no DB). generate() persists a
DayTradeSignal with duplicate-prevention keyed on the 15m candle bucket.
"""
import logging
import math
from dataclasses import dataclass, field
from datetime import timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import pandas as pd

from scanner.indicators.indicator_utils import (
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_adx,
    calculate_atr,
)

logger = logging.getLogger(__name__)

BULLISH = 'BULLISH'
BEARISH = 'BEARISH'
NEUTRAL = 'NEUTRAL'


@dataclass
class DayTradeSignalConfig:
    """Engine parameters, mirroring DayTradeStrategyConfig."""

    symbols: List[str] = field(default_factory=lambda: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'])
    universe_top_n: int = 30
    entry_timeframe: str = '15m'
    trend_timeframe: str = '1h'
    trend_ema_fast: int = 50
    trend_ema_slow: int = 200
    pivot_lookback: int = 5
    pullback_ema_fast: int = 20
    pullback_ema_slow: int = 50
    use_vwap: bool = True
    vwap_anchor: str = 'daily_utc'
    rsi_period: int = 14
    rsi_threshold: float = 50.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    volume_multiplier: float = 1.3
    volume_avg_period: int = 20
    adx_min: float = 20.0
    adx_period: int = 14
    sl_percentage: float = 2.5
    tp_percentage: float = 6.0
    atr_period: int = 14
    sl_atr_mult: float = 1.8
    tp1_atr_mult: float = 2.0
    tp1_close_pct: float = 50.0
    tp2_atr_mult: float = 4.0
    tp2_close_pct: float = 30.0
    runner_pct: float = 20.0
    trail_atr_mult: float = 2.0
    enable_liquidity_sweep: bool = True
    weight_trend: float = 3.0
    weight_structure: float = 3.0
    weight_volume: float = 2.0
    weight_pullback: float = 2.0
    weight_macd: float = 1.5
    weight_rsi: float = 1.0
    weight_atr: float = 1.0
    min_score: float = 8.5
    min_confidence: float = 0.70
    structure_quality_enabled: bool = False
    structure_min_swing_atr: float = 0.0
    weight_structure_bonus: float = 0.0
    require_bos: bool = False
    block_on_choch: bool = False
    trend_filter_enabled: bool = False
    trend_slope_lookback: int = 3
    trend_min_slope_pct: float = 0.0
    trend_min_ema_gap_pct: float = 0.0
    trend_require_price_above_ema50: bool = False
    trend_require_adx_rising: bool = False
    regime_filter_enabled: bool = False
    regime_min_adx: float = 0.0
    regime_max_choppiness: float = 0.0
    regime_choppiness_period: int = 14
    regime_min_bbw_pct: float = 0.0
    regime_bb_period: int = 20
    regime_bb_std: float = 2.0
    regime_atr_percentile_min: float = 0.0
    regime_atr_percentile_period: int = 100
    margin_per_trade: float = 100.0
    leverage: int = 10
    signal_expiry_hours: int = 6

    @property
    def max_score(self) -> float:
        """Sum of all component weights, including the additive structure bonus."""
        return (
            self.weight_trend + self.weight_structure + self.weight_volume
            + self.weight_pullback + self.weight_macd + self.weight_rsi
            + self.weight_atr + self.weight_structure_bonus
        )

    @classmethod
    def from_db(cls, db_config) -> 'DayTradeSignalConfig':
        """Build a config from a DayTradeStrategyConfig row."""
        return cls(
            symbols=db_config.symbols or [],
            universe_top_n=db_config.universe_top_n,
            entry_timeframe=db_config.entry_timeframe,
            trend_timeframe=db_config.trend_timeframe,
            trend_ema_fast=db_config.trend_ema_fast,
            trend_ema_slow=db_config.trend_ema_slow,
            pivot_lookback=db_config.pivot_lookback,
            pullback_ema_fast=db_config.pullback_ema_fast,
            pullback_ema_slow=db_config.pullback_ema_slow,
            use_vwap=db_config.use_vwap,
            vwap_anchor=db_config.vwap_anchor,
            rsi_period=db_config.rsi_period,
            rsi_threshold=db_config.rsi_threshold,
            macd_fast=db_config.macd_fast,
            macd_slow=db_config.macd_slow,
            macd_signal=db_config.macd_signal,
            volume_multiplier=db_config.volume_multiplier,
            volume_avg_period=db_config.volume_avg_period,
            adx_min=db_config.adx_min,
            adx_period=db_config.adx_period,
            sl_percentage=float(db_config.sl_percentage),
            tp_percentage=float(db_config.tp_percentage),
            atr_period=db_config.atr_period,
            sl_atr_mult=db_config.sl_atr_mult,
            tp1_atr_mult=db_config.tp1_atr_mult,
            tp1_close_pct=db_config.tp1_close_pct,
            tp2_atr_mult=db_config.tp2_atr_mult,
            tp2_close_pct=db_config.tp2_close_pct,
            runner_pct=db_config.runner_pct,
            trail_atr_mult=db_config.trail_atr_mult,
            enable_liquidity_sweep=db_config.enable_liquidity_sweep,
            weight_trend=db_config.weight_trend,
            weight_structure=db_config.weight_structure,
            weight_volume=db_config.weight_volume,
            weight_pullback=db_config.weight_pullback,
            weight_macd=db_config.weight_macd,
            weight_rsi=db_config.weight_rsi,
            weight_atr=db_config.weight_atr,
            min_score=db_config.min_score,
            min_confidence=db_config.min_confidence,
            margin_per_trade=float(db_config.margin_per_trade),
            leverage=db_config.leverage,
        )


def _daily_anchored_vwap(df: pd.DataFrame) -> pd.Series:
    """Compute a VWAP that resets at 00:00 UTC each day."""
    typical = (df['high'] + df['low'] + df['close']) / 3
    pv = typical * df['volume']
    day = df.index.tz_convert('UTC') if df.index.tz is not None else df.index
    grouper = pd.Series(day, index=df.index).dt.date
    cum_pv = pv.groupby(grouper).cumsum()
    cum_vol = df['volume'].groupby(grouper).cumsum()
    return cum_pv / cum_vol.replace(0, pd.NA)


def _rolling_vwap(df: pd.DataFrame, period: int) -> pd.Series:
    """Compute a rolling N-period VWAP."""
    typical = (df['high'] + df['low'] + df['close']) / 3
    pv = (typical * df['volume']).rolling(window=period).sum()
    vol = df['volume'].rolling(window=period).sum()
    return pv / vol.replace(0, pd.NA)


def _swing_indices(values: pd.Series, lookback: int, find_high: bool) -> List[int]:
    """Return positional indices of confirmed swing highs or lows.

    A swing point at position i requires ``lookback`` candles on each side
    that do not exceed (high) or undercut (low) it.
    """
    arr = values.to_numpy()
    n = len(arr)
    pivots = []
    for i in range(lookback, n - lookback):
        window = arr[i - lookback:i + lookback + 1]
        center = arr[i]
        if find_high and center == window.max() and (window.argmax() == lookback):
            pivots.append(i)
        elif not find_high and center == window.min() and (window.argmin() == lookback):
            pivots.append(i)
    return pivots


def _market_structure(df: pd.DataFrame, lookback: int) -> str:
    """Classify recent structure as BULLISH (HH+HL), BEARISH (LH+LL) or NEUTRAL."""
    highs = _swing_indices(df['high'], lookback, find_high=True)
    lows = _swing_indices(df['low'], lookback, find_high=False)
    if len(highs) < 2 or len(lows) < 2:
        return NEUTRAL

    last_h, prev_h = df['high'].iloc[highs[-1]], df['high'].iloc[highs[-2]]
    last_l, prev_l = df['low'].iloc[lows[-1]], df['low'].iloc[lows[-2]]

    if last_h > prev_h and last_l > prev_l:
        return BULLISH
    if last_h < prev_h and last_l < prev_l:
        return BEARISH
    return NEUTRAL


def _significant_swings(df, lookback, min_swing_atr, atr):
    """Return time-ordered swing points, filtering legs smaller than min_swing_atr*atr.

    Each point is (index, price, kind) with kind 'H' or 'L'. Consecutive same-kind
    pivots collapse to the more extreme one; an opposite pivot is kept only if its
    leg from the last significant swing is large enough to matter (ignores tiny
    pullbacks). With min_swing_atr <= 0 the raw pivots are returned unfiltered.
    """
    highs = [(i, float(df['high'].iloc[i]), 'H') for i in _swing_indices(df['high'], lookback, True)]
    lows = [(i, float(df['low'].iloc[i]), 'L') for i in _swing_indices(df['low'], lookback, False)]
    points = sorted(highs + lows, key=lambda p: p[0])
    if min_swing_atr <= 0 or atr <= 0:
        return points

    threshold = min_swing_atr * atr
    significant = []
    for point in points:
        if not significant:
            significant.append(point)
            continue
        last = significant[-1]
        if point[2] == last[2]:
            higher = point[2] == 'H' and point[1] >= last[1]
            lower = point[2] == 'L' and point[1] <= last[1]
            if higher or lower:
                significant[-1] = point
            continue
        if abs(point[1] - last[1]) >= threshold:
            significant.append(point)
    return significant


def _analyze_structure(df, lookback, min_swing_atr, atr):
    """Smart-money structure read: direction, BOS, CHoCH and a 0-1 quality score.

    Direction comes from HH+HL / LH+LL over significant swings. BOS (continuation)
    is a close beyond the latest swing in the trend direction; CHoCH (reversal) is
    a close breaking the latest counter-trend swing. Quality rewards a confirmed
    BOS and a strong final leg.
    """
    points = _significant_swings(df, lookback, min_swing_atr, atr)
    highs = [p for p in points if p[2] == 'H']
    lows = [p for p in points if p[2] == 'L']
    empty = {'direction': NEUTRAL, 'quality': 0.0, 'bos': False, 'choch': False, 'strong': False}
    if len(highs) < 2 or len(lows) < 2:
        return empty

    last_h, prev_h = highs[-1][1], highs[-2][1]
    last_l, prev_l = lows[-1][1], lows[-2][1]
    close = float(df['close'].iloc[-1])

    if last_h > prev_h and last_l > prev_l:
        direction = BULLISH
    elif last_h < prev_h and last_l < prev_l:
        direction = BEARISH
    else:
        return empty

    if direction == BULLISH:
        bos = close > last_h
        choch = close < last_l
    else:
        bos = close < last_l
        choch = close > last_h

    last_leg = abs(points[-1][1] - points[-2][1]) if len(points) >= 2 else 0.0
    strong = atr > 0 and last_leg >= 2 * (min_swing_atr if min_swing_atr > 0 else 1.0) * atr

    quality = 0.5 + (0.3 if bos else 0.0) + (0.2 if strong else 0.0)
    return {'direction': direction, 'quality': min(quality, 1.0),
            'bos': bos, 'choch': choch, 'strong': strong}


def _choppiness_index(df: pd.DataFrame, period: int):
    """Choppiness Index over ``period`` bars (high = choppy, low = trending)."""
    if len(df) < period + 1:
        return None
    high, low, close = df['high'], df['low'], df['close']
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    tr_sum = true_range.rolling(period).sum().iloc[-1]
    span = high.rolling(period).max().iloc[-1] - low.rolling(period).min().iloc[-1]
    if pd.isna(tr_sum) or pd.isna(span) or span <= 0 or tr_sum <= 0:
        return None
    return 100 * math.log10(tr_sum / span) / math.log10(period)


def _bollinger_width_pct(df: pd.DataFrame, period: int, std_mult: float):
    """Bollinger Band width as a percentage of the basis (volatility proxy)."""
    if len(df) < period:
        return None
    close = df['close']
    mid = close.rolling(period).mean().iloc[-1]
    std = close.rolling(period).std().iloc[-1]
    if pd.isna(mid) or pd.isna(std) or mid == 0:
        return None
    return (2 * std_mult * std) / mid * 100


def _atr_percentile(df: pd.DataFrame, period: int):
    """Percentile rank (0-100) of the current ATR within the last ``period`` bars."""
    atr = df['atr'].dropna()
    if len(atr) < 2:
        return None
    window = atr.iloc[-period:] if len(atr) >= period else atr
    current = atr.iloc[-1]
    return float((window <= current).mean() * 100)


class DayTradeSignalEngine:
    """Generate 15m Market Structure Pullback signals."""

    def __init__(self, config: Optional[DayTradeSignalConfig] = None):
        self.config = config or DayTradeSignalConfig()

    def _higher_tf_trend(self, df_1h: pd.DataFrame) -> str:
        """Return the 1H trend from the EMA fast/slow relationship."""
        fast = calculate_ema(df_1h, self.config.trend_ema_fast).iloc[-1]
        slow = calculate_ema(df_1h, self.config.trend_ema_slow).iloc[-1]
        if pd.isna(fast) or pd.isna(slow):
            return NEUTRAL
        if fast > slow:
            return BULLISH
        if fast < slow:
            return BEARISH
        return NEUTRAL

    def _trend_strength_ok(self, df_1h: pd.DataFrame, direction: str) -> bool:
        """Optional 1H trend-strength gate beyond the EMA50/EMA200 cross.

        Each sub-check is active only when its config threshold/toggle is set, so
        with trend_filter_enabled on but everything at defaults this is a no-op
        (reproduces V2). Checks are direction-aware: slope and EMA gap must point
        the trend's way, price must sit on the trend side of EMA50, and ADX must
        be rising.
        """
        cfg = self.config
        if not cfg.trend_filter_enabled:
            return True

        lookback = max(1, cfg.trend_slope_lookback)
        ema50 = calculate_ema(df_1h, cfg.trend_ema_fast)
        ema200 = calculate_ema(df_1h, cfg.trend_ema_slow)
        if len(ema50) <= lookback:
            return True

        e50, e50_prev, e200 = ema50.iloc[-1], ema50.iloc[-1 - lookback], ema200.iloc[-1]
        close = float(df_1h['close'].iloc[-1])
        if pd.isna(e50) or pd.isna(e200) or pd.isna(e50_prev) or e50_prev == 0 or close == 0:
            return True

        slope = (e50 - e50_prev) / e50_prev
        gap = (e50 - e200) / close
        is_bull = direction == BULLISH
        checks = []

        if cfg.trend_min_slope_pct > 0:
            thr = cfg.trend_min_slope_pct / 100.0
            checks.append(slope >= thr if is_bull else slope <= -thr)
        if cfg.trend_min_ema_gap_pct > 0:
            thr = cfg.trend_min_ema_gap_pct / 100.0
            checks.append(gap >= thr if is_bull else gap <= -thr)
        if cfg.trend_require_price_above_ema50:
            checks.append(close > e50 if is_bull else close < e50)
        if cfg.trend_require_adx_rising:
            adx, _, _ = calculate_adx(df_1h, cfg.adx_period)
            if len(adx) > lookback and not pd.isna(adx.iloc[-1]) and not pd.isna(adx.iloc[-1 - lookback]):
                checks.append(adx.iloc[-1] > adx.iloc[-1 - lookback])

        return all(checks)

    def _regime_ok(self, prepared: pd.DataFrame) -> bool:
        """Market-regime gate: only trade when the regime suits a pullback system.

        Each sub-check is active only when its threshold is set (> 0), so with
        regime_filter_enabled on but everything at defaults this is a no-op
        (reproduces V2). Rejects choppy ranges (high Choppiness Index), dead/low
        volatility (low Bollinger width or low ATR percentile) and weak trend
        strength (low ADX).
        """
        cfg = self.config
        if not cfg.regime_filter_enabled:
            return True

        current = prepared.iloc[-1]
        checks = []

        if cfg.regime_min_adx > 0 and not pd.isna(current['adx']):
            checks.append(current['adx'] >= cfg.regime_min_adx)
        if cfg.regime_max_choppiness > 0:
            ci = _choppiness_index(prepared, cfg.regime_choppiness_period)
            if ci is not None:
                checks.append(ci <= cfg.regime_max_choppiness)
        if cfg.regime_min_bbw_pct > 0:
            bbw = _bollinger_width_pct(prepared, cfg.regime_bb_period, cfg.regime_bb_std)
            if bbw is not None:
                checks.append(bbw >= cfg.regime_min_bbw_pct)
        if cfg.regime_atr_percentile_min > 0:
            pct = _atr_percentile(prepared, cfg.regime_atr_percentile_period)
            if pct is not None:
                checks.append(pct >= cfg.regime_atr_percentile_min)

        return all(checks)

    def _prepare_entry(self, df_15m: pd.DataFrame) -> pd.DataFrame:
        """Attach the indicators the entry logic needs to the 15m frame."""
        df = df_15m.copy()
        cfg = self.config
        df['ema_fast'] = calculate_ema(df, cfg.pullback_ema_fast)
        df['ema_slow'] = calculate_ema(df, cfg.pullback_ema_slow)
        df['rsi'] = calculate_rsi(df, cfg.rsi_period)
        _, _, df['macd_hist'] = calculate_macd(df, cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
        df['adx'], _, _ = calculate_adx(df, cfg.adx_period)
        df['atr'] = calculate_atr(df, cfg.atr_period)
        df['vol_avg'] = df['volume'].rolling(window=cfg.volume_avg_period).mean()
        if cfg.use_vwap and cfg.vwap_anchor == 'daily_utc':
            df['vwap'] = _daily_anchored_vwap(df)
        elif cfg.use_vwap:
            df['vwap'] = _rolling_vwap(df, cfg.volume_avg_period)
        else:
            df['vwap'] = pd.NA
        return df

    def _in_pullback_zone(self, current, direction: str) -> bool:
        """True if price retraced into the EMA/VWAP pullback zone."""
        levels = [current['ema_fast'], current['ema_slow']]
        if self.config.use_vwap and not pd.isna(current.get('vwap')):
            levels.append(current['vwap'])
        levels = [lv for lv in levels if not pd.isna(lv)]
        if not levels:
            return False
        if direction == BULLISH:
            return current['low'] <= max(levels) and current['close'] >= min(levels)
        return current['high'] >= min(levels) and current['close'] <= max(levels)

    def _liquidity_sweep(self, df: pd.DataFrame, direction: str) -> bool:
        """Detect a sweep of the prior swing level with a close back inside."""
        if len(df) < 3:
            return False
        current = df.iloc[-1]
        prior = df.iloc[-(self.config.pivot_lookback + 1):-1]
        if direction == BULLISH:
            return bool(current['low'] < prior['low'].min() and current['close'] > prior['low'].min())
        return bool(current['high'] > prior['high'].max() and current['close'] < prior['high'].max())

    def _resolve_structure(self, prepared: pd.DataFrame, trend: str, atr: float):
        """Return (structure_direction, bonus_quality), applying V3 gates.

        ``bonus_quality`` is a 0-1 additive confluence reward (BOS + strong leg);
        it never reduces the full base structure weight. With
        ``structure_quality_enabled`` off this reproduces the V2 binary gate and
        zero bonus. With it on the direction gate uses significance-filtered
        swings plus optional BOS / CHoCH hard gates.
        """
        cfg = self.config
        if not cfg.structure_quality_enabled:
            return _market_structure(prepared, cfg.pivot_lookback), 0.0

        result = _analyze_structure(prepared, cfg.pivot_lookback, cfg.structure_min_swing_atr, atr)
        if cfg.block_on_choch and result['choch']:
            return None, 0.0
        if cfg.require_bos and not result['bos']:
            return None, 0.0
        bonus_quality = 0.6 * (1.0 if result['bos'] else 0.0) + 0.4 * (1.0 if result['strong'] else 0.0)
        return result['direction'], bonus_quality

    def _score_components(self, df: pd.DataFrame, direction: str,
                          structure_bonus: float = 0.0) -> Tuple[float, Dict]:
        """Score the soft components for a gated direction.

        Structure keeps its full base weight (it is a passed gate) and earns an
        additive ``weight_structure_bonus * structure_bonus`` for BOS / strong-leg
        confluence. The remaining components are still binary (1.0/0.0) until
        their own quality upgrades land.
        """
        cfg = self.config
        current, previous = df.iloc[-1], df.iloc[-2]
        score = cfg.weight_trend + cfg.weight_structure + cfg.weight_structure_bonus * structure_bonus
        conditions = {'trend': True, 'structure': True,
                      'structure_bonus': round(structure_bonus, 3)}

        if self._in_pullback_zone(current, direction):
            score += cfg.weight_pullback
            conditions['pullback'] = True

        if not pd.isna(current['vol_avg']) and current['volume'] > cfg.volume_multiplier * current['vol_avg']:
            score += cfg.weight_volume
            conditions['volume'] = True

        macd_ok = (current['macd_hist'] > previous['macd_hist']) if direction == BULLISH \
            else (current['macd_hist'] < previous['macd_hist'])
        if macd_ok:
            score += cfg.weight_macd
            conditions['macd'] = True

        rsi_ok = (current['rsi'] > cfg.rsi_threshold) if direction == BULLISH \
            else (current['rsi'] < cfg.rsi_threshold)
        if rsi_ok:
            score += cfg.weight_rsi
            conditions['rsi'] = True

        if not pd.isna(current['adx']) and current['adx'] >= cfg.adx_min:
            score += cfg.weight_atr
            conditions['adx'] = True

        if cfg.enable_liquidity_sweep:
            conditions['liquidity_sweep'] = self._liquidity_sweep(df, direction)

        return score, conditions

    def _build_levels(self, entry: float, direction: str) -> Dict[str, float]:
        """Compute v1-style fixed-percentage single stop and take-profit.

        tp1 and tp2 are set to the same target so the single-exit executor
        and the model's two TP fields stay consistent.
        """
        cfg = self.config
        sl = cfg.sl_percentage / 100.0
        tp = cfg.tp_percentage / 100.0
        if direction == BULLISH:
            stop, target = entry * (1 - sl), entry * (1 + tp)
        else:
            stop, target = entry * (1 + sl), entry * (1 - tp)
        return {'stop_loss': stop, 'tp1': target, 'tp2': target}

    def _has_enough_data(self, df_15m: pd.DataFrame, df_1h: pd.DataFrame) -> bool:
        """Guard against insufficient history for the configured periods."""
        need_15m = max(self.config.pullback_ema_slow, self.config.volume_avg_period,
                       self.config.pivot_lookback * 2 + 2, self.config.atr_period) + 2
        return len(df_15m) >= need_15m and len(df_1h) >= self.config.trend_ema_slow + 1

    def evaluate(self, symbol: str, df_15m: pd.DataFrame, df_1h: pd.DataFrame) -> Optional[Dict]:
        """Evaluate the strategy and return a signal result dict, or None."""
        if not self._has_enough_data(df_15m, df_1h):
            return None

        trend = self._higher_tf_trend(df_1h)
        if trend == NEUTRAL:
            return None

        if not self._trend_strength_ok(df_1h, trend):
            return None

        prepared = self._prepare_entry(df_15m)
        cfg = self.config
        current = prepared.iloc[-1]
        atr = float(current['atr'])
        if pd.isna(atr) or atr <= 0:
            return None

        if not self._regime_ok(prepared):
            return None

        structure_dir, structure_bonus = self._resolve_structure(prepared, trend, atr)
        if structure_dir is None or structure_dir != trend:
            return None

        score, conditions = self._score_components(prepared, trend, structure_bonus)
        if score < cfg.min_score:
            return None

        confidence = score / cfg.max_score
        if confidence < cfg.min_confidence:
            return None

        entry = float(current['close'])
        levels = self._build_levels(entry, trend)
        direction = 'LONG' if trend == BULLISH else 'SHORT'

        return {
            'symbol': symbol,
            'direction': direction,
            'entry': entry,
            'atr': atr,
            'stop_loss': levels['stop_loss'],
            'tp1': levels['tp1'],
            'tp2': levels['tp2'],
            'score': round(score, 3),
            'confidence': round(confidence, 4),
            'candle_open_time': _to_utc(current.name),
            'conditions': conditions,
        }

    def generate(self, symbol: str, df_15m: pd.DataFrame, df_1h: pd.DataFrame):
        """Evaluate and persist a DayTradeSignal, with duplicate prevention."""
        result = self.evaluate(symbol, df_15m, df_1h)
        if result is None:
            return None
        return self._persist(result)

    def _persist(self, result: Dict):
        """Persist a signal idempotently, skipping if one is already live."""
        from django.utils import timezone
        from signals.models.daytrade import DayTradeSignal, DayTradePaperTrade

        symbol = result['symbol']
        if DayTradeSignal.objects.filter(symbol=symbol, status='ACTIVE').exists():
            return None
        if DayTradePaperTrade.objects.filter(
            symbol=symbol, status__in=['PENDING', 'OPEN', 'PARTIAL']
        ).exists():
            return None

        signal, created = DayTradeSignal.objects.get_or_create(
            symbol=symbol,
            entry_timeframe=self.config.entry_timeframe,
            candle_open_time=result['candle_open_time'],
            direction=result['direction'],
            defaults={
                'trend_timeframe': self.config.trend_timeframe,
                'entry': Decimal(str(result['entry'])),
                'stop_loss': Decimal(str(result['stop_loss'])),
                'tp1': Decimal(str(result['tp1'])),
                'tp2': Decimal(str(result['tp2'])),
                'atr': Decimal(str(result['atr'])),
                'confidence': result['confidence'],
                'score': result['score'],
                'meta': {'conditions': result['conditions']},
                'expires_at': timezone.now() + timedelta(hours=self.config.signal_expiry_hours),
            },
        )
        if created:
            logger.info(
                "DayTrade %s signal: %s @ %.6f (score %.2f)",
                result['direction'], symbol, result['entry'], result['score']
            )
            return signal
        return None


def _to_utc(timestamp):
    """Return a tz-aware UTC datetime for a pandas/py timestamp."""
    ts = pd.Timestamp(timestamp)
    if ts.tz is None:
        ts = ts.tz_localize('UTC')
    return ts.to_pydatetime().astimezone(dt_timezone.utc)
