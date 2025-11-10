#!/usr/bin/env python3
"""
Quick Timeframe Comparison Script
Tests the current strategy parameters on different timeframes to identify the best one.
"""
import requests
import json
import time
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import API_BASE

# Current optimized parameters from November 2, 2025
VOLATILITY_CONFIGS = {
    "HIGH": {
        "min_confidence": 0.7,
        "long_adx_min": 18.0,
        "short_adx_min": 18.0,
        "long_rsi_min": 25.0,
        "long_rsi_max": 35.0,
        "short_rsi_min": 65.0,
        "short_rsi_max": 75.0,
        "sl_atr_multiplier": 2.0,
        "tp_atr_multiplier": 7.0
    },
    "MEDIUM": {
        "min_confidence": 0.75,
        "long_adx_min": 22.0,
        "short_adx_min": 22.0,
        "long_rsi_min": 25.0,
        "long_rsi_max": 35.0,
        "short_rsi_min": 65.0,
        "short_rsi_max": 75.0,
        "sl_atr_multiplier": 1.5,
        "tp_atr_multiplier": 5.25
    },
    "LOW": {
        "min_confidence": 0.7,
        "long_adx_min": 20.0,
        "short_adx_min": 20.0,
        "long_rsi_min": 25.0,
        "long_rsi_max": 35.0,
        "short_rsi_min": 65.0,
        "short_rsi_max": 75.0,
        "sl_atr_multiplier": 1.0,
        "tp_atr_multiplier": 3.5
    }
}

SYMBOLS = {
    "HIGH": ["DOGEUSDT"],
    "MEDIUM": ["SOLUSDT"],
    "LOW": ["BTCUSDT"]
}

# Timeframes to test
TIMEFRAMES = ["5m", "15m", "1h", "4h"]

# Test period (adjust based on available data)
START_DATE = "2024-12-01T05:45:00Z"
END_DATE = "2025-01-01T05:40:00Z"


def submit_backtest(name, symbol, timeframe, volatility):
    """Submit a backtest via API"""
    config = VOLATILITY_CONFIGS[volatility]

    payload = {
        "name": name,
        "symbols": [symbol],
        "timeframe": timeframe,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "strategy_params": config,
        "initial_capital": 10000,
        "position_size": 100
    }

    try:
        response = requests.post(f"{API_BASE}/backtest/", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("id")
    except Exception as e:
        print(f"❌ Error submitting {name}: {e}")
        return None


def get_backtest_status(backtest_id):
    """Get backtest status and results"""
    try:
        response = requests.get(f"{API_BASE}/backtest/{backtest_id}/")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching backtest {backtest_id}: {e}")
        return None


def wait_for_completion(backtest_ids, max_wait=600):
    """Wait for all backtests to complete"""
    print(f"\n⏳ Waiting for {len(backtest_ids)} backtests to complete...")
    start_time = time.time()

    while time.time() - start_time < max_wait:
        all_done = True
        for bid in backtest_ids:
            status_data = get_backtest_status(bid)
            if status_data and status_data.get("status") not in ["COMPLETED", "FAILED"]:
                all_done = False
                break

        if all_done:
            print("✅ All backtests completed!")
            return True

        time.sleep(10)

    print("⚠️  Timeout waiting for backtests")
    return False


def main():
    print("=" * 80)
    print("TIMEFRAME OPTIMIZATION TEST")
    print("=" * 80)
    print(f"\nTesting {len(TIMEFRAMES)} timeframes: {', '.join(TIMEFRAMES)}")
    print(f"Test period: {START_DATE} to {END_DATE}")
    print(f"Symbols: {SYMBOLS}")
    print()

    # Submit backtests for each timeframe
    submitted = []

    for timeframe in TIMEFRAMES:
        print(f"\n📊 Submitting backtests for {timeframe} timeframe...")

        for volatility, symbols in SYMBOLS.items():
            for symbol in symbols:
                name = f"Optimize_{timeframe}_{volatility}_{symbol}"
                print(f"  Submitting: {name}")

                backtest_id = submit_backtest(name, symbol, timeframe, volatility)
                if backtest_id:
                    submitted.append({
                        "id": backtest_id,
                        "name": name,
                        "timeframe": timeframe,
                        "symbol": symbol,
                        "volatility": volatility
                    })
                    print(f"    ✅ Queued (ID: {backtest_id})")
                else:
                    print(f"    ❌ Failed to submit")

        # Small delay between batches
        time.sleep(2)

    print(f"\n✅ Submitted {len(submitted)} backtests")

    # Wait for completion
    backtest_ids = [b["id"] for b in submitted]
    if not wait_for_completion(backtest_ids):
        print("\n⚠️  Some backtests may still be running. Check status manually.")

    # Collect and display results
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)

    results = []
    for backtest in submitted:
        data = get_backtest_status(backtest["id"])
        if data:
            results.append({
                "timeframe": backtest["timeframe"],
                "symbol": backtest["symbol"],
                "volatility": backtest["volatility"],
                "status": data.get("status"),
                "total_trades": data.get("total_trades", 0),
                "win_rate": float(data.get("win_rate", 0)),
                "roi": float(data.get("roi", 0)),
                "profit_factor": float(data.get("profit_factor") or 0),
                "sharpe_ratio": float(data.get("sharpe_ratio") or 0),
                "max_drawdown": float(data.get("max_drawdown", 0))
            })

    # Sort by ROI
    results.sort(key=lambda x: x["roi"], reverse=True)

    # Display results table
    print(f"\n{'Timeframe':<10} {'Symbol':<10} {'Trades':<8} {'Win%':<8} {'ROI%':<8} {'PF':<6} {'Sharpe':<8} {'MaxDD%':<8} {'Status':<12}")
    print("-" * 110)

    for r in results:
        print(f"{r['timeframe']:<10} {r['symbol']:<10} {r['total_trades']:<8} "
              f"{r['win_rate']:<8.2f} {r['roi']:<8.2f} {r['profit_factor']:<6.2f} "
              f"{r['sharpe_ratio']:<8.2f} {r['max_drawdown']:<8.2f} {r['status']:<12}")

    # Find best timeframe
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    # Group by timeframe
    by_timeframe = {}
    for r in results:
        tf = r["timeframe"]
        if tf not in by_timeframe:
            by_timeframe[tf] = []
        by_timeframe[tf].append(r)

    print("\nAverage performance by timeframe:")
    print(f"{'Timeframe':<10} {'Avg Trades':<12} {'Avg Win%':<10} {'Avg ROI%':<10} {'Avg PF':<8}")
    print("-" * 60)

    tf_scores = []
    for tf, tf_results in sorted(by_timeframe.items()):
        avg_trades = sum(r["total_trades"] for r in tf_results) / len(tf_results)
        avg_win_rate = sum(r["win_rate"] for r in tf_results) / len(tf_results)
        avg_roi = sum(r["roi"] for r in tf_results) / len(tf_results)
        avg_pf = sum(r["profit_factor"] for r in tf_results) / len(tf_results)

        print(f"{tf:<10} {avg_trades:<12.1f} {avg_win_rate:<10.2f} {avg_roi:<10.2f} {avg_pf:<8.2f}")

        # Calculate score (win_rate * roi * profit_factor)
        score = avg_win_rate * avg_roi * avg_pf if avg_roi > 0 else -1000
        tf_scores.append((tf, score, avg_roi))

    # Best timeframe
    best_tf = max(tf_scores, key=lambda x: x[1])
    print(f"\n🏆 BEST TIMEFRAME: {best_tf[0]} (Score: {best_tf[1]:.2f}, Avg ROI: {best_tf[2]:.2f}%)")

    print("\n💡 Next Steps:")
    print(f"1. Use {best_tf[0]} timeframe for further optimization")
    print("2. Run parameter optimization on this timeframe")
    print("3. Test with tighter RSI ranges and higher ADX thresholds")


if __name__ == "__main__":
    main()
