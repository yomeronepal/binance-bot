"""
Volatility Classifier Service
Auto-classifies symbols into High/Medium/Low volatility and provides appropriate configurations
"""
import logging
from typing import Dict, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class VolatilityProfile:
    """Volatility profile for a symbol"""
    symbol: str
    volatility_level: str  # 'HIGH', 'MEDIUM', 'LOW'
    daily_volatility: float  # Percentage
    atr_pct: float  # ATR as percentage of price
    rsi_extremes_frequency: float  # How often RSI hits 30 or 70
    confidence: float  # Confidence in classification (0-1)
    last_updated: datetime

    # Recommended parameters based on volatility
    sl_atr_multiplier: float
    tp_atr_multiplier: float
    adx_threshold: float
    min_confidence: float


class VolatilityClassifier:
    """
    Classifies symbols by volatility and provides optimal parameters
    """

    # Volatility thresholds (daily % change)
    HIGH_VOL_THRESHOLD = 10.0  # >10% daily volatility
    LOW_VOL_THRESHOLD = 5.0    # <5% daily volatility

    # Known coin categories (can be expanded)
    MEME_COINS = {
        'PEPE', 'SHIB', 'DOGE', 'FLOKI', 'WIF', 'BONK', 'BABYDOGE',
        'ELON', 'AKITA', 'KISHU', 'SAFEMOON', 'MEME'
    }

    STABLE_COINS = {
        'BTC', 'ETH', 'BNB', 'USDT', 'USDC', 'BUSD', 'DAI'
    }

    ESTABLISHED_ALTS = {
        'SOL', 'ADA', 'DOT', 'MATIC', 'AVAX', 'LINK', 'UNI', 'AAVE',
        'ATOM', 'ALGO', 'XLM', 'VET', 'FIL', 'SAND', 'MANA', 'AXS'
    }

    def __init__(self):
        """Initialize volatility classifier"""
        self.cache = {}  # Symbol -> VolatilityProfile
        self.cache_ttl = timedelta(hours=24)  # Recalculate daily

    def classify_symbol(
        self,
        symbol: str,
        historical_data: Optional[pd.DataFrame] = None,
        force_recalculate: bool = False
    ) -> VolatilityProfile:
        """
        Classify a symbol's volatility level

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            historical_data: Optional historical candle data
            force_recalculate: Force recalculation even if cached

        Returns:
            VolatilityProfile with classification and recommended parameters
        """
        # Check cache first
        if not force_recalculate and symbol in self.cache:
            profile = self.cache[symbol]
            if datetime.now() - profile.last_updated < self.cache_ttl:
                logger.debug(f"Using cached volatility profile for {symbol}: {profile.volatility_level}")
                return profile

        # Try quick classification first (based on known categories)
        quick_profile = self._quick_classify(symbol)
        if quick_profile and historical_data is None:
            self.cache[symbol] = quick_profile
            return quick_profile

        # If we have historical data, do detailed analysis
        if historical_data is not None and len(historical_data) > 0:
            detailed_profile = self._detailed_classify(symbol, historical_data)
            self.cache[symbol] = detailed_profile
            return detailed_profile

        # Fallback to quick classification
        if quick_profile:
            self.cache[symbol] = quick_profile
            return quick_profile

        # Ultimate fallback: assume medium volatility
        logger.warning(f"Could not classify {symbol}, using MEDIUM volatility as default")
        return self._create_medium_profile(symbol, confidence=0.5)

    def _quick_classify(self, symbol: str) -> Optional[VolatilityProfile]:
        """
        Quick classification based on coin category
        """
        base_symbol = symbol.replace('USDT', '').replace('BUSD', '').replace('USD', '')

        # Check if it's a known meme coin (HIGH volatility)
        if base_symbol in self.MEME_COINS or 'PEPE' in base_symbol or 'INU' in base_symbol:
            return self._create_high_profile(symbol, confidence=0.8)

        # Check if it's a stablecoin or BTC/ETH (LOW volatility)
        if base_symbol in self.STABLE_COINS:
            return self._create_low_profile(symbol, confidence=0.9)

        # Check if it's an established altcoin (MEDIUM volatility)
        if base_symbol in self.ESTABLISHED_ALTS:
            return self._create_medium_profile(symbol, confidence=0.8)

        # Unknown coin - return None to trigger detailed analysis if data available
        return None

    def _detailed_classify(self, symbol: str, df: pd.DataFrame) -> VolatilityProfile:
        """
        Detailed classification using historical data

        Args:
            symbol: Trading symbol
            df: DataFrame with columns: open, high, low, close, volume

        Returns:
            VolatilityProfile with detailed analysis
        """
        if len(df) < 20:
            logger.warning(f"Insufficient data for {symbol} ({len(df)} candles), using quick classification")
            return self._quick_classify(symbol) or self._create_medium_profile(symbol, confidence=0.5)

        # Calculate daily volatility (standard deviation of returns)
        df = df.copy()
        df['returns'] = df['close'].pct_change()
        daily_vol = float(df['returns'].std() * 100 * np.sqrt(24))  # Annualized daily vol

        # Calculate ATR as percentage of price
        df['tr'] = df.apply(lambda row: max(
            row['high'] - row['low'],
            abs(row['high'] - row.get('prev_close', row['close'])),
            abs(row['low'] - row.get('prev_close', row['close']))
        ), axis=1)
        df['prev_close'] = df['close'].shift(1)
        atr = float(df['tr'].rolling(14).mean().iloc[-1])
        atr_pct = (atr / float(df['close'].iloc[-1])) * 100

        # Calculate RSI to check how often it hits extremes
        try:
            df['rsi'] = self._calculate_rsi(df['close'], period=14)
            rsi_extremes = ((df['rsi'] < 30) | (df['rsi'] > 70)).sum()
            rsi_extreme_freq = float(rsi_extremes / len(df))
        except Exception as e:
            logger.warning(f"Could not calculate RSI for {symbol}: {e}")
            rsi_extreme_freq = 0.1  # Default

        # Classify based on metrics
        if daily_vol >= self.HIGH_VOL_THRESHOLD or atr_pct >= 5.0:
            volatility_level = 'HIGH'
            profile_func = self._create_high_profile
        elif daily_vol <= self.LOW_VOL_THRESHOLD and atr_pct <= 2.0:
            volatility_level = 'LOW'
            profile_func = self._create_low_profile
        else:
            volatility_level = 'MEDIUM'
            profile_func = self._create_medium_profile

        logger.info(
            f"Classified {symbol} as {volatility_level} volatility "
            f"(daily_vol={daily_vol:.2f}%, atr={atr_pct:.2f}%, rsi_extremes={rsi_extreme_freq:.1%})"
        )

        # Create profile with actual metrics
        profile = profile_func(symbol, confidence=0.9)
        profile.daily_volatility = daily_vol
        profile.atr_pct = atr_pct
        profile.rsi_extremes_frequency = rsi_extreme_freq

        return profile

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _create_high_profile(self, symbol: str, confidence: float) -> VolatilityProfile:
        """Create HIGH volatility profile with appropriate parameters"""
        return VolatilityProfile(
            symbol=symbol,
            volatility_level='HIGH',
            daily_volatility=15.0,  # Estimate
            atr_pct=6.0,  # Estimate
            rsi_extremes_frequency=0.3,  # Frequent
            confidence=confidence,
            last_updated=datetime.now(),
            # Recommended parameters for HIGH volatility
            sl_atr_multiplier=2.0,  # Wider stops
            tp_atr_multiplier=3.5,  # Bigger targets
            adx_threshold=18.0,  # Lower threshold (more signals)
            min_confidence=0.70  # Accept more signals
        )

    def _create_medium_profile(self, symbol: str, confidence: float) -> VolatilityProfile:
        """Create MEDIUM volatility profile with appropriate parameters"""
        return VolatilityProfile(
            symbol=symbol,
            volatility_level='MEDIUM',
            daily_volatility=7.5,  # Estimate
            atr_pct=3.0,  # Estimate
            rsi_extremes_frequency=0.15,  # Moderate
            confidence=confidence,
            last_updated=datetime.now(),
            # Recommended parameters for MEDIUM volatility (current optimal)
            sl_atr_multiplier=1.5,  # Standard
            tp_atr_multiplier=2.5,  # Standard
            adx_threshold=22.0,  # Standard
            min_confidence=0.75  # Standard
        )

    def _create_low_profile(self, symbol: str, confidence: float) -> VolatilityProfile:
        """Create LOW volatility profile with appropriate parameters"""
        return VolatilityProfile(
            symbol=symbol,
            volatility_level='LOW',
            daily_volatility=3.5,  # Estimate
            atr_pct=1.5,  # Estimate
            rsi_extremes_frequency=0.05,  # Rare
            confidence=confidence,
            last_updated=datetime.now(),
            # Recommended parameters for LOW volatility
            sl_atr_multiplier=1.0,  # Tighter stops
            tp_atr_multiplier=2.0,  # Closer targets
            adx_threshold=20.0,  # Lower threshold (more signals)
            min_confidence=0.70  # Accept more signals
        )

    def get_config_for_symbol(self, symbol: str, historical_data: Optional[pd.DataFrame] = None) -> Dict:
        """
        Get recommended configuration for a symbol

        Returns:
            Dictionary with recommended signal configuration parameters
        """
        profile = self.classify_symbol(symbol, historical_data)

        return {
            'symbol': symbol,
            'volatility_level': profile.volatility_level,
            'confidence': profile.confidence,
            'parameters': {
                'sl_atr_multiplier': profile.sl_atr_multiplier,
                'tp_atr_multiplier': profile.tp_atr_multiplier,
                'adx_threshold': profile.adx_threshold,
                'min_confidence': profile.min_confidence,
            },
            'metrics': {
                'daily_volatility': profile.daily_volatility,
                'atr_pct': profile.atr_pct,
                'rsi_extremes_frequency': profile.rsi_extremes_frequency,
            }
        }

    def clear_cache(self, symbol: Optional[str] = None):
        """Clear cache for specific symbol or all symbols"""
        if symbol:
            self.cache.pop(symbol, None)
            logger.info(f"Cleared volatility cache for {symbol}")
        else:
            self.cache.clear()
            logger.info("Cleared all volatility cache")


# Singleton instance
_volatility_classifier = None


def get_volatility_classifier() -> VolatilityClassifier:
    """Get singleton volatility classifier instance"""
    global _volatility_classifier
    if _volatility_classifier is None:
        _volatility_classifier = VolatilityClassifier()
    return _volatility_classifier
