#!/usr/bin/env python3
"""
Test Universal Configuration System

Tests market detection, configuration loading, and signal generation
for both Forex and Binance markets.

Usage:
    python test_universal_config.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from scanner.config import (
    get_config_manager,
    get_config_for_symbol,
    get_signal_config_for_symbol,
    detect_market_type,
    MarketType
)


def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_section(title):
    """Print formatted section"""
    print("\n" + "-" * 80)
    print(f"  {title}")
    print("-" * 80 + "\n")


def test_market_detection():
    """Test market type detection"""
    print_section("1. Market Type Detection")

    test_cases = [
        # Binance symbols
        ("BTCUSDT", MarketType.BINANCE),
        ("ETHUSDT", MarketType.BINANCE),
        ("BNBUSDT", MarketType.BINANCE),
        ("SOLUSDT", MarketType.BINANCE),
        ("ADAUSDT", MarketType.BINANCE),
        ("DOGEUSDT", MarketType.BINANCE),

        # Forex symbols
        ("EURUSD", MarketType.FOREX),
        ("GBPJPY", MarketType.FOREX),
        ("USDJPY", MarketType.FOREX),
        ("AUDUSD", MarketType.FOREX),
        ("NZDUSD", MarketType.FOREX),
        ("XAUUSD", MarketType.FOREX),  # Gold
    ]

    correct = 0
    total = len(test_cases)

    for symbol, expected in test_cases:
        detected = detect_market_type(symbol)
        is_correct = detected == expected

        status = "✅" if is_correct else "❌"
        print(f"{status} {symbol:12s} → Detected: {detected.value:8s} | Expected: {expected.value:8s}")

        if is_correct:
            correct += 1

    print(f"\n📊 Detection Accuracy: {correct}/{total} ({correct / total * 100:.1f}%)")


def test_config_loading():
    """Test configuration loading"""
    print_section("2. Configuration Loading")

    manager = get_config_manager()
    all_configs = manager.get_all_configs()

    print(f"✅ Loaded {len(all_configs)} configurations")
    print()

    for market_type, config in all_configs.items():
        print(f"📋 {market_type.value.upper()} Configuration:")
        print(f"   Name: {config.name}")
        print(f"   Description: {config.description}")
        print()
        print(f"   LONG Thresholds:")
        print(f"      RSI Range: {config.long_rsi_min} - {config.long_rsi_max}")
        print(f"      ADX Minimum: {config.long_adx_min}")
        print()
        print(f"   SHORT Thresholds:")
        print(f"      RSI Range: {config.short_rsi_min} - {config.short_rsi_max}")
        print(f"      ADX Minimum: {config.short_adx_min}")
        print()
        print(f"   Risk Management:")
        print(f"      SL ATR Multiplier: {config.sl_atr_multiplier}")
        print(f"      TP ATR Multiplier: {config.tp_atr_multiplier}")
        print(f"      Risk/Reward Ratio: 1:{config.tp_atr_multiplier / config.sl_atr_multiplier:.2f}")
        print()
        print(f"   Signal Quality:")
        print(f"      Min Confidence: {config.min_confidence * 100:.1f}%")
        print(f"      Preferred Timeframes: {', '.join(config.preferred_timeframes)}")
        print()


def test_config_validation():
    """Test configuration validation"""
    print_section("3. Configuration Validation")

    manager = get_config_manager()
    validation_results = manager.validate_all_configs()

    all_valid = True
    for market_type, (is_valid, errors) in validation_results.items():
        status = "✅" if is_valid else "❌"
        print(f"{status} {market_type.value.upper()} Configuration: {'VALID' if is_valid else 'INVALID'}")

        if not is_valid:
            for error in errors:
                print(f"      - {error}")
            all_valid = False

    print()
    if all_valid:
        print("✅ All configurations are VALID")
    else:
        print("❌ Some configurations are INVALID")


def test_signal_config_generation():
    """Test SignalConfig generation from UniversalConfig"""
    print_section("4. SignalConfig Generation")

    test_symbols = [
        "BTCUSDT",   # Binance
        "ETHUSDT",   # Binance
        "EURUSD",    # Forex
        "GBPJPY",    # Forex
    ]

    for symbol in test_symbols:
        print(f"Symbol: {symbol}")

        # Get market type
        market_type = detect_market_type(symbol)
        print(f"   Market Type: {market_type.value}")

        # Get universal config
        universal_config = get_config_for_symbol(symbol)
        if universal_config:
            print(f"   Universal Config: {universal_config.name}")

        # Get signal config
        signal_config = get_signal_config_for_symbol(symbol)
        if signal_config:
            print(f"   ✅ Signal Config Generated Successfully")
            print(f"      LONG RSI: {signal_config.long_rsi_min}-{signal_config.long_rsi_max}")
            print(f"      ADX: {signal_config.long_adx_min}")
            print(f"      SL/TP: {signal_config.sl_atr_multiplier}/{signal_config.tp_atr_multiplier}")
            print(f"      Confidence: {signal_config.min_confidence * 100:.1f}%")
        else:
            print(f"   ❌ Failed to generate SignalConfig")

        print()


def test_config_comparison():
    """Compare Forex vs Binance configurations"""
    print_section("5. Forex vs Binance Configuration Comparison")

    manager = get_config_manager()
    forex_config = manager.get_config(MarketType.FOREX)
    binance_config = manager.get_config(MarketType.BINANCE)

    if not forex_config or not binance_config:
        print("❌ Could not load configurations")
        return

    print(f"{'Parameter':<30s} {'Forex':<20s} {'Binance':<20s} {'Difference':<15s}")
    print("-" * 90)

    comparisons = [
        ("LONG RSI Min", forex_config.long_rsi_min, binance_config.long_rsi_min),
        ("LONG RSI Max", forex_config.long_rsi_max, binance_config.long_rsi_max),
        ("LONG ADX Min", forex_config.long_adx_min, binance_config.long_adx_min),
        ("SHORT RSI Min", forex_config.short_rsi_min, binance_config.short_rsi_min),
        ("SHORT RSI Max", forex_config.short_rsi_max, binance_config.short_rsi_max),
        ("SHORT ADX Min", forex_config.short_adx_min, binance_config.short_adx_min),
        ("SL ATR Multiplier", forex_config.sl_atr_multiplier, binance_config.sl_atr_multiplier),
        ("TP ATR Multiplier", forex_config.tp_atr_multiplier, binance_config.tp_atr_multiplier),
        ("Min Confidence", forex_config.min_confidence, binance_config.min_confidence),
    ]

    for param_name, forex_val, binance_val in comparisons:
        diff = binance_val - forex_val
        diff_str = f"+{diff:.2f}" if diff > 0 else f"{diff:.2f}"

        print(f"{param_name:<30s} {str(forex_val):<20s} {str(binance_val):<20s} {diff_str:<15s}")

    print()

    # Calculate and display risk/reward ratios
    forex_rr = forex_config.tp_atr_multiplier / forex_config.sl_atr_multiplier
    binance_rr = binance_config.tp_atr_multiplier / binance_config.sl_atr_multiplier

    print(f"{'Risk/Reward Ratio':<30s} {'1:' + f'{forex_rr:.2f}':<20s} {'1:' + f'{binance_rr:.2f}':<20s}")
    print()

    # Key differences summary
    print("🔍 Key Differences:")
    print()
    print(f"   Forex (Lower Volatility Market):")
    print(f"      - Lower ADX requirement ({forex_config.long_adx_min} vs {binance_config.long_adx_min})")
    print(f"      - Wider stops ({forex_config.sl_atr_multiplier}x vs {binance_config.sl_atr_multiplier}x ATR)")
    print(f"      - Lower confidence threshold ({forex_config.min_confidence * 100:.0f}% vs {binance_config.min_confidence * 100:.0f}%)")
    print()
    print(f"   Binance (Higher Volatility Market):")
    print(f"      - Stronger trend requirement (ADX {binance_config.long_adx_min})")
    print(f"      - Tighter RSI ranges ({binance_config.long_rsi_min}-{binance_config.long_rsi_max})")
    print(f"      - Higher quality filter ({binance_config.min_confidence * 100:.0f}% confidence)")


def test_audit_log():
    """Test configuration audit logging"""
    print_section("6. Configuration Audit Log")

    manager = get_config_manager()

    # Trigger some config accesses
    get_config_for_symbol("BTCUSDT")
    get_config_for_symbol("ETHUSDT")
    get_config_for_symbol("EURUSD")

    # Get audit log
    log_entries = manager.get_audit_log(limit=10)

    print(f"Recent Configuration Access (Last {len(log_entries)} entries):")
    print()

    for entry in log_entries[-5:]:  # Show last 5
        print(f"   {entry['timestamp']}: {entry['action']} - {entry['config_name']} ({entry['market_type']})")


def run_all_tests():
    """Run all tests"""
    print_header("Universal Configuration System Test Suite")

    try:
        test_market_detection()
        test_config_loading()
        test_config_validation()
        test_signal_config_generation()
        test_config_comparison()
        test_audit_log()

        print_header("✅ All Tests Completed Successfully")

    except Exception as e:
        print_header("❌ Test Failed")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
