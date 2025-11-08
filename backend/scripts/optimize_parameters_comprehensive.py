#!/usr/bin/env python3
"""
Comprehensive Parameter Optimization Script (Local CSV Version)

Tests multiple parameter combinations to find optimal settings for:
- Win rate improvement (target: 25% → 30%+)
- ROI improvement (target: 0% → +0.5%+)
- Profit factor (target: 1.0 → 1.15+)

Based on current ADX optimization (26/28), tests additional parameters:
- RSI ranges
- Confidence thresholds
- SL/TP ratios

Uses local CSV data from backend/backtest_data/ instead of API calls.

Usage:
    cd backend
    python scripts/optimize_parameters_comprehensive.py

Expected Runtime: ~10-15 minutes
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Dict, List
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from scanner.services.historical_data_fetcher import historical_data_fetcher
from scanner.services.backtest_engine import BacktestEngine
from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig

# Test period (11 months for statistical significance)
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2024, 11, 30)
INITIAL_CAPITAL = Decimal('10000')
POSITION_SIZE = Decimal('100')

# Symbol to test (BTCUSDT has best historical performance)
TEST_SYMBOL = "BTCUSDT"
TIMEFRAME = "4h"

# ============================================================================
# OPTIMIZATION CONFIGURATIONS
# ============================================================================

# Current Configuration (with ADX 26/28)
CURRENT_CONFIG = {
    "name": "CURRENT (ADX 26/28)",
    "params": {
        "long_rsi_min": 23.0,
        "long_rsi_max": 33.0,
        "long_adx_min": 26.0,       # ← Already optimized
        "short_rsi_min": 67.0,
        "short_rsi_max": 77.0,
        "short_adx_min": 28.0,      # ← Already optimized
        "sl_atr_multiplier": 1.5,
        "tp_atr_multiplier": 5.25,
        "min_confidence": 0.73
    }
}

# Optimization Test Configurations
OPTIMIZATION_CONFIGS = [
    # Test 1: Tighter RSI ranges (more selective)
    {
        "name": "OPT-1: Tighter RSI",
        "params": {
            "long_rsi_min": 25.0,    # Narrower range
            "long_rsi_max": 30.0,    # More selective
            "long_adx_min": 26.0,
            "short_rsi_min": 70.0,
            "short_rsi_max": 75.0,
            "short_adx_min": 28.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25,
            "min_confidence": 0.73
        },
        "hypothesis": "Tighter RSI = fewer but better quality entries"
    },

    # Test 2: Wider RSI ranges (more signals)
    {
        "name": "OPT-2: Wider RSI",
        "params": {
            "long_rsi_min": 20.0,    # Wider range
            "long_rsi_max": 35.0,    # More signals
            "long_adx_min": 26.0,
            "short_rsi_min": 65.0,
            "short_rsi_max": 80.0,
            "short_adx_min": 28.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25,
            "min_confidence": 0.73
        },
        "hypothesis": "Wider RSI = more signals but need ADX filter"
    },

    # Test 3: Higher confidence threshold
    {
        "name": "OPT-3: High Confidence",
        "params": {
            "long_rsi_min": 23.0,
            "long_rsi_max": 33.0,
            "long_adx_min": 26.0,
            "short_rsi_min": 67.0,
            "short_rsi_max": 77.0,
            "short_adx_min": 28.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25,
            "min_confidence": 0.76    # Higher quality filter
        },
        "hypothesis": "Higher confidence = fewer but more reliable signals"
    },

    # Test 4: Lower confidence (more signals)
    {
        "name": "OPT-4: Lower Confidence",
        "params": {
            "long_rsi_min": 23.0,
            "long_rsi_max": 33.0,
            "long_adx_min": 26.0,
            "short_rsi_min": 67.0,
            "short_rsi_max": 77.0,
            "short_adx_min": 28.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25,
            "min_confidence": 0.70    # More signals
        },
        "hypothesis": "Lower confidence = more signals, ADX should maintain quality"
    },

    # Test 5: Wider stops for breathing room
    {
        "name": "OPT-5: Wider Stops",
        "params": {
            "long_rsi_min": 23.0,
            "long_rsi_max": 33.0,
            "long_adx_min": 26.0,
            "short_rsi_min": 67.0,
            "short_rsi_max": 77.0,
            "short_adx_min": 28.0,
            "sl_atr_multiplier": 2.0,  # More breathing room
            "tp_atr_multiplier": 6.0,  # Maintain ~1:3 R/R
            "min_confidence": 0.73
        },
        "hypothesis": "Wider stops = fewer premature stop-outs"
    },

    # Test 6: Tighter stops, higher targets
    {
        "name": "OPT-6: Better R/R",
        "params": {
            "long_rsi_min": 23.0,
            "long_rsi_max": 33.0,
            "long_adx_min": 26.0,
            "short_rsi_min": 67.0,
            "short_rsi_max": 77.0,
            "short_adx_min": 28.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 6.0,  # 1:4 R/R (need 20% WR)
            "min_confidence": 0.73
        },
        "hypothesis": "Better R/R = lower breakeven win rate required"
    },

    # Test 7: Combined best (tight RSI + high confidence)
    {
        "name": "OPT-7: Quality Focus",
        "params": {
            "long_rsi_min": 25.0,    # Tighter
            "long_rsi_max": 30.0,    # Tighter
            "long_adx_min": 26.0,
            "short_rsi_min": 70.0,
            "short_rsi_max": 75.0,
            "short_adx_min": 28.0,
            "sl_atr_multiplier": 2.0,  # More breathing room
            "tp_atr_multiplier": 6.0,  # Better R/R
            "min_confidence": 0.76     # Higher quality
        },
        "hypothesis": "Maximum quality: tight RSI + high ADX + high confidence + breathing room"
    },

    # Test 8: Balanced approach
    {
        "name": "OPT-8: Balanced",
        "params": {
            "long_rsi_min": 22.0,
            "long_rsi_max": 32.0,
            "long_adx_min": 26.0,
            "short_rsi_min": 68.0,
            "short_rsi_max": 78.0,
            "short_adx_min": 28.0,
            "sl_atr_multiplier": 1.8,  # Moderate breathing room
            "tp_atr_multiplier": 5.5,  # ~1:3.1 R/R
            "min_confidence": 0.74
        },
        "hypothesis": "Balanced: moderate RSI + good ADX + moderate stops"
    },
]


def dict_to_signal_config(params: Dict) -> SignalConfig:
    """Convert parameter dict to SignalConfig object"""
    return SignalConfig(
        long_rsi_min=params.get('long_rsi_min', 25.0),
        long_rsi_max=params.get('long_rsi_max', 35.0),
        long_adx_min=params.get('long_adx_min', 20.0),
        short_rsi_min=params.get('short_rsi_min', 65.0),
        short_rsi_max=params.get('short_rsi_max', 75.0),
        short_adx_min=params.get('short_adx_min', 20.0),
        sl_atr_multiplier=params.get('sl_atr_multiplier', 1.5),
        tp_atr_multiplier=params.get('tp_atr_multiplier', 5.25),
        min_confidence=params.get('min_confidence', 0.70),
        long_volume_multiplier=params.get('long_volume_multiplier', 1.2),
        short_volume_multiplier=params.get('short_volume_multiplier', 1.2)
    )


async def run_single_backtest(config: Dict, symbol: str, timeframe: str) -> Dict:
    """
    Run backtest for a single configuration using local CSV data.

    Args:
        config: Configuration dict with name, params, hypothesis
        symbol: Trading symbol (e.g., BTCUSDT)
        timeframe: Timeframe (e.g., 4h)

    Returns:
        Dict with backtest results
    """
    print(f"\n{'='*80}")
    print(f"Running: {config['name']}")
    print(f"{'='*80}")

    try:
        # Load historical data from CSV
        print(f"📂 Loading CSV data for {symbol} {timeframe}...")
        symbols_data = await historical_data_fetcher.fetch_multiple_symbols_from_csv(
            symbols=[symbol],
            interval=timeframe,
            start_date=START_DATE,
            end_date=END_DATE,
            data_dir="backtest_data"
        )

        if not symbols_data or symbol not in symbols_data:
            print(f"❌ No data loaded for {symbol}")
            return None

        klines = symbols_data[symbol]
        print(f"✅ Loaded {len(klines)} candles from CSV")

        # Generate signals
        print(f"🔍 Generating signals with {config['name']} parameters...")
        signal_config = dict_to_signal_config(config['params'])

        # IMPORTANT: Disable volatility-aware mode to test custom parameters
        engine = SignalDetectionEngine(signal_config, use_volatility_aware=False)

        signals = []
        for i, candle in enumerate(klines):
            # Add candle to engine
            engine.update_candles(symbol, [candle])

            # Only check for signals after we have enough candles for indicators
            if i < 50:
                continue

            # Check for signal
            result = engine.process_symbol(symbol, timeframe)
            if result and result.get('action') == 'created':
                signal_data = result['signal']

                # Get timestamp from candle
                if isinstance(candle, dict):
                    timestamp = candle.get('timestamp')
                else:
                    timestamp = candle[0]

                signals.append({
                    'symbol': symbol,
                    'timestamp': timestamp,
                    'direction': signal_data['direction'],
                    'entry': signal_data['entry'],
                    'tp': signal_data['tp'],
                    'sl': signal_data['sl'],
                    'confidence': signal_data.get('confidence', 0.7),
                    'indicators': signal_data.get('conditions_met', {})
                })

        print(f"✅ Generated {len(signals)} signals")

        # Run backtest
        print(f"🎯 Running backtest simulation...")
        backtest_engine = BacktestEngine(
            initial_capital=INITIAL_CAPITAL,
            position_size=POSITION_SIZE,
            strategy_params=config['params']
        )

        results = backtest_engine.run_backtest(symbols_data, signals)

        # Add config info to results
        results['config_name'] = config['name']
        results['hypothesis'] = config.get('hypothesis', '')
        results['parameters'] = config['params']

        # Print summary
        print(f"\n📊 Results Summary:")
        print(f"   Total Trades: {results.get('total_trades', 0)}")
        print(f"   Win Rate: {results.get('win_rate', 0):.1f}%")
        print(f"   ROI: {results.get('roi', 0):.2f}%")
        print(f"   Profit Factor: {results.get('profit_factor', 0):.2f}")
        print(f"   Total P&L: ${results.get('total_profit_loss', 0):.2f}")

        return results

    except Exception as e:
        print(f"❌ Error running backtest: {e}")
        import traceback
        traceback.print_exc()
        return None


def calculate_score(results: Dict) -> float:
    """
    Calculate optimization score based on multiple factors.

    Scoring:
    - Win Rate: 40% weight (target: 30%+)
    - ROI: 30% weight (target: 0.5%+)
    - Profit Factor: 20% weight (target: 1.15+)
    - Trade Frequency: 10% weight (target: 6+ trades)
    """
    if not results:
        return 0.0

    win_rate = results.get('win_rate', 0.0)
    roi = results.get('roi', 0.0)
    profit_factor = results.get('profit_factor', 0.0)
    total_trades = results.get('total_trades', 0)

    # Normalize scores (0-100)
    win_rate_score = min(100, (win_rate / 35.0) * 100)  # 35% = perfect
    roi_score = min(100, ((roi + 5.0) / 10.0) * 100)     # +5% = perfect
    pf_score = min(100, (profit_factor / 1.5) * 100)     # 1.5 = perfect
    trade_score = min(100, (total_trades / 10.0) * 100)  # 10 trades = perfect

    # Weighted average
    score = (
        win_rate_score * 0.4 +
        roi_score * 0.3 +
        pf_score * 0.2 +
        trade_score * 0.1
    )

    return round(score, 2)


def format_results_for_display(results: Dict) -> Dict:
    """Format results for display"""
    if not results:
        return {
            "config_name": "FAILED",
            "status": "FAILED",
            "score": 0.0
        }

    return {
        "config_name": results.get('config_name', 'Unknown'),
        "hypothesis": results.get('hypothesis', ''),
        "status": "SUCCESS",
        "score": calculate_score(results),
        "metrics": {
            "roi": results.get('roi', 0.0),
            "win_rate": results.get('win_rate', 0.0),
            "profit_factor": results.get('profit_factor', 0.0),
            "total_trades": results.get('total_trades', 0),
            "winning_trades": results.get('winning_trades', 0),
            "losing_trades": results.get('losing_trades', 0),
            "avg_win": results.get('avg_win', 0.0),
            "avg_loss": results.get('avg_loss', 0.0),
            "max_drawdown": results.get('max_drawdown_percentage', 0.0),
            "sharpe_ratio": results.get('sharpe_ratio', 0.0),
            "total_pnl": float(results.get('total_profit_loss', 0.0)),
            "final_capital": float(INITIAL_CAPITAL) + float(results.get('total_profit_loss', 0.0))
        },
        "parameters": results.get('parameters', {})
    }


def print_results_table(all_results: List[Dict]):
    """Print formatted results table"""
    print("\n" + "=" * 120)
    print("OPTIMIZATION RESULTS SUMMARY")
    print("=" * 120)
    print()

    # Sort by score
    sorted_results = sorted(all_results, key=lambda x: x["score"], reverse=True)

    # Print header
    print(f"{'Rank':<6}{'Configuration':<25}{'Score':<10}{'ROI %':<10}{'Win %':<10}{'PF':<8}{'Trades':<10}{'P&L $':<12}")
    print("-" * 120)

    # Print results
    for i, result in enumerate(sorted_results, 1):
        if result["status"] != "SUCCESS":
            continue

        metrics = result["metrics"]

        # Color coding
        roi_color = "✅" if metrics["roi"] > 0 else "❌"
        wr_color = "✅" if metrics["win_rate"] >= 30 else "⚠️" if metrics["win_rate"] >= 25 else "❌"

        print(f"{i:<6}"
              f"{result['config_name']:<25}"
              f"{result['score']:<10.2f}"
              f"{roi_color} {metrics['roi']:<7.2f}"
              f"{wr_color} {metrics['win_rate']:<7.1f}"
              f"{metrics['profit_factor']:<8.2f}"
              f"{metrics['total_trades']:<10}"
              f"${metrics['total_pnl']:<11.2f}")

    print()
    print("=" * 120)

    # Print winner details
    if sorted_results:
        winner = sorted_results[0]
        print()
        print("🏆 WINNER: " + winner["config_name"])
        print("─" * 80)
        print(f"Score: {winner['score']:.2f}/100")
        print(f"Hypothesis: {winner.get('hypothesis', 'N/A')}")
        print()
        print("Performance Metrics:")
        metrics = winner["metrics"]
        print(f"  ROI: {metrics['roi']:.2f}%")
        print(f"  Win Rate: {metrics['win_rate']:.1f}% ({metrics['winning_trades']}W / {metrics['losing_trades']}L)")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"  Total Trades: {metrics['total_trades']}")
        print(f"  Average Win: ${metrics['avg_win']:.2f}")
        print(f"  Average Loss: ${metrics['avg_loss']:.2f}")
        print(f"  Max Drawdown: {metrics['max_drawdown']:.2f}%")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"  Total P&L: ${metrics['total_pnl']:.2f}")
        print(f"  Final Capital: ${metrics['final_capital']:.2f}")
        print()
        print("Winning Parameters:")
        params = winner["parameters"]
        print(f"  RSI Range (LONG): {params['long_rsi_min']}-{params['long_rsi_max']}")
        print(f"  RSI Range (SHORT): {params['short_rsi_min']}-{params['short_rsi_max']}")
        print(f"  ADX Min (LONG): {params['long_adx_min']}")
        print(f"  ADX Min (SHORT): {params['short_adx_min']}")
        print(f"  SL ATR: {params['sl_atr_multiplier']}x")
        print(f"  TP ATR: {params['tp_atr_multiplier']}x")
        print(f"  R/R Ratio: 1:{params['tp_atr_multiplier'] / params['sl_atr_multiplier']:.1f}")
        print(f"  Min Confidence: {params['min_confidence'] * 100:.0f}%")
        print()


def save_results(all_results: List[Dict], filename: str = "optimization_results.json"):
    """Save results to JSON file"""
    output_path = project_root / filename

    with open(output_path, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "test_period": f"{START_DATE.isoformat()} to {END_DATE.isoformat()}",
            "symbol": TEST_SYMBOL,
            "timeframe": TIMEFRAME,
            "results": all_results
        }, f, indent=2)

    print(f"📁 Results saved to: {output_path}")


async def main():
    """Run comprehensive optimization"""
    print("=" * 80)
    print("🚀 COMPREHENSIVE PARAMETER OPTIMIZATION")
    print("=" * 80)
    print()
    print(f"Test Period: {START_DATE.date()} to {END_DATE.date()}")
    print(f"Symbol: {TEST_SYMBOL}")
    print(f"Timeframe: {TIMEFRAME}")
    print(f"Initial Capital: ${INITIAL_CAPITAL}")
    print(f"Position Size: ${POSITION_SIZE}")
    print(f"Data Source: Local CSV files (backend/backtest_data/)")
    print()

    all_configs = [CURRENT_CONFIG] + OPTIMIZATION_CONFIGS
    print(f"Testing {len(all_configs)} configurations...")
    print(f"Estimated time: ~{len(all_configs) * 1} minutes")
    print()

    all_results = []

    # Run backtests sequentially
    for i, config in enumerate(all_configs, 1):
        print(f"\n[{i}/{len(all_configs)}] Testing: {config['name']}")

        results = await run_single_backtest(config, TEST_SYMBOL, TIMEFRAME)
        formatted = format_results_for_display(results)
        all_results.append(formatted)

        if formatted["status"] == "SUCCESS":
            metrics = formatted["metrics"]
            print(f"✅ Complete: Score={formatted['score']:.1f}, ROI={metrics['roi']:.2f}%, WR={metrics['win_rate']:.1f}%")
        else:
            print(f"❌ Failed")

    # Print results table
    print_results_table(all_results)

    # Save results
    save_results(all_results)

    print()
    print("=" * 80)
    print("✅ OPTIMIZATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())
