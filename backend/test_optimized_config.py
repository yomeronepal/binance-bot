#!/usr/bin/env python3
"""
Quick test to verify optimized configuration loads correctly.
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from scanner.config import get_signal_config_for_symbol, get_config_for_symbol, detect_market_type

print("=" * 80)
print("OPTIMIZED CONFIGURATION TEST")
print("=" * 80)
print()

# Test 1: Market detection
print("1. Testing Market Detection")
print("-" * 80)
test_symbols = ["BTCUSDT", "ETHUSDT", "DOGEUSDT", "EURUSD"]
for symbol in test_symbols:
    market_type = detect_market_type(symbol)
    print(f"   {symbol:<12} → {market_type.value}")
print()

# Test 2: Load Binance configuration
print("2. Testing Binance Configuration Loading")
print("-" * 80)
btc_config = get_config_for_symbol("BTCUSDT")
print(f"   Name: {btc_config.name}")
print(f"   Market Type: {btc_config.market_type.value}")
print()
print("   LONG Parameters:")
print(f"      RSI Range: {btc_config.long_rsi_min} - {btc_config.long_rsi_max}")
print(f"      ADX Min: {btc_config.long_adx_min}")
print()
print("   SHORT Parameters:")
print(f"      RSI Range: {btc_config.short_rsi_min} - {btc_config.short_rsi_max}")
print(f"      ADX Min: {btc_config.short_adx_min}")
print()
print("   Risk Management:")
print(f"      SL ATR Multiplier: {btc_config.sl_atr_multiplier}x")
print(f"      TP ATR Multiplier: {btc_config.tp_atr_multiplier}x")
print(f"      R/R Ratio: 1:{btc_config.tp_atr_multiplier / btc_config.sl_atr_multiplier:.2f}")
print()
print("   Quality Filter:")
print(f"      Min Confidence: {btc_config.min_confidence * 100:.0f}%")
print()

# Test 3: Verify optimized values
print("3. Verifying Optimized Values")
print("-" * 80)
expected = {
    "long_adx_min": 25.0,
    "short_adx_min": 25.0,
    "sl_atr_multiplier": 3.0,
    "tp_atr_multiplier": 7.0,
}

all_correct = True
for key, expected_value in expected.items():
    actual_value = getattr(btc_config, key)
    status = "✅" if actual_value == expected_value else "❌"
    print(f"   {status} {key}: {actual_value} (expected: {expected_value})")
    if actual_value != expected_value:
        all_correct = False
print()

# Test 4: Convert to SignalConfig
print("4. Testing SignalConfig Generation")
print("-" * 80)
signal_config = get_signal_config_for_symbol("BTCUSDT")
print(f"   ✅ SignalConfig generated successfully")
print(f"   LONG ADX Min: {signal_config.long_adx_min}")
print(f"   SHORT ADX Min: {signal_config.short_adx_min}")
print(f"   SL ATR: {signal_config.sl_atr_multiplier}x")
print(f"   TP ATR: {signal_config.tp_atr_multiplier}x")
print()

# Final result
print("=" * 80)
if all_correct:
    print("✅ ALL TESTS PASSED - CONFIGURATION LOADED CORRECTLY")
    print()
    print("Next Steps:")
    print("  1. Restart services: docker-compose restart backend celery_worker celery_beat")
    print("  2. Monitor logs: docker logs -f binancebot_celery_worker")
    print("  3. Watch for signals with new parameters")
else:
    print("❌ SOME TESTS FAILED - PLEASE CHECK CONFIGURATION")
print("=" * 80)
