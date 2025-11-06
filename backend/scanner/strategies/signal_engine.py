"""
Rule-based signal detection engine with real-time updates.
Maintains in-memory cache of candles and active signals.
Supports volatility-aware configuration adjustment.
"""
import logging
from typing import Dict, List, Optional, Deque
from collections import deque, defaultdict
from decimal import Decimal
from datetime import datetime, timedelta
import pandas as pd
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Import volatility classifier
try:
    from scanner.services.volatility_classifier import get_volatility_classifier
    VOLATILITY_CLASSIFIER_AVAILABLE = True
except ImportError:
    logger.warning("VolatilityClassifier not available - using default configurations")
    VOLATILITY_CLASSIFIER_AVAILABLE = False


@dataclass
class SignalConfig:
    """Configuration for signal detection rules."""
    # LONG signal thresholds (Buy when oversold - mean reversion)
    long_rsi_min: float = 25.0  # Buy when RSI is low (oversold)
    long_rsi_max: float = 35.0  # Maximum RSI for LONG entry
    long_adx_min: float = 22.0  # Require stronger trend
    long_volume_multiplier: float = 1.2

    # SHORT signal thresholds (Sell when overbought - mean reversion)
    short_rsi_min: float = 65.0  # Minimum RSI for SHORT entry
    short_rsi_max: float = 75.0  # Sell when RSI is high (overbought)
    short_adx_min: float = 22.0  # Require stronger trend
    short_volume_multiplier: float = 1.2

    # Stop loss and take profit multipliers (ATR-based)
    sl_atr_multiplier: float = 1.5  # 1.5x ATR for stop loss (good risk management)
    tp_atr_multiplier: float = 5.25  # 5.25x ATR for take profit (3.5:1 R/R)

    # Signal management
    min_confidence: float = 0.75  # Increased to filter marginal signals
    max_candles_cache: int = 200
    signal_expiry_minutes: int = 60

    # Indicator weights for confidence scoring (more realistic distribution)
    macd_weight: float = 2.0       # Strong momentum indicator
    rsi_weight: float = 1.5         # Key overbought/oversold indicator
    price_ema_weight: float = 1.8   # Trend confirmation
    adx_weight: float = 1.7         # Trend strength is crucial
    ha_weight: float = 1.6          # Smoothed trend direction
    volume_weight: float = 1.4      # Confirmation of interest
    ema_alignment_weight: float = 1.2  # Multiple timeframe alignment
    di_weight: float = 1.0          # Directional movement
    bb_weight: float = 0.8          # Volatility and price extremes
    volatility_weight: float = 0.5  # Market condition adjustment

    # NEW INDICATOR WEIGHTS
    supertrend_weight: float = 1.9  # Strong trend following indicator
    mfi_weight: float = 1.3         # Volume-weighted momentum
    psar_weight: float = 1.1        # Adaptive trailing stop/trend


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
            'signal_type': self.direction,  # Database expects 'signal_type'
            'direction': self.direction,  # Keep for backward compatibility
            'entry_price': float(self.entry),  # Database expects 'entry_price'
            'entry': float(self.entry),  # Keep for backward compatibility
            'stop_loss': float(self.sl),  # Database expects 'stop_loss'
            'sl': float(self.sl),  # Keep for backward compatibility
            'take_profit': float(self.tp),  # Database expects 'take_profit'
            'tp': float(self.tp),  # Keep for backward compatibility
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
    Supports volatility-aware configuration adjustment.
    """

    def __init__(self, config: Optional[SignalConfig] = None, use_volatility_aware: bool = False):
        """
        Initialize signal detection engine.

        Args:
            config: Signal configuration (uses defaults if None)
            use_volatility_aware: Enable volatility-aware configuration adjustment
        """
        self.config = config or SignalConfig()
        self.use_volatility_aware = use_volatility_aware and VOLATILITY_CLASSIFIER_AVAILABLE

        # In-memory cache: symbol -> deque of candles
        self.candle_cache: Dict[str, Deque[List]] = defaultdict(
            lambda: deque(maxlen=self.config.max_candles_cache)
        )

        # Active signals: symbol -> ActiveSignal
        self.active_signals: Dict[str, ActiveSignal] = {}

        # Tracking for signal changes
        self.signal_history: Dict[str, List[ActiveSignal]] = defaultdict(list)

        # Volatility classifier instance
        self.volatility_classifier = None
        if self.use_volatility_aware:
            self.volatility_classifier = get_volatility_classifier()
            logger.info("Volatility-aware mode ENABLED - configs will auto-adjust per symbol")

        # Cache for symbol-specific configs
        self.symbol_configs: Dict[str, SignalConfig] = {}

        logger.info(
            f"Signal engine initialized (min_confidence={self.config.min_confidence}, "
            f"cache_size={self.config.max_candles_cache}, "
            f"volatility_aware={self.use_volatility_aware})"
        )

    def get_config_for_symbol(self, symbol: str, df: Optional[pd.DataFrame] = None) -> SignalConfig:
        """
        Get configuration for specific symbol (with volatility adjustment if enabled).

        Args:
            symbol: Trading pair symbol
            df: Optional DataFrame with historical data for classification

        Returns:
            SignalConfig for the symbol (default or volatility-adjusted)
        """
        # If volatility-aware mode disabled, use default config
        if not self.use_volatility_aware:
            return self.config

        # Check cache first
        if symbol in self.symbol_configs:
            return self.symbol_configs[symbol]

        # Classify symbol and get recommended parameters
        try:
            profile = self.volatility_classifier.classify_symbol(symbol, df)

            # Create adjusted config based on volatility profile
            adjusted_config = SignalConfig(
                # Keep RSI ranges (they work across volatility levels)
                long_rsi_min=self.config.long_rsi_min,
                long_rsi_max=self.config.long_rsi_max,
                short_rsi_min=self.config.short_rsi_min,
                short_rsi_max=self.config.short_rsi_max,

                # Adjust SL/TP based on volatility
                sl_atr_multiplier=profile.sl_atr_multiplier,
                tp_atr_multiplier=profile.tp_atr_multiplier,

                # Adjust ADX threshold based on volatility
                long_adx_min=profile.adx_threshold,
                short_adx_min=profile.adx_threshold,

                # Adjust confidence threshold based on volatility
                min_confidence=profile.min_confidence,

                # Keep volume multipliers
                long_volume_multiplier=self.config.long_volume_multiplier,
                short_volume_multiplier=self.config.short_volume_multiplier,

                # Keep other settings
                max_candles_cache=self.config.max_candles_cache,
                signal_expiry_minutes=self.config.signal_expiry_minutes,

                # Keep indicator weights
                macd_weight=self.config.macd_weight,
                rsi_weight=self.config.rsi_weight,
                price_ema_weight=self.config.price_ema_weight,
                adx_weight=self.config.adx_weight,
                ha_weight=self.config.ha_weight,
                volume_weight=self.config.volume_weight,
                ema_alignment_weight=self.config.ema_alignment_weight,
                di_weight=self.config.di_weight,
                bb_weight=self.config.bb_weight,
                volatility_weight=self.config.volatility_weight,
            )

            # Cache it
            self.symbol_configs[symbol] = adjusted_config

            logger.info(
                f"📊 {symbol} classified as {profile.volatility_level} volatility: "
                f"SL={profile.sl_atr_multiplier}x, TP={profile.tp_atr_multiplier}x, "
                f"ADX={profile.adx_threshold}, Conf={profile.min_confidence:.0%}"
            )

            return adjusted_config

        except Exception as e:
            logger.error(f"Error getting volatility-adjusted config for {symbol}: {e}")
            return self.config

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

    def _get_higher_timeframe_trend(self, symbol: str) -> str:
        """
        Get daily trend direction using EMA crossover.

        PHASE 2 OPTIMIZATION: Multi-Timeframe Confirmation
        Only take signals aligned with higher timeframe trend.

        Args:
            symbol: Trading pair symbol

        Returns:
            "BULLISH", "BEARISH", or "NEUTRAL"

        NOTE: Currently disabled to avoid event loop conflicts.
        Returns NEUTRAL to allow all signals through.
        """
        # TEMPORARILY DISABLED: Event loop conflict issues
        # This feature will be re-enabled after refactoring to use proper async context
        logger.debug(f"{symbol}: Daily trend check disabled, returning NEUTRAL")
        return "NEUTRAL"

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

            # Get symbol-specific config (with volatility adjustment if enabled)
            symbol_config = self.get_config_for_symbol(symbol, df)

            # Check if we have an active signal
            existing_signal = self.active_signals.get(symbol)

            if existing_signal:
                # Update existing signal
                return self._update_existing_signal(symbol, df, existing_signal, timeframe, symbol_config)
            else:
                # Detect new signal
                return self._detect_new_signal(symbol, df, timeframe, symbol_config)

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            return None

    def _detect_new_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        timeframe: str,
        config: SignalConfig
    ) -> Optional[Dict]:
        """Detect new trading signal."""
        if len(df) < 2:
            return None

        current = df.iloc[-1]
        previous = df.iloc[-2]

        # PHASE 1 OPTIMIZATION: Volume Filter (DISABLED - was filtering out winners)
        # Testing showed 1.5x threshold removed winning trades, keeping only losers
        # Volume is already factored into the weighted scoring system
        # if current['volume_trend'] < 1.5:
        #     logger.debug(
        #         f"{symbol}: Low volume ({current['volume_trend']:.2f}x average), "
        #         f"skipping signal detection"
        #     )
        #     return None

        # PHASE 3 OPTIMIZATION: Volatility-Based No-Trade Zones
        # Avoid trading in ranging/choppy markets (low ADX)
        if current['adx'] < 18:
            logger.debug(
                f"{symbol}: Market is ranging (ADX: {current['adx']:.1f} < 18), "
                f"skipping signal detection to avoid false breakouts"
            )
            return None

        # PHASE 3 OPTIMIZATION: Volume Spike Confirmation
        # For breakout strategies, require above-average volume to confirm momentum
        # This is different from Phase 1 volume filter - we need volume SPIKE, not just absolute volume
        volume_ma_20 = df['volume'].rolling(20).mean().iloc[-1]
        volume_spike_ratio = current['volume'] / volume_ma_20 if volume_ma_20 > 0 else 0

        if volume_spike_ratio < 1.2:
            logger.debug(
                f"{symbol}: No volume spike detected ({volume_spike_ratio:.2f}x vs 20-period avg), "
                f"waiting for stronger momentum confirmation"
            )
            return None

        # Check LONG conditions
        long_signal, long_conf, long_conditions = self._check_long_conditions(
            df, current, previous, config
        )

        if long_signal and long_conf >= config.min_confidence:
            # PHASE 2 OPTIMIZATION: Multi-Timeframe Confirmation
            # Only take LONG signals aligned with daily trend
            daily_trend = self._get_higher_timeframe_trend(symbol)

            if daily_trend == "BEARISH":
                logger.info(
                    f"{symbol}: LONG signal detected (Conf: {long_conf:.0%}) but daily trend is BEARISH, "
                    f"skipping to avoid counter-trend trade"
                )
                return None
            elif daily_trend == "NEUTRAL":
                logger.info(
                    f"{symbol}: LONG signal detected (Conf: {long_conf:.0%}), daily trend NEUTRAL, "
                    f"proceeding with caution"
                )

            signal = self._create_signal(
                symbol, 'LONG', df, current, long_conf, long_conditions, timeframe, config
            )
            self.active_signals[symbol] = signal
            logger.info(
                f"🆕 NEW LONG signal: {symbol} @ ${signal.entry} (Conf: {signal.confidence:.0%}, "
                f"Daily Trend: {daily_trend})"
            )
            return {'action': 'created', 'signal': signal.to_dict()}

        # Check SHORT conditions
        short_signal, short_conf, short_conditions = self._check_short_conditions(
            df, current, previous, config
        )

        if short_signal and short_conf >= config.min_confidence:
            # PHASE 2 OPTIMIZATION: Multi-Timeframe Confirmation
            # Only take SHORT signals aligned with daily trend
            daily_trend = self._get_higher_timeframe_trend(symbol)

            if daily_trend == "BULLISH":
                logger.info(
                    f"{symbol}: SHORT signal detected (Conf: {short_conf:.0%}) but daily trend is BULLISH, "
                    f"skipping to avoid counter-trend trade"
                )
                return None
            elif daily_trend == "NEUTRAL":
                logger.info(
                    f"{symbol}: SHORT signal detected (Conf: {short_conf:.0%}), daily trend NEUTRAL, "
                    f"proceeding with caution"
                )

            signal = self._create_signal(
                symbol, 'SHORT', df, current, short_conf, short_conditions, timeframe, config
            )
            self.active_signals[symbol] = signal
            logger.info(
                f"🆕 NEW SHORT signal: {symbol} @ ${signal.entry} (Conf: {signal.confidence:.0%}, "
                f"Daily Trend: {daily_trend})"
            )
            return {'action': 'created', 'signal': signal.to_dict()}

        return None

    def _update_existing_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        signal: ActiveSignal,
        timeframe: str,
        config: SignalConfig
    ) -> Optional[Dict]:
        """Update or invalidate existing signal."""
        current = df.iloc[-1]
        previous = df.iloc[-2]

        # Check if signal conditions are still valid
        if signal.direction == 'LONG':
            valid, conf, conditions = self._check_long_conditions(df, current, previous, config)
        else:
            valid, conf, conditions = self._check_short_conditions(df, current, previous, config)

        # Check for signal invalidation
        if not valid or conf < config.min_confidence * 0.7:  # 30% tolerance
            logger.info(f"❌ INVALIDATED {signal.direction} signal: {symbol}")
            del self.active_signals[symbol]
            return {'action': 'deleted', 'signal_id': symbol}

        # Check for signal expiry
        if datetime.now() - signal.created_at > timedelta(minutes=config.signal_expiry_minutes):
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
                signal.sl = Decimal(str(entry - (config.sl_atr_multiplier * atr)))
                signal.tp = Decimal(str(entry + (config.tp_atr_multiplier * atr)))
            else:
                signal.sl = Decimal(str(entry + (config.sl_atr_multiplier * atr)))
                signal.tp = Decimal(str(entry - (config.tp_atr_multiplier * atr)))

            logger.info(
                f"🔄 UPDATED {signal.direction} signal: {symbol} "
                f"(Conf: {signal.confidence:.0%}, Change: {conf_change:+.1%})"
            )
            return {'action': 'updated', 'signal': signal.to_dict()}

        return None  # No significant change

    def _check_long_conditions(self, df, current, previous, config: SignalConfig) -> tuple[bool, float, Dict[str, bool]]:
        """Check LONG signal conditions with realistic confidence scoring."""
        score = 0.0
        max_score = (
            config.macd_weight +
            config.rsi_weight +
            config.price_ema_weight +
            config.adx_weight +
            config.ha_weight +
            config.volume_weight +
            config.ema_alignment_weight +
            config.di_weight +
            config.bb_weight +
            config.volatility_weight +
            config.supertrend_weight +
            config.mfi_weight +
            config.psar_weight
        )

        conditions = {}

        try:
            # 1. MACD Crossover
            if previous['macd_hist'] <= 0 and current['macd_hist'] > 0:
                score += config.macd_weight
                conditions['macd_crossover'] = True
            else:
                conditions['macd_crossover'] = False

            # 2. RSI Range
            if config.long_rsi_min < current['rsi'] < config.long_rsi_max:
                score += config.rsi_weight
                conditions['rsi_favorable'] = True
            elif current['rsi'] > previous['rsi']:
                score += config.rsi_weight * 0.5
                conditions['rsi_favorable'] = True
            else:
                conditions['rsi_favorable'] = False

            # 3. Price above EMA50
            if current['close'] > current['ema_50']:
                score += config.price_ema_weight
                conditions['price_above_ema'] = True
            else:
                conditions['price_above_ema'] = False

            # 4. ADX Strength
            if current['adx'] > config.long_adx_min:
                score += config.adx_weight
                conditions['strong_trend'] = True
            else:
                conditions['strong_trend'] = False

            # 5. Heikin Ashi Bullish
            if current['ha_bullish']:
                score += config.ha_weight
                conditions['ha_bullish'] = True
            else:
                conditions['ha_bullish'] = False

            # 6. Volume Increase
            if current['volume_trend'] > config.long_volume_multiplier:
                score += config.volume_weight
                conditions['volume_spike'] = True
            elif current['volume_trend'] > 1.0:
                score += config.volume_weight * 0.5
                conditions['volume_spike'] = True
            else:
                conditions['volume_spike'] = False

            # 7. EMA Alignment
            if current['ema_9'] > current['ema_21'] > current['ema_50']:
                score += config.ema_alignment_weight
                conditions['ema_aligned'] = True
            else:
                conditions['ema_aligned'] = False

            # 8. +DI > -DI (Directional Movement)
            if current['plus_di'] > current['minus_di']:
                di_diff = current['plus_di'] - current['minus_di']
                if di_diff > 10:
                    score += config.di_weight
                else:
                    score += config.di_weight * min(di_diff / 10, 1.0)
                conditions['positive_di'] = True
            else:
                conditions['positive_di'] = False

            # 9. Bollinger Bands Position
            bb_range = current['bb_upper'] - current['bb_lower']
            if bb_range > 0:
                bb_position = (current['close'] - current['bb_lower']) / bb_range
                if 0.3 < bb_position < 0.7:
                    score += config.bb_weight
                    conditions['bb_favorable'] = True
                elif bb_position < 0.3:
                    score += config.bb_weight * 0.7
                    conditions['bb_favorable'] = True
                else:
                    conditions['bb_favorable'] = False
            else:
                conditions['bb_favorable'] = False

            # 10. Volatility Adjustment
            atr_percent = (current['atr'] / current['close']) * 100
            if atr_percent < 2.0:
                score += config.volatility_weight
                conditions['low_volatility'] = True
            elif atr_percent < 4.0:
                score += config.volatility_weight * 0.5
                conditions['low_volatility'] = True
            else:
                conditions['low_volatility'] = False

            # 11. SuperTrend Bullish
            if current['supertrend_direction'] == 1:
                score += config.supertrend_weight
                conditions['supertrend_bullish'] = True
            else:
                conditions['supertrend_bullish'] = False

            # 12. MFI (Money Flow Index) - Volume-weighted momentum
            if 20 < current['mfi'] < 50:  # Oversold to neutral
                score += config.mfi_weight
                conditions['mfi_favorable'] = True
            elif current['mfi'] > previous['mfi']:  # Rising MFI
                score += config.mfi_weight * 0.6
                conditions['mfi_favorable'] = True
            else:
                conditions['mfi_favorable'] = False

            # 13. Parabolic SAR Bullish
            if current['psar_bullish']:  # Price above SAR
                score += config.psar_weight
                conditions['psar_bullish'] = True
            else:
                conditions['psar_bullish'] = False

            # Calculate realistic confidence
            raw_confidence = score / max_score

            # Apply non-linear transformation for more realistic distribution
            # This prevents too many 90%+ signals
            if raw_confidence > 0.88:
                confidence = 0.78 + (raw_confidence - 0.88) * 1.17  # Map 0.88-1.0 to 0.78-0.92
            elif raw_confidence > 0.75:
                confidence = 0.68 + (raw_confidence - 0.75) * 0.77  # Map 0.75-0.88 to 0.68-0.78
            else:
                confidence = raw_confidence * 0.91  # Map 0.0-0.75 to 0.0-0.68

            confidence = min(confidence, 0.92)  # Cap at 92% for realism
            triggered = score >= (max_score * config.min_confidence)

            return triggered, confidence, conditions

        except Exception as e:
            logger.error(f"Error checking LONG conditions: {e}")
            return False, 0.0, {}

    def _check_short_conditions(self, df, current, previous, config: SignalConfig) -> tuple[bool, float, Dict[str, bool]]:
        """CHECK SHORT signal conditions with realistic confidence scoring."""
        score = 0.0
        max_score = (
            config.macd_weight +
            config.rsi_weight +
            config.price_ema_weight +
            config.adx_weight +
            config.ha_weight +
            config.volume_weight +
            config.ema_alignment_weight +
            config.di_weight +
            config.bb_weight +
            config.volatility_weight +
            config.supertrend_weight +
            config.mfi_weight +
            config.psar_weight
        )

        conditions = {}

        try:
            # 1. MACD Crossover
            if previous['macd_hist'] >= 0 and current['macd_hist'] < 0:
                score += config.macd_weight
                conditions['macd_crossover'] = True
            else:
                conditions['macd_crossover'] = False

            # 2. RSI Range
            if config.short_rsi_min < current['rsi'] < config.short_rsi_max:
                score += config.rsi_weight
                conditions['rsi_favorable'] = True
            elif current['rsi'] < previous['rsi']:
                score += config.rsi_weight * 0.5
                conditions['rsi_favorable'] = True
            else:
                conditions['rsi_favorable'] = False

            # 3. Price below EMA50
            if current['close'] < current['ema_50']:
                score += config.price_ema_weight
                conditions['price_below_ema'] = True
            else:
                conditions['price_below_ema'] = False

            # 4. ADX Strength
            if current['adx'] > config.short_adx_min:
                score += config.adx_weight
                conditions['strong_trend'] = True
            else:
                conditions['strong_trend'] = False

            # 5. Heikin Ashi Bearish
            if not current['ha_bullish']:
                score += config.ha_weight
                conditions['ha_bearish'] = True
            else:
                conditions['ha_bearish'] = False

            # 6. Volume Increase
            if current['volume_trend'] > config.short_volume_multiplier:
                score += config.volume_weight
                conditions['volume_spike'] = True
            elif current['volume_trend'] > 1.0:
                score += config.volume_weight * 0.5
                conditions['volume_spike'] = True
            else:
                conditions['volume_spike'] = False

            # 7. EMA Alignment
            if current['ema_9'] < current['ema_21'] < current['ema_50']:
                score += config.ema_alignment_weight
                conditions['ema_aligned'] = True
            else:
                conditions['ema_aligned'] = False

            # 8. -DI > +DI (Directional Movement)
            if current['minus_di'] > current['plus_di']:
                di_diff = current['minus_di'] - current['plus_di']
                if di_diff > 10:
                    score += config.di_weight
                else:
                    score += config.di_weight * min(di_diff / 10, 1.0)
                conditions['negative_di'] = True
            else:
                conditions['negative_di'] = False

            # 9. Bollinger Bands Position
            bb_range = current['bb_upper'] - current['bb_lower']
            if bb_range > 0:
                bb_position = (current['close'] - current['bb_lower']) / bb_range
                if 0.3 < bb_position < 0.7:
                    score += config.bb_weight
                    conditions['bb_favorable'] = True
                elif bb_position > 0.7:
                    score += config.bb_weight * 0.7
                    conditions['bb_favorable'] = True
                else:
                    conditions['bb_favorable'] = False
            else:
                conditions['bb_favorable'] = False

            # 10. Volatility Adjustment
            atr_percent = (current['atr'] / current['close']) * 100
            if atr_percent < 2.0:
                score += config.volatility_weight
                conditions['low_volatility'] = True
            elif atr_percent < 4.0:
                score += config.volatility_weight * 0.5
                conditions['low_volatility'] = True
            else:
                conditions['low_volatility'] = False

            # 11. SuperTrend Bearish
            if current['supertrend_direction'] == -1:
                score += config.supertrend_weight
                conditions['supertrend_bearish'] = True
            else:
                conditions['supertrend_bearish'] = False

            # 12. MFI (Money Flow Index) - Volume-weighted momentum
            if 50 < current['mfi'] < 80:  # Overbought to neutral
                score += config.mfi_weight
                conditions['mfi_favorable'] = True
            elif current['mfi'] < previous['mfi']:  # Falling MFI
                score += config.mfi_weight * 0.6
                conditions['mfi_favorable'] = True
            else:
                conditions['mfi_favorable'] = False

            # 13. Parabolic SAR Bearish
            if not current['psar_bullish']:  # Price below SAR
                score += config.psar_weight
                conditions['psar_bearish'] = True
            else:
                conditions['psar_bearish'] = False

            # Calculate realistic confidence
            raw_confidence = score / max_score

            # Apply non-linear transformation for more realistic distribution
            if raw_confidence > 0.88:
                confidence = 0.78 + (raw_confidence - 0.88) * 1.17  # Map 0.88-1.0 to 0.78-0.92
            elif raw_confidence > 0.75:
                confidence = 0.68 + (raw_confidence - 0.75) * 0.77  # Map 0.75-0.88 to 0.68-0.78
            else:
                confidence = raw_confidence * 0.91  # Map 0.0-0.75 to 0.0-0.68

            confidence = min(confidence, 0.92)  # Cap at 92% for realism
            triggered = score >= (max_score * config.min_confidence)

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
        timeframe: str,
        config: SignalConfig
    ) -> ActiveSignal:
        """Create new active signal."""
        entry = float(current['close'])
        atr = float(current['atr'])

        if direction == 'LONG':
            sl = entry - (config.sl_atr_multiplier * atr)
            tp = entry + (config.tp_atr_multiplier * atr)
        else:
            sl = entry + (config.sl_atr_multiplier * atr)
            tp = entry - (config.tp_atr_multiplier * atr)

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
