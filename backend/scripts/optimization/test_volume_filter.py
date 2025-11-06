#!/usr/bin/env python3
"""
Phase 1 Optimization Test - Volume Filter
Tests the impact of adding a 1.5x volume filter to signal detection
Expected: Win rate improvement from 22% → 30-35%
"""
import requests
import time

API_BASE = "http://localhost:8000/api"

# Test configurations
CONFIGS = [
    {
        "name": "BASELINE - 4h BTC (No Volume Filter)",
        "description": "Original strategy for comparison",
        "symbol": "BTCUSDT",
        "params": {
            "min_confidence": 0.70,
            "long_adx_min": 20.0,
            "short_adx_min": 20.0,
            "long_rsi_min": 25.0,
            "long_rsi_max": 35.0,
            "short_rsi_min": 65.0,
            "short_rsi_max": 75.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
        }
    },
    {
        "name": "PHASE 1 - 4h BTC (With Volume Filter)",
        "description": "Volume filter active (1.5x average minimum)",
        "symbol": "BTCUSDT",
        "params": {
            "min_confidence": 0.70,
            "long_adx_min": 20.0,
            "short_adx_min": 20.0,
            "long_rsi_min": 25.0,
            "long_rsi_max": 35.0,
            "short_rsi_min": 65.0,
            "short_rsi_max": 75.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
        }
    },
    # Test on other symbols too
    {
        "name": "PHASE 1 - 4h ETH (With Volume Filter)",
        "description": "Test volume filter on ETH",
        "symbol": "ETHUSDT",
        "params": {
            "min_confidence": 0.70,
            "long_adx_min": 20.0,
            "short_adx_min": 20.0,
            "long_rsi_min": 25.0,
            "long_rsi_max": 35.0,
            "short_rsi_min": 65.0,
            "short_rsi_max": 75.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
        }
    },
    {
        "name": "PHASE 1 - 4h SOL (With Volume Filter)",
        "description": "Test volume filter on SOL",
        "symbol": "SOLUSDT",
        "params": {
            "min_confidence": 0.70,
            "long_adx_min": 20.0,
            "short_adx_min": 20.0,
            "long_rsi_min": 25.0,
            "long_rsi_max": 35.0,
            "short_rsi_min": 65.0,
            "short_rsi_max": 75.0,
            "sl_atr_multiplier": 2.0,
            "tp_atr_multiplier": 7.0
        }
    }
]


def submit_backtest(config):
    payload = {
        "name": config["name"],
        "symbols": [config["symbol"]],
        "timeframe": "4h",
        "start_date": "2024-08-04T00:00:00Z",
        "end_date": "2025-11-02T00:00:00Z",
        "strategy_params": config["params"],
        "initial_capital": 10000,
        "position_size": 100
    }

    try:
        response = requests.post(f"{API_BASE}/backtest/", json=payload)
        response.raise_for_status()
        return response.json().get("id")
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def get_results(backtest_id):
    try:
        response = requests.get(f"{API_BASE}/backtest/{backtest_id}/")
        response.raise_for_status()
        return response.json()
    except:
        return None


def wait_for_completion(ids, max_wait=600):
    print(f"\n⏳ Waiting for {len(ids)} backtests to complete...")
    start = time.time()

    while time.time() - start < max_wait:
        completed = sum(1 for bid in ids
                       if (d := get_results(bid)) and d.get("status") in ["COMPLETED", "FAILED"])
        print(f"  Progress: {completed}/{len(ids)} completed", end="\r")

        if completed == len(ids):
            print(f"\n✅ All backtests completed!")
            return True

        time.sleep(10)

    return False


print("=" * 80)
print("PHASE 1 OPTIMIZATION TEST - VOLUME FILTER")
print("=" * 80)
print("\n🎯 Testing volume filter impact:")
print("   • Baseline: Original strategy (22% win rate, -0.02% ROI)")
print("   • Phase 1: With 1.5x volume filter")
print("   • Expected: +5-10% win rate improvement\n")

submitted = []
for i, config in enumerate(CONFIGS):
    print(f"📊 [{i+1}/{len(CONFIGS)}] {config['name']}")
    print(f"    {config['description']}")

    bid = submit_backtest(config)
    if bid:
        print(f"    ✅ Queued (ID: {bid})\n")
        submitted.append({"id": bid, "config": config})
        time.sleep(1)

if not submitted:
    print("❌ No backtests submitted")
    exit(1)

wait_for_completion([s["id"] for s in submitted])

print("\n" + "=" * 80)
print("RESULTS - PHASE 1 OPTIMIZATION")
print("=" * 80)

results = []
for item in submitted:
    data = get_results(item["id"])
    if data and data.get("status") == "COMPLETED":
        results.append({
            "name": item["config"]["name"],
            "symbol": item["config"]["symbol"],
            "trades": data.get("total_trades", 0),
            "win_rate": float(data.get("win_rate", 0)),
            "roi": float(data.get("roi", 0)),
            "pf": float(data.get("profit_factor") or 0),
            "pnl": float(data.get("total_profit_loss", 0)),
            "dd": float(data.get("max_drawdown", 0)),
            "sharpe": float(data.get("sharpe_ratio") or 0)
        })

results.sort(key=lambda x: x["roi"], reverse=True)

print(f"\n{'Name':<45} {'Symbol':<8} {'Trades':<7} {'Win%':<7} {'ROI%':<9} {'P/L $':<10}")
print("-" * 100)

baseline = None
phase1_results = []

for r in results:
    roi_str = f"+{r['roi']:.2f}" if r['roi'] > 0 else f"{r['roi']:.2f}"
    pnl_str = f"+{r['pnl']:.2f}" if r['pnl'] > 0 else f"{r['pnl']:.2f}"

    print(f"{r['name']:<45} {r['symbol']:<8} {r['trades']:<7} {r['win_rate']:<7.1f} "
          f"{roi_str:<9} ${pnl_str:<9}")

    if "BASELINE" in r["name"]:
        baseline = r
    elif "PHASE 1" in r["name"]:
        phase1_results.append(r)

print("\n" + "=" * 80)
print("ANALYSIS - VOLUME FILTER IMPACT")
print("=" * 80)

if baseline and phase1_results:
    print("\n📊 BASELINE (No Volume Filter):")
    print(f"   Trades: {baseline['trades']}")
    print(f"   Win Rate: {baseline['win_rate']:.1f}%")
    print(f"   ROI: {baseline['roi']:+.2f}%")
    print(f"   P/L: ${baseline['pnl']:+.2f}")
    print(f"   Profit Factor: {baseline['pf']:.2f}")

    print("\n📈 PHASE 1 RESULTS (With Volume Filter):")
    for r in phase1_results:
        print(f"\n   {r['symbol']}:")
        print(f"   Trades: {r['trades']} ({r['trades'] - baseline['trades']:+d} vs baseline)")
        print(f"   Win Rate: {r['win_rate']:.1f}% ({r['win_rate'] - baseline['win_rate']:+.1f}%)")
        print(f"   ROI: {r['roi']:+.2f}% ({r['roi'] - baseline['roi']:+.2f}%)")
        print(f"   P/L: ${r['pnl']:+.2f} (${r['pnl'] - baseline['pnl']:+.2f})")
        print(f"   Profit Factor: {r['pf']:.2f} ({r['pf'] - baseline['pf']:+.2f})")

    best_phase1 = max(phase1_results, key=lambda x: x["roi"])

    print("\n" + "=" * 80)
    print("VERDICT")
    print("=" * 80)

    if best_phase1["roi"] > 0:
        print("\n✅ ✅ ✅ SUCCESS - PROFITABLE! ✅ ✅ ✅")
        print(f"\n💰 Volume filter pushed strategy into profitability!")
        print(f"   Best: {best_phase1['symbol']} at {best_phase1['roi']:+.2f}% ROI")
        print(f"   Win Rate Improvement: {baseline['win_rate']:.1f}% → {best_phase1['win_rate']:.1f}%")
        print(f"   (+{best_phase1['win_rate'] - baseline['win_rate']:.1f}% improvement)")

        print("\n📋 NEXT STEPS:")
        print("   ✅ Phase 1 Complete - Volume filter working!")
        print("   ⏭️  Phase 2: Add multi-timeframe confirmation")
        print("   ⏭️  Phase 3: Implement adaptive parameters")

    elif best_phase1["roi"] > baseline["roi"]:
        print(f"\n⚠️  IMPROVEMENT BUT NOT YET PROFITABLE")
        print(f"   Baseline: {baseline['roi']:+.2f}% ROI")
        print(f"   Phase 1:  {best_phase1['roi']:+.2f}% ROI")
        print(f"   Improvement: {best_phase1['roi'] - baseline['roi']:+.2f}%")
        print(f"   Win Rate: {baseline['win_rate']:.1f}% → {best_phase1['win_rate']:.1f}%")

        if best_phase1["roi"] > -0.05:
            print("\n💡 Very close! Suggested next steps:")
            print("   1. Add multi-timeframe confirmation (Phase 2)")
            print("   2. Test with adjusted R/R ratio (widen TP)")
            print("   3. Both should push into profitability")
        else:
            print("\n💡 Good progress. Continue with:")
            print("   1. Phase 2: Multi-timeframe confirmation")
            print("   2. May need Phase 3: Adaptive parameters")

    else:
        print(f"\n❌ NO IMPROVEMENT")
        print(f"   Baseline: {baseline['roi']:+.2f}% ROI")
        print(f"   Phase 1:  {best_phase1['roi']:+.2f}% ROI")
        print(f"   Change: {best_phase1['roi'] - baseline['roi']:+.2f}%")

        print("\n💡 Volume filter may be too strict or not the issue:")
        print("   • Try lowering volume threshold to 1.2x or 1.3x")
        print("   • Or proceed directly to Phase 2 (multi-timeframe)")
        print("   • Check if signals are being filtered too aggressively")

else:
    print("\n⚠️  Could not compare baseline vs Phase 1")
    print("   Check that both baseline and Phase 1 tests completed")

print("\n" + "=" * 80)
print("DETAILED METRICS")
print("=" * 80)

for r in results:
    print(f"\n{r['name']}:")
    print(f"   Symbol: {r['symbol']}")
    print(f"   Total Trades: {r['trades']}")
    print(f"   Win Rate: {r['win_rate']:.1f}%")
    print(f"   ROI: {r['roi']:+.2f}%")
    print(f"   Profit/Loss: ${r['pnl']:+.2f}")
    print(f"   Profit Factor: {r['pf']:.2f}")
    print(f"   Max Drawdown: {r['dd']:.2f}%")
    print(f"   Sharpe Ratio: {r['sharpe']:.2f}")
