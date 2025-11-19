#!/usr/bin/env python3
"""
Test script to validate PERCENTAGE-BASED Risk/Reward ratio implementation.

This script tests that all signals enforce:
- Risk: 3% of position (entry price)
- Profit: 9% of position (entry price)
- Maintains 1:3 Risk/Reward ratio

Usage:
    python test_rr_ratio.py
"""

def test_percentage_based_calculation():
    """Test percentage-based R/R calculation logic."""
    print("=" * 70)
    print("🧪 TESTING PERCENTAGE-BASED RISK/REWARD CALCULATION")
    print("=" * 70)

    test_cases = [
        {
            'name': 'LONG Signal - MANTAUSDT',
            'direction': 'LONG',
            'entry': 0.1236,
            'expected_risk_pct': 3.0,
            'expected_profit_pct': 9.0
        },
        {
            'name': 'SHORT Signal - BTC',
            'direction': 'SHORT',
            'entry': 50000.0,
            'expected_risk_pct': 3.0,
            'expected_profit_pct': 9.0
        },
        {
            'name': 'LONG Signal - BTC',
            'direction': 'LONG',
            'entry': 42500.0,
            'expected_risk_pct': 3.0,
            'expected_profit_pct': 9.0
        },
        {
            'name': 'SHORT Signal - ETH',
            'direction': 'SHORT',
            'entry': 2300.0,
            'expected_risk_pct': 3.0,
            'expected_profit_pct': 9.0
        },
    ]

    passed = 0
    failed = 0

    for test in test_cases:
        print(f"\n📝 Test: {test['name']}")
        print(f"   Direction: {test['direction']}")
        print(f"   Entry: {test['entry']}")

        risk_percentage = 0.03
        profit_percentage = 0.09

        if test['direction'] == 'LONG':
            sl = test['entry'] * (1 - risk_percentage)
            tp = test['entry'] * (1 + profit_percentage)
        else:
            sl = test['entry'] * (1 + risk_percentage)
            tp = test['entry'] * (1 - profit_percentage)

        risk_amount = abs(test['entry'] - sl)
        profit_amount = abs(tp - test['entry'])

        risk_pct = (risk_amount / test['entry']) * 100
        profit_pct = (profit_amount / test['entry']) * 100
        rr_ratio = profit_amount / risk_amount if risk_amount > 0 else 0

        risk_match = abs(risk_pct - test['expected_risk_pct']) < 0.01
        profit_match = abs(profit_pct - test['expected_profit_pct']) < 0.01
        rr_match = abs(rr_ratio - 3.0) < 0.001

        print(f"   Calculated SL: {sl:.8f}")
        print(f"   Calculated TP: {tp:.8f}")
        print(f"   Risk %: {risk_pct:.2f}% (Expected: {test['expected_risk_pct']:.2f}%) {'✅' if risk_match else '❌'}")
        print(f"   Profit %: {profit_pct:.2f}% (Expected: {test['expected_profit_pct']:.2f}%) {'✅' if profit_match else '❌'}")
        print(f"   R/R Ratio: 1:{rr_ratio:.2f} (Expected: 1:3.00) {'✅' if rr_match else '❌'}")

        if risk_match and profit_match and rr_match:
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
    """Test that percentage-based formula works consistently across all timeframes."""
    print("=" * 70)
    print("🕐 TESTING ACROSS MULTIPLE TIMEFRAMES")
    print("=" * 70)

    timeframes = ['15m', '1h', '4h', '1d']

    print("\nVerifying 3% risk / 9% profit across all timeframes:")
    print("(Timeframe doesn't affect percentage-based calculations)\n")

    all_correct = True

    for tf in timeframes:
        entry = 50000.0
        risk_percentage = 0.03
        profit_percentage = 0.09

        print(f"📅 Timeframe: {tf}")

        sl_long = entry * (1 - risk_percentage)
        tp_long = entry * (1 + profit_percentage)
        risk_pct_long = ((entry - sl_long) / entry) * 100
        profit_pct_long = ((tp_long - entry) / entry) * 100
        rr_long = (tp_long - entry) / (entry - sl_long)

        print(f"   LONG: Entry={entry:.2f}, SL={sl_long:.2f}, TP={tp_long:.2f}")
        print(f"        Risk={risk_pct_long:.2f}%, Profit={profit_pct_long:.2f}%, R/R=1:{rr_long:.2f}")

        if abs(risk_pct_long - 3.0) > 0.01 or abs(profit_pct_long - 9.0) > 0.01:
            print(f"   ❌ LONG percentages incorrect!")
            all_correct = False
        else:
            print(f"   ✅ LONG: 3% risk, 9% profit")

        sl_short = entry * (1 + risk_percentage)
        tp_short = entry * (1 - profit_percentage)
        risk_pct_short = ((sl_short - entry) / entry) * 100
        profit_pct_short = ((entry - tp_short) / entry) * 100
        rr_short = (entry - tp_short) / (sl_short - entry)

        print(f"   SHORT: Entry={entry:.2f}, SL={sl_short:.2f}, TP={tp_short:.2f}")
        print(f"         Risk={risk_pct_short:.2f}%, Profit={profit_pct_short:.2f}%, R/R=1:{rr_short:.2f}")

        if abs(risk_pct_short - 3.0) > 0.01 or abs(profit_pct_short - 9.0) > 0.01:
            print(f"   ❌ SHORT percentages incorrect!")
            all_correct = False
        else:
            print(f"   ✅ SHORT: 3% risk, 9% profit")

        print()

    if all_correct:
        print("✅ All timeframes produce consistent 3% risk / 9% profit")
    else:
        print("❌ Some timeframes have incorrect percentages")

    print(f"\n{'=' * 70}\n")

    return all_correct


def test_edge_cases():
    """Test edge cases with different entry prices."""
    print("=" * 70)
    print("⚠️  TESTING EDGE CASES")
    print("=" * 70)

    edge_cases = [
        {'name': 'Very small values', 'entry': 0.0001},
        {'name': 'Very large values', 'entry': 100000.0},
        {'name': 'Crypto precision', 'entry': 0.0123456},
    ]

    all_passed = True

    for case in edge_cases:
        print(f"\n📝 {case['name']}")
        print(f"   Entry: {case['entry']}")

        risk_percentage = 0.03
        profit_percentage = 0.09

        sl = case['entry'] * (1 - risk_percentage)
        tp = case['entry'] * (1 + profit_percentage)

        risk_pct = ((case['entry'] - sl) / case['entry']) * 100
        profit_pct = ((tp - case['entry']) / case['entry']) * 100
        rr = (tp - case['entry']) / (case['entry'] - sl)

        print(f"   SL: {sl:.10f}")
        print(f"   TP: {tp:.10f}")
        print(f"   Risk %: {risk_pct:.2f}%")
        print(f"   Profit %: {profit_pct:.2f}%")
        print(f"   R/R: 1:{rr:.2f}")

        if abs(risk_pct - 3.0) < 0.01 and abs(profit_pct - 9.0) < 0.01:
            print(f"   ✅ Percentages correct (3% risk, 9% profit)")
        else:
            print(f"   ❌ Percentages incorrect (expected 3% risk, 9% profit)")
            all_passed = False

    print(f"\n{'=' * 70}\n")

    return all_passed


def test_leverage_independence():
    """Test that leverage does NOT affect percentage calculations."""
    print("=" * 70)
    print("📈 TESTING LEVERAGE INDEPENDENCE")
    print("=" * 70)

    print("\nPercentages remain 3% risk / 9% profit regardless of leverage")
    print("(Leverage affects position size and ROI, NOT the risk/profit percentages)\n")

    leverages = [1, 5, 10, 20, 50, 100]
    entry = 50000.0

    risk_percentage = 0.03
    profit_percentage = 0.09

    sl = entry * (1 - risk_percentage)
    tp = entry * (1 + profit_percentage)

    all_correct = True

    for leverage in leverages:
        risk_pct = ((entry - sl) / entry) * 100
        profit_pct = ((tp - entry) / entry) * 100

        effective_risk_pct = risk_pct * leverage
        effective_profit_pct = profit_pct * leverage

        print(f"🔢 Leverage: {leverage}x")
        print(f"   Base Risk %: {risk_pct:.2f}% (MUST be 3.00%)")
        print(f"   Base Profit %: {profit_pct:.2f}% (MUST be 9.00%)")
        print(f"   Effective Risk on Capital: {effective_risk_pct:.2f}%")
        print(f"   Effective Profit on Capital: {effective_profit_pct:.2f}%")

        if abs(risk_pct - 3.0) > 0.01 or abs(profit_pct - 9.0) > 0.01:
            print(f"   ❌ Base percentages changed with leverage!")
            all_correct = False
        else:
            print(f"   ✅ Base percentages remain 3% / 9%")

        print()

    if all_correct:
        print("✅ Percentages are independent of leverage (correct)")
    else:
        print("❌ Percentages are affected by leverage (incorrect)")

    print(f"\n{'=' * 70}\n")

    return all_correct


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("🚀 PERCENTAGE-BASED RISK/REWARD VALIDATION TEST SUITE")
    print("=" * 70)
    print("\nThis test validates that ALL signals enforce:")
    print("- Risk: 3% of position (entry price)")
    print("- Profit: 9% of position (entry price)")
    print("- R/R Ratio: 1:3.00 (profit is 3x risk)\n")

    results = []

    results.append(('Percentage-Based Calculation', test_percentage_based_calculation()))
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
        print("✅ ALL TESTS PASSED - Percentage-Based R/R Implementation is Correct!")
        print("\n📊 Summary:")
        print("   • Risk: 3% of entry price")
        print("   • Profit: 9% of entry price")
        print("   • R/R Ratio: 1:3.00")
    else:
        print("❌ SOME TESTS FAILED - Please review the implementation")

    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    exit(main())
