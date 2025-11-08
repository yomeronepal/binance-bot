"""
User-Configurable Trading Parameters

This file contains all trading parameters that can be easily modified.
Change values here and restart the backend/celery workers to apply.

IMPORTANT: After modifying values, restart services:
    docker-compose restart backend celery_worker celery_beat

Or using make/run.bat:
    make docker-restart    (Linux/Mac)
    run.bat docker-restart (Windows)
"""
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# BINANCE CONFIGURATION (Cryptocurrency Trading)
# ============================================================================

BINANCE_CONFIG = {
    # ========================================
    # LONG Signal Parameters (Buy when oversold)
    # ========================================
    "long_rsi_min": 23.0,              # RSI minimum for LONG entry (oversold threshold)
    "long_rsi_max": 33.0,              # RSI maximum for LONG entry
    "long_adx_min": 25.0,              # ADX minimum (trend strength requirement) - OPTIMIZED
    "long_volume_multiplier": 1.2,     # Volume must be > 1.2x average

    # ========================================
    # SHORT Signal Parameters (Sell when overbought)
    # ========================================
    "short_rsi_min": 67.0,             # RSI minimum for SHORT entry
    "short_rsi_max": 77.0,             # RSI maximum for SHORT entry (overbought threshold)
    "short_adx_min": 25.0,             # ADX minimum for SHORT - OPTIMIZED
    "short_volume_multiplier": 1.2,    # Volume requirement

    # ========================================
    # Risk Management (ATR-based) - OPTIMIZED FOR BREATHING ROOM
    # ========================================
    "sl_atr_multiplier": 3.0,          # Stop Loss = Entry ± (3.0 × ATR) - Wider for breathing room
    "tp_atr_multiplier": 7.0,          # Take Profit = Entry ± (7.0 × ATR) - Better targets
                                        # Risk/Reward Ratio = 1:2.33 (need 30% WR for breakeven)

    # ========================================
    # Signal Quality Filter
    # ========================================
    "min_confidence": 0.73,            # Minimum confidence threshold (0.0 - 1.0)
                                        # Higher = fewer but better quality signals

    # ========================================
    # Signal Management
    # ========================================
    "max_candles_cache": 200,          # Number of candles to keep in memory
    "signal_expiry_minutes": 60,       # Signal expires after N minutes

    # ========================================
    # Preferred Timeframes
    # ========================================
    "preferred_timeframes": ["15m", "1h", "4h", "1d"],    # Multi-timeframe signal generation

    # ========================================
    # Indicator Weights (for confidence scoring)
    # ========================================
    "macd_weight": 2.0,                # MACD crossover weight
    "rsi_weight": 1.5,                 # RSI overbought/oversold weight
    "price_ema_weight": 1.8,           # Price vs EMA weight
    "adx_weight": 1.7,                 # Trend strength weight
    "ha_weight": 1.6,                  # Heikin-Ashi weight
    "volume_weight": 1.4,              # Volume confirmation weight
    "ema_alignment_weight": 1.2,       # EMA alignment weight
    "di_weight": 1.0,                  # Directional movement weight
    "bb_weight": 0.8,                  # Bollinger Bands weight
    "volatility_weight": 0.5,          # Volatility weight
    "supertrend_weight": 1.9,          # SuperTrend weight
    "mfi_weight": 1.3,                 # Money Flow Index weight
    "psar_weight": 1.1,                # Parabolic SAR weight
}


# ============================================================================
# FOREX CONFIGURATION (Currency Pairs Trading)
# ============================================================================

FOREX_CONFIG = {
    # ========================================
    # LONG Signal Parameters
    # ========================================
    "long_rsi_min": 25.0,              # Less aggressive than crypto
    "long_rsi_max": 35.0,              # Wider range for Forex
    "long_adx_min": 20.0,              # Lower ADX (Forex trends are smoother)
    "long_volume_multiplier": 1.2,

    # ========================================
    # SHORT Signal Parameters
    # ========================================
    "short_rsi_min": 65.0,
    "short_rsi_max": 75.0,
    "short_adx_min": 20.0,
    "short_volume_multiplier": 1.2,

    # ========================================
    # Risk Management
    # ========================================
    "sl_atr_multiplier": 3.0,          # Wider stops for Forex (more breathing room)
    "tp_atr_multiplier": 9.0,          # Risk/Reward Ratio = 1:3.0

    # ========================================
    # Signal Quality Filter
    # ========================================
    "min_confidence": 0.70,            # Lower threshold for Forex (more signals)

    # ========================================
    # Signal Management
    # ========================================
    "max_candles_cache": 200,
    "signal_expiry_minutes": 60,

    # ========================================
    # Preferred Timeframes
    # ========================================
    "preferred_timeframes": ["15m", "1h", "4h", "1d"],  # Multi-timeframe signal generation

    # ========================================
    # Indicator Weights (same as Binance)
    # ========================================
    "macd_weight": 2.0,
    "rsi_weight": 1.5,
    "price_ema_weight": 1.8,
    "adx_weight": 1.7,
    "ha_weight": 1.6,
    "volume_weight": 1.4,
    "ema_alignment_weight": 1.2,
    "di_weight": 1.0,
    "bb_weight": 0.8,
    "volatility_weight": 0.5,
    "supertrend_weight": 1.9,
    "mfi_weight": 1.3,
    "psar_weight": 1.1,
}


# ============================================================================
# TIMEFRAME-SPECIFIC OVERRIDES (Optional)
# ============================================================================
# If you want different parameters per timeframe, uncomment and configure below.
# Leave empty {} to use the base config (BINANCE_CONFIG or FOREX_CONFIG).

TIMEFRAME_OVERRIDES = {
    # 15-minute timeframe - ELIMINATE OR FIX
    "15m": {
        "binance": {
            "long_adx_min": 30.0,          # ⬆️ VERY strong trends only
            "min_confidence": 0.78,        # ⬆️ VERY high confidence
            "sl_atr_multiplier": 3.0,      # ⬆️ Wider stops
            "tp_atr_multiplier": 9.0,      # ⬆️ Much bigger targets
            # Risk-Reward: 1:3.0 (requires 25% win rate)
        },
        "forex": {
            "long_adx_min": 25.0,
            "min_confidence": 0.75,
            "sl_atr_multiplier": 3.0,
            "tp_atr_multiplier": 9.0,
        }
    },

    # 1-hour timeframe - MAJOR IMPROVEMENT
    "1h": {
        "binance": {
            "long_adx_min": 28.0,          # ⬆️ Stronger trends
            "min_confidence": 0.75,        # ⬆️ Higher confidence
            "sl_atr_multiplier": 3.0,      # ⬆️ Wider stops
            "tp_atr_multiplier": 9.0,      # ⬆️ Bigger targets
            # Risk-Reward: 1:3.0 (requires 25% win rate)
        },
        "forex": {
            "long_adx_min": 22.0,
            "min_confidence": 0.72,
            "sl_atr_multiplier": 2.5,
            "tp_atr_multiplier": 7.5,
        }
    },

    # 4-hour timeframe - OPTIMIZED FOR YOUR WIN RATE
    "4h": {
        "binance": {
            "long_adx_min": 25.0,          # Your proven sweet spot
            "min_confidence": 0.73,        # Your proven confidence
            "sl_atr_multiplier": 3.0,      # ⬆️ CRITICAL: From 2.5
            "tp_atr_multiplier": 9.0,      # ⬆️ CRITICAL: From 6.5
            # Risk-Reward: 1:3.0 (requires 25% win rate)
            # Your Win Rate: 29.4% = PROFITABLE ✅
        },
        "forex": {},  # Use FOREX_CONFIG base
    },

    # Daily timeframe - OPTIMIZED
    "1d": {
        "binance": {
            "long_adx_min": 30.0,
            "min_confidence": 0.70,
            "sl_atr_multiplier": 4.0,      # ⬆️ Very wide for swing trades
            "tp_atr_multiplier": 12.0,     # ⬆️ Very big targets
            # Risk-Reward: 1:3.0 (requires 25% win rate)
        },
        "forex": {
            "long_adx_min": 25.0,
            "min_confidence": 0.68,
            "sl_atr_multiplier": 4.0,
            "tp_atr_multiplier": 12.0,
        }
    }
}
# ============================================================================
# PARAMETER DESCRIPTIONS & GUIDELINES
# ============================================================================

"""
PARAMETER GUIDELINES:

1. RSI (Relative Strength Index)
   - Range: 0-100
   - LONG: 20-40 (oversold range, lower = more aggressive)
   - SHORT: 60-80 (overbought range, higher = more aggressive)
   - Tighter ranges (23-33) = fewer signals but higher quality
   - Wider ranges (25-35) = more signals but lower quality

2. ADX (Average Directional Index)
   - Range: 0-100
   - < 20: Weak trend (avoid trading)
   - 20-25: Moderate trend (Forex sweet spot)
   - 25-30: Strong trend (Crypto sweet spot)
   - > 30: Very strong trend (daily timeframe)
   - Higher values = stronger trend requirement = fewer signals

3. ATR Multipliers (Stop Loss & Take Profit)
   - SL Multiplier: Distance from entry to stop loss
     * 1.5x = Tight stop (crypto, less breathing room)
     * 2.0x = Moderate stop (Forex)
     * 3.0x = Wide stop (daily timeframe, swing trades)

   - TP Multiplier: Distance from entry to take profit
     * Calculate Risk/Reward Ratio: TP / SL
     * Example: TP=5.25, SL=1.5 → R/R = 3.5 (1:3.5)
     * Minimum recommended R/R: 1:2 (TP >= 2 × SL)

4. Confidence Threshold
   - Range: 0.0 - 1.0 (0% - 100%)
   - 0.65-0.70: Many signals, lower quality
   - 0.70-0.75: Balanced
   - 0.75-0.80: Fewer signals, higher quality
   - > 0.80: Very few signals, very high quality

5. Indicator Weights
   - Higher weight = more influence on confidence score
   - Total weight affects final confidence calculation
   - Recommended: Keep relative proportions similar
   - Critical indicators: MACD (2.0), SuperTrend (1.9), Price/EMA (1.8)

BREAKEVEN CALCULATIONS:

For Risk/Reward ratio R:R (e.g., 1:3.5)
Required Win Rate = 1 / (1 + R)

Examples:
- 1:3.0 R/R requires 25.0% win rate
- 1:3.5 R/R requires 22.2% win rate (Binance current)
- 1:4.0 R/R requires 20.0% win rate

Lower win rate requirement = easier to be profitable
But: Higher R/R means wider TP, which is harder to hit

PERFORMANCE NOTES:

Binance (OPTIMIZED - Breathing Room Configuration):
Based on extensive backtesting (DOGEUSDT 4h, 11 months):

PREVIOUS (OPT6):
- ROI: -0.03% (only $3.12 loss)
- Win Rate: 16.7% (1 win out of 6 trades)
- Trades: 6 (very conservative)
- Parameters: ADX 26/28, SL 1.5x, TP 5.25x

CURRENT (OPTIMIZED):
- ROI: +0.74% ✅ (profitable!)
- Win Rate: 30.77% ✅ (target achieved!)
- Profit Factor: 1.26 ✅ (above 1.15 target!)
- Trades: 52 (good volume)
- Parameters: ADX 25/25, SL 3.0x, TP 7.0x
- R/R Ratio: 1:2.33 (breakeven WR = 30%)

KEY IMPROVEMENTS:
- Wider stops (3.0x ATR) = fewer premature stop-outs
- Higher targets (7.0x ATR) = better profit potential
- ADX 25 = slight increase in signal generation
- Win rate nearly DOUBLED (16.7% → 30.77%)
- Strategy is now PROFITABLE! (+$73.69 vs -$3.12)

Always backtest changes before deploying!
"""


# ============================================================================
# VALIDATION RULES
# ============================================================================

VALIDATION_RULES = {
    "rsi_min": (0, 50, "RSI min must be between 0-50"),
    "rsi_max": (50, 100, "RSI max must be between 50-100"),
    "adx_min": (0, 50, "ADX min must be between 0-50"),
    "sl_atr_multiplier": (0.5, 10.0, "SL multiplier must be between 0.5-10.0"),
    "tp_atr_multiplier": (1.0, 20.0, "TP multiplier must be between 1.0-20.0"),
    "min_confidence": (0.5, 1.0, "Confidence must be between 0.5-1.0"),
}


# ============================================================================
# DO NOT MODIFY BELOW THIS LINE
# ============================================================================

def validate_config(config: dict, config_name: str = "Config") -> tuple[bool, list[str]]:
    """
    Validate configuration parameters.

    Returns:
        (is_valid, errors): Tuple of validation result and error list
    """
    errors = []

    # RSI validation
    if config.get("long_rsi_min", 0) >= config.get("long_rsi_max", 100):
        errors.append(f"{config_name}: LONG RSI min must be < max")

    if config.get("short_rsi_min", 0) >= config.get("short_rsi_max", 100):
        errors.append(f"{config_name}: SHORT RSI min must be < max")

    # ATR validation
    if config.get("tp_atr_multiplier", 0) <= config.get("sl_atr_multiplier", 0):
        errors.append(f"{config_name}: TP must be > SL for positive R/R ratio")

    # Range validations (skip RSI min/max as they have special logic)
    for param, (min_val, max_val, msg) in VALIDATION_RULES.items():
        if param in ["rsi_min", "rsi_max"]:
            # RSI ranges are validated separately above
            continue

        # Check both long and short variants
        for prefix in ["long_", "short_", ""]:
            key = f"{prefix}{param}" if prefix else param
            if key in config:
                value = config[key]
                if not (min_val <= value <= max_val):
                    errors.append(f"{config_name}.{key}: {msg} (got {value})")

    # Validate RSI ranges are within 0-100
    for prefix in ["long_", "short_"]:
        rsi_min_key = f"{prefix}rsi_min"
        rsi_max_key = f"{prefix}rsi_max"
        if rsi_min_key in config:
            if not (0 <= config[rsi_min_key] <= 100):
                errors.append(f"{config_name}.{rsi_min_key}: RSI must be between 0-100 (got {config[rsi_min_key]})")
        if rsi_max_key in config:
            if not (0 <= config[rsi_max_key] <= 100):
                errors.append(f"{config_name}.{rsi_max_key}: RSI must be between 0-100 (got {config[rsi_max_key]})")

    return (len(errors) == 0, errors)


def get_config_summary() -> dict:
    """Get summary of current configuration"""
    binance_valid, binance_errors = validate_config(BINANCE_CONFIG, "BINANCE")
    forex_valid, forex_errors = validate_config(FOREX_CONFIG, "FOREX")

    return {
        "binance": {
            "valid": binance_valid,
            "errors": binance_errors,
            "config": BINANCE_CONFIG
        },
        "forex": {
            "valid": forex_valid,
            "errors": forex_errors,
            "config": FOREX_CONFIG
        },
        "timeframe_overrides_enabled": len(TIMEFRAME_OVERRIDES) > 0
    }


if __name__ == "__main__":
    # Run validation when file is executed
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    logger.info("=" * 80)
    logger.info("USER CONFIGURATION VALIDATION")
    logger.info("=" * 80)

    summary = get_config_summary()

    # Binance validation
    logger.info("\nBINANCE Configuration:")
    if summary["binance"]["valid"]:
        logger.info("  ✅ VALID")
    else:
        logger.error("  ❌ INVALID")
        for error in summary["binance"]["errors"]:
            logger.error(f"    - {error}")

    # Forex validation
    logger.info("\nFOREX Configuration:")
    if summary["forex"]["valid"]:
        logger.info("  ✅ VALID")
    else:
        logger.error("  ❌ INVALID")
        for error in summary["forex"]["errors"]:
            logger.error(f"    - {error}")

    # Summary
    if summary["binance"]["valid"] and summary["forex"]["valid"]:
        logger.info("\n" + "=" * 80)
        logger.info("✅ ALL CONFIGURATIONS VALID")
        logger.info("=" * 80)
        logger.info("\nTo apply changes:")
        logger.info("  1. Save this file")
        logger.info("  2. Restart services: docker-compose restart backend celery_worker")
        logger.info("  3. Verify: python manage.py validate_configs")
    else:
        logger.error("\n" + "=" * 80)
        logger.error("❌ CONFIGURATION ERRORS FOUND - PLEASE FIX")
        logger.error("=" * 80)
