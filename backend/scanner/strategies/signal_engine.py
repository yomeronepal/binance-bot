"""
Rule-based signal detection engine with real-time updates.
Maintains in-memory cache of candles and active signals.
"""
import logging
from typing import Dict, List, Optional, Deque
from collections import deque, defaultdict
from decimal import Decimal
from datetime import datetime, timedelta
import pandas as pd
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SignalConfig:
    """Configuration for signal detection rules."""
    # LONG signal thresholds
    long_rsi_min: float = 50.0
    long_rsi_max: float = 70.0
    long_adx_min: float = 20.0
    long_volume_multiplier: float = 1.2

    # SHORT signal thresholds
    short_rsi_min: float = 30.0
    short_rsi_max: float = 50.0
    short_adx_min: float = 20.0
    short_volume_multiplier: float = 1.2

    # Stop loss and take profit multipliers (ATR-based)
    sl_atr_multiplier: float = 1.5
    tp_atr_multiplier: float = 2.5

    # Signal management
    min_confidence: float = 0.7
    max_candles_cache: int = 200
    signal_expiry_minutes: int = 60

    # Indicator weights for confidence scoring
    macd_weight: float = 1.5
    rsi_weight: float = 1.0
    price_ema_weight: float = 1.0
    adx_weight: float = 1.0
    ha_weight: float = 1.5
    volume_weight: float = 1.0
    ema_alignment_weight: float = 0.5
    di_weight: float = 0.5


@dataclass
class ActiveSignal:
    """Represents an active trading signal."""
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    entry: Decimal
    sl: Decimal
    tp: Decimal
    confidence: float
    timeframe: str
    description: str
    created_at: datetime
    last_updated: datetime
    db_id: Optional[int] = None
    conditions_met: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for broadcasting."""
        return {
            'symbol': self.symbol,
            'direction': self.direction,
            'entry': float(self.entry),
            'sl': float(self.sl),
            'tp': float(self.tp),
            'confidence': self.confidence,
            'timeframe': self.timeframe,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat(),
        }


class SignalDetectionEngine:
    """
    Rule-based signal detection engine with real-time updates.
    Maintains in-memory cache and dynamically updates signals.
    """

    def __init__(self, config: Optional[SignalConfig] = None):
        """
        Initialize signal detection engine.

        Args:
            config: Signal configuration (uses defaults if None)
        """
        self.config = config or SignalConfig()

        # In-memory cache: symbol -> deque of candles
        self.candle_cache: Dict[str, Deque[List]] = defaultdict(
            lambda: deque(maxlen=self.config.max_candles_cache)
        )

        # Active signals: symbol -> ActiveSignal
        self.active_signals: Dict[str, ActiveSignal] = {}

        # Tracking for signal changes
        self.signal_history: Dict[str, List[ActiveSignal]] = defaultdict(list)

        logger.info(
            f"Signal engine initialized (min_confidence={self.config.min_confidence}, "
            f"cache_size={self.config.max_candles_cache})"
        )

    def update_candles(self, symbol: str, klines: List[List]) -> None:
        """
        Update candle cache for a symbol.

        Args:
            symbol: Trading pair symbol
            klines: List of klines from Binance API
        """
        cache = self.candle_cache[symbol]

        # Add new candles to cache
        for kline in klines:
            cache.append(kline)

        logger.debug(f"Updated {symbol} cache: {len(cache)} candles")

    def process_symbol(
        self,
        symbol: str,
        timeframe: str = '5m'
    ) -> Optional[Dict]:
        """
        Process symbol and detect/update signals.

        Args:
            symbol: Trading pair symbol
            timeframe: Candlestick timeframe

        Returns:
            Signal update dictionary or None
        """
        from scanner.indicators.indicator_utils import (
            klines_to_dataframe,
            calculate_all_indicators
        )

        # Get cached candles
        candles = list(self.candle_cache[symbol])
        if len(candles) < 50:
            logger.debug(f"{symbol}: Not enough candles ({len(candles)})")
            return None

        try:
            # Convert to DataFrame and calculate indicators
            df = klines_to_dataframe(candles)
            df = calculate_all_indicators(df)

            # Check if we have an active signal
            existing_signal = self.active_signals.get(symbol)

            if existing_signal:
                # Update existing signal
                return self._update_existing_signal(symbol, df, existing_signal, timeframe)
            else:
                # Detect new signal
                return self._detect_new_signal(symbol, df, timeframe)

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            return None

    def _detect_new_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        timeframe: str
    ) -> Optional[Dict]:
        """Detect new trading signal."""
        if len(df) < 2:
            return None

        current = df.iloc[-1]
        previous = df.iloc[-2]

        # Check LONG conditions
        long_signal, long_conf, long_conditions = self._check_long_conditions(
            df, current, previous
        )

        if long_signal and long_conf >= self.config.min_confidence:
            signal = self._create_signal(
                symbol, 'LONG', df, current, long_conf, long_conditions, timeframe
            )
            self.active_signals[symbol] = signal
            logger.info(f"🆕 NEW LONG signal: {symbol} @ ${signal.entry} (Conf: {signal.confidence:.0%})")
            return {'action': 'created', 'signal': signal.to_dict()}

        # Check SHORT conditions
        short_signal, short_conf, short_conditions = self._check_short_conditions(
            df, current, previous
        )

        if short_signal and short_conf >= self.config.min_confidence:
            signal = self._create_signal(
                symbol, 'SHORT', df, current, short_conf, short_conditions, timeframe
            )
            self.active_signals[symbol] = signal
            logger.info(f"🆕 NEW SHORT signal: {symbol} @ ${signal.entry} (Conf: {signal.confidence:.0%})")
            return {'action': 'created', 'signal': signal.to_dict()}

        return None

    def _update_existing_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        signal: ActiveSignal,
        timeframe: str
    ) -> Optional[Dict]:
        """Update or invalidate existing signal."""
        current = df.iloc[-1]
        previous = df.iloc[-2]

        # Check if signal conditions are still valid
        if signal.direction == 'LONG':
            valid, conf, conditions = self._check_long_conditions(df, current, previous)
        else:
            valid, conf, conditions = self._check_short_conditions(df, current, previous)

        # Check for signal invalidation
        if not valid or conf < self.config.min_confidence * 0.7:  # 30% tolerance
            logger.info(f"❌ INVALIDATED {signal.direction} signal: {symbol}")
            del self.active_signals[symbol]
            return {'action': 'deleted', 'signal_id': symbol}

        # Check for signal expiry
        if datetime.now() - signal.created_at > timedelta(minutes=self.config.signal_expiry_minutes):
            logger.info(f"⏰ EXPIRED {signal.direction} signal: {symbol}")
            del self.active_signals[symbol]
            return {'action': 'deleted', 'signal_id': symbol}

        # Update signal if confidence changed significantly
        conf_change = abs(conf - signal.confidence)
        if conf_change > 0.05:  # 5% change threshold
            signal.confidence = conf
            signal.last_updated = datetime.now()
            signal.conditions_met = conditions

            # Update SL/TP based on current ATR
            atr = float(current['atr'])
            entry = float(signal.entry)

            if signal.direction == 'LONG':
                signal.sl = Decimal(str(entry - (self.config.sl_atr_multiplier * atr)))
                signal.tp = Decimal(str(entry + (self.config.tp_atr_multiplier * atr)))
            else:
                signal.sl = Decimal(str(entry + (self.config.sl_atr_multiplier * atr)))
                signal.tp = Decimal(str(entry - (self.config.tp_atr_multiplier * atr)))

            logger.info(
                f"🔄 UPDATED {signal.direction} signal: {symbol} "
                f"(Conf: {signal.confidence:.0%}, Change: {conf_change:+.1%})"
            )
            return {'action': 'updated', 'signal': signal.to_dict()}

        return None  # No significant change

    def _check_long_conditions(self, df, current, previous) -> tuple[bool, float, Dict[str, bool]]:
        """Check LONG signal conditions with detailed tracking."""
        score = 0.0
        max_score = (
            self.config.macd_weight +
            self.config.rsi_weight +
            self.config.price_ema_weight +
            self.config.adx_weight +
            self.config.ha_weight +
            self.config.volume_weight +
            self.config.ema_alignment_weight +
            self.config.di_weight
        )

        conditions = {}

        try:
            # 1. MACD Crossover
            if previous['macd_hist'] <= 0 and current['macd_hist'] > 0:
                score += self.config.macd_weight
                conditions['macd_crossover'] = True
            else:
                conditions['macd_crossover'] = False

            # 2. RSI Range
            if self.config.long_rsi_min < current['rsi'] < self.config.long_rsi_max:
                score += self.config.rsi_weight
                conditions['rsi_favorable'] = True
            elif current['rsi'] > previous['rsi']:
                score += self.config.rsi_weight * 0.5
                conditions['rsi_favorable'] = True
            else:
                conditions['rsi_favorable'] = False

            # 3. Price above EMA50
            if current['close'] > current['ema_50']:
                score += self.config.price_ema_weight
                conditions['price_above_ema'] = True
            else:
                conditions['price_above_ema'] = False

            # 4. ADX Strength
            if current['adx'] > self.config.long_adx_min:
                score += self.config.adx_weight
                conditions['strong_trend'] = True
            else:
                conditions['strong_trend'] = False

            # 5. Heikin Ashi Bullish
            if current['ha_bullish']:
                score += self.config.ha_weight
                conditions['ha_bullish'] = True
            else:
                conditions['ha_bullish'] = False

            # 6. Volume Increase
            if current['volume_trend'] > self.config.long_volume_multiplier:
                score += self.config.volume_weight
                conditions['volume_spike'] = True
            elif current['volume_trend'] > 1.0:
                score += self.config.volume_weight * 0.5
                conditions['volume_spike'] = True
            else:
                conditions['volume_spike'] = False

            # 7. EMA Alignment
            if current['ema_9'] > current['ema_21'] > current['ema_50']:
                score += self.config.ema_alignment_weight
                conditions['ema_aligned'] = True
            else:
                conditions['ema_aligned'] = False

            # 8. +DI > -DI
            if current['plus_di'] > current['minus_di']:
                score += self.config.di_weight
                conditions['positive_di'] = True
            else:
                conditions['positive_di'] = False

            confidence = min(score / max_score, 1.0)
            triggered = score >= (max_score * self.config.min_confidence)

            return triggered, confidence, conditions

        except Exception as e:
            logger.error(f"Error checking LONG conditions: {e}")
            return False, 0.0, {}

    def _check_short_conditions(self, df, current, previous) -> tuple[bool, float, Dict[str, bool]]:
        """Check SHORT signal conditions with detailed tracking."""
        score = 0.0
        max_score = (
            self.config.macd_weight +
            self.config.rsi_weight +
            self.config.price_ema_weight +
            self.config.adx_weight +
            self.config.ha_weight +
            self.config.volume_weight +
            self.config.ema_alignment_weight +
            self.config.di_weight
        )

        conditions = {}

        try:
            # 1. MACD Crossover
            if previous['macd_hist'] >= 0 and current['macd_hist'] < 0:
                score += self.config.macd_weight
                conditions['macd_crossover'] = True
            else:
                conditions['macd_crossover'] = False

            # 2. RSI Range
            if self.config.short_rsi_min < current['rsi'] < self.config.short_rsi_max:
                score += self.config.rsi_weight
                conditions['rsi_favorable'] = True
            elif current['rsi'] < previous['rsi']:
                score += self.config.rsi_weight * 0.5
                conditions['rsi_favorable'] = True
            else:
                conditions['rsi_favorable'] = False

            # 3. Price below EMA50
            if current['close'] < current['ema_50']:
                score += self.config.price_ema_weight
                conditions['price_below_ema'] = True
            else:
                conditions['price_below_ema'] = False

            # 4. ADX Strength
            if current['adx'] > self.config.short_adx_min:
                score += self.config.adx_weight
                conditions['strong_trend'] = True
            else:
                conditions['strong_trend'] = False

            # 5. Heikin Ashi Bearish
            if not current['ha_bullish']:
                score += self.config.ha_weight
                conditions['ha_bearish'] = True
            else:
                conditions['ha_bearish'] = False

            # 6. Volume Increase
            if current['volume_trend'] > self.config.short_volume_multiplier:
                score += self.config.volume_weight
                conditions['volume_spike'] = True
            elif current['volume_trend'] > 1.0:
                score += self.config.volume_weight * 0.5
                conditions['volume_spike'] = True
            else:
                conditions['volume_spike'] = False

            # 7. EMA Alignment
            if current['ema_9'] < current['ema_21'] < current['ema_50']:
                score += self.config.ema_alignment_weight
                conditions['ema_aligned'] = True
            else:
                conditions['ema_aligned'] = False

            # 8. -DI > +DI
            if current['minus_di'] > current['plus_di']:
                score += self.config.di_weight
                conditions['negative_di'] = True
            else:
                conditions['negative_di'] = False

            confidence = min(score / max_score, 1.0)
            triggered = score >= (max_score * self.config.min_confidence)

            return triggered, confidence, conditions

        except Exception as e:
            logger.error(f"Error checking SHORT conditions: {e}")
            return False, 0.0, {}

    def _create_signal(
        self,
        symbol: str,
        direction: str,
        df: pd.DataFrame,
        current,
        confidence: float,
        conditions: Dict[str, bool],
        timeframe: str
    ) -> ActiveSignal:
        """Create new active signal."""
        entry = float(current['close'])
        atr = float(current['atr'])

        if direction == 'LONG':
            sl = entry - (self.config.sl_atr_multiplier * atr)
            tp = entry + (self.config.tp_atr_multiplier * atr)
        else:
            sl = entry + (self.config.sl_atr_multiplier * atr)
            tp = entry - (self.config.tp_atr_multiplier * atr)

        description = self._generate_description(direction, current, conditions)

        signal = ActiveSignal(
            symbol=symbol,
            direction=direction,
            entry=Decimal(str(entry)),
            sl=Decimal(str(sl)),
            tp=Decimal(str(tp)),
            confidence=confidence,
            timeframe=timeframe,
            description=description,
            created_at=datetime.now(),
            last_updated=datetime.now(),
            conditions_met=conditions
        )

        return signal

    def _generate_description(self, direction: str, current, conditions: Dict[str, bool]) -> str:
        """Generate human-readable signal description."""
        met_conditions = [k for k, v in conditions.items() if v]

        parts = [f"{direction} setup:"]

        if 'macd_crossover' in met_conditions:
            parts.append("MACD crossover")
        if current.get('rsi'):
            parts.append(f"RSI {current['rsi']:.1f}")
        if current.get('adx'):
            parts.append(f"ADX {current['adx']:.1f}")

        parts.append(f"({len(met_conditions)}/{len(conditions)} conditions)")

        return ", ".join(parts)

    def get_active_signals(self) -> List[Dict]:
        """Get all active signals as dictionaries."""
        return [signal.to_dict() for signal in self.active_signals.values()]

    def remove_signal(self, symbol: str) -> bool:
        """
        Remove signal for a symbol.

        Returns:
            True if signal was removed, False if not found
        """
        if symbol in self.active_signals:
            del self.active_signals[symbol]
            logger.info(f"Removed signal for {symbol}")
            return True
        return False

    def cleanup_expired_signals(self) -> List[str]:
        """
        Remove expired signals.

        Returns:
            List of removed symbol names
        """
        now = datetime.now()
        expiry_threshold = timedelta(minutes=self.config.signal_expiry_minutes)

        expired = []
        for symbol, signal in list(self.active_signals.items()):
            if now - signal.created_at > expiry_threshold:
                expired.append(symbol)
                del self.active_signals[symbol]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired signals")

        return expired
