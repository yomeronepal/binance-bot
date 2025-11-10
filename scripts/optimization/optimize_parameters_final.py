#!/usr/bin/env python3
"""
Final Parameter Optimization
Since volume filter didn't help (signals already had good volume),
let's optimize the actual entry parameters to filter bad trades.

Strategy: Test combinations that should increase win rate:
1. Tighter RSI ranges (more extreme oversold/overbought)
2. Higher confidence threshold (stricter entry)
3. Higher ADX (stronger trends only)
4. Wider R/R ratio (let winners run)
"""
import requests
import time
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import API_BASE

# Optimized configurations
CONFIGS = [
    {
        "name": "BASELINE - 4h BTC",
        "description": "Current: 22.2% win rate, 9 trades",
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
        "name": "OPT1 - Tighter RSI (23-33)",
        "description": "More extreme entry points",
        "symbol": "BTCUSDT",
        "params": {
            "min_confidence": 0.70,
            "long_adx_min": 20.0,
            "short_adx_min": 20.0,
            "long_rsi_min": 23.0,  # Tighter
            "long_rsi_max": 33.0,
            "short_rsi_min": 67.0,
            "short_rsi_max": 77.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
        }
    },
    {
        "name": "OPT2 - Higher Confidence (75%)",
        "description": "Only very confident signals",
        "symbol": "BTCUSDT",
        "params": {
            "min_confidence": 0.75,  # Higher
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
        "name": "OPT3 - Higher ADX (25)",
        "description": "Stronger trends only",
        "symbol": "BTCUSDT",
        "params": {
            "min_confidence": 0.70,
            "long_adx_min": 25.0,  # Higher
            "short_adx_min": 25.0,
            "long_rsi_min": 25.0,
            "long_rsi_max": 35.0,
            "short_rsi_min": 65.0,
            "short_rsi_max": 75.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
        }
    },
    {
        "name": "OPT4 - Wider R/R (1:4)",
        "description": "Let winners run further",
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
            "tp_atr_multiplier": 6.0  # Wider TP (1:4)
        }
    },
    {
        "name": "OPT5 - Tighter SL (1:3.5)",
        "description": "Cut losses faster",
        "symbol": "BTCUSDT",
        "params": {
            "min_confidence": 0.70,
            "long_adx_min": 20.0,
            "short_adx_min": 20.0,
            "long_rsi_min": 25.0,
            "long_rsi_max": 35.0,
            "short_rsi_min": 65.0,
            "short_rsi_max": 75.0,
            "sl_atr_multiplier": 1.25,  # Tighter SL
            "tp_atr_multiplier": 4.375
        }
    },
    {
        "name": "OPT6 - Combined Best (Tight RSI + High Conf)",
        "description": "Best filters combined",
        "symbol": "BTCUSDT",
        "params": {
            "min_confidence": 0.73,  # Higher
            "long_adx_min": 22.0,    # Slightly higher
            "short_adx_min": 22.0,
            "long_rsi_min": 23.0,    # Tighter
            "long_rsi_max": 33.0,
            "short_rsi_min": 67.0,
            "short_rsi_max": 77.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
        }
    },
    {
        "name": "OPT7 - Aggressive (RSI 20-30)",
        "description": "Very extreme entries",
        "symbol": "BTCUSDT",
        "params": {
            "min_confidence": 0.70,
            "long_adx_min": 20.0,
            "short_adx_min": 20.0,
            "long_rsi_min": 20.0,  # Very tight
            "long_rsi_max": 30.0,
            "short_rsi_min": 70.0,
            "short_rsi_max": 80.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
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
print("FINAL PARAMETER OPTIMIZATION")
print("=" * 80)
print("\n🎯 Goal: Find parameter combination that increases win rate")
print("   Current: 22.2% win rate, 9 trades, -$1.83")
print("   Target: 25-30% win rate = PROFITABLE\n")
print("   Strategy: Test different filters to remove 1-2 losing trades\n")

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
print("RESULTS - PARAMETER OPTIMIZATION")
print("=" * 80)

results = []
for item in submitted:
    data = get_results(item["id"])
    if data and data.get("status") == "COMPLETED":
        results.append({
            "name": item["config"]["name"],
            "description": item["config"]["description"],
            "trades": data.get("total_trades", 0),
            "win_rate": float(data.get("win_rate", 0)),
            "roi": float(data.get("roi", 0)),
            "pf": float(data.get("profit_factor") or 0),
            "pnl": float(data.get("total_profit_loss", 0)),
            "dd": float(data.get("max_drawdown", 0)),
            "sharpe": float(data.get("sharpe_ratio") or 0),
            "params": item["config"]["params"]
        })

results.sort(key=lambda x: x["roi"], reverse=True)

print(f"\n{'Name':<45} {'Trades':<7} {'Win%':<7} {'ROI%':<9} {'P/L $':<10}")
print("-" * 100)

baseline = None
for r in results:
    roi_str = f"+{r['roi']:.2f}" if r['roi'] > 0 else f"{r['roi']:.2f}"
    pnl_str = f"+{r['pnl']:.2f}" if r['pnl'] > 0 else f"{r['pnl']:.2f}"

    marker = ""
    if r['roi'] > 0:
        marker = " ✅ PROFITABLE!"
    elif r['roi'] > -0.01:
        marker = " 🔥 VERY CLOSE!"

    print(f"{r['name']:<45} {r['trades']:<7} {r['win_rate']:<7.1f} "
          f"{roi_str:<9} ${pnl_str:<9}{marker}")

    if "BASELINE" in r["name"]:
        baseline = r

print("\n" + "=" * 80)
print("DETAILED ANALYSIS")
print("=" * 80)

if baseline:
    print(f"\n📊 BASELINE PERFORMANCE:")
    print(f"   Trades: {baseline['trades']}")
    print(f"   Win Rate: {baseline['win_rate']:.1f}%")
    print(f"   ROI: {baseline['roi']:+.2f}%")
    print(f"   P/L: ${baseline['pnl']:+.2f}")
    print(f"   Profit Factor: {baseline['pf']:.2f}")

    print(f"\n📈 OPTIMIZATION RESULTS:")
    for r in results:
        if "BASELINE" not in r["name"]:
            win_rate_change = r['win_rate'] - baseline['win_rate']
            roi_change = r['roi'] - baseline['roi']
            trades_change = r['trades'] - baseline['trades']

            print(f"\n{r['name']}:")
            print(f"   {r['description']}")
            print(f"   Trades: {r['trades']} ({trades_change:+d})")
            print(f"   Win Rate: {r['win_rate']:.1f}% ({win_rate_change:+.1f}%)")
            print(f"   ROI: {r['roi']:+.2f}% ({roi_change:+.3f}%)")
            print(f"   P/L: ${r['pnl']:+.2f} (${r['pnl'] - baseline['pnl']:+.2f})")

    best = max(results, key=lambda x: x["roi"])

    print("\n" + "=" * 80)
    print("FINAL VERDICT")
    print("=" * 80)

    if best["roi"] > 0:
        print("\n✅ ✅ ✅ SUCCESS - PROFITABLE! ✅ ✅ ✅")
        print(f"\n🏆 {best['name']}")
        print(f"   {best['description']}")
        print(f"   Trades: {best['trades']}")
        print(f"   Win Rate: {best['win_rate']:.1f}%")
        print(f"   ROI: {best['roi']:+.2f}%")
        print(f"   P/L: ${best['pnl']:+.2f}")
        print(f"   Profit Factor: {best['pf']:.2f}")
        print(f"   Sharpe Ratio: {best['sharpe']:.2f}")

        print("\n📋 WINNING PARAMETERS:")
        for k, v in best['params'].items():
            print(f"   {k}: {v}")

        print("\n📋 NEXT STEPS:")
        print("   ✅ 1. Profitable parameters identified!")
        print("   ⏭️  2. Deploy to paper trading for validation")
        print("   ⏭️  3. Monitor for 1-2 weeks")
        print("   ⏭️  4. If performance holds, deploy to live trading")

    elif best["roi"] > baseline["roi"]:
        print(f"\n⚠️  IMPROVEMENT BUT NOT YET PROFITABLE")
        print(f"   Baseline: {baseline['roi']:+.2f}% ROI")
        print(f"   Best: {best['roi']:+.2f}% ROI ({best['name']})")
        print(f"   Improvement: {best['roi'] - baseline['roi']:+.3f}%")

        if best["roi"] > -0.01:
            print(f"\n🔥 EXTREMELY CLOSE! Only ${-best['pnl']:.2f} away from breakeven")
            print(f"   Win Rate: {best['win_rate']:.1f}% (need ~23-24% for profitability)")
            print("\n💡 Suggested next steps:")
            print("   1. Test with slightly wider TP (6.0-6.5x ATR)")
            print("   2. Or lower volume threshold to 1.2x (we already added this)")
            print("   3. Or test on longer period (6-12 months)")
            print("   4. Consider the strategy might be profitable in different market conditions")
        else:
            print("\n💡 Making progress. Continue optimization:")
            print("   1. Try combination of best parameters from above")
            print("   2. Test different date ranges (maybe strategy works in specific regimes)")
            print("   3. Consider adding multi-timeframe filter (Phase 2)")

    else:
        print(f"\n❌ NO IMPROVEMENT")
        print(f"   All optimizations performed worse than baseline")
        print(f"   This suggests the issue is not with parameter tuning")
        print("\n💡 Recommended next steps:")
        print("   1. Implement multi-timeframe confirmation (Phase 2)")
        print("   2. Add market regime detection")
        print("   3. Consider completely different entry logic")

else:
    print("\n⚠️  Could not find baseline results")

print("\n" + "=" * 80)
