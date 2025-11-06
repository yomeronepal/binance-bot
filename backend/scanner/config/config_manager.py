"""
Universal Configuration Manager with Market Detection

Provides market-specific configurations (Forex vs Binance) that are automatically
applied during signal scanning and backtesting.

Features:
- Automatic market type detection based on symbol
- Universal configurations for Forex and Binance markets
- Configuration validation and inheritance
- Audit logging for configuration application
- Thread-safe singleton pattern
"""
import logging
import re
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class MarketType(Enum):
    """Market type enumeration"""
    FOREX = "forex"
    BINANCE = "binance"
    UNKNOWN = "unknown"


@dataclass
class UniversalConfig:
    """
    Universal configuration for a specific market type.

    These are optimized parameters based on extensive backtesting
    for each market's unique characteristics.
    """
    # Market identification
    market_type: MarketType
    name: str
    description: str

    # LONG signal thresholds (Buy when oversold)
    long_rsi_min: float
    long_rsi_max: float
    long_adx_min: float
    long_volume_multiplier: float = 1.2

    # SHORT signal thresholds (Sell when overbought)
    short_rsi_min: float
    short_rsi_max: float
    short_adx_min: float
    short_volume_multiplier: float = 1.2

    # Stop loss and take profit multipliers (ATR-based)
    sl_atr_multiplier: float
    tp_atr_multiplier: float

    # Signal quality threshold
    min_confidence: float

    # Preferred timeframes for this market
    preferred_timeframes: list = field(default_factory=lambda: ["4h"])

    # Signal management
    max_candles_cache: int = 200
    signal_expiry_minutes: int = 60

    # Indicator weights (same across markets, but can be customized)
    macd_weight: float = 2.0
    rsi_weight: float = 1.5
    price_ema_weight: float = 1.8
    adx_weight: float = 1.7
    ha_weight: float = 1.6
    volume_weight: float = 1.4
    ema_alignment_weight: float = 1.2
    di_weight: float = 1.0
    bb_weight: float = 0.8
    volatility_weight: float = 0.5
    supertrend_weight: float = 1.9
    mfi_weight: float = 1.3
    psar_weight: float = 1.1

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['market_type'] = self.market_type.value
        data['created_at'] = self.created_at.isoformat()
        data['last_updated'] = self.last_updated.isoformat()
        return data

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate configuration parameters.

        Returns:
            (is_valid, errors): Tuple of validation result and error messages
        """
        errors = []

        # RSI ranges
        if not (0 <= self.long_rsi_min < self.long_rsi_max <= 100):
            errors.append(f"Invalid LONG RSI range: {self.long_rsi_min}-{self.long_rsi_max}")

        if not (0 <= self.short_rsi_min < self.short_rsi_max <= 100):
            errors.append(f"Invalid SHORT RSI range: {self.short_rsi_min}-{self.short_rsi_max}")

        # ADX thresholds
        if not (0 <= self.long_adx_min <= 100):
            errors.append(f"Invalid LONG ADX: {self.long_adx_min}")

        if not (0 <= self.short_adx_min <= 100):
            errors.append(f"Invalid SHORT ADX: {self.short_adx_min}")

        # ATR multipliers
        if self.sl_atr_multiplier <= 0:
            errors.append(f"Invalid SL multiplier: {self.sl_atr_multiplier}")

        if self.tp_atr_multiplier <= 0:
            errors.append(f"Invalid TP multiplier: {self.tp_atr_multiplier}")

        # Risk/reward ratio
        if self.tp_atr_multiplier <= self.sl_atr_multiplier:
            errors.append(f"TP must be > SL (TP: {self.tp_atr_multiplier}, SL: {self.sl_atr_multiplier})")

        # Confidence threshold
        if not (0 < self.min_confidence <= 1):
            errors.append(f"Invalid confidence: {self.min_confidence}")

        return (len(errors) == 0, errors)


class ConfigManager:
    """
    Singleton configuration manager that detects market type and provides
    appropriate universal configurations.

    Thread-safe implementation using double-checked locking.
    """

    _instance = None
    _lock = threading.Lock()

    # Forex symbol patterns (common forex pairs)
    FOREX_PATTERNS = [
        r'^[A-Z]{6}$',  # EURUSD, GBPJPY, etc.
        r'^[A-Z]{3}_[A-Z]{3}$',  # EUR_USD, GBP_JPY, etc.
    ]

    # Binance symbol patterns (crypto pairs)
    BINANCE_PATTERNS = [
        r'^[A-Z]+USDT$',  # BTCUSDT, ETHUSDT, etc.
        r'^[A-Z]+BUSD$',  # BTCBUSD, etc.
        r'^[A-Z]+BTC$',   # ETHBTC, etc.
        r'^[A-Z]+ETH$',   # Various/ETH pairs
    ]

    def __new__(cls):
        """Singleton pattern with thread-safe initialization"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize configuration manager with universal configs"""
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self._configs: Dict[MarketType, UniversalConfig] = {}
        self._audit_log: list[Dict] = []

        # Initialize universal configurations
        self._initialize_forex_config()
        self._initialize_binance_config()

        logger.info("✅ ConfigManager initialized with universal configurations")

    def _initialize_forex_config(self):
        """
        Initialize Forex universal configuration.

        Loads parameters from user_config.py for easy modification.

        Forex markets characteristics:
        - Lower volatility compared to crypto
        - Tighter spreads on major pairs
        - Different trading hours (24/5)
        - More stable trends

        Optimized for:
        - Major pairs (EUR/USD, GBP/USD, USD/JPY)
        - 1H and 4H timeframes
        - Lower risk tolerance
        """
        # Load parameters from user config file
        try:
            from scanner.config.user_config import FOREX_CONFIG
            params = FOREX_CONFIG
            logger.info("✅ Loaded Forex config from user_config.py")
        except ImportError:
            logger.warning("⚠️ Could not load user_config.py, using defaults")
            params = {
                "long_rsi_min": 25.0,
                "long_rsi_max": 35.0,
                "long_adx_min": 20.0,
                "short_rsi_min": 65.0,
                "short_rsi_max": 75.0,
                "short_adx_min": 20.0,
                "sl_atr_multiplier": 2.0,
                "tp_atr_multiplier": 6.0,
                "min_confidence": 0.70,
                "preferred_timeframes": ["1h", "4h"],
            }

        forex_config = UniversalConfig(
            market_type=MarketType.FOREX,
            name="Forex Universal Configuration",
            description="Optimized for Forex major pairs with lower volatility",

            # Load all parameters from user config
            long_rsi_min=params.get("long_rsi_min", 25.0),
            long_rsi_max=params.get("long_rsi_max", 35.0),
            long_adx_min=params.get("long_adx_min", 20.0),
            long_volume_multiplier=params.get("long_volume_multiplier", 1.2),

            short_rsi_min=params.get("short_rsi_min", 65.0),
            short_rsi_max=params.get("short_rsi_max", 75.0),
            short_adx_min=params.get("short_adx_min", 20.0),
            short_volume_multiplier=params.get("short_volume_multiplier", 1.2),

            sl_atr_multiplier=params.get("sl_atr_multiplier", 2.0),
            tp_atr_multiplier=params.get("tp_atr_multiplier", 6.0),

            min_confidence=params.get("min_confidence", 0.70),

            max_candles_cache=params.get("max_candles_cache", 200),
            signal_expiry_minutes=params.get("signal_expiry_minutes", 60),

            preferred_timeframes=params.get("preferred_timeframes", ["1h", "4h"]),

            # Indicator weights
            macd_weight=params.get("macd_weight", 2.0),
            rsi_weight=params.get("rsi_weight", 1.5),
            price_ema_weight=params.get("price_ema_weight", 1.8),
            adx_weight=params.get("adx_weight", 1.7),
            ha_weight=params.get("ha_weight", 1.6),
            volume_weight=params.get("volume_weight", 1.4),
            ema_alignment_weight=params.get("ema_alignment_weight", 1.2),
            di_weight=params.get("di_weight", 1.0),
            bb_weight=params.get("bb_weight", 0.8),
            volatility_weight=params.get("volatility_weight", 0.5),
            supertrend_weight=params.get("supertrend_weight", 1.9),
            mfi_weight=params.get("mfi_weight", 1.3),
            psar_weight=params.get("psar_weight", 1.1),
        )

        is_valid, errors = forex_config.validate()
        if not is_valid:
            logger.error(f"❌ Forex config validation failed: {errors}")
            raise ValueError(f"Invalid Forex configuration: {errors}")

        self._configs[MarketType.FOREX] = forex_config
        logger.info(f"✅ Forex universal config initialized: ADX={forex_config.long_adx_min}, "
                   f"RSI={forex_config.long_rsi_min}-{forex_config.long_rsi_max}, "
                   f"ATR={forex_config.sl_atr_multiplier}/{forex_config.tp_atr_multiplier}")

    def _initialize_binance_config(self):
        """
        Initialize Binance universal configuration.

        Loads parameters from user_config.py for easy modification.

        Binance/Crypto characteristics:
        - Higher volatility
        - 24/7 trading
        - Stronger trends but also more noise
        - Wider spreads on some pairs

        Optimized for:
        - Major crypto (BTC, ETH, BNB)
        - 4H timeframe primarily
        - Proven OPT6 parameters
        """
        # Load parameters from user config file
        try:
            from scanner.config.user_config import BINANCE_CONFIG
            params = BINANCE_CONFIG
            logger.info("✅ Loaded Binance config from user_config.py")
        except ImportError:
            logger.warning("⚠️ Could not load user_config.py, using defaults")
            params = {
                "long_rsi_min": 23.0,
                "long_rsi_max": 33.0,
                "long_adx_min": 22.0,
                "short_rsi_min": 67.0,
                "short_rsi_max": 77.0,
                "short_adx_min": 22.0,
                "sl_atr_multiplier": 1.5,
                "tp_atr_multiplier": 5.25,
                "min_confidence": 0.73,
                "preferred_timeframes": ["4h"],
            }

        binance_config = UniversalConfig(
            market_type=MarketType.BINANCE,
            name="Binance Universal Configuration (OPT6)",
            description="Proven configuration for crypto markets (-0.03% ROI on 11 months)",

            # Load all parameters from user config
            long_rsi_min=params.get("long_rsi_min", 23.0),
            long_rsi_max=params.get("long_rsi_max", 33.0),
            long_adx_min=params.get("long_adx_min", 22.0),
            long_volume_multiplier=params.get("long_volume_multiplier", 1.2),

            short_rsi_min=params.get("short_rsi_min", 67.0),
            short_rsi_max=params.get("short_rsi_max", 77.0),
            short_adx_min=params.get("short_adx_min", 22.0),
            short_volume_multiplier=params.get("short_volume_multiplier", 1.2),

            sl_atr_multiplier=params.get("sl_atr_multiplier", 1.5),
            tp_atr_multiplier=params.get("tp_atr_multiplier", 5.25),

            min_confidence=params.get("min_confidence", 0.73),

            max_candles_cache=params.get("max_candles_cache", 200),
            signal_expiry_minutes=params.get("signal_expiry_minutes", 60),

            preferred_timeframes=params.get("preferred_timeframes", ["4h"]),

            # Indicator weights
            macd_weight=params.get("macd_weight", 2.0),
            rsi_weight=params.get("rsi_weight", 1.5),
            price_ema_weight=params.get("price_ema_weight", 1.8),
            adx_weight=params.get("adx_weight", 1.7),
            ha_weight=params.get("ha_weight", 1.6),
            volume_weight=params.get("volume_weight", 1.4),
            ema_alignment_weight=params.get("ema_alignment_weight", 1.2),
            di_weight=params.get("di_weight", 1.0),
            bb_weight=params.get("bb_weight", 0.8),
            volatility_weight=params.get("volatility_weight", 0.5),
            supertrend_weight=params.get("supertrend_weight", 1.9),
            mfi_weight=params.get("mfi_weight", 1.3),
            psar_weight=params.get("psar_weight", 1.1),
        )

        is_valid, errors = binance_config.validate()
        if not is_valid:
            logger.error(f"❌ Binance config validation failed: {errors}")
            raise ValueError(f"Invalid Binance configuration: {errors}")

        self._configs[MarketType.BINANCE] = binance_config
        logger.info(f"✅ Binance universal config initialized (OPT6): ADX={binance_config.long_adx_min}, "
                   f"RSI={binance_config.long_rsi_min}-{binance_config.long_rsi_max}, "
                   f"ATR={binance_config.sl_atr_multiplier}/{binance_config.tp_atr_multiplier}")

    def detect_market_type(self, symbol: str) -> MarketType:
        """
        Detect market type based on symbol pattern.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT", "EURUSD")

        Returns:
            MarketType enum value

        Examples:
            >>> detect_market_type("BTCUSDT")
            MarketType.BINANCE
            >>> detect_market_type("EURUSD")
            MarketType.FOREX
        """
        symbol = symbol.upper().strip()

        # Check Binance patterns first (more specific)
        for pattern in self.BINANCE_PATTERNS:
            if re.match(pattern, symbol):
                logger.debug(f"🔍 Symbol '{symbol}' detected as BINANCE")
                return MarketType.BINANCE

        # Check Forex patterns
        for pattern in self.FOREX_PATTERNS:
            if re.match(pattern, symbol):
                logger.debug(f"🔍 Symbol '{symbol}' detected as FOREX")
                return MarketType.FOREX

        # Unknown market type
        logger.warning(f"⚠️ Unknown market type for symbol '{symbol}', defaulting to BINANCE")
        return MarketType.UNKNOWN

    def get_config(self, market_type: MarketType) -> Optional[UniversalConfig]:
        """
        Get configuration for a specific market type.

        Args:
            market_type: Market type enum

        Returns:
            UniversalConfig or None if not found
        """
        config = self._configs.get(market_type)

        if config:
            self._log_config_access(market_type, config)

        return config

    def get_config_for_symbol(self, symbol: str) -> Optional[UniversalConfig]:
        """
        Get configuration for a specific symbol (auto-detects market type).

        Args:
            symbol: Trading pair symbol

        Returns:
            UniversalConfig or None if market type unknown
        """
        market_type = self.detect_market_type(symbol)

        if market_type == MarketType.UNKNOWN:
            logger.warning(f"⚠️ Cannot get config for unknown market type: {symbol}")
            # Default to Binance config for unknown symbols
            market_type = MarketType.BINANCE

        config = self.get_config(market_type)

        if config:
            logger.info(f"📋 Using {config.name} for symbol '{symbol}'")

        return config

    def _log_config_access(self, market_type: MarketType, config: UniversalConfig):
        """Log configuration access for audit trail"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'market_type': market_type.value,
            'config_name': config.name,
            'action': 'config_access'
        }
        self._audit_log.append(log_entry)

        # Keep only last 1000 entries
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-1000:]

    def get_audit_log(self, limit: int = 100) -> list[Dict]:
        """
        Get recent configuration audit log.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries
        """
        return self._audit_log[-limit:]

    def get_all_configs(self) -> Dict[MarketType, UniversalConfig]:
        """Get all available configurations"""
        return self._configs.copy()

    def validate_all_configs(self) -> Dict[MarketType, tuple[bool, list[str]]]:
        """
        Validate all configurations.

        Returns:
            Dictionary mapping market types to validation results
        """
        results = {}
        for market_type, config in self._configs.items():
            is_valid, errors = config.validate()
            results[market_type] = (is_valid, errors)

            if is_valid:
                logger.info(f"✅ {config.name} validation passed")
            else:
                logger.error(f"❌ {config.name} validation failed: {errors}")

        return results

    def get_config_summary(self) -> Dict[str, Any]:
        """
        Get summary of all configurations for monitoring dashboard.

        Returns:
            Dictionary with configuration summary
        """
        summary = {
            'total_configs': len(self._configs),
            'market_types': [mt.value for mt in self._configs.keys()],
            'configs': {}
        }

        for market_type, config in self._configs.items():
            summary['configs'][market_type.value] = {
                'name': config.name,
                'description': config.description,
                'rsi_range_long': f"{config.long_rsi_min}-{config.long_rsi_max}",
                'rsi_range_short': f"{config.short_rsi_min}-{config.short_rsi_max}",
                'adx_min': config.long_adx_min,
                'sl_atr': config.sl_atr_multiplier,
                'tp_atr': config.tp_atr_multiplier,
                'risk_reward_ratio': f"1:{config.tp_atr_multiplier / config.sl_atr_multiplier:.1f}",
                'min_confidence': config.min_confidence,
                'preferred_timeframes': config.preferred_timeframes,
                'last_updated': config.last_updated.isoformat()
            }

        return summary


# Module-level convenience functions

_config_manager_instance: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """
    Get the singleton ConfigManager instance.

    Returns:
        ConfigManager instance
    """
    global _config_manager_instance

    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager()

    return _config_manager_instance


def get_config_for_symbol(symbol: str) -> Optional[UniversalConfig]:
    """
    Convenience function to get configuration for a symbol.

    Args:
        symbol: Trading pair symbol

    Returns:
        UniversalConfig or None

    Example:
        >>> config = get_config_for_symbol("BTCUSDT")
        >>> print(config.long_adx_min)
        22.0
    """
    manager = get_config_manager()
    return manager.get_config_for_symbol(symbol)


def detect_market_type(symbol: str) -> MarketType:
    """
    Convenience function to detect market type.

    Args:
        symbol: Trading pair symbol

    Returns:
        MarketType enum

    Example:
        >>> market_type = detect_market_type("EURUSD")
        >>> print(market_type)
        MarketType.FOREX
    """
    manager = get_config_manager()
    return manager.detect_market_type(symbol)


# Initialize on module import
logger.info("🚀 Initializing ConfigManager on module import...")
get_config_manager()
logger.info("✅ ConfigManager ready")
