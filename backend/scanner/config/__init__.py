"""
Configuration management package for market-specific trading parameters.
"""
from .config_manager import (
    ConfigManager,
    MarketType,
    UniversalConfig,
    get_config_manager,
    get_config_for_symbol,
    detect_market_type
)
from .config_adapter import (
    universal_to_signal_config,
    get_signal_config_for_symbol,
    get_market_specific_config
)

__all__ = [
    'ConfigManager',
    'MarketType',
    'UniversalConfig',
    'get_config_manager',
    'get_config_for_symbol',
    'detect_market_type',
    'universal_to_signal_config',
    'get_signal_config_for_symbol',
    'get_market_specific_config'
]
