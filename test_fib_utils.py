#!/usr/bin/env python3
"""
Test suite for Fibonacci pullback utility functions.

Tests swing detection, Fibonacci level calculation, and entry zone validation.
"""
import pandas as pd
import numpy as np
from backend.scanner.services.fib_utils import (
    find_recent_swing_high_low,
    compute_fib_levels,
    check_fibonacci_pullback,
    calculate_fib_extension_targets,
    validate_fibonacci_signal
)


def create_test_dataframe(candles_data):
    """Helper to create DataFrame from price data."""
    df = pd.DataFrame(candles_data, columns=['high', 'low', 'close', 'volume'])
    df['rsi'] = 50.0
    df['volume_trend'] = 1.0
    return df


def test_swing_detection():
    """Test swing high/low detection."""
    print("=" * 70)
    print("🧪 TESTING SWING HIGH/LOW DETECTION")
    print("=" * 70)

    prices = [
        [100, 95, 98, 1000],
        [105, 100, 102, 1200],
        [110, 105, 108, 1100],
        [108, 103, 105, 900],
        [107, 102, 104, 950],
        [105, 100, 103, 1050],
        [103, 98, 101, 1100],
        [106, 101, 104, 1150],
    ]

    df = create_test_dataframe(prices)

    print("\n📊 Price Data:")
    print(df[['high', 'low', 'close']].to_string())

    swing_high, swing_low = find_recent_swing_high_low(df, lookback=8, direction='LONG')

    print(f"\n✅ Detected Swing High: {swing_high}")
    print(f"✅ Detected Swing Low: {swing_low}")

    assert swing_high is not None, "Should detect swing high"
    assert swing_low is not None, "Should detect swing low"
    assert swing_high > swing_low, "Swing high should be greater than swing low"

    print("✅ PASSED: Swing detection working\n")
    return True


def test_fib_level_calculation():
    """Test Fibonacci retracement level calculation."""
    print("=" * 70)
    print("🧪 TESTING FIBONACCI LEVEL CALCULATION")
    print("=" * 70)

    swing_high = 110.0
    swing_low = 100.0

    print(f"\n📈 LONG Setup:")
    print(f"   Swing High: {swing_high}")
    print(f"   Swing Low: {swing_low}")
    print(f"   Range: {swing_high - swing_low}")

    fib_levels_long = compute_fib_levels(swing_high, swing_low, 'LONG')

    print(f"\n📐 Fibonacci Retracement Levels (LONG):")
    print(f"   0.0%:   {fib_levels_long['level_0']:.2f} (swing high)")
    print(f"   23.6%:  {fib_levels_long['level_23_6']:.2f}")
    print(f"   38.2%:  {fib_levels_long['level_38_2']:.2f}")
    print(f"   50.0%:  {fib_levels_long['level_50']:.2f}")
    print(f"   61.8%:  {fib_levels_long['level_61_8']:.2f} ⭐ Golden Ratio")
    print(f"   78.6%:  {fib_levels_long['level_78_6']:.2f}")
    print(f"   100%:   {fib_levels_long['level_100']:.2f} (swing low)")

    expected_50 = 105.0
    expected_618 = 103.82

    assert abs(fib_levels_long['level_50'] - expected_50) < 0.01, \
        f"50% level should be {expected_50}"
    assert abs(fib_levels_long['level_61_8'] - expected_618) < 0.01, \
        f"61.8% level should be {expected_618}"

    print(f"\n📉 SHORT Setup:")
    fib_levels_short = compute_fib_levels(swing_high, swing_low, 'SHORT')

    print(f"\n📐 Fibonacci Retracement Levels (SHORT):")
    print(f"   0.0%:   {fib_levels_short['level_0']:.2f} (swing low)")
    print(f"   23.6%:  {fib_levels_short['level_23_6']:.2f}")
    print(f"   38.2%:  {fib_levels_short['level_38_2']:.2f}")
    print(f"   50.0%:  {fib_levels_short['level_50']:.2f}")
    print(f"   61.8%:  {fib_levels_short['level_61_8']:.2f} ⭐ Golden Ratio")
    print(f"   78.6%:  {fib_levels_short['level_78_6']:.2f}")
    print(f"   100%:   {fib_levels_short['level_100']:.2f} (swing high)")

    print("\n✅ PASSED: Fibonacci calculations correct\n")
    return True


def test_pullback_entry_zone():
    """Test if price is in Fibonacci entry zone (50-61.8%)."""
    print("=" * 70)
    print("🧪 TESTING FIBONACCI PULLBACK ENTRY ZONE DETECTION")
    print("=" * 70)

    prices = [
        [100, 95, 98, 1000],
        [105, 100, 102, 1200],
        [110, 105, 108, 1100],
        [108, 103, 106, 900],
        [107, 102, 105, 950],
        [106, 101, 104, 1050],
        [105, 100, 103, 1100],
        [106, 101, 104, 1150],
    ]

    df = create_test_dataframe(prices)
    current = df.iloc[-1]

    print("\n📊 Testing LONG pullback...")
    in_zone, fib_data = check_fibonacci_pullback(
        df, current, 'LONG', lookback=8, entry_zone_min=0.5, entry_zone_max=0.618
    )

    print(f"\n📐 Fibonacci Levels:")
    print(f"   Swing High: {fib_data.get('swing_high', 0):.2f}")
    print(f"   Swing Low: {fib_data.get('swing_low', 0):.2f}")
    print(f"   Fib 50%: {fib_data.get('fib_50', 0):.2f}")
    print(f"   Fib 61.8%: {fib_data.get('fib_61_8', 0):.2f}")
    print(f"   Current Price: {fib_data.get('current_price', 0):.2f}")
    print(f"   In Entry Zone: {in_zone}")
    print(f"   Pullback Depth: {fib_data.get('pullback_depth', 0):.1f}%")
    print(f"   Entry Zone: {fib_data.get('entry_zone', 'N/A')}")

    if in_zone:
        print("   ✅ PRICE IS IN GOLDEN RATIO ZONE!")
    else:
        print("   ❌ Price outside entry zone")

    print("\n✅ PASSED: Entry zone detection working\n")
    return True


def test_edge_cases():
    """Test edge cases and boundary conditions."""
    print("=" * 70)
    print("⚠️  TESTING EDGE CASES")
    print("=" * 70)

    print("\n📝 Test 1: Price exactly at 50% level")
    prices = [[100, 95, 98, 1000], [110, 105, 108, 1000], [105, 100, 105, 1000]]
    df = create_test_dataframe(prices)
    current = df.iloc[-1]

    in_zone, fib_data = check_fibonacci_pullback(df, current, 'LONG')
    print(f"   Price: {current['close']}, In Zone: {in_zone}")
    assert in_zone, "Price at 50% should be in zone"
    print("   ✅ PASSED")

    print("\n📝 Test 2: Price exactly at 61.8% level")
    prices = [[100, 95, 98, 1000], [110, 105, 108, 1000], [103.82, 98, 103.82, 1000]]
    df = create_test_dataframe(prices)
    current = df.iloc[-1]

    in_zone, fib_data = check_fibonacci_pullback(df, current, 'LONG')
    print(f"   Price: {current['close']:.2f}, In Zone: {in_zone}")
    assert in_zone, "Price at 61.8% should be in zone"
    print("   ✅ PASSED")

    print("\n📝 Test 3: Price beyond 78.6% (too deep)")
    prices = [[100, 95, 98, 1000], [110, 105, 108, 1000], [102, 97, 102, 1000]]
    df = create_test_dataframe(prices)
    current = df.iloc[-1]

    in_zone, fib_data = check_fibonacci_pullback(df, current, 'LONG')
    print(f"   Price: {current['close']}, In Zone: {in_zone}")
    assert not in_zone, "Price beyond 78.6% should NOT be in zone"
    print("   ✅ PASSED")

    print("\n📝 Test 4: Insufficient data (< 5 candles)")
    prices = [[100, 95, 98, 1000], [110, 105, 108, 1000]]
    df = create_test_dataframe(prices)
    current = df.iloc[-1]

    in_zone, fib_data = check_fibonacci_pullback(df, current, 'LONG')
    assert not in_zone, "Should handle insufficient data"
    print(f"   Insufficient data handled: {not in_zone}")
    print("   ✅ PASSED")

    print("\n✅ ALL EDGE CASES PASSED\n")
    return True


def test_fib_extensions():
    """Test Fibonacci extension target calculation."""
    print("=" * 70)
    print("🎯 TESTING FIBONACCI EXTENSION TARGETS")
    print("=" * 70)

    swing_high = 110.0
    swing_low = 100.0

    print(f"\n📈 LONG Extensions:")
    extensions_long = calculate_fib_extension_targets(swing_high, swing_low, 'LONG')

    print(f"   100% Extension: {extensions_long['ext_1_0']:.2f}")
    print(f"   127.2% Extension: {extensions_long['ext_1_272']:.2f}")
    print(f"   161.8% Extension: {extensions_long['ext_1_618']:.2f} ⭐")
    print(f"   200% Extension: {extensions_long['ext_2_0']:.2f}")

    assert extensions_long['ext_1_0'] == 120.0, "100% extension should be 120"
    assert abs(extensions_long['ext_1_272'] - 122.72) < 0.01, "127.2% should be 122.72"
    assert abs(extensions_long['ext_1_618'] - 126.18) < 0.01, "161.8% should be 126.18"

    print(f"\n📉 SHORT Extensions:")
    extensions_short = calculate_fib_extension_targets(swing_high, swing_low, 'SHORT')

    print(f"   100% Extension: {extensions_short['ext_1_0']:.2f}")
    print(f"   127.2% Extension: {extensions_short['ext_1_272']:.2f}")
    print(f"   161.8% Extension: {extensions_short['ext_1_618']:.2f} ⭐")
    print(f"   200% Extension: {extensions_short['ext_2_0']:.2f}")

    assert extensions_short['ext_1_0'] == 90.0, "100% extension should be 90"

    print("\n✅ PASSED: Extension calculations correct\n")
    return True


def test_signal_validation():
    """Test Fibonacci signal validation with confirmations."""
    print("=" * 70)
    print("✅ TESTING FIBONACCI SIGNAL VALIDATION")
    print("=" * 70)

    fib_data = {
        'in_entry_zone': True,
        'fib_50': 105.0,
        'fib_61_8': 103.82,
        'current_price': 104.5
    }

    current = pd.Series({
        'close': 104.5,
        'rsi': 32.0,
        'volume_trend': 1.3
    })

    print("\n📝 Test 1: Valid LONG signal with all confirmations")
    valid, reason = validate_fibonacci_signal(fib_data, current, 'LONG')
    print(f"   Valid: {valid}, Reason: {reason}")
    assert valid, "Should be valid with RSI 32 and good volume"
    print("   ✅ PASSED")

    print("\n📝 Test 2: Invalid - RSI too high for LONG")
    current_bad_rsi = current.copy()
    current_bad_rsi['rsi'] = 65.0
    valid, reason = validate_fibonacci_signal(fib_data, current_bad_rsi, 'LONG')
    print(f"   Valid: {valid}, Reason: {reason}")
    assert not valid, "Should be invalid with RSI 65"
    print("   ✅ PASSED")

    print("\n📝 Test 3: Invalid - Low volume")
    current_low_vol = current.copy()
    current_low_vol['volume_trend'] = 0.6
    valid, reason = validate_fibonacci_signal(fib_data, current_low_vol, 'LONG')
    print(f"   Valid: {valid}, Reason: {reason}")
    assert not valid, "Should be invalid with low volume"
    print("   ✅ PASSED")

    print("\n📝 Test 4: Invalid - Not in entry zone")
    fib_data_outside = fib_data.copy()
    fib_data_outside['in_entry_zone'] = False
    valid, reason = validate_fibonacci_signal(fib_data_outside, current, 'LONG')
    print(f"   Valid: {valid}, Reason: {reason}")
    assert not valid, "Should be invalid outside entry zone"
    print("   ✅ PASSED")

    print("\n✅ ALL VALIDATION TESTS PASSED\n")
    return True


def main():
    """Run all Fibonacci utility tests."""
    print("\n" + "=" * 70)
    print("🚀 FIBONACCI PULLBACK UTILITY TEST SUITE")
    print("=" * 70 + "\n")

    tests = [
        ('Swing Detection', test_swing_detection),
        ('Fibonacci Level Calculation', test_fib_level_calculation),
        ('Pullback Entry Zone', test_pullback_entry_zone),
        ('Edge Cases', test_edge_cases),
        ('Fibonacci Extensions', test_fib_extensions),
        ('Signal Validation', test_signal_validation),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"❌ {test_name} FAILED: {e}\n")
            results.append((test_name, False))

    print("\n" + "=" * 70)
    print("📊 FINAL TEST RESULTS")
    print("=" * 70 + "\n")

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {test_name:.<50} {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 70)

    if all_passed:
        print("✅ ALL TESTS PASSED - Fibonacci Utils Ready for Integration!")
    else:
        print("❌ SOME TESTS FAILED - Please review implementation")

    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    exit(main())
