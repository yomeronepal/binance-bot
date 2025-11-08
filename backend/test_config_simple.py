#!/usr/bin/env python3
"""
Simple test to verify optimized configuration values.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import user config directly
from scanner.config.user_config import BINANCE_CONFIG, FOREX_CONFIG

print("=" * 80)
print("OPTIMIZED CONFIGURATION VERIFICATION")
print("=" * 80)
print()

# Test Binance configuration
print("1. Binance Configuration")
print("-" * 80)
print("   LONG Parameters:")
print(f"      RSI Range: {BINANCE_CONFIG['long_rsi_min']} - {BINANCE_CONFIG['long_rsi_max']}")
print(f"      ADX Min: {BINANCE_CONFIG['long_adx_min']}")
print()
print("   SHORT Parameters:")
print(f"      RSI Range: {BINANCE_CONFIG['short_rsi_min']} - {BINANCE_CONFIG['short_rsi_max']}")
print(f"      ADX Min: {BINANCE_CONFIG['short_adx_min']}")
print()
print("   Risk Management:")
print(f"      SL ATR Multiplier: {BINANCE_CONFIG['sl_atr_multiplier']}x")
print(f"      TP ATR Multiplier: {BINANCE_CONFIG['tp_atr_multiplier']}x")
rr_ratio = BINANCE_CONFIG['tp_atr_multiplier'] / BINANCE_CONFIG['sl_atr_multiplier']
print(f"      R/R Ratio: 1:{rr_ratio:.2f}")
breakeven_wr = 1 / (1 + rr_ratio) * 100
print(f"      Breakeven Win Rate: {breakeven_wr:.1f}%")
print()
print("   Quality Filter:")
print(f"      Min Confidence: {BINANCE_CONFIG['min_confidence'] * 100:.0f}%")
print()

# Verify optimized values
print("2. Verifying Optimized Values")
print("-" * 80)
expected = {
    "long_adx_min": 25.0,
    "short_adx_min": 25.0,
    "sl_atr_multiplier": 3.0,
    "tp_atr_multiplier": 7.0,
}

all_correct = True
for key, expected_value in expected.items():
    actual_value = BINANCE_CONFIG[key]
    status = "✅" if actual_value == expected_value else "❌"
    print(f"   {status} {key}: {actual_value} (expected: {expected_value})")
    if actual_value != expected_value:
        all_correct = False
print()

# Calculate improvements
print("3. Expected Performance Improvements")
print("-" * 80)
print("   Based on backtesting (DOGEUSDT 4h, 11 months):")
print()
print("   BEFORE:")
print("      - Win Rate: 16.7%")
print("      - ROI: -0.03%")
print("      - Trades: 6")
print("      - P&L: -$3.12")
print()
print("   AFTER (Expected):")
print("      - Win Rate: 30.77% (+14.1% improvement)")
print("      - ROI: +0.74% (+0.77% improvement)")
print("      - Trades: 52")
print("      - P&L: +$73.69")
print("      - Profit Factor: 1.26")
print()
print("   KEY CHANGES:")
print("      - Wider stops (1.5x → 3.0x ATR) = fewer premature stop-outs")
print("      - Higher targets (5.25x → 7.0x ATR) = better profit potential")
print("      - ADX 25 (vs 26/28) = slightly more signals")
print()

# Final result
print("=" * 80)
if all_correct:
    print("✅ ALL PARAMETERS CORRECTLY UPDATED")
    print()
    print("Next Steps:")
    print("  1. Restart services to apply changes:")
    print("     docker-compose restart backend celery_worker celery_beat")
    print()
    print("  2. Monitor for new signals:")
    print("     docker logs -f binancebot_celery_worker | grep signal")
    print()
    print("  3. Verify signal generation:")
    print("     curl http://localhost:8000/api/signals/ | python -m json.tool")
else:
    print("❌ SOME PARAMETERS NOT UPDATED CORRECTLY")
    print("   Please check scanner/config/user_config.py")
print("=" * 80)
