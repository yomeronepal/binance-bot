#!/usr/bin/env python3
"""
4-Hour Timeframe Final Optimization
Fine-tune parameters on 4h since it's almost profitable (-0.02% ROI)
"""
import requests
import time

API_BASE = "http://localhost:8000/api"

# Fine-tuned configurations for 4h timeframe
# Testing slight variations to push into profitability
CONFIGS = [
    {
        "name": "4h BTC - Base (Light Filter)",
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
        "name": "4h BTC - Higher Confidence",
        "symbol": "BTCUSDT",
        "params": {
            "min_confidence": 0.75,  # Higher confidence
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
        "name": "4h BTC - Higher ADX",
        "symbol": "BTCUSDT",
        "params": {
            "min_confidence": 0.70,
            "long_adx_min": 25.0,  # Higher ADX = stronger trends
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
        "name": "4h BTC - Wider R/R",
        "symbol": "BTCUSDT",
        "params": {
            "min_confidence": 0.70,
            "long_adx_min": 20.0,
            "short_adx_min": 20.0,
            "long_rsi_min": 25.0,
            "long_rsi_max": 35.0,
            "short_rsi_min": 65.0,
            "short_rsi_max": 75.0,
            "sl_atr_multiplier": 2.0,  # Wider SL
            "tp_atr_multiplier": 7.0   # Wider TP (1:3.5 R/R)
        }
    },
    {
        "name": "4h BTC - Combined Best",
        "symbol": "BTCUSDT",
        "params": {
            "min_confidence": 0.72,  # Slightly higher
            "long_adx_min": 22.0,    # Slightly higher
            "short_adx_min": 22.0,
            "long_rsi_min": 25.0,
            "long_rsi_max": 35.0,
            "short_rsi_min": 65.0,
            "short_rsi_max": 75.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
        }
    },
    # Also test other symbols on 4h
    {
        "name": "4h SOL - Moderate",
        "symbol": "SOLUSDT",
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
        "name": "4h ETH - Conservative",
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
print("4-HOUR TIMEFRAME - FINAL OPTIMIZATION")
print("=" * 80)
print("\n🎯 Goal: Push 4h timeframe into profitability")
print("   Current: -0.02% ROI, 22% win rate (very close!)")
print("   Testing: 7 parameter variations\n")

submitted = []
for config in CONFIGS:
    print(f"📊 {config['name']}")
    bid = submit_backtest(config)
    if bid:
        print(f"   ✅ Queued (ID: {bid})\n")
        submitted.append({"id": bid, "config": config})
        time.sleep(1)

if not submitted:
    exit(1)

wait_for_completion([s["id"] for s in submitted])

print("\n" + "=" * 80)
print("RESULTS - 4H TIMEFRAME OPTIMIZATION")
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
            "sharpe": float(data.get("sharpe_ratio") or 0),
            "dd": float(data.get("max_drawdown", 0)),
            "pnl": float(data.get("total_profit_loss", 0))
        })

results.sort(key=lambda x: x["roi"], reverse=True)

print(f"\n{'Name':<35} {'Symbol':<8} {'Trades':<7} {'Win%':<7} {'ROI%':<8} {'PF':<6} {'P/L $':<10}")
print("-" * 95)

for r in results:
    roi_color = "+" if r["roi"] > 0 else ""
    print(f"{r['name']:<35} {r['symbol']:<8} {r['trades']:<7} {r['win_rate']:<7.1f} "
          f"{roi_color}{r['roi']:<8.2f} {r['pf']:<6.2f} ${r['pnl']:<9.2f}")

print("\n" + "=" * 80)
print("ANALYSIS & RECOMMENDATIONS")
print("=" * 80)

if results:
    best = max(results, key=lambda x: x["roi"])
    profitable = [r for r in results if r["roi"] > 0]

    print(f"\n🏆 BEST RESULT: {best['name']}")
    print(f"   Symbol: {best['symbol']}")
    print(f"   Trades: {best['trades']}")
    print(f"   Win Rate: {best['win_rate']:.1f}%")
    print(f"   ROI: {best['roi']:+.2f}%")
    print(f"   Profit Factor: {best['pf']:.2f}")
    print(f"   P/L: ${best['pnl']:+.2f}")
    print(f"   Drawdown: {best['dd']:.2f}%")

    if profitable:
        print(f"\n✅ PROFITABLE CONFIGURATIONS FOUND: {len(profitable)}")
        print("\n💰 Profitable Results:")
        for r in profitable:
            print(f"   • {r['name']}: {r['roi']:+.2f}% ROI, {r['trades']} trades, {r['win_rate']:.1f}% win rate")

        print("\n🎉 SUCCESS! These parameters are ready for paper trading:")
        print(f"   1. Deploy best configuration to paper trading")
        print(f"   2. Monitor for 1-2 weeks")
        print(f"   3. If performance holds, deploy to live with small capital")

    elif best["roi"] > -0.10:
        print(f"\n⚠️  Very close to profitability ({best['roi']:+.2f}% ROI)")
        print("\n💡 Suggested refinements:")
        if best["pf"] < 1.0:
            print("   • Widen take profit (increase TP multiplier by 0.5x)")
            print("   • Or tighten stop loss (decrease SL multiplier)")
        if best["win_rate"] < 30:
            print("   • Increase confidence threshold by 3-5%")
            print("   • Or increase ADX minimum by 2-3 points")
        if best["trades"] < 5:
            print("   • Too few trades - loosen parameters slightly")

    else:
        print(f"\n❌ Still unprofitable ({best['roi']:+.2f}% ROI)")
        print("\n💡 Consider:")
        print("   • Add volume filter (trade only on high volume)")
        print("   • Implement multi-timeframe confirmation")
        print("   • Test alternative strategy approaches")

    # Compare with 5m baseline
    print("\n📊 IMPROVEMENT vs 5m BASELINE:")
    print(f"   5m BTCUSDT: -0.16% ROI, 8.6% win rate, 116 trades")
    print(f"   4h Best:    {best['roi']:+.2f}% ROI, {best['win_rate']:.1f}% win rate, {best['trades']} trades")
    print(f"   ")
    print(f"   ROI Improvement: {best['roi'] - (-0.16):+.2f}%")
    print(f"   Win Rate Improvement: {best['win_rate'] - 8.6:+.1f}%")
    print(f"   Trades Reduced: {116 - best['trades']} (quality over quantity!)")
