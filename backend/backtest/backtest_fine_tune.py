#!/usr/bin/env python3
"""
Fine-Tuning Backtest Script
Grid search over multiple indicator parameters to find optimal settings
"""

import requests
import time
import json
import itertools

API_BASE = "http://localhost:8000/api"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "DOGEUSDT", "ADAUSDT", "SOLUSDT"]
TIMEFRAMES = ["4h", "1d"] #"1h",

# Define parameter grid for fine-tuning
PARAM_GRID = {
    "min_confidence": [0.70, 0.73, 0.75],
    "long_adx_min": [20, 22, 25],
    "short_adx_min": [20, 22, 25],
    "long_rsi_min": [20, 23, 25],
    "long_rsi_max": [30, 33, 35],
    "short_rsi_min": [65, 67, 70],
    "short_rsi_max": [75, 77, 80],
    "sl_atr_multiplier": [2.0, 2.5, 3.0, 3.5],
    "tp_atr_multiplier": [6.0, 7.0, 8.0, 9.0]
}

# Function to generate all parameter combinations
def generate_combinations(grid):
    keys = list(grid.keys())
    values = list(grid.values())
    for combo in itertools.product(*values):
        yield dict(zip(keys, combo))

# Submit backtest to API
def submit_backtest(symbol, timeframe, name, params):
    payload = {
        "name": name,
        "symbols": [symbol],
        "timeframe": timeframe,
        "start_date": "2023-01-01T00:00:00Z",
        "end_date": "2024-12-31T23:59:59Z",
        "strategy_params": params,
        "initial_capital": 10000,
        "position_size": 100
    }
    print(f"\n[SUBMIT] {name} | {symbol} | {timeframe} | SL:{params['sl_atr_multiplier']} TP:{params['tp_atr_multiplier']}")
    try:
        response = requests.post(f"{API_BASE}/backtest/", json=payload, timeout=15)
        response.raise_for_status()
        return response.json().get("id")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] {e}")
        return None

# Wait for backtest completion
def wait_for_completion(backtest_id, max_wait=300):
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{API_BASE}/backtest/{backtest_id}/", timeout=10)
            response.raise_for_status()
            data = response.json()
            status = data.get("status", "").upper()
            if status == "COMPLETED":
                elapsed = time.time() - start_time
                print(f"[OK] Completed in {elapsed:.1f}s")
                return data
            elif status == "FAILED":
                print(f"[FAILED] {data.get('error_message')}")
                return None
            else:
                print(".", end="", flush=True)
                time.sleep(3)
        except:
            time.sleep(3)
    print(f"[TIMEOUT] {max_wait}s exceeded")
    return None

# Display results summary
def display_summary(data):
    if not data:
        return
    name = data.get('name', 'Unknown')
    trades = data.get('total_trades', 0)
    win_rate = float(data.get('win_rate', 0))
    roi = float(data.get('roi', 0))
    pnl = float(data.get('total_profit_loss', 0))
    max_dd = float(data.get('max_drawdown', 0))
    sharpe = data.get('sharpe_ratio', 'N/A')
    pf = data.get('profit_factor', 'N/A')
    print(f"Trades: {trades} | Win Rate: {win_rate:.1f}% | ROI: {roi:.2f}% | P/L: ${pnl:.2f} | Max DD: {max_dd:.1f}% | Sharpe: {sharpe} | PF: {pf}")

def main():
    results = []

    total_tests = len(SYMBOLS) * len(TIMEFRAMES) * len(list(generate_combinations(PARAM_GRID)))
    print(f"Starting fine-tuning backtest: {total_tests} total tests...\n")

    test_count = 0
    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            for params in generate_combinations(PARAM_GRID):
                test_count += 1
                config_name = f"{symbol} {timeframe} FineTune {test_count}"
                backtest_id = submit_backtest(symbol, timeframe, config_name, params)
                if not backtest_id:
                    continue

                result = wait_for_completion(backtest_id)
                if result:
                    display_summary(result)
                    results.append({
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "name": config_name,
                        **params,
                        "trades": result.get("total_trades", 0),
                        "win_rate": float(result.get("win_rate", 0)),
                        "roi": float(result.get("roi", 0)),
                        "pnl": float(result.get("total_profit_loss", 0)),
                        "sharpe": result.get("sharpe_ratio"),
                        "profit_factor": result.get("profit_factor")
                    })

                # Optional: small wait between submissions
                time.sleep(2)

    # Save all results
    filename = f"fine_tune_results_{int(time.time())}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Results saved to {filename}")

    # Find top configs
    if results:
        best_roi = max(results, key=lambda x: x["roi"])
        best_sharpe = max(results, key=lambda x: x["sharpe"] or 0)
        best_win = max(results, key=lambda x: x["win_rate"])

        print("\n=== TOP CONFIGURATIONS ===")
        print(f"Best ROI: {best_roi['name']} | ROI: {best_roi['roi']:.2f}%")
        print(f"Best Sharpe: {best_sharpe['name']} | Sharpe: {best_sharpe['sharpe']}")
        print(f"Best Win Rate: {best_win['name']} | Win Rate: {best_win['win_rate']:.1f}%")

if __name__ == "__main__":
    main()
