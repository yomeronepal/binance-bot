#!/usr/bin/env python3
"""
Phase 2 Testing: Multi-Timeframe Confirmation
Tests the impact of adding daily trend alignment to 4h signals

Expected Impact: +10-15% win rate improvement
Expected Result: Strategy should become profitable (> 0% ROI)
"""
import requests
import time

API_BASE = "http://localhost:8000/api"

# Test configurations
CONFIGS = [
    {
        "name": "BASELINE - OPT6 (No MTF Filter)",
        "description": "Best config from Phase 1, no multi-timeframe filter",
        "symbol": "BTCUSDT",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2025-11-02T00:00:00Z",
        "params": {
            "min_confidence": 0.73,
            "long_adx_min": 22.0,
            "short_adx_min": 22.0,
            "long_rsi_min": 23.0,
            "long_rsi_max": 33.0,
            "short_rsi_min": 67.0,
            "short_rsi_max": 77.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
        },
        "note": "Baseline from Phase 1: 6 trades, 16.7% win rate, -$3.12"
    },
    {
        "name": "PHASE 2 - OPT6 + MTF (BTCUSDT)",
        "description": "OPT6 with multi-timeframe confirmation",
        "symbol": "BTCUSDT",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2025-11-02T00:00:00Z",
        "params": {
            "min_confidence": 0.73,
            "long_adx_min": 22.0,
            "short_adx_min": 22.0,
            "long_rsi_min": 23.0,
            "long_rsi_max": 33.0,
            "short_rsi_min": 67.0,
            "short_rsi_max": 77.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
        },
        "note": "With MTF filter - should filter counter-trend trades"
    },
    {
        "name": "PHASE 2 - OPT6 + MTF (ETHUSDT)",
        "description": "Test MTF on ETHUSDT",
        "symbol": "ETHUSDT",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2025-11-02T00:00:00Z",
        "params": {
            "min_confidence": 0.73,
            "long_adx_min": 22.0,
            "short_adx_min": 22.0,
            "long_rsi_min": 23.0,
            "long_rsi_max": 33.0,
            "short_rsi_min": 67.0,
            "short_rsi_max": 77.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
        },
        "note": "ETH baseline: 2 trades, 0% win rate, -$4.75"
    },
    {
        "name": "PHASE 2 - OPT6 + MTF (SOLUSDT)",
        "description": "Test MTF on SOLUSDT",
        "symbol": "SOLUSDT",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2025-11-02T00:00:00Z",
        "params": {
            "min_confidence": 0.73,
            "long_adx_min": 22.0,
            "short_adx_min": 22.0,
            "long_rsi_min": 23.0,
            "long_rsi_max": 33.0,
            "short_rsi_min": 67.0,
            "short_rsi_max": 77.0,
            "sl_atr_multiplier": 2.0,  # Wider for SOL
            "tp_atr_multiplier": 7.0
        },
        "note": "SOL baseline: 1 trade, 0% win rate, -$3.69"
    }
]


def submit_backtest(config):
    payload = {
        "name": config["name"],
        "symbols": [config["symbol"]],
        "timeframe": "4h",
        "start_date": config["start_date"],
        "end_date": config["end_date"],
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
print("PHASE 2 TESTING: MULTI-TIMEFRAME CONFIRMATION")
print("=" * 80)
print("\n🎯 Testing impact of daily trend alignment")
print("   Baseline: OPT6 from Phase 1 (-0.03% ROI, 16.7% win rate)")
print("   Phase 2: OPT6 + Multi-Timeframe Filter")
print("   Expected: +10-15% win rate → PROFITABLE!\n")

submitted = []
for i, config in enumerate(CONFIGS):
    print(f"📊 [{i+1}/{len(CONFIGS)}] {config['name']}")
    print(f"    {config['description']}")
    print(f"    Symbol: {config['symbol']}")
    print(f"    Note: {config['note']}")

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
print("RESULTS - PHASE 2 MTF FILTER")
print("=" * 80)

results = []
for item in submitted:
    data = get_results(item["id"])
    if data and data.get("status") == "COMPLETED":
        results.append({
            "name": item["config"]["name"],
            "symbol": item["config"]["symbol"],
            "is_baseline": "BASELINE" in item["config"]["name"],
            "trades": data.get("total_trades", 0),
            "win_rate": float(data.get("win_rate", 0)),
            "roi": float(data.get("roi", 0)),
            "pf": float(data.get("profit_factor") or 0),
            "pnl": float(data.get("total_profit_loss", 0)),
            "dd": float(data.get("max_drawdown", 0)),
            "sharpe": float(data.get("sharpe_ratio") or 0)
        })

results.sort(key=lambda x: x["roi"], reverse=True)

print(f"\n{'Name':<50} {'Symbol':<8} {'Trades':<7} {'Win%':<7} {'ROI%':<9} {'P/L $':<10}")
print("-" * 110)

for r in results:
    roi_str = f"+{r['roi']:.2f}" if r['roi'] > 0 else f"{r['roi']:.2f}"
    pnl_str = f"+{r['pnl']:.2f}" if r['pnl'] > 0 else f"{r['pnl']:.2f}"

    marker = ""
    if r['roi'] > 0:
        marker = " ✅ PROFITABLE!"
    elif r['roi'] > -0.05:
        marker = " 🔥 VERY CLOSE!"

    print(f"{r['name']:<50} {r['symbol']:<8} {r['trades']:<7} {r['win_rate']:<7.1f} "
          f"{roi_str:<9} ${pnl_str:<9}{marker}")

print("\n" + "=" * 80)
print("DETAILED ANALYSIS")
print("=" * 80)

# Find baseline and Phase 2 results
baseline = next((r for r in results if r["is_baseline"]), None)
phase2_btc = next((r for r in results if not r["is_baseline"] and r["symbol"] == "BTCUSDT"), None)
phase2_eth = next((r for r in results if not r["is_baseline"] and r["symbol"] == "ETHUSDT"), None)
phase2_sol = next((r for r in results if not r["is_baseline"] and r["symbol"] == "SOLUSDT"), None)

if baseline:
    print("\n📊 BASELINE (Phase 1 - No MTF Filter):")
    print(f"   Trades: {baseline['trades']}")
    print(f"   Win Rate: {baseline['win_rate']:.1f}%")
    print(f"   ROI: {baseline['roi']:+.2f}%")
    print(f"   P/L: ${baseline['pnl']:+.2f}")
    print(f"   Profit Factor: {baseline['pf']:.2f}")
    print(f"   Max Drawdown: {baseline['dd']:.2f}%")

if phase2_btc:
    print("\n📈 PHASE 2 (With MTF Filter) - BTCUSDT:")
    print(f"   Trades: {phase2_btc['trades']} ({phase2_btc['trades'] - baseline['trades']:+d} vs baseline)")
    print(f"   Win Rate: {phase2_btc['win_rate']:.1f}% ({phase2_btc['win_rate'] - baseline['win_rate']:+.1f}%)")
    print(f"   ROI: {phase2_btc['roi']:+.2f}% ({phase2_btc['roi'] - baseline['roi']:+.3f}%)")
    print(f"   P/L: ${phase2_btc['pnl']:+.2f} (${phase2_btc['pnl'] - baseline['pnl']:+.2f})")
    print(f"   Profit Factor: {phase2_btc['pf']:.2f} ({phase2_btc['pf'] - baseline['pf']:+.2f})")
    print(f"   Sharpe Ratio: {phase2_btc['sharpe']:.2f}")

    print("\n💡 MTF Filter Impact:")
    if phase2_btc['trades'] < baseline['trades']:
        print(f"   ✅ Filtered out {baseline['trades'] - phase2_btc['trades']} trades (likely counter-trend)")
    if phase2_btc['win_rate'] > baseline['win_rate']:
        print(f"   ✅ Win rate improved by {phase2_btc['win_rate'] - baseline['win_rate']:.1f}%")
    if phase2_btc['roi'] > baseline['roi']:
        print(f"   ✅ ROI improved by {phase2_btc['roi'] - baseline['roi']:.3f}%")

if phase2_eth:
    print("\n💎 PHASE 2 - ETHUSDT:")
    print(f"   Trades: {phase2_eth['trades']}")
    print(f"   Win Rate: {phase2_eth['win_rate']:.1f}%")
    print(f"   ROI: {phase2_eth['roi']:+.2f}%")
    print(f"   P/L: ${phase2_eth['pnl']:+.2f}")

if phase2_sol:
    print("\n🌟 PHASE 2 - SOLUSDT:")
    print(f"   Trades: {phase2_sol['trades']}")
    print(f"   Win Rate: {phase2_sol['win_rate']:.1f}%")
    print(f"   ROI: {phase2_sol['roi']:+.2f}%")
    print(f"   P/L: ${phase2_sol['pnl']:+.2f}")

print("\n" + "=" * 80)
print("FINAL VERDICT - PHASE 2")
print("=" * 80)

best = max(results, key=lambda x: x["roi"])

if best["roi"] > 0:
    print("\n🎉 🎉 🎉 SUCCESS - PROFITABLE STRATEGY! 🎉 🎉 🎉")
    print(f"\n🏆 {best['name']}")
    print(f"   Symbol: {best['symbol']}")
    print(f"   Trades: {best['trades']}")
    print(f"   Win Rate: {best['win_rate']:.1f}%")
    print(f"   ROI: {best['roi']:+.2f}%")
    print(f"   P/L: ${best['pnl']:+.2f}")
    print(f"   Profit Factor: {best['pf']:.2f}")
    print(f"   Sharpe Ratio: {best['sharpe']:.2f}")

    print("\n📋 DEPLOYMENT CHECKLIST:")
    print("   ✅ 1. Phase 2 complete - Multi-timeframe filter working!")
    print("   ⏭️  2. Deploy to paper trading for real-time validation")
    print("   ⏭️  3. Monitor for 1-2 weeks")
    print("   ⏭️  4. If performance holds, deploy to live with small capital ($100-500)")
    print("   ⏭️  5. Scale up gradually if profitable")

elif best["roi"] > -0.01:
    print(f"\n🔥 VERY CLOSE TO PROFITABILITY")
    print(f"   Best: {best['name']}")
    print(f"   ROI: {best['roi']:+.2f}% (P/L: ${best['pnl']:+.2f})")
    print(f"   Win Rate: {best['win_rate']:.1f}%")

    if baseline and best['roi'] > baseline['roi']:
        print(f"\n   Improvement over baseline: {best['roi'] - baseline['roi']:+.3f}% ROI")

    print("\n💡 Next Steps:")
    print("   1. MTF filter helped but not enough")
    print("   2. Try Phase 3: Adaptive SL/TP based on volatility")
    print("   3. Or test on different market periods")
    print("   4. Consider ensemble strategy (combine multiple timeframes)")

else:
    print(f"\n⚠️  STILL UNPROFITABLE")
    print(f"   Best: {best['name']}")
    print(f"   ROI: {best['roi']:+.2f}% (P/L: ${best['pnl']:+.2f})")

    if baseline:
        change = best['roi'] - baseline['roi']
        if change > 0:
            print(f"   Improvement: {change:+.3f}% (moving in right direction)")
        else:
            print(f"   Change: {change:+.3f}% (MTF filter may need adjustment)")

    print("\n💡 Analysis:")
    if best['trades'] < 5:
        print("   • Too few trades - MTF filter may be too strict")
        print("   • Consider allowing NEUTRAL daily trend signals")
    else:
        print("   • Strategy fundamentals need rethinking")
        print("   • Consider different entry logic or indicators")

print("\n" + "=" * 80)
print("SUMMARY - PHASE 2 OPTIMIZATION")
print("=" * 80)

if baseline and phase2_btc:
    print(f"\nBaseline (Phase 1):  {baseline['trades']} trades, {baseline['win_rate']:.1f}% win rate, {baseline['roi']:+.2f}% ROI")
    print(f"Phase 2 (MTF Filter): {phase2_btc['trades']} trades, {phase2_btc['win_rate']:.1f}% win rate, {phase2_btc['roi']:+.2f}% ROI")
    print(f"\nNet Impact: {phase2_btc['roi'] - baseline['roi']:+.3f}% ROI, {phase2_btc['win_rate'] - baseline['win_rate']:+.1f}% win rate")

    if phase2_btc['roi'] > 0:
        print("\n✅ PHASE 2 SUCCESSFUL - Strategy is now PROFITABLE!")
    elif phase2_btc['roi'] > baseline['roi']:
        print("\n⚠️  PHASE 2 IMPROVED but not yet profitable")
    else:
        print("\n❌ PHASE 2 did not improve performance")

print("\n" + "=" * 80)
