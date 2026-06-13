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
    margin_per_trade: float = 100.0
    leverage: int = 10
    signal_expiry_hours: int = 6

    @property
    def max_score(self) -> float:
        """Sum of all component weights."""
        return (
            self.weight_trend + self.weight_structure + self.weight_volume
            + self.weight_pullback + self.weight_macd + self.weight_rsi
            + self.weight_atr
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

    def _score_components(self, df: pd.DataFrame, direction: str) -> Tuple[float, Dict]:
        """Score the soft components for a gated direction."""
        cfg = self.config
        current, previous = df.iloc[-1], df.iloc[-2]
        score = cfg.weight_trend + cfg.weight_structure
        conditions = {'trend': True, 'structure': True}

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

    def _build_levels(self, entry: float, atr: float, direction: str) -> Dict[str, float]:
        """Compute ATR-based stop and TP1/TP2 targets."""
        cfg = self.config
        if direction == BULLISH:
            return {
                'stop_loss': entry - cfg.sl_atr_mult * atr,
                'tp1': entry + cfg.tp1_atr_mult * atr,
                'tp2': entry + cfg.tp2_atr_mult * atr,
            }
        return {
            'stop_loss': entry + cfg.sl_atr_mult * atr,
            'tp1': entry - cfg.tp1_atr_mult * atr,
            'tp2': entry - cfg.tp2_atr_mult * atr,
        }

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

        prepared = self._prepare_entry(df_15m)
        structure = _market_structure(prepared, self.config.pivot_lookback)
        if structure != trend:
            return None

        score, conditions = self._score_components(prepared, trend)
        if score < self.config.min_score:
            return None

        confidence = score / self.config.max_score
        if confidence < self.config.min_confidence:
            return None

        current = prepared.iloc[-1]
        atr = float(current['atr'])
        if pd.isna(atr) or atr <= 0:
            return None

        entry = float(current['close'])
        levels = self._build_levels(entry, atr, trend)
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
