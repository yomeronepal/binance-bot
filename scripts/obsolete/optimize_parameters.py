#!/usr/bin/env python3
"""
Parameter Optimization Script
Tests multiple parameter combinations to find optimal strategy settings.
Uses the Django API's built-in optimization endpoint.
"""
import requests
import json
import time

API_BASE = "http://localhost:8000/api"

# Define parameter ranges to test
OPTIMIZATION_CONFIGS = {
    "conservative_tighter": {
        "name": "Conservative Tighter Parameters",
        "description": "Higher ADX, tighter RSI, higher confidence",
        "parameter_ranges": {
            "min_confidence": [0.75, 0.80, 0.85],
            "long_adx_min": [25.0, 28.0, 30.0],
            "short_adx_min": [25.0, 28.0, 30.0],
            "long_rsi_min": [25.0, 28.0],
            "long_rsi_max": [30.0, 32.0],
            "short_rsi_min": [68.0, 70.0],
            "short_rsi_max": [72.0, 75.0],
            "sl_atr_multiplier": [1.5, 2.0],
            "tp_atr_multiplier": [5.25, 7.0]
        }
    },
    "aggressive_selective": {
        "name": "Aggressive but Selective",
        "description": "Very high ADX, very tight RSI, very high confidence",
        "parameter_ranges": {
            "min_confidence": [0.85, 0.90],
            "long_adx_min": [30.0, 35.0, 40.0],
            "short_adx_min": [30.0, 35.0, 40.0],
            "long_rsi_min": [28.0, 30.0],
            "long_rsi_max": [30.0, 32.0],
            "short_rsi_min": [68.0, 70.0],
            "short_rsi_max": [70.0, 72.0],
            "sl_atr_multiplier": [2.0, 2.5],
            "tp_atr_multiplier": [7.0, 8.75]
        }
    },
    "balanced_15m": {
        "name": "Balanced for 15-minute",
        "description": "Optimized for 15m timeframe with moderate filtering",
        "parameter_ranges": {
            "min_confidence": [0.75, 0.80],
            "long_adx_min": [25.0, 28.0, 30.0],
            "short_adx_min": [25.0, 28.0, 30.0],
            "long_rsi_min": [25.0, 28.0, 30.0],
            "long_rsi_max": [28.0, 30.0, 32.0],
            "short_rsi_min": [68.0, 70.0, 72.0],
            "short_rsi_max": [70.0, 72.0, 75.0],
            "sl_atr_multiplier": [1.5, 2.0, 2.5],
            "tp_atr_multiplier": [5.25, 7.0, 8.75]
        }
    }
}


def run_optimization(config_name, timeframe="15m", symbols=["BTCUSDT"], max_combinations=50):
    """
    Run parameter optimization using the API

    Args:
        config_name: Name of optimization config to use
        timeframe: Timeframe to test on
        symbols: List of symbols to test
        max_combinations: Maximum parameter combinations to test
    """
    config = OPTIMIZATION_CONFIGS[config_name]

    print("=" * 80)
    print(f"OPTIMIZATION: {config['name']}")
    print("=" * 80)
    print(f"Description: {config['description']}")
    print(f"Timeframe: {timeframe}")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Max Combinations: {max_combinations}")
    print()

    # Count total combinations
    total_combos = 1
    for param, values in config["parameter_ranges"].items():
        total_combos *= len(values)
        print(f"  {param}: {values} ({len(values)} values)")

    print(f"\nTotal possible combinations: {total_combos}")

    if total_combos > max_combinations:
        print(f"⚠️  Will use random search (limited to {max_combinations} combinations)")
        search_method = "random"
    else:
        print(f"✅ Will use grid search (all {total_combos} combinations)")
        search_method = "grid"

    # Prepare optimization request
    payload = {
        "name": f"{config['name']} - {timeframe}",
        "symbols": symbols,
        "timeframe": timeframe,
        "start_date": "2024-12-01T05:45:00Z",
        "end_date": "2025-01-01T05:40:00Z",
        "parameter_ranges": config["parameter_ranges"],
        "search_method": search_method,
        "max_combinations": max_combinations
    }

    print(f"\n🚀 Submitting optimization job...")

    try:
        response = requests.post(
            f"{API_BASE}/optimization/run/",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()

        print(f"✅ Optimization queued!")
        print(f"   Task ID: {data.get('task_id')}")
        print(f"\n⏳ This will take approximately {(total_combos if search_method == 'grid' else max_combinations) * 2 / 60:.1f} minutes...")
        print(f"   Check results in the admin panel or via API")

        return data

    except requests.exceptions.HTTPError as e:
        print(f"❌ API Error: {e}")
        print(f"   Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def check_optimization_results():
    """Fetch recent optimization results"""
    try:
        response = requests.get(f"{API_BASE}/optimization/results/")
        response.raise_for_status()
        results = response.json()

        if not results:
            print("No optimization results found yet.")
            return

        print("\n" + "=" * 80)
        print("TOP OPTIMIZATION RESULTS")
        print("=" * 80)

        print(f"\n{'Name':<40} {'Trades':<8} {'Win%':<8} {'ROI%':<8} {'Score':<8}")
        print("-" * 80)

        for result in results[:10]:  # Top 10
            print(f"{result['name'][:40]:<40} {result['total_trades']:<8} "
                  f"{result['win_rate']:<8.2f} {result['roi']:<8.2f} "
                  f"{result.get('optimization_score', 0):<8.4f}")

            if result == results[0]:  # Best result
                print("\n🏆 BEST PARAMETERS:")
                params = result.get('params', {})
                for key, value in params.items():
                    print(f"   {key}: {value}")
                print()

    except Exception as e:
        print(f"❌ Error fetching results: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run strategy parameter optimization")
    parser.add_argument("--config", choices=list(OPTIMIZATION_CONFIGS.keys()),
                        default="balanced_15m",
                        help="Optimization configuration to use")
    parser.add_argument("--timeframe", default="15m",
                        help="Timeframe to optimize for (default: 15m)")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT"],
                        help="Symbols to test (default: BTCUSDT)")
    parser.add_argument("--max-combos", type=int, default=50,
                        help="Maximum combinations for random search (default: 50)")
    parser.add_argument("--results-only", action="store_true",
                        help="Only show results, don't run optimization")

    args = parser.parse_args()

    if args.results_only:
        check_optimization_results()
        return

    # Run optimization
    result = run_optimization(
        args.config,
        timeframe=args.timeframe,
        symbols=args.symbols,
        max_combinations=args.max_combos
    )

    if result:
        print("\n✅ Optimization submitted successfully!")
        print("\n💡 To check results later, run:")
        print(f"   python optimize_parameters.py --results-only")


if __name__ == "__main__":
    main()
