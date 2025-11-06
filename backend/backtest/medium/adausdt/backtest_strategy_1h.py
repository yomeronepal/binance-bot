#!/usr/bin/env python3
"""
Test backtest with BREATHING ROOM parameters
Gives trades more room to breathe before hitting stop loss
"""
import requests
import time
import json

API_BASE = "http://localhost:8000/api"


CONFIGS = [
    # {
    #     "name": "ADAUSDT 1h BR1 - Wider SL (2.5x ATR)",
    #     "symbol": "ADAUSDT",
    #     "timeframe": "1h",
    #     "start_date": "2023-01-01T00:00:00Z",
    #     "end_date": "2024-12-31T23:59:59Z",
    #     "params": {
    #         "min_confidence": 0.73,
    #         "long_adx_min": 22.0,
    #         "short_adx_min": 22.0,
    #         "long_rsi_min": 23.0,
    #         "long_rsi_max": 33.0,
    #         "short_rsi_min": 67.0,
    #         "short_rsi_max": 77.0,
    #         "sl_atr_multiplier": 2.5,
    #         "tp_atr_multiplier": 7.0
    #     },
    #     "performance": {
    #         "trades": 153,
    #         "win_rate": 26.14,
    #         "roi": -0.15,
    #         "pnl": -14.57,
    #         "sharpe": -0.017,
    #         "profit_factor": 0.958
    #     }
    # },
    # {
    #     "name": "ADAUSDT 1h BR2 - Even Wider SL (3.0x ATR)",
    #     "symbol": "ADAUSDT",
    #     "timeframe": "1h",
    #     "start_date": "2023-01-01T00:00:00Z",
    #     "end_date": "2024-12-31T23:59:59Z",
    #     "params": {
    #         "min_confidence": 0.73,
    #         "long_adx_min": 22.0,
    #         "short_adx_min": 22.0,
    #         "long_rsi_min": 23.0,
    #         "long_rsi_max": 33.0,
    #         "short_rsi_min": 67.0,
    #         "short_rsi_max": 77.0,
    #         "sl_atr_multiplier": 3.0,
    #         "tp_atr_multiplier": 8.0
    #     },
    #     "performance": {
    #         "trades": 153,
    #         "win_rate": 30.07,
    #         "roi": 0.43,
    #         "pnl": 42.73,
    #         "sharpe": 0.042,
    #         "profit_factor": 1.108
    #     }
    # },
    # {
    #     "name": "ADAUSDT 1h BR3 - Balanced (2.0x ATR)",
    #     "symbol": "ADAUSDT",
    #     "timeframe": "1h",
    #     "start_date": "2023-01-01T00:00:00Z",
    #     "end_date": "2024-12-31T23:59:59Z",
    #     "params": {
    #         "min_confidence": 0.73,
    #         "long_adx_min": 22.0,
    #         "short_adx_min": 22.0,
    #         "long_rsi_min": 23.0,
    #         "long_rsi_max": 33.0,
    #         "short_rsi_min": 67.0,
    #         "short_rsi_max": 77.0,
    #         "sl_atr_multiplier": 2.0,
    #         "tp_atr_multiplier": 6.0
    #     },
    #     "performance": {
    #         "trades": 153,
    #         "win_rate": 19.61,
    #         "roi": -0.96,
    #         "pnl": -96.01,
    #         "sharpe": -0.149,
    #         "profit_factor": 0.685
    #     }
    # },
    # {
    #     "name": "ADAUSDT 1h BR4 - Conservative (3.5x ATR)",
    #     "symbol": "ADAUSDT",
    #     "timeframe": "1h",
    #     "start_date": "2023-01-01T00:00:00Z",
    #     "end_date": "2024-12-31T23:59:59Z",
    #     "params": {
    #         "min_confidence": 0.70,
    #         "long_adx_min": 22.0,
    #         "short_adx_min": 22.0,
    #         "long_rsi_min": 23.0,
    #         "long_rsi_max": 33.0,
    #         "short_rsi_min": 67.0,
    #         "short_rsi_max": 77.0,
    #         "sl_atr_multiplier": 3.5,
    #         "tp_atr_multiplier": 9.0
    #     },
    #     "performance": {
    #         "trades": 217,
    #         "win_rate": 30.88,
    #         "roi": 0.54,
    #         "pnl": 53.82,
    #         "sharpe": 0.033,
    #         "profit_factor": 1.086
    #     }
    # }

    {
        "name": "ADAUSDT 1h Tuned ATR",
        "symbol": "ADAUSDT",
        "timeframe": "1h",
        "start_date": "2023-01-01T00:00:00Z",
        "end_date": "2024-12-31T23:59:59Z",
        "params": {
            "min_confidence": 0.70,
            "long_adx_min": 22.0,
            "short_adx_min": 22.0,
            "long_rsi_min": 23.0,
            "long_rsi_max": 33.0,
            "short_rsi_min": 67.0,
            "short_rsi_max": 77.0,
            "sl_atr_multiplier": 2.5,
            "tp_atr_multiplier": 6.5
        },
        "performance": {
            "trades": 217,
            "win_rate": 30.88,
            "roi": 0.54,
            "pnl": 53.82,
            "sharpe": 0.033,
            "profit_factor": 1.086
        }
    }
]

def submit_backtest(config):
    """Submit backtest to API"""
    payload = {
        "name": config["name"],
        "symbols": [config["symbol"]],
        "timeframe": config["timeframe"],
        "start_date": config["start_date"],
        "end_date": config["end_date"],
        "strategy_params": config["params"],
        "initial_capital": 10000,
        "position_size": 100
    }

    print(f"\n{'='*70}")
    print(f"Submitting: {config['name']}")
    print(f"SL: {config['params']['sl_atr_multiplier']}x ATR, "
          f"TP: {config['params']['tp_atr_multiplier']}x ATR, "
          f"R/R: 1:{config['params']['tp_atr_multiplier']/config['params']['sl_atr_multiplier']:.1f}")
    print(f"{'='*70}")

    try:
        response = requests.post(f"{API_BASE}/backtest/", json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        backtest_id = data.get("id")
        print(f"[OK] Backtest submitted! ID: {backtest_id}")
        return backtest_id
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error submitting backtest: {e}")
        return None

def wait_for_completion(backtest_id, max_wait=300):
    """Wait for backtest to complete"""
    print("[WAITING] Waiting for completion...", end='', flush=True)
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{API_BASE}/backtest/{backtest_id}/", timeout=10)
            response.raise_for_status()
            data = response.json()
            status = data.get("status", "").upper()

            if status == "COMPLETED":
                elapsed = time.time() - start_time
                print(f"\n[OK] Completed in {elapsed:.1f}s!")
                return data
            elif status == "FAILED":
                print(f"\n[ERROR] Failed: {data.get('error_message')}")
                return None
            else:
                print(".", end='', flush=True)
                time.sleep(3)
        except:
            time.sleep(3)

    print(f"\n[WARNING] Timeout after {max_wait}s")
    return None

def display_summary(data):
    """Display compact results summary"""
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

    print(f"\n{'='*70}")
    print(f"RESULTS: {name}")
    print(f"{'='*70}")
    print(f"Trades: {trades} | Win Rate: {win_rate:.1f}% | ROI: {roi:.2f}%")
    print(f"P/L: ${pnl:.2f} | Max DD: {max_dd:.1f}% | Sharpe: {sharpe}")
    print(f"Profit Factor: {pf}")
    print(f"{'='*70}")

def main():
    """Main execution"""
    print("\n" + "="*70)
    print("BREATHING ROOM BACKTEST - TESTING WIDER STOP LOSSES")
    print("="*70)
    print(f"Testing {len(CONFIGS)} configurations...")
    print("Hypothesis: Wider stops = more breathing room = better win rate")
    print("="*70)

    results = []

    for i, config in enumerate(CONFIGS, 1):
        print(f"\n[{i}/{len(CONFIGS)}] Testing: {config['name']}")

        backtest_id = submit_backtest(config)
        if not backtest_id:
            print("[ERROR] Failed to submit")
            continue

        result = wait_for_completion(backtest_id, max_wait=300)
        if result:
            display_summary(result)
            results.append({
                'name': config['name'],
                'sl_multiplier': config['params']['sl_atr_multiplier'],
                'tp_multiplier': config['params']['tp_atr_multiplier'],
                'trades': result.get('total_trades', 0),
                'win_rate': float(result.get('win_rate', 0)),
                'roi': float(result.get('roi', 0)),
                'pnl': float(result.get('total_profit_loss', 0)),
                'sharpe': result.get('sharpe_ratio'),
                'profit_factor': result.get('profit_factor')
            })

        # Wait between tests
        if i < len(CONFIGS):
            print("\n[WAIT] Waiting 10s before next test...")
            time.sleep(10)

    # Final comparison
    print(f"\n\n{'='*70}")
    print("FINAL COMPARISON - BREATHING ROOM ANALYSIS")
    print(f"{'='*70}")
    print(f"{'Config':<45} {'SL':<6} {'Trades':<8} {'Win%':<8} {'ROI%':<10} {'P/L':<12}")
    print("-" * 70)

    for r in results:
        print(f"{r['name']:<45} {r['sl_multiplier']:<6.1f} {r['trades']:<8} "
              f"{r['win_rate']:<8.1f} {r['roi']:<10.2f} ${r['pnl']:<11.2f}")

    print("="*70)

    # Find best
    if results:
        best_roi = max(results, key=lambda x: x['roi'])
        best_wr = max(results, key=lambda x: x['win_rate'])

        print(f"\nBEST ROI: {best_roi['name']} ({best_roi['roi']:.2f}%)")
        print(f"BEST WIN RATE: {best_wr['name']} ({best_wr['win_rate']:.1f}%)")

    # Save results
    filename = f"breathing_room_results_{int(time.time())}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Results saved to: {filename}")

if __name__ == "__main__":
    main()
