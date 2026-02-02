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

try:
    from scanner.services.fib_utils import check_fibonacci_pullback
    FIBONACCI_AVAILABLE = True
except ImportError:
    logger.warning("Fibonacci utils not available - pullback detection disabled")
    FIBONACCI_AVAILABLE = False

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
    long_rsi_min: float = 20.0
    long_rsi_max: float = 40.0
    long_adx_min: float = 18.0
    long_volume_multiplier: float = 1.2

    short_rsi_min: float = 60.0
    short_rsi_max: float = 80.0
    short_adx_min: float = 18.0
    short_volume_multiplier: float = 1.2

    sl_atr_multiplier: float = 2.5
    tp_atr_multiplier: float = 7.5

    risk_reward_ratio: float = 3.0

    min_confidence: float = 0.65
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

    # FIBONACCI PULLBACK PARAMETERS
    fibonacci_weight: float = 2.5    # Strong pullback confirmation
    fib_lookback_candles: int = 50   # How many candles to search for swing high/low
    fib_entry_zone_min: float = 0.5  # 50% Fibonacci retracement
    fib_entry_zone_max: float = 0.618  # Golden ratio (61.8%)
    fib_enable_pullback: bool = True  # Enable Fibonacci pullback detection


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
    meta: Dict = field(default_factory=dict)  # Fibonacci & strategy metadata
    status: str = 'ACTIVE'  # ACTIVE, WAITING_FOR_PULLBACK, ENTRY_ZONE_REACHED

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
            'meta': self.meta,  # Fibonacci & strategy metadata
            'status': self.status,  # Signal status
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

    def _get_higher_timeframe_trend(self, symbol: str, current_timeframe: str) -> str:
        """
        Get higher timeframe trend direction using EMA crossover.

        PHASE 2 OPTIMIZATION: Multi-Timeframe Confirmation
        Only take signals aligned with higher timeframe trend.

        Timeframe mapping:
        - 15m -> check 1h trend
        - 1h -> check 4h trend
        - 4h, 1d -> no confirmation needed (return BULLISH to allow)

        Args:
            symbol: Trading pair symbol
            current_timeframe: Current signal timeframe

        Returns:
            "BULLISH", "BEARISH", or "NEUTRAL"
        """
        from scanner.indicators.indicator_utils import (
            klines_to_dataframe,
            calculate_all_indicators
        )

        # Timeframe mapping: current -> higher timeframe
        timeframe_map = {
            '15m': '1h',
            '1h': '4h'
        }

        # 4h and 1d don't need confirmation
        if current_timeframe not in timeframe_map:
            logger.debug(f"{symbol}: {current_timeframe} doesn't need MTF confirmation, returning BULLISH")
            return "BULLISH"

        higher_tf = timeframe_map[current_timeframe]

        try:
            # Get higher timeframe candles from cache
            # We need at least 50 candles for EMA calculation
            cache_key = f"{symbol}_{higher_tf}"

            if cache_key not in self.candle_cache:
                logger.debug(f"{symbol}: No {higher_tf} candles in cache (key: {cache_key}), returning NEUTRAL")
                return "NEUTRAL"

            higher_candles = self.candle_cache[cache_key]

            if len(higher_candles) < 50:
                logger.debug(
                    f"{symbol}: Not enough {higher_tf} candles for MTF check "
                    f"({len(higher_candles)}/50 required), returning NEUTRAL"
                )
                return "NEUTRAL"

            # Convert to DataFrame and calculate indicators
            df = klines_to_dataframe(list(higher_candles))
            df = calculate_all_indicators(df)

            if len(df) == 0:
                logger.debug(f"{symbol}: Empty dataframe for {higher_tf}, returning NEUTRAL")
                return "NEUTRAL"

            current = df.iloc[-1]

            # EMA9 vs EMA50 trend determination
            ema_9 = current.get('ema_9', 0)
            ema_50 = current.get('ema_50', 0)
            close = current.get('close', 0)

            if ema_9 > ema_50:
                if close > ema_50:
                    logger.debug(f"{symbol}: {higher_tf} trend is BULLISH (EMA9 > EMA50, close above EMA50)")
                    return "BULLISH"
            elif ema_9 < ema_50:
                if close < ema_50:
                    logger.debug(f"{symbol}: {higher_tf} trend is BEARISH (EMA9 < EMA50, close below EMA50)")
                    return "BEARISH"

            logger.debug(f"{symbol}: {higher_tf} trend is NEUTRAL")
            return "NEUTRAL"

        except Exception as e:
            logger.error(f"Error getting {higher_tf} trend for {symbol}: {e}")
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


        long_signal, long_conf, long_conditions = self._check_long_conditions(
            df, current, previous, config, symbol
        )

        if long_signal and long_conf >= config.min_confidence:
            signal = self._create_signal(
                symbol, 'LONG', df, current, long_conf, long_conditions, timeframe, config
            )
            self.active_signals[symbol] = signal
            logger.info(
                f"🆕 NEW LONG signal: {symbol} @ ${signal.entry} (Conf: {signal.confidence:.0%})"
            )
            signal_dict = signal.to_dict()
            return {'action': 'created', 'signal': signal_dict}

        short_signal, short_conf, short_conditions = self._check_short_conditions(
            df, current, previous, config, symbol
        )

        if short_signal and short_conf >= config.min_confidence:
            signal = self._create_signal(
                symbol, 'SHORT', df, current, short_conf, short_conditions, timeframe, config
            )
            self.active_signals[symbol] = signal
            logger.info(
                f"🆕 NEW SHORT signal: {symbol} @ ${signal.entry} (Conf: {signal.confidence:.0%})"
            )
            signal_dict = signal.to_dict()
            return {'action': 'created', 'signal': signal_dict}

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

        if signal.direction == 'LONG':
            valid, conf, conditions = self._check_long_conditions(df, current, previous, config, symbol)
        else:
            valid, conf, conditions = self._check_short_conditions(df, current, previous, config, symbol)

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
        if conf_change > 0.05:
            signal.confidence = conf
            signal.last_updated = datetime.now()
            signal.conditions_met = conditions

            entry = float(signal.entry)
            risk_percentage = 0.025
            profit_percentage = 0.06

            if signal.direction == 'LONG':
                sl = entry * (1 - risk_percentage)
                tp = entry * (1 + profit_percentage)
            else:
                sl = entry * (1 + risk_percentage)
                tp = entry * (1 - profit_percentage)

            signal.sl = Decimal(str(sl))
            signal.tp = Decimal(str(tp))

            risk_amount = abs(entry - sl)
            reward_amount = abs(tp - entry)
            risk_pct = (risk_amount / entry) * 100
            reward_pct = (reward_amount / entry) * 100
            rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0

            logger.info(
                f"🔄 UPDATED {signal.direction} signal: {symbol} "
                f"(Conf: {signal.confidence:.0%}, Change: {conf_change:+.1%}, Risk={risk_pct:.2f}%, Profit={reward_pct:.2f}%, R/R=1:{rr_ratio:.2f})"
            )
            return {'action': 'updated', 'signal': signal.to_dict()}

        return None  # No significant change

    def _check_long_conditions(self, df, current, previous, config: SignalConfig, symbol: str = None) -> tuple[bool, float, Dict[str, bool]]:
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
            config.psar_weight +
            (config.fibonacci_weight if config.fib_enable_pullback else 0)
        )

        conditions = {}
        fib_meta = {}

        try:
            # 1. MACD Crossover - LONG SPECIFIC: Require histogram increasing
            macd_crossed = previous['macd_hist'] <= 0 and current['macd_hist'] > 0
            macd_increasing = current['macd_hist'] > previous['macd_hist']

            if macd_crossed and macd_increasing:
                score += config.macd_weight
                conditions['macd_crossover'] = True
            elif macd_crossed:
                score += config.macd_weight * 0.5
                conditions['macd_crossover'] = True
            elif macd_increasing and current['macd_hist'] > 0:
                score += config.macd_weight * 0.3
                conditions['macd_crossover'] = True
            else:
                conditions['macd_crossover'] = False

            # 2. RSI Range - MUST be in range AND rising for LONG
            rsi_in_range = config.long_rsi_min < current['rsi'] < config.long_rsi_max
            rsi_rising = current['rsi'] > previous['rsi']

            if rsi_in_range and rsi_rising:
                score += config.rsi_weight
                conditions['rsi_favorable'] = True
            elif rsi_in_range:
                score += config.rsi_weight * 0.4
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

            # 8. +DI > -DI (Directional Movement) - LONG SPECIFIC: +DI must also be rising
            di_positive = current['plus_di'] > current['minus_di']
            di_rising = current['plus_di'] > previous['plus_di']

            if di_positive and di_rising:
                di_diff = current['plus_di'] - current['minus_di']
                if di_diff > 10:
                    score += config.di_weight
                else:
                    score += config.di_weight * min(di_diff / 10, 1.0)
                conditions['positive_di'] = True
            elif di_positive:
                score += config.di_weight * 0.3
                conditions['positive_di'] = True
            else:
                conditions['positive_di'] = False

            # 9. Bollinger Bands Position - LONG SPECIFIC: Prefer price near lower band (mean reversion)
            bb_range = current['bb_upper'] - current['bb_lower']
            if bb_range > 0:
                bb_position = (current['close'] - current['bb_lower']) / bb_range
                if bb_position < 0.25:
                    score += config.bb_weight
                    conditions['bb_favorable'] = True
                elif bb_position < 0.4:
                    score += config.bb_weight * 0.6
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

            if config.fib_enable_pullback and FIBONACCI_AVAILABLE:
                try:
                    in_zone, fib_data = check_fibonacci_pullback(
                        df, current, 'LONG',
                        lookback=config.fib_lookback_candles,
                        entry_zone_min=config.fib_entry_zone_min,
                        entry_zone_max=config.fib_entry_zone_max,
                        symbol=symbol
                    )
                    if in_zone:
                        score += config.fibonacci_weight
                        conditions['fibonacci_pullback'] = True
                        conditions['_fib_meta'] = fib_data
                        logger.info(
                            f"🎯 Fibonacci pullback confirmed: "
                            f"Price {fib_data.get('current_price'):.2f} in golden zone "
                            f"[{fib_data.get('fib_61_8'):.2f} - {fib_data.get('fib_50'):.2f}]"
                        )
                    else:
                        conditions['fibonacci_pullback'] = False
                        if fib_data:
                            conditions['_fib_meta'] = fib_data
                except Exception as e:
                    logger.warning(f"Fibonacci pullback check failed: {e}")
                    conditions['fibonacci_pullback'] = False
            else:
                conditions['fibonacci_pullback'] = False

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

            # LONG-SPECIFIC: Require minimum bullish confirmations to avoid weak entries
            if triggered:
                bullish_checks = [
                    conditions.get('supertrend_bullish', False),
                    conditions.get('positive_di', False),
                    conditions.get('ema_aligned', False),
                    conditions.get('ha_bullish', False),
                    conditions.get('psar_bullish', False),
                ]
                bullish_count = sum(bullish_checks)

                if bullish_count < 3:
                    logger.debug(
                        f"LONG rejected: Only {bullish_count}/5 bullish confirmations "
                        f"(need 3+). ST={conditions.get('supertrend_bullish')}, "
                        f"+DI={conditions.get('positive_di')}, EMA={conditions.get('ema_aligned')}"
                    )
                    triggered = False

            return triggered, confidence, conditions

        except Exception as e:
            logger.error(f"Error checking LONG conditions: {e}")
            return False, 0.0, {}

    def _check_short_conditions(self, df, current, previous, config: SignalConfig, symbol: str = None) -> tuple[bool, float, Dict[str, bool]]:
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
            config.psar_weight +
            (config.fibonacci_weight if config.fib_enable_pullback else 0)
        )

        conditions = {}
        fib_meta = {}

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

            if config.fib_enable_pullback and FIBONACCI_AVAILABLE:
                try:
                    in_zone, fib_data = check_fibonacci_pullback(
                        df, current, 'SHORT',
                        lookback=config.fib_lookback_candles,
                        entry_zone_min=config.fib_entry_zone_min,
                        entry_zone_max=config.fib_entry_zone_max,
                        symbol=symbol
                    )
                    if in_zone:
                        score += config.fibonacci_weight
                        conditions['fibonacci_pullback'] = True
                        conditions['_fib_meta'] = fib_data
                        logger.info(
                            f"🎯 Fibonacci pullback confirmed (SHORT): "
                            f"Price {fib_data.get('current_price'):.2f} in golden zone "
                            f"[{fib_data.get('fib_50'):.2f} - {fib_data.get('fib_61_8'):.2f}]"
                        )
                    else:
                        conditions['fibonacci_pullback'] = False
                        if fib_data:
                            conditions['_fib_meta'] = fib_data
                except Exception as e:
                    logger.warning(f"Fibonacci pullback check failed (SHORT): {e}")
                    conditions['fibonacci_pullback'] = False
            else:
                conditions['fibonacci_pullback'] = False

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
        """
        Create new active signal with PERCENTAGE-BASED Risk/Reward.

        Risk: 3% of position size
        Profit: 6% of position size (1:2 R/R ratio)

        SL and TP are calculated to achieve exactly:
        - 3% loss if SL is hit
        - 6% gain if TP is hit (1:2.4 R/R ratio)
        """
        entry = float(current['close'])

        risk_percentage = 0.025
        profit_percentage = 0.06

        if direction == 'LONG':
            sl = entry * (1 - risk_percentage)
            tp = entry * (1 + profit_percentage)
        else:
            sl = entry * (1 + risk_percentage)
            tp = entry * (1 - profit_percentage)

        risk_amount = abs(entry - sl)
        reward_amount = abs(tp - entry)
        risk_pct = (risk_amount / entry) * 100
        reward_pct = (reward_amount / entry) * 100
        rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0

        logger.info(
            f"📐 {symbol} {direction} ({timeframe}): Entry={entry:.8f}, SL={sl:.8f}, TP={tp:.8f}, "
            f"Risk={risk_pct:.2f}%, Profit={reward_pct:.2f}%, R/R=1:{rr_ratio:.2f}"
        )

        description = self._generate_description(direction, current, conditions)

        fib_meta = conditions.get('_fib_meta', {})
        has_fib_pullback = conditions.get('fibonacci_pullback', False)

        meta = {}
        if has_fib_pullback and fib_meta:
            meta = {
                'strategy': 'fibonacci_pullback',
                'swing_high': fib_meta.get('swing_high'),
                'swing_low': fib_meta.get('swing_low'),
                'fib_38_2': fib_meta.get('fib_38_2'),
                'fib_50': fib_meta.get('fib_50'),
                'fib_61_8': fib_meta.get('fib_61_8'),
                'fib_78_6': fib_meta.get('fib_78_6'),
                'pullback_depth': fib_meta.get('pullback_depth'),
                'entry_zone': fib_meta.get('entry_zone'),
                'in_entry_zone': fib_meta.get('in_entry_zone')
            }

        conditions_copy = {k: v for k, v in conditions.items() if not k.startswith('_')}

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
            conditions_met=conditions_copy,
            meta=meta,
            status='WAITING_FOR_PULLBACK' if has_fib_pullback else 'ACTIVE'
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
