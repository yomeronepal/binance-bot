#!/usr/bin/env python3
"""
Balanced Timeframe Test
Tests 15m, 1h, 4h with MODERATE parameter improvements (not too strict)
"""
import requests
import json
import time
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import API_BASE

# Moderately improved configurations (not too strict!)
CONFIGS = [
    {
        "name": "15m - HIGH Vol DOGE (Moderate)",
        "symbol": "DOGEUSDT",
        "timeframe": "15m",
        "params": {
            "min_confidence": 0.70,  # Keep at 70% (not 80%)
            "long_adx_min": 20.0,    # Slightly higher (was 18)
            "short_adx_min": 20.0,
            "long_rsi_min": 25.0,
            "long_rsi_max": 33.0,    # Slightly tighter (was 35)
            "short_rsi_min": 67.0,   # Slightly tighter (was 65)
            "short_rsi_max": 75.0,
            "sl_atr_multiplier": 2.0,
            "tp_atr_multiplier": 7.0
        }
    },
    {
        "name": "15m - MED Vol SOL (Moderate)",
        "symbol": "SOLUSDT",
        "timeframe": "15m",
        "params": {
            "min_confidence": 0.73,  # Slightly higher (was 75%)
            "long_adx_min": 22.0,
            "short_adx_min": 22.0,
            "long_rsi_min": 25.0,
            "long_rsi_max": 33.0,
            "short_rsi_min": 67.0,
            "short_rsi_max": 75.0,
            "sl_atr_multiplier": 2.0,
            "tp_atr_multiplier": 7.0
        }
    },
    {
        "name": "15m - LOW Vol BTC (Moderate)",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "params": {
            "min_confidence": 0.70,
            "long_adx_min": 20.0,
            "short_adx_min": 20.0,
            "long_rsi_min": 25.0,
            "long_rsi_max": 33.0,
            "short_rsi_min": 67.0,
            "short_rsi_max": 75.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
        }
    },
    {
        "name": "1h - LOW Vol BTC (Moderate)",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "params": {
            "min_confidence": 0.70,
            "long_adx_min": 22.0,  # Slightly higher for 1h
            "short_adx_min": 22.0,
            "long_rsi_min": 25.0,
            "long_rsi_max": 35.0,  # Keep wider for 1h
            "short_rsi_min": 65.0,
            "short_rsi_max": 75.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
        }
    },
    {
        "name": "1h - MED Vol SOL (Moderate)",
        "symbol": "SOLUSDT",
        "timeframe": "1h",
        "params": {
            "min_confidence": 0.73,
            "long_adx_min": 22.0,
            "short_adx_min": 22.0,
            "long_rsi_min": 25.0,
            "long_rsi_max": 35.0,
            "short_rsi_min": 65.0,
            "short_rsi_max": 75.0,
            "sl_atr_multiplier": 2.0,
            "tp_atr_multiplier": 7.0
        }
    },
    {
        "name": "4h - LOW Vol BTC (Light Filter)",
        "symbol": "BTCUSDT",
        "timeframe": "4h",
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
    }
]


def submit_backtest(config):
    payload = {
        "name": config["name"],
        "symbols": [config["symbol"]],
        "timeframe": config["timeframe"],
        "start_date": "2024-08-04T00:00:00Z",
        "end_date": "2025-11-02T00:00:00Z",
        "strategy_params": config["params"],
        "initial_capital": 10000,
        "position_size": 100
    }

    try:
        response = requests.post(f"{API_BASE}/backtest/", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("id")
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
        completed = 0
        for bid in ids:
            data = get_results(bid)
            if data and data.get("status") in ["COMPLETED", "FAILED"]:
                completed += 1

        print(f"  Progress: {completed}/{len(ids)} completed", end="\r")

        if completed == len(ids):
            print(f"\n✅ All backtests completed!")
            return True

        time.sleep(10)

    return False


print("=" * 80)
print("BALANCED TIMEFRAME TEST")
print("=" * 80)
print("\n🎯 Testing moderate improvements across multiple timeframes:")
print("   • 15m: Slightly tighter RSI (25-33/67-75) vs baseline (25-35/65-75)")
print("   • 1h: Standard parameters with slightly higher ADX")
print("   • 4h: Light filtering to test longer timeframe")
print()

submitted = []
for config in CONFIGS:
    print(f"📊 {config['name']}")
    print(f"    Symbol: {config['symbol']}, Timeframe: {config['timeframe']}")

    bid = submit_backtest(config)
    if bid:
        print(f"    ✅ Queued (ID: {bid})\n")
        submitted.append({"id": bid, "config": config})
    else:
        print(f"    ❌ Failed\n")

    time.sleep(1)

if not submitted:
    print("❌ No backtests submitted")
    exit(1)

# Wait
wait_for_completion([s["id"] for s in submitted])

# Results
print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)

results = []
for item in submitted:
    data = get_results(item["id"])
    if data and data.get("status") == "COMPLETED":
        results.append({
            "name": item["config"]["name"],
            "timeframe": item["config"]["timeframe"],
            "symbol": item["config"]["symbol"],
            "trades": data.get("total_trades", 0),
            "win_rate": float(data.get("win_rate", 0)),
            "roi": float(data.get("roi", 0)),
            "pf": float(data.get("profit_factor") or 0),
            "sharpe": float(data.get("sharpe_ratio") or 0),
            "dd": float(data.get("max_drawdown", 0))
        })

results.sort(key=lambda x: x["roi"], reverse=True)

print(f"\n{'Name':<40} {'TF':<5} {'Trades':<8} {'Win%':<8} {'ROI%':<8} {'PF':<6} {'Sharpe':<8} {'DD%':<8}")
print("-" * 110)

for r in results:
    print(f"{r['name']:<40} {r['timeframe']:<5} {r['trades']:<8} {r['win_rate']:<8.2f} "
          f"{r['roi']:<8.2f} {r['pf']:<6.2f} {r['sharpe']:<8.2f} {r['dd']:<8.2f}")

# Analysis
print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)

if not results:
    print("\n❌ No completed results")
elif all(r["trades"] == 0 for r in results):
    print("\n⚠️  ALL backtests generated 0 trades - parameters still too strict!")
    print("\n💡 Recommendations:")
    print("   • Lower ADX to 18-20")
    print("   • Lower confidence to 65-70%")
    print("   • Widen RSI ranges back to 25-35/65-75")
    print("   • Or use completely different strategy approach")
else:
    by_tf = {}
    for r in results:
        tf = r["timeframe"]
        if tf not in by_tf:
            by_tf[tf] = []
        by_tf[tf].append(r)

    print("\n📊 Average by Timeframe:")
    for tf, items in sorted(by_tf.items()):
        avg_trades = sum(x["trades"] for x in items) / len(items)
        avg_win = sum(x["win_rate"] for x in items) / len(items)
        avg_roi = sum(x["roi"] for x in items) / len(items)
        print(f"\n  {tf}: {avg_trades:.0f} trades, {avg_win:.1f}% win rate, {avg_roi:+.2f}% ROI")

    best = max(results, key=lambda x: x["roi"])
    print(f"\n🏆 BEST: {best['name']}")
    print(f"   {best['trades']} trades, {best['win_rate']:.1f}% win rate, {best['roi']:+.2f}% ROI")

    if best["roi"] > 0:
        print("\n✅ PROFITABLE! Use these parameters for this timeframe.")
    elif best["pf"] > 0.7:
        print("\n⚠️  Close to breakeven. Fine-tune parameters slightly.")
    else:
        print("\n❌ Still losing. Need more aggressive optimization.")
