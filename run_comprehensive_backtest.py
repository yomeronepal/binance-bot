#!/usr/bin/env python
"""
Comprehensive Backtesting Suite for Volatility-Aware Strategy
Tests across all volatility levels and market conditions
"""
import os
import django
import json
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from scanner.services.backtester import Backtester
from scanner.strategies.signal_engine import SignalConfig
from scanner.services.volatility_classifier import get_volatility_classifier

def create_volatility_aware_config(volatility_level: str) -> SignalConfig:
    """Create config based on volatility level"""

    if volatility_level == 'HIGH':
        return SignalConfig(
            # LONG thresholds
            long_rsi_min=25.0,
            long_rsi_max=35.0,
            long_adx_min=18.0,  # Lower for more signals
            long_volume_multiplier=1.2,

            # SHORT thresholds
            short_rsi_min=65.0,
            short_rsi_max=75.0,
            short_adx_min=18.0,
            short_volume_multiplier=1.2,

            # SL/TP for HIGH volatility
            sl_atr_multiplier=2.0,  # Wider stops
            tp_atr_multiplier=3.5,  # Bigger targets

            # Signal management
            min_confidence=0.70,  # Accept more signals
        )

    elif volatility_level == 'MEDIUM':
        return SignalConfig(
            # LONG thresholds
            long_rsi_min=25.0,
            long_rsi_max=35.0,
            long_adx_min=22.0,  # Standard
            long_volume_multiplier=1.2,

            # SHORT thresholds
            short_rsi_min=65.0,
            short_rsi_max=75.0,
            short_adx_min=22.0,
            short_volume_multiplier=1.2,

            # SL/TP for MEDIUM volatility
            sl_atr_multiplier=1.5,  # Optimal
            tp_atr_multiplier=2.5,  # Good R/R

            # Signal management
            min_confidence=0.75,  # Quality signals
        )

    else:  # LOW
        return SignalConfig(
            # LONG thresholds
            long_rsi_min=25.0,
            long_rsi_max=35.0,
            long_adx_min=20.0,  # Slightly lower
            long_volume_multiplier=1.2,

            # SHORT thresholds
            short_rsi_min=65.0,
            short_rsi_max=75.0,
            short_adx_min=20.0,
            short_volume_multiplier=1.2,

            # SL/TP for LOW volatility
            sl_atr_multiplier=1.0,  # Tighter stops
            tp_atr_multiplier=2.0,  # Closer targets

            # Signal management
            min_confidence=0.70,  # Accept more signals
        )


def run_comprehensive_backtests():
    """Run backtests across all scenarios"""

    print("=" * 100)
    print("COMPREHENSIVE VOLATILITY-AWARE BACKTEST SUITE")
    print("=" * 100)
    print()

    # Define test scenarios
    scenarios = {
        'HIGH': {
            'symbols': ['PEPEUSDT', 'SHIBUSDT', 'DOGEUSDT', 'WIFUSDT', 'FLOKIUSDT'],
            'description': 'High Volatility Meme Coins',
            'expected_win_rate': '40-50%',
            'expected_profit_factor': '1.8-2.5'
        },
        'MEDIUM': {
            'symbols': ['SOLUSDT', 'ADAUSDT', 'MATICUSDT', 'DOTUSDT', 'AVAXUSDT'],
            'description': 'Medium Volatility Established Alts',
            'expected_win_rate': '50-60%',
            'expected_profit_factor': '2.0-3.0'
        },
        'LOW': {
            'symbols': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
            'description': 'Low Volatility Major Coins',
            'expected_win_rate': '55-65%',
            'expected_profit_factor': '2.0-3.0'
        }
    }

    # Time periods to test
    end_date = datetime.now()
    test_periods = [
        {
            'name': 'Last 30 Days',
            'days': 30,
            'start_date': end_date - timedelta(days=30)
        },
        {
            'name': 'Last 60 Days',
            'days': 60,
            'start_date': end_date - timedelta(days=60)
        },
        {
            'name': 'Last 90 Days',
            'days': 90,
            'start_date': end_date - timedelta(days=90)
        }
    ]

    all_results = []

    # Get volatility classifier
    classifier = get_volatility_classifier()

    # Test each volatility level
    for vol_level, scenario in scenarios.items():
        print(f"\n{'=' * 100}")
        print(f"{vol_level} VOLATILITY SCENARIO: {scenario['description']}")
        print(f"Expected Win Rate: {scenario['expected_win_rate']}")
        print(f"Expected Profit Factor: {scenario['expected_profit_factor']}")
        print(f"{'=' * 100}\n")

        # Get config for this volatility level
        config = create_volatility_aware_config(vol_level)

        print(f"Configuration:")
        print(f"  SL ATR Multiplier: {config.sl_atr_multiplier}x")
        print(f"  TP ATR Multiplier: {config.tp_atr_multiplier}x")
        print(f"  ADX Threshold: {config.long_adx_min}")
        print(f"  Min Confidence: {config.min_confidence:.0%}")
        print()

        # Test each symbol in this volatility level
        for symbol in scenario['symbols']:
            print(f"\n{'-' * 80}")
            print(f"Testing {symbol}")
            print(f"{'-' * 80}")

            # Verify classification
            profile = classifier.classify_symbol(symbol)
            print(f"Volatility Classification: {profile.volatility_level} (Confidence: {profile.confidence:.0%})")

            if profile.volatility_level != vol_level:
                print(f"⚠️  Warning: Expected {vol_level} but got {profile.volatility_level}")

            # Test each time period
            for period in test_periods:
                try:
                    print(f"\n  Period: {period['name']} ({period['start_date'].strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})")

                    # Create backtester
                    backtester = Backtester(
                        symbol=symbol,
                        interval='5m',
                        config=config
                    )

                    # Run backtest
                    print(f"  Running backtest...")
                    result = backtester.run(
                        start_date=period['start_date'],
                        end_date=end_date,
                        initial_capital=10000.0
                    )

                    if result:
                        # Display results
                        print(f"  ✅ Backtest Complete:")
                        print(f"     Total Trades: {result.get('total_trades', 0)}")
                        print(f"     Win Rate: {result.get('win_rate', 0):.1f}%")
                        print(f"     Profit Factor: {result.get('profit_factor', 0):.2f}")
                        print(f"     Total Return: {result.get('total_return_pct', 0):.2f}%")
                        print(f"     Max Drawdown: {result.get('max_drawdown_pct', 0):.2f}%")
                        print(f"     Sharpe Ratio: {result.get('sharpe_ratio', 0):.2f}")

                        # Store result
                        all_results.append({
                            'volatility_level': vol_level,
                            'symbol': symbol,
                            'period': period['name'],
                            'days': period['days'],
                            'config': {
                                'sl_multiplier': config.sl_atr_multiplier,
                                'tp_multiplier': config.tp_atr_multiplier,
                                'adx_threshold': config.long_adx_min,
                                'min_confidence': config.min_confidence
                            },
                            'results': result
                        })
                    else:
                        print(f"  ❌ Backtest failed - insufficient data or error")

                except Exception as e:
                    print(f"  ❌ Error: {e}")
                    import traceback
                    traceback.print_exc()

    # Generate summary report
    print("\n" + "=" * 100)
    print("COMPREHENSIVE SUMMARY")
    print("=" * 100)
    print()

    # Group results by volatility level
    for vol_level in ['HIGH', 'MEDIUM', 'LOW']:
        vol_results = [r for r in all_results if r['volatility_level'] == vol_level]

        if not vol_results:
            continue

        print(f"\n{vol_level} Volatility Summary:")
        print("-" * 80)

        # Calculate averages
        total_trades = sum(r['results'].get('total_trades', 0) for r in vol_results)
        avg_win_rate = sum(r['results'].get('win_rate', 0) for r in vol_results) / len(vol_results) if vol_results else 0
        avg_profit_factor = sum(r['results'].get('profit_factor', 0) for r in vol_results) / len(vol_results) if vol_results else 0
        avg_return = sum(r['results'].get('total_return_pct', 0) for r in vol_results) / len(vol_results) if vol_results else 0
        avg_sharpe = sum(r['results'].get('sharpe_ratio', 0) for r in vol_results) / len(vol_results) if vol_results else 0

        print(f"  Total Backtests: {len(vol_results)}")
        print(f"  Total Trades: {total_trades}")
        print(f"  Average Win Rate: {avg_win_rate:.1f}%")
        print(f"  Average Profit Factor: {avg_profit_factor:.2f}")
        print(f"  Average Return: {avg_return:.2f}%")
        print(f"  Average Sharpe Ratio: {avg_sharpe:.2f}")

        # Show best performing symbol
        best_result = max(vol_results, key=lambda r: r['results'].get('profit_factor', 0))
        print(f"\n  Best Performer: {best_result['symbol']} ({best_result['period']})")
        print(f"    Win Rate: {best_result['results'].get('win_rate', 0):.1f}%")
        print(f"    Profit Factor: {best_result['results'].get('profit_factor', 0):.2f}")
        print(f"    Return: {best_result['results'].get('total_return_pct', 0):.2f}%")

    # Overall summary
    print("\n" + "=" * 100)
    print("OVERALL PERFORMANCE")
    print("=" * 100)

    if all_results:
        total_trades = sum(r['results'].get('total_trades', 0) for r in all_results)
        overall_win_rate = sum(r['results'].get('win_rate', 0) for r in all_results) / len(all_results)
        overall_profit_factor = sum(r['results'].get('profit_factor', 0) for r in all_results) / len(all_results)
        overall_return = sum(r['results'].get('total_return_pct', 0) for r in all_results) / len(all_results)

        print(f"Total Backtests Run: {len(all_results)}")
        print(f"Total Trades Executed: {total_trades}")
        print(f"Overall Average Win Rate: {overall_win_rate:.1f}%")
        print(f"Overall Average Profit Factor: {overall_profit_factor:.2f}")
        print(f"Overall Average Return: {overall_return:.2f}%")

    # Save results to file
    output_file = f'backtest_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    print(f"\n✅ Results saved to: {output_file}")
    print("=" * 100)

    return all_results


if __name__ == '__main__':
    try:
        results = run_comprehensive_backtests()
        print("\n✅ All backtests completed successfully!")
    except Exception as e:
        print(f"\n❌ Backtest suite failed: {e}")
        import traceback
        traceback.print_exc()
