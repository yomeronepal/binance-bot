"""
Configuration Adapter

Converts UniversalConfig to SignalConfig for backward compatibility
with existing SignalDetectionEngine.
"""
import logging
from typing import Optional
from scanner.config.config_manager import UniversalConfig, get_config_for_symbol, MarketType

logger = logging.getLogger(__name__)


def universal_to_signal_config(universal_config: UniversalConfig):
    """
    Convert UniversalConfig to SignalConfig.

    This adapter allows the new configuration system to work with
    the existing SignalDetectionEngine without breaking changes.

    Args:
        universal_config: UniversalConfig instance

    Returns:
        SignalConfig instance
    """
    # Import here to avoid circular dependency
    from scanner.strategies.signal_engine import SignalConfig

    signal_config = SignalConfig(
        # LONG thresholds
        long_rsi_min=universal_config.long_rsi_min,
        long_rsi_max=universal_config.long_rsi_max,
        long_adx_min=universal_config.long_adx_min,
        long_volume_multiplier=universal_config.long_volume_multiplier,

        # SHORT thresholds
        short_rsi_min=universal_config.short_rsi_min,
        short_rsi_max=universal_config.short_rsi_max,
        short_adx_min=universal_config.short_adx_min,
        short_volume_multiplier=universal_config.short_volume_multiplier,

        # Risk management
        sl_atr_multiplier=universal_config.sl_atr_multiplier,
        tp_atr_multiplier=universal_config.tp_atr_multiplier,

        # Signal quality
        min_confidence=universal_config.min_confidence,

        # Signal management
        max_candles_cache=universal_config.max_candles_cache,
        signal_expiry_minutes=universal_config.signal_expiry_minutes,

        # Indicator weights
        macd_weight=universal_config.macd_weight,
        rsi_weight=universal_config.rsi_weight,
        price_ema_weight=universal_config.price_ema_weight,
        adx_weight=universal_config.adx_weight,
        ha_weight=universal_config.ha_weight,
        volume_weight=universal_config.volume_weight,
        ema_alignment_weight=universal_config.ema_alignment_weight,
        di_weight=universal_config.di_weight,
        bb_weight=universal_config.bb_weight,
        volatility_weight=universal_config.volatility_weight,
        supertrend_weight=universal_config.supertrend_weight,
        mfi_weight=universal_config.mfi_weight,
        psar_weight=universal_config.psar_weight,
    )

    logger.debug(f"📋 Converted {universal_config.name} to SignalConfig")
    return signal_config


def get_signal_config_for_symbol(symbol: str):
    """
    Get SignalConfig for a specific symbol (auto-detects market type).

    This is the main entry point for getting market-appropriate configurations.

    Args:
        symbol: Trading pair symbol (e.g., "BTCUSDT", "EURUSD")

    Returns:
        SignalConfig instance configured for the symbol's market type

    Example:
        >>> config = get_signal_config_for_symbol("BTCUSDT")
        >>> print(config.long_adx_min)  # Will be 22.0 (Binance config)
        22.0

        >>> config = get_signal_config_for_symbol("EURUSD")
        >>> print(config.long_adx_min)  # Will be 20.0 (Forex config)
        20.0
    """
    universal_config = get_config_for_symbol(symbol)

    if universal_config is None:
        logger.warning(f"⚠️ No universal config found for symbol '{symbol}', using defaults")
        # Import here to avoid circular dependency
        from scanner.strategies.signal_engine import SignalConfig
        return SignalConfig()  # Return default config

    signal_config = universal_to_signal_config(universal_config)

    logger.info(f"✅ Generated SignalConfig for '{symbol}' using {universal_config.name}")
    logger.debug(f"   📊 Config: ADX={signal_config.long_adx_min}, "
                f"RSI={signal_config.long_rsi_min}-{signal_config.long_rsi_max}, "
                f"ATR={signal_config.sl_atr_multiplier}/{signal_config.tp_atr_multiplier}, "
                f"Confidence={signal_config.min_confidence}")

    return signal_config


def get_market_specific_config(market_type: MarketType):
    """
    Get SignalConfig for a specific market type.

    Args:
        market_type: MarketType enum (FOREX or BINANCE)

    Returns:
        SignalConfig instance

    Example:
        >>> config = get_market_specific_config(MarketType.FOREX)
        >>> print(config.long_adx_min)
        20.0
    """
    from scanner.config.config_manager import get_config_manager

    manager = get_config_manager()
    universal_config = manager.get_config(market_type)

    if universal_config is None:
        logger.error(f"❌ No config found for market type: {market_type}")
        from scanner.strategies.signal_engine import SignalConfig
        return SignalConfig()

    return universal_to_signal_config(universal_config)
