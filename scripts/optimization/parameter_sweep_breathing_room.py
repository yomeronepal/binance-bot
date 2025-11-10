#!/usr/bin/env python3
"""
Breathing Room Parameter Sweep - Phase 3 (Refined)

INSIGHT: Current strategy has tight R/R ratios causing premature stop-outs
- Current best: SL=1.5 ATR, TP=5.25 ATR (R/R 3.5:1)
- Problem: 1.5 ATR SL is too tight, trades hit SL before move develops
- Solution: Test WIDER stop losses (2.0-3.5 ATR) with proportional TPs

Focus Areas:
1. Wider SL (2.0-3.5 ATR) - Give trades room to breathe
2. Realistic TP (5.0-10.0 ATR) - Let winners run
3. Lower confidence (0.60-0.70) - Generate more trades
4. Lower ADX (18-20) - Don't be too picky on trend strength

Expected: With wider SL, win rate should improve (fewer premature exits)
"""
import requests
import time
import itertools
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import API_BASE
import json
from typing import List, Dict
from datetime import datetime

# BREATHING ROOM PARAMETERS
# Focus: Give trades room to breathe, don't choke them with tight stops

RSI_LONG_MIN = [20, 23, 25]      # Keep existing
RSI_LONG_MAX = [30, 33, 35]      # Keep existing
ADX_MIN = [18, 20, 22]           # Added 18 (less strict)
CONFIDENCE = [0.60, 0.65, 0.70]  # Lower thresholds for more trades

# KEY CHANGE: WIDER STOP LOSSES
SL_ATR = [2.0, 2.5, 3.0, 3.5]    # Much wider! (was 1.5, 2.0)

# PROPORTIONAL TAKE PROFITS
# Maintain reasonable R/R ratios with wider stops
TP_ATR = [5.0, 6.0, 7.0, 8.0, 10.0]  # Higher absolute values

# Focused R/R pairs optimized for breathing room
FOCUSED_RR_PAIRS = [
    # Wide SL with proportional TP
    (2.0, 5.0),   # R/R 2.5:1 - Conservative
    (2.0, 6.0),   # R/R 3.0:1 - Balanced
    (2.5, 7.0),   # R/R 2.8:1 - Balanced
    (3.0, 8.0),   # R/R 2.67:1 - Wide breathing room
    (3.0, 10.0),  # R/R 3.33:1 - Let winners run
    (3.5, 10.0),  # R/R 2.86:1 - Maximum breathing room
]


def generate_param_combinations():
    """Generate all parameter combinations optimized for breathing room"""
    configs = []

    for rsi_min, rsi_max, adx, conf, sl, tp in itertools.product(
        RSI_LONG_MIN, RSI_LONG_MAX, ADX_MIN, CONFIDENCE, SL_ATR, TP_ATR
    ):
        # Skip invalid combinations
        if rsi_min >= rsi_max:
            continue
        if sl >= tp:
            continue

        # Skip unrealistic R/R ratios
        rr_ratio = tp / sl
        if rr_ratio < 1.5 or rr_ratio > 5.0:
            continue

        # Calculate SHORT RSI ranges (inverse of LONG)
        rsi_short_min = 100 - rsi_max
        rsi_short_max = 100 - rsi_min

        configs.append({
            "name": f"Breathe_RSI{rsi_min}-{rsi_max}_ADX{adx}_C{conf:.2f}_SL{sl}_TP{tp}_RR{rr_ratio:.2f}",
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
                "is_focused": (sl, tp) in FOCUSED_RR_PAIRS,
                "breathing_room": "wide" if sl >= 3.0 else "medium" if sl >= 2.5 else "standard"
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
        "is_focused": config["metadata"].get("is_focused", False),
        "breathing_room": config["metadata"].get("breathing_room", "standard")
    }


def run_parameter_sweep(batch_size=10, symbol="BTCUSDT"):
    """Run breathing room parameter sweep in batches"""
    print("=" * 80)
    print("BREATHING ROOM PARAMETER SWEEP - PHASE 3")
    print("=" * 80)
    print("\n💡 INSIGHT: Tight stop losses cause premature exits")
    print("   Strategy: Test WIDER stops (2.0-3.5 ATR) with proportional TPs")
    print("   Goal: Give trades room to breathe, improve win rate\n")

    # Generate all configurations
    all_configs = generate_param_combinations()
    total = len(all_configs)

    focused_count = sum(1 for c in all_configs if c["metadata"]["is_focused"])
    wide_count = sum(1 for c in all_configs if c["metadata"]["breathing_room"] == "wide")

    print(f"🎯 Testing {total} parameter combinations")
    print(f"   Symbol: {symbol}")
    print(f"   Batch Size: {batch_size}")
    print(f"   RSI ranges: {RSI_LONG_MIN} - {RSI_LONG_MAX}")
    print(f"   ADX: {ADX_MIN}")
    print(f"   Confidence: {CONFIDENCE} (lower for more trades)")
    print(f"   SL/ATR: {SL_ATR} (WIDER than before!)")
    print(f"   TP/ATR: {TP_ATR}")
    print(f"   Focused pairs: {focused_count} configs ⭐")
    print(f"   Wide breathing room (SL >= 3.0): {wide_count} configs")
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
                marker += f" [{config['metadata']['breathing_room'].upper()}]"
                print(f"  ✅ {config['name'][:65]}{marker}")
                time.sleep(0.5)

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


def save_top_configs(results, filename="top_10_breathing_room_configs.json"):
    """Save top configurations to JSON file"""
    if not results:
        print("\n❌ No results to save")
        return

    # Sort by Sharpe ratio
    sorted_results = sorted(results, key=lambda x: x["sharpe"], reverse=True)[:10]

    output = {
        "timestamp": datetime.now().isoformat(),
        "sweep_type": "breathing_room",
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
    print("BREATHING ROOM PARAMETER SWEEP RESULTS")
    print("=" * 80)

    # Filter results with enough trades
    valid_results = [r for r in results if r["trades"] >= 3]

    if not valid_results:
        print("\n⚠️  No configurations generated 3+ trades")
        print("   Phase 3 filters may be too strict (ADX < 18, volume spike 1.2x)")
        return

    # Sort by different metrics
    by_sharpe = sorted(valid_results, key=lambda x: x["sharpe"], reverse=True)[:10]
    by_roi = sorted(valid_results, key=lambda x: x["roi"], reverse=True)[:10]
    by_win_rate = sorted(valid_results, key=lambda x: x["win_rate"], reverse=True)[:10]

    # Analyze by breathing room
    wide_results = [r for r in valid_results if r["breathing_room"] == "wide"]
    medium_results = [r for r in valid_results if r["breathing_room"] == "medium"]
    standard_results = [r for r in valid_results if r["breathing_room"] == "standard"]

    print(f"\n📊 SUMMARY:")
    print(f"   Total Tested: {len(results)}")
    print(f"   Valid Results (3+ trades): {len(valid_results)}")
    print(f"   Profitable: {sum(1 for r in valid_results if r['roi'] > 0)}")
    print(f"\n   By Stop Loss Width:")
    print(f"   • Wide (SL >= 3.0 ATR): {len(wide_results)} results, "
          f"{sum(1 for r in wide_results if r['roi'] > 0)} profitable")
    print(f"   • Medium (SL 2.5-2.9 ATR): {len(medium_results)} results, "
          f"{sum(1 for r in medium_results if r['roi'] > 0)} profitable")
    print(f"   • Standard (SL 2.0-2.4 ATR): {len(standard_results)} results, "
          f"{sum(1 for r in standard_results if r['roi'] > 0)} profitable")

    # Compare win rates by breathing room
    if wide_results:
        avg_wr_wide = sum(r["win_rate"] for r in wide_results) / len(wide_results)
        print(f"   • Avg Win Rate (Wide): {avg_wr_wide:.1f}%")
    if medium_results:
        avg_wr_medium = sum(r["win_rate"] for r in medium_results) / len(medium_results)
        print(f"   • Avg Win Rate (Medium): {avg_wr_medium:.1f}%")
    if standard_results:
        avg_wr_standard = sum(r["win_rate"] for r in standard_results) / len(standard_results)
        print(f"   • Avg Win Rate (Standard): {avg_wr_standard:.1f}%")

    # Top by Sharpe Ratio
    print("\n" + "=" * 80)
    print("🏆 TOP 10 BY SHARPE RATIO")
    print("=" * 80)
    print(f"\n{'Name':<70} {'Trades':<7} {'Win%':<7} {'ROI%':<9} {'Sharpe':<8} {'SL':<5}")
    print("-" * 120)

    for i, r in enumerate(by_sharpe, 1):
        roi_str = f"+{r['roi']:.2f}" if r['roi'] > 0 else f"{r['roi']:.2f}"
        marker = " ✅ PROFIT!" if r['roi'] > 0 else ""
        focused = " ⭐" if r['is_focused'] else ""
        sl_atr = r['params']['sl_atr_multiplier']
        print(f"{i:2}. {r['name'][:65]:<65} {r['trades']:<7} {r['win_rate']:<7.1f} "
              f"{roi_str:<9} {r['sharpe']:<8.2f} {sl_atr:<5.1f}{marker}{focused}")

    # Top by Win Rate
    print("\n" + "=" * 80)
    print("🎯 TOP 10 BY WIN RATE (Testing Breathing Room Hypothesis)")
    print("=" * 80)
    print(f"\n{'Name':<70} {'Trades':<7} {'Win%':<7} {'SL':<5} {'TP':<5} {'ROI%':<9}")
    print("-" * 120)

    for i, r in enumerate(by_win_rate, 1):
        roi_str = f"+{r['roi']:.2f}" if r['roi'] > 0 else f"{r['roi']:.2f}"
        sl_atr = r['params']['sl_atr_multiplier']
        tp_atr = r['params']['tp_atr_multiplier']
        room = r['breathing_room'].upper()[:1]
        print(f"{i:2}. {r['name'][:65]:<65} {r['trades']:<7} {r['win_rate']:<7.1f} "
              f"{sl_atr:<5.1f} {tp_atr:<5.1f} {roi_str:<9} [{room}]")

    # Best overall
    best = next((r for r in by_sharpe if r['roi'] > 0), by_sharpe[0])

    print("\n" + "=" * 80)
    print("RECOMMENDED CONFIGURATION")
    print("=" * 80)

    if best['roi'] > 0:
        print("\n🎉 🎉 🎉 PROFITABLE CONFIGURATION FOUND! 🎉 🎉 🎉")
        print("   ✅ Breathing room strategy WORKED!")
    else:
        print("\n⚠️  BEST CONFIGURATION (Testing Hypothesis):")

    print(f"\n🏆 {best['name']}")
    print(f"   Stop Loss: {best['params']['sl_atr_multiplier']} ATR [{best['breathing_room'].upper()}]")
    print(f"   Take Profit: {best['params']['tp_atr_multiplier']} ATR")
    print(f"   R/R Ratio: {best['rr_ratio']:.2f}:1")

    print(f"\n   Performance:")
    print(f"   • Trades: {best['trades']} ({best['winning_trades']}W / {best['losing_trades']}L)")
    print(f"   • Win Rate: {best['win_rate']:.1f}%")
    print(f"   • ROI: {best['roi']:+.2f}%")
    print(f"   • P/L: ${best['pnl']:+.2f}")
    print(f"   • Profit Factor: {best['profit_factor']:.2f}")
    print(f"   • Sharpe Ratio: {best['sharpe']:.2f}")
    print(f"   • Max Drawdown: {best['max_drawdown']:.2f}%")

    # Compare to baseline (1.5 ATR SL)
    baseline_sl = 1.5
    current_sl = best['params']['sl_atr_multiplier']
    sl_increase = ((current_sl - baseline_sl) / baseline_sl) * 100

    print(f"\n   💡 Breathing Room Analysis:")
    print(f"   • SL increased by {sl_increase:.0f}% vs baseline ({baseline_sl} → {current_sl} ATR)")
    print(f"   • Win rate: {best['win_rate']:.1f}% (baseline was 16.7%)")

    if best['win_rate'] > 16.7:
        improvement = best['win_rate'] - 16.7
        print(f"   • ✅ Win rate IMPROVED by {improvement:.1f}% with wider stops!")
    else:
        print(f"   • ⚠️  Win rate did not improve (hypothesis needs revision)")

    print("\n📋 NEXT STEPS:")
    if best['roi'] > 0:
        print("   ✅ 1. Breathing room strategy validated!")
        print("   ⏭️  2. Test on other symbols (ETH, SOL)")
        print("   ⏭️  3. Deploy to paper trading")
    else:
        print("   1. Analyze why wider stops didn't improve performance")
        print("   2. Consider relaxing Phase 3 filters (ADX, volume spike)")
        print("   3. Test on extended dataset (2 years)")

    print("\n" + "=" * 80)

    # Save top 10
    save_top_configs(results)


if __name__ == "__main__":
    print("\n🚀 Starting Breathing Room Parameter Sweep...")
    print("   Testing hypothesis: Wider stops = Better win rate")
    print("   Focus: SL 2.0-3.5 ATR (vs previous 1.5-2.0 ATR)\n")

    # Run sweep
    results = run_parameter_sweep(batch_size=10, symbol="BTCUSDT")

    # Analyze
    analyze_results(results)

    print("\n✅ Breathing room parameter sweep complete!")
    print("📁 Results saved to: top_10_breathing_room_configs.json")
