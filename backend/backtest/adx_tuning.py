#!/usr/bin/env python3
"""
OPTIMIZED ADX Tuning Backtest Script
With asset-specific optimizations, better risk management, and rate limiting
"""

import requests
import time
import json
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

API_BASE = "http://localhost:8000/api"

# Expanded coin list for scanner approach
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "DOGEUSDT", "SOLUSDT", "ADAUSDT", 
    "DOTUSDT", "LINKUSDT", "MATICUSDT", "AVAXUSDT", "XRPUSDT"
]

TIMEFRAMES = ["4h"]  # Focus on 4H for now

# Rate limiting - 4 minutes between batch starts
BATCH_DELAY_MINUTES = 4
REQUESTS_PER_BATCH = 2  # Conservative to avoid API overload

# ASSET-SPECIFIC FIXED PARAMETERS
def get_asset_params(symbol):
    """Return optimized fixed parameters per asset"""
    base_params = {
        "min_confidence": 0.73,
        "sl_atr_multiplier": 2.5,
        "tp_atr_multiplier": 7.0
    }
    
    # Asset-specific RSI ranges based on your successful DOGE configuration
    asset_configs = {
        "DOGEUSDT": {
            "long_rsi_min": 23.0,
            "long_rsi_max": 33.0, 
            "short_rsi_min": 67.0,
            "short_rsi_max": 77.0
        },
        "BTCUSDT": {
            "long_rsi_min": 25.0,    # Slightly less aggressive for BTC
            "long_rsi_max": 35.0,
            "short_rsi_min": 65.0,   # Slightly less aggressive  
            "short_rsi_max": 75.0
        },
        # Default configuration for other coins
        "default": {
            "long_rsi_min": 24.0,
            "long_rsi_max": 34.0,
            "short_rsi_min": 66.0,
            "short_rsi_max": 76.0
        }
    }
    
    return {**base_params, **asset_configs.get(symbol, asset_configs["default"])}

# OPTIMIZED ADX GRID - Focus on promising ranges
ADX_GRID = {
    "long_adx_min": [20, 22, 25, 28],
    "short_adx_min": [20, 22, 25, 28]
}

# PRIORITY COMBINATIONS - Test best performers first
PRIORITY_COMBINATIONS = [
    (25, 28),  # DOGE optimal
    (28, 28),  # BTC optimal  
    (25, 25),  # Balanced
    (22, 28),  # More long opportunities
    (28, 25),  # More short opportunities
]

def generate_optimized_combinations():
    """Generate combinations with priority ones first"""
    priority_set = set(PRIORITY_COMBINATIONS)
    
    # Priority combinations first
    for long_adx, short_adx in PRIORITY_COMBINATIONS:
        yield {"long_adx_min": long_adx, "short_adx_min": short_adx}
    
    # Then the rest
    all_combos = list(itertools.product(ADX_GRID["long_adx_min"], ADX_GRID["short_adx_min"]))
    for long_adx, short_adx in all_combos:
        if (long_adx, short_adx) not in priority_set:
            yield {"long_adx_min": long_adx, "short_adx_min": short_adx}

def submit_backtest(symbol, timeframe, name, params):
    """Submit backtest with enhanced error handling"""
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
    
    print(f"🔍 Testing {symbol} | ADX({params['long_adx_min']}/{params['short_adx_min']}) | RSI({params['long_rsi_min']}-{params['long_rsi_max']}/{params['short_rsi_min']}-{params['short_rsi_max']})")
    
    try:
        response = requests.post(f"{API_BASE}/backtest/", json=payload, timeout=30)
        response.raise_for_status()
        backtest_id = response.json().get("id")
        print(f"   ✅ Submitted - ID: {backtest_id}")
        return backtest_id
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Failed to submit: {e}")
        return None

def wait_for_completion(backtest_id, max_wait=300):
    """Wait for backtest completion with progress tracking"""
    start_time = time.time()
    dots = 0
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{API_BASE}/backtest/{backtest_id}/", timeout=10)
            response.raise_for_status()
            data = response.json()
            status = data.get("status", "").upper()
            
            if status == "COMPLETED":
                elapsed = time.time() - start_time
                print(f"   ✅ Completed in {elapsed:.1f}s")
                return data
            elif status == "FAILED":
                error_msg = data.get('error_message', 'Unknown error')
                print(f"   ❌ Failed: {error_msg}")
                return None
            else:
                dots = (dots + 1) % 4
                print(f"   ⏳ Waiting{'.' * dots}   ", end='\r')
                time.sleep(5)
                
        except Exception as e:
            print(f"   ⚠️  Check error: {e}")
            time.sleep(5)
    
    print(f"   ⏰ Timeout after {max_wait}s")
    return None

def evaluate_result_quality(result):
    """Evaluate if result meets minimum quality standards"""
    if not result:
        return False, "No result data"
    
    trades = result.get('total_trades', 0)
    win_rate = float(result.get('win_rate', 0))
    roi = float(result.get('roi', 0))
    profit_factor = float(result.get('profit_factor', 0))
    
    # Quality filters
    if trades < 15:
        return False, f"Too few trades: {trades}"
    if win_rate < 25:
        return False, f"Win rate too low: {win_rate:.1f}%"
    if profit_factor < 1.0:
        return False, f"Negative expectancy: PF={profit_factor:.2f}"
    
    return True, "Pass"

def process_single_test(symbol, timeframe, adx_params, test_num, total_tests):
    """Process a single backtest configuration"""
    print(f"\n[{test_num}/{total_tests}] Processing {symbol} {timeframe}")
    
    # Get asset-specific parameters
    fixed_params = get_asset_params(symbol)
    params = {**fixed_params, **adx_params}
    
    config_name = f"ADXTune_{symbol}_{timeframe}_L{adx_params['long_adx_min']}S{adx_params['short_adx_min']}"
    
    backtest_id = submit_backtest(symbol, timeframe, config_name, params)
    if not backtest_id:
        return None
    
    result = wait_for_completion(backtest_id)
    if not result:
        return None
    
    # Evaluate result quality
    is_quality, quality_msg = evaluate_result_quality(result)
    
    result_data = {
        "symbol": symbol,
        "timeframe": timeframe,
        "name": config_name,
        **params,
        "trades": result.get("total_trades", 0),
        "win_rate": float(result.get("win_rate", 0)),
        "roi": float(result.get("roi", 0)),
        "pnl": float(result.get("total_profit_loss", 0)),
        "sharpe": result.get("sharpe_ratio"),
        "profit_factor": result.get("profit_factor"),
        "max_drawdown": float(result.get("max_drawdown", 0)),
        "quality_check": is_quality,
        "quality_message": quality_msg
    }
    
    # Display result with quality indicator
    quality_icon = "✅" if is_quality else "⚠️"
    print(f"   {quality_icon} Trades: {result_data['trades']} | Win: {result_data['win_rate']:.1f}% | ROI: {result_data['roi']:.2f}% | PF: {result_data['profit_factor']:.2f}")
    
    if not is_quality:
        print(f"   📝 Quality note: {quality_msg}")
    
    return result_data

def process_batch(test_batch, batch_num, total_batches):
    """Process a batch of tests with rate limiting"""
    print(f"\n{'='*50}")
    print(f"🔄 Processing Batch {batch_num}/{total_batches} ({len(test_batch)} tests)")
    print(f"⏰ Next batch in {BATCH_DELAY_MINUTES} minutes")
    print(f"{'='*50}")
    
    batch_results = []
    
    # Process batch with limited parallelism
    with ThreadPoolExecutor(max_workers=REQUESTS_PER_BATCH) as executor:
        future_to_config = {
            executor.submit(process_single_test, symbol, timeframe, adx_params, i+1, len(test_batch)): 
            (symbol, timeframe, adx_params)
            for i, (symbol, timeframe, adx_params) in enumerate(test_batch)
        }
        
        for future in as_completed(future_to_config):
            result = future.result()
            if result:
                batch_results.append(result)
    
    return batch_results

def main():
    results = []
    
    # Generate all test configurations
    test_configs = []
    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            for adx_params in generate_optimized_combinations():
                test_configs.append((symbol, timeframe, adx_params))
    
    total_tests = len(test_configs)
    
    # Split into batches for rate limiting
    batch_size = REQUESTS_PER_BATCH * 2  # Adjust based on your API capacity
    batches = [test_configs[i:i + batch_size] for i in range(0, len(test_configs), batch_size)]
    total_batches = len(batches)
    
    print(f"🚀 Starting OPTIMIZED ADX tuning: {total_tests} tests across {len(SYMBOLS)} symbols")
    print(f"📊 Organized into {total_batches} batches with {BATCH_DELAY_MINUTES}-minute intervals")
    print(f"🎯 Priority testing: {PRIORITY_COMBINATIONS}")
    print(f"⏰ Estimated completion: {total_batches * BATCH_DELAY_MINUTES} minutes")
    print("=" * 60)
    
    # Process batches with delays
    for batch_num, batch_configs in enumerate(batches, 1):
        batch_start_time = time.time()
        
        # Process current batch
        batch_results = process_batch(batch_configs, batch_num, total_batches)
        results.extend(batch_results)
        
        # Calculate time until next batch
        batch_duration = time.time() - batch_start_time
        wait_time = max(0, (BATCH_DELAY_MINUTES * 60) - batch_duration)
        
        if batch_num < total_batches:  # Don't wait after last batch
            print(f"\n⏳ Waiting {wait_time/60:.1f} minutes until next batch...")
            
            # Progress countdown
            for remaining in range(int(wait_time), 0, -30):  # Update every 30 seconds
                minutes = remaining // 60
                seconds = remaining % 60
                print(f"   Next batch in: {minutes:02d}:{seconds:02d}", end='\r')
                time.sleep(30)
            
            print(f"   ✅ Resuming with batch {batch_num + 1}/{total_batches}")
    
    # Save comprehensive results
    timestamp = int(time.time())
    filename = f"optimized_adx_results_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Generate summary report
    generate_summary_report(results, filename)

def generate_summary_report(results, filename):
    """Generate a comprehensive summary report"""
    if not results:
        print("❌ No results to analyze")
        return
    
    quality_results = [r for r in results if r.get('quality_check', False)]
    
    print(f"\n{'='*60}")
    print("📊 OPTIMIZED ADX TUNING - SUMMARY REPORT")
    print(f"{'='*60}")
    
    print(f"\n📈 Overall Statistics:")
    print(f"   Total tests: {len(results)}")
    print(f"   Quality passes: {len(quality_results)} ({len(quality_results)/len(results)*100:.1f}%)")
    
    # Best performers by symbol
    print(f"\n🏆 TOP PERFORMERS BY SYMBOL:")
    
    for symbol in sorted(set(r['symbol'] for r in results)):
        symbol_results = [r for r in quality_results if r['symbol'] == symbol]
        if not symbol_results:
            print(f"\n   {symbol}: ❌ No quality results")
            continue
            
        best_roi = max(symbol_results, key=lambda x: x["roi"])
        best_pf = max(symbol_results, key=lambda x: float(x["profit_factor"] or 0))
        
        print(f"\n   {symbol}:")
        print(f"     Best ROI: ADX({best_roi['long_adx_min']}/{best_roi['short_adx_min']}) -> {best_roi['roi']:.2f}% ROI, {best_roi['profit_factor']:.2f} PF")
        print(f"     Best PF:  ADX({best_pf['long_adx_min']}/{best_pf['short_adx_min']}) -> {best_pf['profit_factor']:.2f} PF, {best_pf['roi']:.2f}% ROI")
    
    # Portfolio recommendations
    print(f"\n💡 PORTFOLIO RECOMMENDATIONS:")
    
    top_coins = []
    for symbol in set(r['symbol'] for r in quality_results):
        symbol_results = [r for r in quality_results if r['symbol'] == symbol]
        if symbol_results:
            best_roi = max(symbol_results, key=lambda x: x["roi"])
            if best_roi['roi'] > 0.1:  # Minimum 0.1% ROI
                top_coins.append((symbol, best_roi))
    
    # Sort by ROI descending
    top_coins.sort(key=lambda x: x[1]['roi'], reverse=True)
    
    if top_coins:
        for i, (symbol, config) in enumerate(top_coins[:5]):  # Top 5 only
            grade = "A+" if config['roi'] > 0.3 else "A" if config['roi'] > 0.2 else "B"
            print(f"   {i+1}. {symbol}: ADX({config['long_adx_min']}/{config['short_adx_min']}) -> {config['roi']:.2f}% ROI ({grade})")
    else:
        print("   ❌ No coins passed minimum ROI threshold")
    
    print(f"\n💾 Full results saved to: {filename}")

if __name__ == "__main__":
    main()