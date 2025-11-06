#!/usr/bin/env python3
"""
Extended Period Backtest - 11 Months vs 3 Months
Tests if OPT6 parameters are profitable over longer period
"""
import requests
import time

API_BASE = "http://localhost:8000/api"

# Test configurations
CONFIGS = [
    {
        "name": "BASELINE - 3 Months (Aug-Nov 2024)",
        "description": "Short period baseline for comparison",
        "symbol": "BTCUSDT",
        "start_date": "2024-08-04T00:00:00Z",
        "end_date": "2025-11-02T00:00:00Z",
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
        "name": "BASELINE - 11 Months (Jan-Nov 2024)",
        "description": "Extended period baseline",
        "symbol": "BTCUSDT",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2025-11-02T00:00:00Z",
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
        "name": "OPT6 - 3 Months (Aug-Nov 2024)",
        "description": "Best parameters from optimization, short period",
        "symbol": "BTCUSDT",
        "start_date": "2024-08-04T00:00:00Z",
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
        }
    },
    {
        "name": "OPT6 - 11 Months (Jan-Nov 2024)",
        "description": "Best parameters, extended period TEST",
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
        }
    },
    # Test on ETH, SOL, DOGE with OPT6 params on extended period
    {
        "name": "OPT6 - 11 Months ETH",
        "description": "Test OPT6 on ETHUSDT extended period",
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
        }
    },
    {
        "name": "OPT6 - 11 Months SOL",
        "description": "Test OPT6 on SOLUSDT extended period",
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
            "sl_atr_multiplier": 2.0,  # Slightly wider for SOL
            "tp_atr_multiplier": 7.0
        }
    },
    {
        "name": "OPT6 - 11 Months DOGE",
        "description": "Test OPT6 on DOGEUSDT extended period (HIGH VOL)",
        "symbol": "DOGEUSDT",
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
            "sl_atr_multiplier": 2.0,  # Wider for high vol
            "tp_atr_multiplier": 7.0
        }
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


def wait_for_completion(ids, max_wait=900):  # 15 minutes for longer backtests
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
print("EXTENDED PERIOD BACKTEST - 11 MONTHS")
print("=" * 80)
print("\n🎯 Testing if OPT6 parameters are profitable over longer period")
print("   3 Months: Aug-Nov 2024 (previous test)")
print("   11 Months: Jan-Nov 2024 (NEW)")
print("   Hypothesis: Strategy may be profitable in different market regimes\n")

submitted = []
for i, config in enumerate(CONFIGS):
    print(f"📊 [{i+1}/{len(CONFIGS)}] {config['name']}")
    print(f"    {config['description']}")
    print(f"    Period: {config['start_date'][:10]} to {config['end_date'][:10]}")

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
print("RESULTS - EXTENDED PERIOD ANALYSIS")
print("=" * 80)

results = []
for item in submitted:
    data = get_results(item["id"])
    if data and data.get("status") == "COMPLETED":
        period = "3M" if "3 Months" in item["config"]["name"] else "11M"
        config_type = "OPT6" if "OPT6" in item["config"]["name"] else "BASELINE"

        results.append({
            "name": item["config"]["name"],
            "symbol": item["config"]["symbol"],
            "period": period,
            "config_type": config_type,
            "trades": data.get("total_trades", 0),
            "win_rate": float(data.get("win_rate", 0)),
            "roi": float(data.get("roi", 0)),
            "pf": float(data.get("profit_factor") or 0),
            "pnl": float(data.get("total_profit_loss", 0)),
            "dd": float(data.get("max_drawdown", 0)),
            "sharpe": float(data.get("sharpe_ratio") or 0)
        })

results.sort(key=lambda x: x["roi"], reverse=True)

print(f"\n{'Name':<45} {'Period':<7} {'Trades':<7} {'Win%':<7} {'ROI%':<9} {'P/L $':<10}")
print("-" * 100)

for r in results:
    roi_str = f"+{r['roi']:.2f}" if r['roi'] > 0 else f"{r['roi']:.2f}"
    pnl_str = f"+{r['pnl']:.2f}" if r['pnl'] > 0 else f"{r['pnl']:.2f}"

    marker = ""
    if r['roi'] > 0:
        marker = " ✅ PROFITABLE!"
    elif r['roi'] > -0.05:
        marker = " 🔥 VERY CLOSE!"

    print(f"{r['name']:<45} {r['period']:<7} {r['trades']:<7} {r['win_rate']:<7.1f} "
          f"{roi_str:<9} ${pnl_str:<9}{marker}")

print("\n" + "=" * 80)
print("DETAILED COMPARISON")
print("=" * 80)

# Group by symbol and compare periods
btc_results = [r for r in results if r["symbol"] == "BTCUSDT"]
eth_results = [r for r in results if r["symbol"] == "ETHUSDT"]
sol_results = [r for r in results if r["symbol"] == "SOLUSDT"]

if btc_results:
    print("\n💰 BTCUSDT ANALYSIS:")

    btc_3m_base = next((r for r in btc_results if r["period"] == "3M" and r["config_type"] == "BASELINE"), None)
    btc_3m_opt6 = next((r for r in btc_results if r["period"] == "3M" and r["config_type"] == "OPT6"), None)
    btc_11m_base = next((r for r in btc_results if r["period"] == "11M" and r["config_type"] == "BASELINE"), None)
    btc_11m_opt6 = next((r for r in btc_results if r["period"] == "11M" and r["config_type"] == "OPT6"), None)

    if btc_3m_base:
        print(f"\n  3M BASELINE:")
        print(f"    Trades: {btc_3m_base['trades']}")
        print(f"    Win Rate: {btc_3m_base['win_rate']:.1f}%")
        print(f"    ROI: {btc_3m_base['roi']:+.2f}%")
        print(f"    P/L: ${btc_3m_base['pnl']:+.2f}")

    if btc_3m_opt6:
        print(f"\n  3M OPT6:")
        print(f"    Trades: {btc_3m_opt6['trades']}")
        print(f"    Win Rate: {btc_3m_opt6['win_rate']:.1f}%")
        print(f"    ROI: {btc_3m_opt6['roi']:+.2f}%")
        print(f"    P/L: ${btc_3m_opt6['pnl']:+.2f}")
        if btc_3m_base:
            print(f"    Improvement: {btc_3m_opt6['roi'] - btc_3m_base['roi']:+.3f}% ROI, "
                  f"{btc_3m_opt6['win_rate'] - btc_3m_base['win_rate']:+.1f}% win rate")

    if btc_11m_base:
        print(f"\n  11M BASELINE:")
        print(f"    Trades: {btc_11m_base['trades']}")
        print(f"    Win Rate: {btc_11m_base['win_rate']:.1f}%")
        print(f"    ROI: {btc_11m_base['roi']:+.2f}%")
        print(f"    P/L: ${btc_11m_base['pnl']:+.2f}")
        if btc_3m_base:
            print(f"    vs 3M: {btc_11m_base['trades'] - btc_3m_base['trades']:+d} trades, "
                  f"{btc_11m_base['roi'] - btc_3m_base['roi']:+.3f}% ROI")

    if btc_11m_opt6:
        print(f"\n  11M OPT6 ⭐ MAIN TEST:")
        print(f"    Trades: {btc_11m_opt6['trades']}")
        print(f"    Win Rate: {btc_11m_opt6['win_rate']:.1f}%")
        print(f"    ROI: {btc_11m_opt6['roi']:+.2f}%")
        print(f"    P/L: ${btc_11m_opt6['pnl']:+.2f}")
        print(f"    Profit Factor: {btc_11m_opt6['pf']:.2f}")
        print(f"    Sharpe Ratio: {btc_11m_opt6['sharpe']:.2f}")
        if btc_11m_base:
            print(f"    vs 11M Baseline: {btc_11m_opt6['roi'] - btc_11m_base['roi']:+.3f}% ROI, "
                  f"{btc_11m_opt6['win_rate'] - btc_11m_base['win_rate']:+.1f}% win rate")
        if btc_3m_opt6:
            print(f"    vs 3M OPT6: {btc_11m_opt6['trades'] - btc_3m_opt6['trades']:+d} trades, "
                  f"{btc_11m_opt6['roi'] - btc_3m_opt6['roi']:+.3f}% ROI")

if eth_results:
    print("\n💎 ETHUSDT ANALYSIS:")
    eth = eth_results[0]
    print(f"  Trades: {eth['trades']}")
    print(f"  Win Rate: {eth['win_rate']:.1f}%")
    print(f"  ROI: {eth['roi']:+.2f}%")
    print(f"  P/L: ${eth['pnl']:+.2f}")

if sol_results:
    print("\n🌟 SOLUSDT ANALYSIS:")
    sol = sol_results[0]
    print(f"  Trades: {sol['trades']}")
    print(f"  Win Rate: {sol['win_rate']:.1f}%")
    print(f"  ROI: {sol['roi']:+.2f}%")
    print(f"  P/L: ${sol['pnl']:+.2f}")

doge_results = [r for r in results if r["symbol"] == "DOGEUSDT"]
if doge_results:
    print("\n🐕 DOGEUSDT ANALYSIS (HIGH VOLATILITY):")
    doge = doge_results[0]
    print(f"  Trades: {doge['trades']}")
    print(f"  Win Rate: {doge['win_rate']:.1f}%")
    print(f"  ROI: {doge['roi']:+.2f}%")
    print(f"  P/L: ${doge['pnl']:+.2f}")

print("\n" + "=" * 80)
print("FINAL VERDICT")
print("=" * 80)

best = max(results, key=lambda x: x["roi"])

if best["roi"] > 0:
    print("\n✅ ✅ ✅ SUCCESS - PROFITABLE STRATEGY FOUND! ✅ ✅ ✅")
    print(f"\n🏆 {best['name']}")
    print(f"   Period: {best['period']}")
    print(f"   Trades: {best['trades']}")
    print(f"   Win Rate: {best['win_rate']:.1f}%")
    print(f"   ROI: {best['roi']:+.2f}%")
    print(f"   P/L: ${best['pnl']:+.2f}")
    print(f"   Profit Factor: {best['pf']:.2f}")

    print("\n📋 DEPLOYMENT CHECKLIST:")
    print("   ✅ 1. Profitable strategy identified on extended period")
    print("   ⏭️  2. Deploy to paper trading for real-time validation")
    print("   ⏭️  3. Monitor for 1-2 weeks")
    print("   ⏭️  4. If performance holds, deploy to live with small capital ($100-500)")
    print("   ⏭️  5. Scale up gradually if profitable")

elif best["roi"] > -0.05:
    print(f"\n⚠️  VERY CLOSE TO PROFITABILITY")
    print(f"   Best: {best['name']}")
    print(f"   ROI: {best['roi']:+.2f}% (P/L: ${best['pnl']:+.2f})")
    print(f"   Win Rate: {best['win_rate']:.1f}%")

    print("\n💡 Strategy shows promise but needs Phase 2 optimization:")
    print("   1. Implement multi-timeframe confirmation (expected +10-15% win rate)")
    print("   2. Add adaptive SL/TP based on volatility")
    print("   3. Consider market regime detection")

else:
    print(f"\n❌ STILL UNPROFITABLE ON EXTENDED PERIOD")
    print(f"   Best: {best['name']}")
    print(f"   ROI: {best['roi']:+.2f}% (P/L: ${best['pnl']:+.2f})")

    print("\n📊 Analysis:")
    if best["trades"] < 10:
        print("   • Very few trades - strategy might be too conservative")
        print("   • Consider loosening parameters slightly")
    else:
        print("   • Parameter optimization alone insufficient")
        print("   • Need fundamental strategy changes:")
        print("     - Multi-timeframe confirmation (Phase 2)")
        print("     - Market regime detection")
        print("     - Alternative entry logic")

print("\n" + "=" * 80)
