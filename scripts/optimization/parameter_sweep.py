#!/usr/bin/env python3
"""
Automatic Parameter Sweep - Phase 3
Tests multiple parameter combinations to find optimal Sharpe ratio

Sweeps over:
- RSI ranges
- ADX thresholds
- Confidence levels
- SL/TP ratios

Auto-selects best combination based on Sharpe ratio
"""
import requests
import time
import itertools
from typing import List, Dict

API_BASE = "http://localhost:8000/api"

# Parameter ranges to sweep
RSI_LONG_MIN = [20, 23, 25]
RSI_LONG_MAX = [30, 33, 35]
ADX_MIN = [20, 22, 25]
CONFIDENCE = [0.70, 0.73, 0.75]
SL_ATR = [1.5, 2.0]
TP_ATR = [4.5, 5.25, 6.0]

# Generate all combinations
def generate_param_combinations():
    """Generate all parameter combinations to test"""
    configs = []

    for rsi_min, rsi_max, adx, conf, sl, tp in itertools.product(
        RSI_LONG_MIN, RSI_LONG_MAX, ADX_MIN, CONFIDENCE, SL_ATR, TP_ATR
    ):
        # Skip invalid combinations
        if rsi_min >= rsi_max:
            continue
        if sl >= tp:
            continue

        # Calculate SHORT RSI ranges (inverse of LONG)
        rsi_short_min = 100 - rsi_max
        rsi_short_max = 100 - rsi_min

        configs.append({
            "name": f"Sweep_RSI{rsi_min}-{rsi_max}_ADX{adx}_C{conf:.2f}_RR{tp/sl:.1f}",
            "params": {
                "long_rsi_min": rsi_min,
                "long_rsi_max": rsi_max,
                "short_rsi_min": rsi_short_min,
                "short_rsi_max": rsi_short_max,
                "long_adx_min": adx,
                "short_adx_min": adx,
                "min_confidence": conf,
                "sl_atr_multiplier": sl,
                "tp_atr_multiplier": tp
            }
        })

    return configs


def submit_backtest(config, symbol="BTCUSDT"):
    """Submit a single backtest configuration"""
    payload = {
        "name": config["name"],
        "symbols": [symbol],
        "timeframe": "4h",
        "start_date": "2024-01-01T00:00:00Z",
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
        print(f"❌ Error submitting {config['name']}: {e}")
        return None


def get_results(backtest_id):
    """Get backtest results"""
    try:
        response = requests.get(f"{API_BASE}/backtest/{backtest_id}/")
        response.raise_for_status()
        return response.json()
    except:
        return None


def wait_for_batch(ids, max_wait=600):
    """Wait for batch of backtests to complete"""
    start = time.time()

    while time.time() - start < max_wait:
        completed = sum(1 for bid in ids
                       if (d := get_results(bid)) and d.get("status") in ["COMPLETED", "FAILED"])

        print(f"  Progress: {completed}/{len(ids)} completed", end="\r")

        if completed == len(ids):
            print(f"\n  ✅ Batch complete")
            return True

        time.sleep(10)

    return False


def run_parameter_sweep(batch_size=10, symbol="BTCUSDT"):
    """
    Run parameter sweep in batches

    Args:
        batch_size: Number of backtests to run concurrently
        symbol: Symbol to test on
    """
    print("=" * 80)
    print("AUTOMATIC PARAMETER SWEEP - PHASE 3")
    print("=" * 80)

    # Generate all configurations
    all_configs = generate_param_combinations()
    total = len(all_configs)

    print(f"\n🎯 Testing {total} parameter combinations")
    print(f"   Symbol: {symbol}")
    print(f"   Batch Size: {batch_size}")
    print(f"   RSI ranges: {RSI_LONG_MIN} - {RSI_LONG_MAX}")
    print(f"   ADX: {ADX_MIN}")
    print(f"   Confidence: {CONFIDENCE}")
    print(f"   R/R ratios: {[f'{tp}/{sl}' for tp in TP_ATR for sl in SL_ATR]}")
    print()

    # Process in batches
    all_results = []

    for batch_num in range(0, total, batch_size):
        batch_configs = all_configs[batch_num:batch_num + batch_size]
        batch_end = min(batch_num + batch_size, total)

        print(f"\n📊 Batch {batch_num//batch_size + 1}/{(total + batch_size - 1)//batch_size} "
              f"({batch_num + 1}-{batch_end}/{total})")

        # Submit batch
        submitted = []
        for config in batch_configs:
            bid = submit_backtest(config, symbol)
            if bid:
                submitted.append({"id": bid, "config": config})
                print(f"  ✅ {config['name'][:60]}")
                time.sleep(0.5)  # Rate limiting

        # Wait for batch to complete
        if submitted:
            wait_for_batch([s["id"] for s in submitted])

            # Collect results
            for item in submitted:
                data = get_results(item["id"])
                if data and data.get("status") == "COMPLETED":
                    all_results.append({
                        "name": item["config"]["name"],
                        "params": item["config"]["params"],
                        "trades": data.get("total_trades", 0),
                        "win_rate": float(data.get("win_rate", 0)),
                        "roi": float(data.get("roi", 0)),
                        "pf": float(data.get("profit_factor") or 0),
                        "pnl": float(data.get("total_profit_loss", 0)),
                        "sharpe": float(data.get("sharpe_ratio") or -999),
                        "dd": float(data.get("max_drawdown", 0))
                    })

    return all_results


def analyze_results(results):
    """Analyze sweep results and find best configurations"""
    if not results:
        print("\n❌ No results to analyze")
        return

    print("\n" + "=" * 80)
    print("PARAMETER SWEEP RESULTS")
    print("=" * 80)

    # Filter results with enough trades
    valid_results = [r for r in results if r["trades"] >= 3]

    if not valid_results:
        print("\n⚠️  No configurations generated 3+ trades")
        print("   Try loosening parameters or using longer backtest period")
        return

    # Sort by different metrics
    by_sharpe = sorted(valid_results, key=lambda x: x["sharpe"], reverse=True)[:5]
    by_roi = sorted(valid_results, key=lambda x: x["roi"], reverse=True)[:5]
    by_win_rate = sorted(valid_results, key=lambda x: x["win_rate"], reverse=True)[:5]

    print(f"\n📊 SUMMARY:")
    print(f"   Total Tested: {len(results)}")
    print(f"   Valid Results (3+ trades): {len(valid_results)}")
    print(f"   Profitable: {sum(1 for r in valid_results if r['roi'] > 0)}")

    # Top by Sharpe Ratio (risk-adjusted returns)
    print("\n🏆 TOP 5 BY SHARPE RATIO (Risk-Adjusted Returns):")
    print(f"\n{'Name':<60} {'Trades':<7} {'Win%':<7} {'ROI%':<9} {'Sharpe':<8}")
    print("-" * 100)

    for r in by_sharpe:
        roi_str = f"+{r['roi']:.2f}" if r['roi'] > 0 else f"{r['roi']:.2f}"
        marker = " ✅ PROFIT!" if r['roi'] > 0 else ""
        print(f"{r['name']:<60} {r['trades']:<7} {r['win_rate']:<7.1f} "
              f"{roi_str:<9} {r['sharpe']:<8.2f}{marker}")

    # Top by ROI
    print("\n💰 TOP 5 BY ROI:")
    print(f"\n{'Name':<60} {'Trades':<7} {'Win%':<7} {'ROI%':<9} {'P/L $':<10}")
    print("-" * 100)

    for r in by_roi:
        roi_str = f"+{r['roi']:.2f}" if r['roi'] > 0 else f"{r['roi']:.2f}"
        pnl_str = f"+{r['pnl']:.2f}" if r['pnl'] > 0 else f"{r['pnl']:.2f}"
        marker = " ✅" if r['roi'] > 0 else ""
        print(f"{r['name']:<60} {r['trades']:<7} {r['win_rate']:<7.1f} "
              f"{roi_str:<9} ${pnl_str:<9}{marker}")

    # Top by Win Rate
    print("\n🎯 TOP 5 BY WIN RATE:")
    print(f"\n{'Name':<60} {'Trades':<7} {'Win%':<7} {'ROI%':<9}")
    print("-" * 100)

    for r in by_win_rate:
        roi_str = f"+{r['roi']:.2f}" if r['roi'] > 0 else f"{r['roi']:.2f}"
        print(f"{r['name']:<60} {r['trades']:<7} {r['win_rate']:<7.1f} {roi_str:<9}")

    # Best overall (highest Sharpe with positive ROI)
    best = next((r for r in by_sharpe if r['roi'] > 0), by_sharpe[0])

    print("\n" + "=" * 80)
    print("RECOMMENDED CONFIGURATION")
    print("=" * 80)

    if best['roi'] > 0:
        print("\n🎉 PROFITABLE CONFIGURATION FOUND!")
    else:
        print("\n⚠️  BEST CONFIGURATION (Not Yet Profitable):")

    print(f"\n🏆 {best['name']}")
    print(f"\n   Performance:")
    print(f"   • Trades: {best['trades']}")
    print(f"   • Win Rate: {best['win_rate']:.1f}%")
    print(f"   • ROI: {best['roi']:+.2f}%")
    print(f"   • P/L: ${best['pnl']:+.2f}")
    print(f"   • Profit Factor: {best['pf']:.2f}")
    print(f"   • Sharpe Ratio: {best['sharpe']:.2f}")
    print(f"   • Max Drawdown: {best['dd']:.2f}%")

    print(f"\n   Parameters:")
    for key, value in best['params'].items():
        print(f"   • {key}: {value}")

    print("\n📋 NEXT STEPS:")
    if best['roi'] > 0:
        print("   ✅ 1. Configuration is profitable!")
        print("   ⏭️  2. Deploy to paper trading")
        print("   ⏭️  3. Monitor for 1-2 weeks")
        print("   ⏭️  4. Deploy to live with small capital")
    else:
        print("   1. Use this configuration as new baseline")
        print("   2. Test on other symbols (ETH, SOL)")
        print("   3. Consider Phase 3b: Adaptive SL/TP")
        print("   4. Or expand parameter ranges for further sweep")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    # Run sweep
    results = run_parameter_sweep(batch_size=10, symbol="BTCUSDT")

    # Analyze
    analyze_results(results)

    print("\n✅ Parameter sweep complete!")
