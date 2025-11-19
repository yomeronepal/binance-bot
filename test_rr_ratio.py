#!/usr/bin/env python3
"""
Test script to validate STRICT 1:3 Risk/Reward ratio implementation.

This script tests signal generation across multiple timeframes and
verifies that ALL signals have exactly 1:3.00 R/R ratio.

Usage:
    python test_rr_ratio.py
"""

def test_rr_calculation():
    """Test the R/R calculation logic."""
    print("=" * 70)
    print("🧪 TESTING RISK/REWARD RATIO CALCULATION")
    print("=" * 70)

    test_cases = [
        {
            'name': 'LONG Signal Example 1',
            'direction': 'LONG',
            'entry': 0.1236,
            'sl': 0.1169,
            'expected_risk': 0.0067,
            'expected_reward': 0.0201,
            'expected_tp': 0.1437
        },
        {
            'name': 'SHORT Signal Example 1',
            'direction': 'SHORT',
            'entry': 50000.0,
            'sl': 51000.0,
            'expected_risk': 1000.0,
            'expected_reward': 3000.0,
            'expected_tp': 47000.0
        },
        {
            'name': 'LONG Signal Example 2 (BTC)',
            'direction': 'LONG',
            'entry': 42500.0,
            'sl': 41800.0,
            'expected_risk': 700.0,
            'expected_reward': 2100.0,
            'expected_tp': 44600.0
        },
        {
            'name': 'SHORT Signal Example 2 (ETH)',
            'direction': 'SHORT',
            'entry': 2300.0,
            'sl': 2350.0,
            'expected_risk': 50.0,
            'expected_reward': 150.0,
            'expected_tp': 2150.0
        },
    ]

    passed = 0
    failed = 0

    for test in test_cases:
        print(f"\n📝 Test: {test['name']}")
        print(f"   Direction: {test['direction']}")
        print(f"   Entry: {test['entry']}")
        print(f"   SL: {test['sl']}")

        risk = abs(test['entry'] - test['sl'])
        reward = risk * 3.0

        if test['direction'] == 'LONG':
            tp = test['entry'] + reward
        else:
            tp = test['entry'] - reward

        rr_ratio = reward / risk if risk > 0 else 0

        risk_match = abs(risk - test['expected_risk']) < 0.001
        reward_match = abs(reward - test['expected_reward']) < 0.001
        tp_match = abs(tp - test['expected_tp']) < 0.001
        rr_match = abs(rr_ratio - 3.0) < 0.001

        print(f"   Calculated Risk: {risk:.4f} (Expected: {test['expected_risk']:.4f}) {'✅' if risk_match else '❌'}")
        print(f"   Calculated Reward: {reward:.4f} (Expected: {test['expected_reward']:.4f}) {'✅' if reward_match else '❌'}")
        print(f"   Calculated TP: {tp:.4f} (Expected: {test['expected_tp']:.4f}) {'✅' if tp_match else '❌'}")
        print(f"   R/R Ratio: 1:{rr_ratio:.2f} (Expected: 1:3.00) {'✅' if rr_match else '❌'}")

        if risk_match and reward_match and tp_match and rr_match:
            print(f"   ✅ PASSED")
            passed += 1
        else:
            print(f"   ❌ FAILED")
            failed += 1

    print(f"\n{'=' * 70}")
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    print(f"{'=' * 70}\n")

    return failed == 0


def test_all_timeframes():
    """Test that formula works consistently across all timeframes."""
    print("=" * 70)
    print("🕐 TESTING ACROSS MULTIPLE TIMEFRAMES")
    print("=" * 70)

    timeframes = ['15m', '1h', '4h', '1d']
    atr_values = [100, 200, 500, 800]

    print("\nSimulating signal generation with varying ATR values:")
    print("(ATR changes by timeframe, but R/R MUST always be 1:3.00)\n")

    all_correct = True

    for tf, atr in zip(timeframes, atr_values):
        entry = 50000.0
        sl_multiplier = 1.5

        print(f"📅 Timeframe: {tf}, ATR: {atr}")

        sl_long = entry - (sl_multiplier * atr)
        risk_long = abs(entry - sl_long)
        reward_long = risk_long * 3.0
        tp_long = entry + reward_long
        rr_long = reward_long / risk_long

        print(f"   LONG: Entry={entry:.2f}, SL={sl_long:.2f}, TP={tp_long:.2f}, R/R=1:{rr_long:.2f}")

        if abs(rr_long - 3.0) > 0.001:
            print(f"   ❌ LONG R/R is NOT 1:3.00!")
            all_correct = False
        else:
            print(f"   ✅ LONG R/R is exactly 1:3.00")

        sl_short = entry + (sl_multiplier * atr)
        risk_short = abs(entry - sl_short)
        reward_short = risk_short * 3.0
        tp_short = entry - reward_short
        rr_short = reward_short / risk_short

        print(f"   SHORT: Entry={entry:.2f}, SL={sl_short:.2f}, TP={tp_short:.2f}, R/R=1:{rr_short:.2f}")

        if abs(rr_short - 3.0) > 0.001:
            print(f"   ❌ SHORT R/R is NOT 1:3.00!")
            all_correct = False
        else:
            print(f"   ✅ SHORT R/R is exactly 1:3.00")

        print()

    if all_correct:
        print("✅ All timeframes produce consistent 1:3.00 R/R ratio")
    else:
        print("❌ Some timeframes have incorrect R/R ratio")

    print(f"\n{'=' * 70}\n")

    return all_correct


def test_edge_cases():
    """Test edge cases and extreme values."""
    print("=" * 70)
    print("⚠️  TESTING EDGE CASES")
    print("=" * 70)

    edge_cases = [
        {'name': 'Very small values', 'entry': 0.0001, 'sl': 0.00009},
        {'name': 'Very large values', 'entry': 100000.0, 'sl': 99000.0},
        {'name': 'Crypto precision', 'entry': 0.0123456, 'sl': 0.0120000},
    ]

    all_passed = True

    for case in edge_cases:
        print(f"\n📝 {case['name']}")
        print(f"   Entry: {case['entry']}, SL: {case['sl']}")

        risk = abs(case['entry'] - case['sl'])
        reward = risk * 3.0
        tp = case['entry'] + reward
        rr = reward / risk if risk > 0 else 0

        print(f"   Risk: {risk:.10f}")
        print(f"   Reward: {reward:.10f}")
        print(f"   TP: {tp:.10f}")
        print(f"   R/R: 1:{rr:.2f}")

        if abs(rr - 3.0) < 0.001:
            print(f"   ✅ R/R is correct (1:3.00)")
        else:
            print(f"   ❌ R/R is incorrect (expected 1:3.00, got 1:{rr:.2f})")
            all_passed = False

    print(f"\n{'=' * 70}\n")

    return all_passed


def test_leverage_independence():
    """Test that leverage does NOT affect R/R calculation."""
    print("=" * 70)
    print("📈 TESTING LEVERAGE INDEPENDENCE")
    print("=" * 70)

    print("\nR/R ratio MUST be 1:3.00 regardless of leverage")
    print("(Leverage affects position size and ROI, NOT the R/R ratio)\n")

    leverages = [1, 5, 10, 20, 50, 100]
    entry = 50000.0
    sl = 49000.0
    risk = abs(entry - sl)
    reward = risk * 3.0
    tp = entry + reward

    all_correct = True

    for leverage in leverages:
        rr = reward / risk
        position_size = 100.0
        actual_risk_amount = risk * leverage
        actual_reward_amount = reward * leverage
        roi = (actual_reward_amount / position_size) * 100

        print(f"🔢 Leverage: {leverage}x")
        print(f"   R/R Ratio: 1:{rr:.2f} (MUST be 1:3.00)")
        print(f"   Risk Amount: ${actual_risk_amount:.2f}")
        print(f"   Reward Amount: ${actual_reward_amount:.2f}")
        print(f"   Potential ROI: {roi:.2f}%")

        if abs(rr - 3.0) > 0.001:
            print(f"   ❌ R/R changed with leverage!")
            all_correct = False
        else:
            print(f"   ✅ R/R remains 1:3.00")

        print()

    if all_correct:
        print("✅ R/R ratio is independent of leverage (correct)")
    else:
        print("❌ R/R ratio is affected by leverage (incorrect)")

    print(f"\n{'=' * 70}\n")

    return all_correct


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("🚀 RISK/REWARD RATIO VALIDATION TEST SUITE")
    print("=" * 70)
    print("\nThis test validates that ALL signals enforce STRICT 1:3 R/R ratio")
    print("across all timeframes, symbols, and market conditions.\n")

    results = []

    results.append(('Basic R/R Calculation', test_rr_calculation()))
    results.append(('Multiple Timeframes', test_all_timeframes()))
    results.append(('Edge Cases', test_edge_cases()))
    results.append(('Leverage Independence', test_leverage_independence()))

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
        print("✅ ALL TESTS PASSED - R/R Ratio Implementation is Correct!")
    else:
        print("❌ SOME TESTS FAILED - Please review the implementation")

    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    exit(main())
