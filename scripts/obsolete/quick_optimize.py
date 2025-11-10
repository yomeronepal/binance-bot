#!/usr/bin/env python3
"""
Quick Optimization Script - Immediate Improvements
Tests proven better parameters on 15m timeframe to get quick wins.

Based on analysis, these changes should improve win rate significantly:
- Switch from 5m to 15m (reduce noise)
- Increase ADX from 20-22 to 28-30 (stronger trends only)
- Tighten RSI from 25-35/65-75 to 28-32/68-72 (more selective)
- Increase confidence from 70-75% to 80% (quality over quantity)
"""
import requests
import json
import time
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import API_BASE

# Improved configurations based on best practices
IMPROVED_CONFIGS = [
    {
        "name": "QUICK_WIN_1 - HIGH Vol DOGE (15m, Tighter)",
        "symbol": "DOGEUSDT",
        "timeframe": "15m",
        "params": {
            "min_confidence": 0.80,  # Was 0.70
            "long_adx_min": 28.0,    # Was 18.0
            "short_adx_min": 28.0,   # Was 18.0
            "long_rsi_min": 28.0,    # Was 25.0
            "long_rsi_max": 32.0,    # Was 35.0
            "short_rsi_min": 68.0,   # Was 65.0
            "short_rsi_max": 72.0,   # Was 75.0
            "sl_atr_multiplier": 2.0,
            "tp_atr_multiplier": 7.0
        }
    },
    {
        "name": "QUICK_WIN_2 - MED Vol SOL (15m, Tighter)",
        "symbol": "SOLUSDT",
        "timeframe": "15m",
        "params": {
            "min_confidence": 0.80,  # Was 0.75
            "long_adx_min": 28.0,    # Was 22.0
            "short_adx_min": 28.0,   # Was 22.0
            "long_rsi_min": 28.0,    # Was 25.0
            "long_rsi_max": 32.0,    # Was 35.0
            "short_rsi_min": 68.0,   # Was 65.0
            "short_rsi_max": 72.0,   # Was 75.0
            "sl_atr_multiplier": 2.0,  # Was 1.5
            "tp_atr_multiplier": 7.0   # Was 5.25
        }
    },
    {
        "name": "QUICK_WIN_3 - LOW Vol BTC (15m, Tighter)",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "params": {
            "min_confidence": 0.80,  # Was 0.70
            "long_adx_min": 28.0,    # Was 20.0
            "short_adx_min": 28.0,   # Was 20.0
            "long_rsi_min": 28.0,    # Was 25.0
            "long_rsi_max": 32.0,    # Was 35.0
            "short_rsi_min": 68.0,   # Was 65.0
            "short_rsi_max": 72.0,   # Was 75.0
            "sl_atr_multiplier": 1.5,  # Was 1.0
            "tp_atr_multiplier": 5.25  # Was 3.5
        }
    }
]

# Also test 1-hour for comparison
HOURLY_CONFIGS = [
    {
        "name": "QUICK_WIN_4 - LOW Vol BTC (1h, Moderate)",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "params": {
            "min_confidence": 0.75,
            "long_adx_min": 25.0,
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
        "name": "QUICK_WIN_5 - MED Vol SOL (1h, Moderate)",
        "symbol": "SOLUSDT",
        "timeframe": "1h",
        "params": {
            "min_confidence": 0.75,
            "long_adx_min": 25.0,
            "short_adx_min": 25.0,
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
    """Submit a single backtest"""
    payload = {
        "name": config["name"],
        "symbols": [config["symbol"]],
        "timeframe": config["timeframe"],
        "start_date": "2024-12-01T05:45:00Z",
        "end_date": "2025-01-01T05:40:00Z",
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


def get_backtest_results(backtest_id):
    """Get backtest results"""
    try:
        response = requests.get(f"{API_BASE}/backtest/{backtest_id}/")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def wait_for_completion(backtest_ids, max_wait=600):
    """Wait for all backtests to complete"""
    print(f"\n⏳ Waiting for {len(backtest_ids)} backtests to complete...")
    start_time = time.time()

    while time.time() - start_time < max_wait:
        all_done = True
        completed = 0

        for bid in backtest_ids:
            data = get_backtest_results(bid)
            if data:
                status = data.get("status")
                if status == "COMPLETED":
                    completed += 1
                elif status not in ["FAILED"]:
                    all_done = False

        print(f"  Progress: {completed}/{len(backtest_ids)} completed", end="\r")

        if all_done:
            print(f"\n✅ All backtests completed!")
            return True

        time.sleep(10)

    print("\n⚠️  Timeout - some tests may still be running")
    return False


def main():
    print("=" * 80)
    print("QUICK OPTIMIZATION - IMMEDIATE IMPROVEMENTS")
    print("=" * 80)
    print("\n🎯 Testing improved parameters:")
    print("   • 15m timeframe (less noise than 5m)")
    print("   • ADX ≥ 28 (stronger trends)")
    print("   • RSI 28-32/68-72 (more selective)")
    print("   • Confidence ≥ 80% (quality over quantity)")
    print()

    # Combine all configs
    all_configs = IMPROVED_CONFIGS + HOURLY_CONFIGS

    # Submit all backtests
    print(f"📊 Submitting {len(all_configs)} backtests...\n")
    submitted = []

    for config in all_configs:
        print(f"  {config['name']}")
        print(f"    Symbol: {config['symbol']}, Timeframe: {config['timeframe']}")

        backtest_id = submit_backtest(config)
        if backtest_id:
            print(f"    ✅ Queued (ID: {backtest_id})\n")
            submitted.append({
                "id": backtest_id,
                "config": config
            })
        else:
            print(f"    ❌ Failed\n")

        time.sleep(1)

    if not submitted:
        print("❌ No backtests submitted successfully")
        return

    # Wait for completion
    backtest_ids = [b["id"] for b in submitted]
    wait_for_completion(backtest_ids)

    # Collect results
    print("\n" + "=" * 80)
    print("RESULTS - QUICK OPTIMIZATION")
    print("=" * 80)

    results = []
    for backtest in submitted:
        data = get_backtest_results(backtest["id"])
        if data and data.get("status") == "COMPLETED":
            config = backtest["config"]
            results.append({
                "name": config["name"],
                "symbol": config["symbol"],
                "timeframe": config["timeframe"],
                "total_trades": data.get("total_trades", 0),
                "win_rate": float(data.get("win_rate", 0)),
                "roi": float(data.get("roi", 0)),
                "profit_factor": float(data.get("profit_factor") or 0),
                "sharpe_ratio": float(data.get("sharpe_ratio") or 0),
                "max_drawdown": float(data.get("max_drawdown", 0)),
                "total_pnl": float(data.get("total_profit_loss", 0))
            })

    # Compare with baseline (5m results from earlier)
    BASELINE_5M = {
        "DOGEUSDT": {"win_rate": 8.03, "roi": -0.41, "trades": 137, "pf": 0.38},
        "SOLUSDT": {"win_rate": 9.79, "roi": -0.32, "trades": 143, "pf": 0.34},
        "BTCUSDT": {"win_rate": 8.62, "roi": -0.16, "trades": 116, "pf": 0.28}
    }

    # Sort by ROI
    results.sort(key=lambda x: x["roi"], reverse=True)

    print(f"\n{'Name':<40} {'TF':<5} {'Trades':<8} {'Win%':<8} {'ROI%':<8} {'PF':<6} {'Sharpe':<8}")
    print("-" * 95)

    for r in results:
        print(f"{r['name'][:40]:<40} {r['timeframe']:<5} {r['total_trades']:<8} "
              f"{r['win_rate']:<8.2f} {r['roi']:<8.2f} {r['profit_factor']:<6.2f} "
              f"{r['sharpe_ratio']:<8.2f}")

    # Analysis
    print("\n" + "=" * 80)
    print("COMPARISON WITH BASELINE (5m)")
    print("=" * 80)

    for r in results:
        if r["symbol"] in BASELINE_5M and r["timeframe"] == "15m":
            baseline = BASELINE_5M[r["symbol"]]
            print(f"\n{r['symbol']}:")
            print(f"  Win Rate:      {baseline['win_rate']:.2f}% → {r['win_rate']:.2f}% "
                  f"({r['win_rate'] - baseline['win_rate']:+.2f}%)")
            print(f"  ROI:           {baseline['roi']:.2f}% → {r['roi']:.2f}% "
                  f"({r['roi'] - baseline['roi']:+.2f}%)")
            print(f"  Profit Factor: {baseline['pf']:.2f} → {r['profit_factor']:.2f} "
                  f"({r['profit_factor'] - baseline['pf']:+.2f})")
            print(f"  Trades:        {baseline['trades']} → {r['total_trades']} "
                  f"({r['total_trades'] - baseline['trades']:+d})")

    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    best = max(results, key=lambda x: x["roi"])
    print(f"\n🏆 Best Result: {best['name']}")
    print(f"   Win Rate: {best['win_rate']:.2f}%")
    print(f"   ROI: {best['roi']:.2f}%")
    print(f"   Profit Factor: {best['profit_factor']:.2f}")
    print(f"   Trades: {best['total_trades']}")

    if best["roi"] > 0:
        print("\n✅ POSITIVE ROI ACHIEVED! These parameters are ready to use.")
    elif best["profit_factor"] > 0.8:
        print("\n⚠️  Close to breakeven. Fine-tune these parameters further:")
        print("   • Increase ADX minimum to 30-32")
        print("   • Tighten RSI range to 29-31/69-71")
        print("   • Consider adding volume filter")
    else:
        print("\n❌ Still unprofitable. Consider:")
        print("   • Testing 1h or 4h timeframe")
        print("   • Adding multi-timeframe trend filter")
        print("   • Implementing market regime detection")

    print("\n💡 Next Steps:")
    print("   1. If profitable: Deploy to paper trading")
    print("   2. If break-even: Run full parameter optimization")
    print("   3. If still losing: Redesign strategy approach")


if __name__ == "__main__":
    main()
