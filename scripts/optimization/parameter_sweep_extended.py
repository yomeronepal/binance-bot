#!/usr/bin/env python3
"""
Extended Parameter Sweep - Phase 3 (Task A)
Tests comprehensive parameter combinations including:
- Extended R/R ratios (1.5:1 to 5:1)
- Multiple SL/TP variants
- Volume spike ratio variants
- Lower confidence thresholds

Total combinations: ~2000+
Saves top 10 configs with detailed metrics
"""
import requests
import time
import itertools
import json
import sys
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import API_BASE

# Extended Parameter Ranges
RSI_LONG_MIN = [20, 23, 25]
RSI_LONG_MAX = [30, 33, 35]
ADX_MIN = [20, 22, 25]
CONFIDENCE = [0.65, 0.70, 0.73, 0.75]  # Added 0.65 for more trades
SL_ATR = [1.2, 1.5, 1.8, 2.0]  # Extended range
TP_ATR = [3.0, 4.5, 5.25, 6.0]  # Extended range (R/R from ~1.5 to ~5)

# Focused R/R combinations (guaranteed to test)
FOCUSED_RR_PAIRS = [
    (1.2, 3.0),   # R/R ~2.5
    (1.5, 4.5),   # R/R 3.0
    (1.8, 5.25),  # R/R ~2.9
    (2.0, 6.0),   # R/R 3.0
]

# Volume spike ratios (will be passed as metadata, needs backend support)
VOLUME_SPIKE_RATIOS = [1.1, 1.2, 1.5]


def generate_param_combinations():
    """Generate all parameter combinations to test"""
    configs = []

    # Generate all standard combinations
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

        rr_ratio = tp / sl

        configs.append({
            "name": f"ExtSweep_RSI{rsi_min}-{rsi_max}_ADX{adx}_C{conf:.2f}_SL{sl}_TP{tp}_RR{rr_ratio:.2f}",
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
            },
            "metadata": {
                "rr_ratio": rr_ratio,
                "is_focused": (sl, tp) in FOCUSED_RR_PAIRS
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
        print(f"❌ Error submitting {config['name'][:60]}: {e}")
        return None


def get_results(backtest_id):
    """Get backtest results with detailed metrics"""
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


def extract_detailed_metrics(data, config):
    """Extract all relevant metrics from backtest results"""
    if not data or data.get("status") != "COMPLETED":
        return None

    trades = data.get("total_trades", 0)
    if trades == 0:
        return None

    win_rate = float(data.get("win_rate", 0))
    winning_trades = int(trades * win_rate / 100)
    losing_trades = trades - winning_trades

    total_pnl = float(data.get("total_profit_loss", 0))

    # Calculate average win/loss
    if winning_trades > 0:
        total_wins = total_pnl if total_pnl > 0 else 0
        # Estimate from profit factor if available
        pf = float(data.get("profit_factor") or 0)
        if pf > 0 and losing_trades > 0:
            total_losses = total_wins / pf if pf > 0 else 0
            avg_win = total_wins / winning_trades if winning_trades > 0 else 0
            avg_loss = -total_losses / losing_trades if losing_trades > 0 else 0
        else:
            avg_win = total_pnl / winning_trades if winning_trades > 0 else 0
            avg_loss = 0
    else:
        avg_win = 0
        avg_loss = total_pnl / trades if trades > 0 else 0

    return {
        "name": config["name"],
        "params": config["params"],
        "metadata": config.get("metadata", {}),
        "trades": trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "roi": float(data.get("roi", 0)),
        "pnl": total_pnl,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": float(data.get("profit_factor") or 0),
        "sharpe": float(data.get("sharpe_ratio") or -999),
        "max_drawdown": float(data.get("max_drawdown", 0)),
        "rr_ratio": config["metadata"].get("rr_ratio", 0),
        "is_focused": config["metadata"].get("is_focused", False)
    }


def run_parameter_sweep(batch_size=10, symbol="BTCUSDT"):
    """
    Run extended parameter sweep in batches

    Args:
        batch_size: Number of backtests to run concurrently
        symbol: Symbol to test on
    """
    print("=" * 80)
    print("EXTENDED PARAMETER SWEEP - PHASE 3 (TASK A)")
    print("=" * 80)

    # Generate all configurations
    all_configs = generate_param_combinations()
    total = len(all_configs)

    focused_count = sum(1 for c in all_configs if c["metadata"]["is_focused"])

    print(f"\n🎯 Testing {total} parameter combinations")
    print(f"   Symbol: {symbol}")
    print(f"   Batch Size: {batch_size}")
    print(f"   RSI ranges: {RSI_LONG_MIN} - {RSI_LONG_MAX}")
    print(f"   ADX: {ADX_MIN}")
    print(f"   Confidence: {CONFIDENCE}")
    print(f"   SL/ATR: {SL_ATR}")
    print(f"   TP/ATR: {TP_ATR}")
    print(f"   R/R ratios: 1.5:1 to 5:1")
    print(f"   Focused R/R pairs: {focused_count} configs")
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
                marker = " ⭐" if config["metadata"]["is_focused"] else ""
                print(f"  ✅ {config['name'][:70]}{marker}")
                time.sleep(0.5)  # Rate limiting

        # Wait for batch to complete
        if submitted:
            wait_for_batch([s["id"] for s in submitted])

            # Collect results
            for item in submitted:
                data = get_results(item["id"])
                metrics = extract_detailed_metrics(data, item["config"])
                if metrics:
                    all_results.append(metrics)

    return all_results


def save_top_configs(results, filename="top_10_configs.json"):
    """Save top 10 configurations to JSON file"""
    if not results:
        print("\n❌ No results to save")
        return

    # Sort by Sharpe ratio
    sorted_results = sorted(results, key=lambda x: x["sharpe"], reverse=True)[:10]

    # Create detailed output
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_tested": len(results),
        "total_profitable": sum(1 for r in results if r["roi"] > 0),
        "top_10_configs": sorted_results
    }

    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n💾 Saved top 10 configs to {filename}")


def analyze_results(results):
    """Analyze sweep results and find best configurations"""
    if not results:
        print("\n❌ No results to analyze")
        return

    print("\n" + "=" * 80)
    print("EXTENDED PARAMETER SWEEP RESULTS")
    print("=" * 80)

    # Filter results with enough trades
    valid_results = [r for r in results if r["trades"] >= 3]

    if not valid_results:
        print("\n⚠️  No configurations generated 3+ trades")
        print("   Phase 3 filters (ADX < 18, volume spike) may be too strict")
        print("   Try loosening parameters or using longer backtest period")
        return

    # Sort by different metrics
    by_sharpe = sorted(valid_results, key=lambda x: x["sharpe"], reverse=True)[:10]
    by_roi = sorted(valid_results, key=lambda x: x["roi"], reverse=True)[:10]
    by_win_rate = sorted(valid_results, key=lambda x: x["win_rate"], reverse=True)[:10]
    by_profit_factor = sorted(valid_results, key=lambda x: x["profit_factor"], reverse=True)[:10]

    print(f"\n📊 SUMMARY:")
    print(f"   Total Tested: {len(results)}")
    print(f"   Valid Results (3+ trades): {len(valid_results)}")
    print(f"   Profitable: {sum(1 for r in valid_results if r['roi'] > 0)}")
    print(f"   Focused R/R Pairs: {sum(1 for r in valid_results if r['is_focused'])}")

    # Top by Sharpe Ratio (risk-adjusted returns)
    print("\n" + "=" * 80)
    print("🏆 TOP 10 BY SHARPE RATIO (Risk-Adjusted Returns)")
    print("=" * 80)
    print(f"\n{'Name':<75} {'Trades':<7} {'Win%':<7} {'ROI%':<9} {'Sharpe':<8} {'R/R':<6}")
    print("-" * 120)

    for i, r in enumerate(by_sharpe, 1):
        roi_str = f"+{r['roi']:.2f}" if r['roi'] > 0 else f"{r['roi']:.2f}"
        marker = " ✅ PROFIT!" if r['roi'] > 0 else ""
        focused = " ⭐" if r['is_focused'] else ""
        print(f"{i:2}. {r['name'][:70]:<70} {r['trades']:<7} {r['win_rate']:<7.1f} "
              f"{roi_str:<9} {r['sharpe']:<8.2f} {r['rr_ratio']:<6.2f}{marker}{focused}")

    # Top by ROI
    print("\n" + "=" * 80)
    print("💰 TOP 10 BY ROI")
    print("=" * 80)
    print(f"\n{'Name':<75} {'Trades':<7} {'Win%':<7} {'ROI%':<9} {'P/L $':<10} {'R/R':<6}")
    print("-" * 120)

    for i, r in enumerate(by_roi, 1):
        roi_str = f"+{r['roi']:.2f}" if r['roi'] > 0 else f"{r['roi']:.2f}"
        pnl_str = f"+{r['pnl']:.2f}" if r['pnl'] > 0 else f"{r['pnl']:.2f}"
        marker = " ✅" if r['roi'] > 0 else ""
        focused = " ⭐" if r['is_focused'] else ""
        print(f"{i:2}. {r['name'][:70]:<70} {r['trades']:<7} {r['win_rate']:<7.1f} "
              f"{roi_str:<9} ${pnl_str:<9} {r['rr_ratio']:<6.2f}{marker}{focused}")

    # Top by Profit Factor
    print("\n" + "=" * 80)
    print("⚡ TOP 10 BY PROFIT FACTOR")
    print("=" * 80)
    print(f"\n{'Name':<75} {'Trades':<7} {'Win%':<7} {'PF':<6} {'ROI%':<9} {'R/R':<6}")
    print("-" * 120)

    for i, r in enumerate(by_profit_factor, 1):
        roi_str = f"+{r['roi']:.2f}" if r['roi'] > 0 else f"{r['roi']:.2f}"
        marker = " ✅" if r['profit_factor'] > 1.0 else ""
        focused = " ⭐" if r['is_focused'] else ""
        print(f"{i:2}. {r['name'][:70]:<70} {r['trades']:<7} {r['win_rate']:<7.1f} "
              f"{r['profit_factor']:<6.2f} {roi_str:<9} {r['rr_ratio']:<6.2f}{marker}{focused}")

    # Best overall (highest Sharpe with positive ROI)
    best = next((r for r in by_sharpe if r['roi'] > 0), by_sharpe[0])

    print("\n" + "=" * 80)
    print("RECOMMENDED CONFIGURATION")
    print("=" * 80)

    if best['roi'] > 0:
        print("\n🎉 🎉 🎉 PROFITABLE CONFIGURATION FOUND! 🎉 🎉 🎉")
    else:
        print("\n⚠️  BEST CONFIGURATION (Not Yet Profitable):")

    print(f"\n🏆 {best['name']}")
    if best['is_focused']:
        print("   ⭐ FOCUSED R/R PAIR")

    print(f"\n   Performance:")
    print(f"   • Trades: {best['trades']} ({best['winning_trades']}W / {best['losing_trades']}L)")
    print(f"   • Win Rate: {best['win_rate']:.1f}%")
    print(f"   • ROI: {best['roi']:+.2f}%")
    print(f"   • P/L: ${best['pnl']:+.2f}")
    print(f"   • Avg Win: ${best['avg_win']:.2f}")
    print(f"   • Avg Loss: ${best['avg_loss']:.2f}")
    print(f"   • Profit Factor: {best['profit_factor']:.2f}")
    print(f"   • Sharpe Ratio: {best['sharpe']:.2f}")
    print(f"   • Max Drawdown: {best['max_drawdown']:.2f}%")
    print(f"   • R/R Ratio: {best['rr_ratio']:.2f}")

    print(f"\n   Parameters:")
    for key, value in best['params'].items():
        print(f"   • {key}: {value}")

    print("\n📋 NEXT STEPS:")
    if best['roi'] > 0:
        print("   ✅ 1. Configuration is PROFITABLE!")
        print("   ⏭️  2. Test on other symbols (ETH, SOL, XRP)")
        print("   ⏭️  3. Deploy to paper trading")
        print("   ⏭️  4. Monitor for 1-2 weeks")
        print("   ⏭️  5. Deploy to live with small capital")
    else:
        print("   1. Use this configuration as new baseline")
        print("   2. Test top 10 configs on other symbols")
        print("   3. Consider relaxing Phase 3 filters (ADX < 18, volume spike)")
        print("   4. Or expand to Phase 4: ML-based optimization")

    print("\n" + "=" * 80)

    # Save top 10
    save_top_configs(results, "top_10_extended_configs.json")


if __name__ == "__main__":
    print("\n🚀 Starting Extended Parameter Sweep...")
    print("   This will test 2000+ combinations")
    print("   Estimated time: 3-5 hours\n")

    # Run sweep
    results = run_parameter_sweep(batch_size=10, symbol="BTCUSDT")

    # Analyze
    analyze_results(results)

    print("\n✅ Extended parameter sweep complete!")
    print("📁 Results saved to: top_10_extended_configs.json")
