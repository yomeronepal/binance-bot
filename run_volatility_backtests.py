#!/usr/bin/env python
"""
Comprehensive Backtesting for Volatility-Aware Strategy
Creates and runs backtests for all volatility levels using Django models
"""
import os
import django
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from signals.models_backtest import BacktestRun
from scanner.tasks.backtest_tasks import run_backtest_async
from django.utils import timezone
import time

def create_backtest_configs():
    """Create backtest configurations for all volatility scenarios"""

    print("=" * 100)
    print("CREATING VOLATILITY-AWARE BACKTEST CONFIGURATIONS")
    print("=" * 100)
    print()

    # Define scenarios
    scenarios = [
        {
            'name': 'HIGH Volatility - 30 Days - PEPE/SHIB/DOGE',
            'symbols': ['PEPEUSDT', 'SHIBUSDT', 'DOGEUSDT'],
            'volatility': 'HIGH',
            'params': {
                'long_rsi_min': 25.0,
                'long_rsi_max': 35.0,
                'short_rsi_min': 65.0,
                'short_rsi_max': 75.0,
                'long_adx_min': 18.0,
                'short_adx_min': 18.0,
                'sl_atr_multiplier': 2.0,
                'tp_atr_multiplier': 3.5,
                'min_confidence': 0.70,
            },
            'days': 30
        },
        {
            'name': 'HIGH Volatility - 60 Days - PEPE/SHIB/DOGE',
            'symbols': ['PEPEUSDT', 'SHIBUSDT', 'DOGEUSDT'],
            'volatility': 'HIGH',
            'params': {
                'long_rsi_min': 25.0,
                'long_rsi_max': 35.0,
                'short_rsi_min': 65.0,
                'short_rsi_max': 75.0,
                'long_adx_min': 18.0,
                'short_adx_min': 18.0,
                'sl_atr_multiplier': 2.0,
                'tp_atr_multiplier': 3.5,
                'min_confidence': 0.70,
            },
            'days': 60
        },
        {
            'name': 'HIGH Volatility - 30 Days - WIF/FLOKI/BONK',
            'symbols': ['WIFUSDT', 'FLOKIUSDT', 'BONKUSDT'],
            'volatility': 'HIGH',
            'params': {
                'long_rsi_min': 25.0,
                'long_rsi_max': 35.0,
                'short_rsi_min': 65.0,
                'short_rsi_max': 75.0,
                'long_adx_min': 18.0,
                'short_adx_min': 18.0,
                'sl_atr_multiplier': 2.0,
                'tp_atr_multiplier': 3.5,
                'min_confidence': 0.70,
            },
            'days': 30
        },
        {
            'name': 'MEDIUM Volatility - 30 Days - SOL/ADA/MATIC',
            'symbols': ['SOLUSDT', 'ADAUSDT', 'MATICUSDT'],
            'volatility': 'MEDIUM',
            'params': {
                'long_rsi_min': 25.0,
                'long_rsi_max': 35.0,
                'short_rsi_min': 65.0,
                'short_rsi_max': 75.0,
                'long_adx_min': 22.0,
                'short_adx_min': 22.0,
                'sl_atr_multiplier': 1.5,
                'tp_atr_multiplier': 2.5,
                'min_confidence': 0.75,
            },
            'days': 30
        },
        {
            'name': 'MEDIUM Volatility - 60 Days - SOL/ADA/MATIC',
            'symbols': ['SOLUSDT', 'ADAUSDT', 'MATICUSDT'],
            'volatility': 'MEDIUM',
            'params': {
                'long_rsi_min': 25.0,
                'long_rsi_max': 35.0,
                'short_rsi_min': 65.0,
                'short_rsi_max': 75.0,
                'long_adx_min': 22.0,
                'short_adx_min': 22.0,
                'sl_atr_multiplier': 1.5,
                'tp_atr_multiplier': 2.5,
                'min_confidence': 0.75,
            },
            'days': 60
        },
        {
            'name': 'MEDIUM Volatility - 30 Days - DOT/AVAX/LINK',
            'symbols': ['DOTUSDT', 'AVAXUSDT', 'LINKUSDT'],
            'volatility': 'MEDIUM',
            'params': {
                'long_rsi_min': 25.0,
                'long_rsi_max': 35.0,
                'short_rsi_min': 65.0,
                'short_rsi_max': 75.0,
                'long_adx_min': 22.0,
                'short_adx_min': 22.0,
                'sl_atr_multiplier': 1.5,
                'tp_atr_multiplier': 2.5,
                'min_confidence': 0.75,
            },
            'days': 30
        },
        {
            'name': 'LOW Volatility - 30 Days - BTC/ETH/BNB',
            'symbols': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
            'volatility': 'LOW',
            'params': {
                'long_rsi_min': 25.0,
                'long_rsi_max': 35.0,
                'short_rsi_min': 65.0,
                'short_rsi_max': 75.0,
                'long_adx_min': 20.0,
                'short_adx_min': 20.0,
                'sl_atr_multiplier': 1.0,
                'tp_atr_multiplier': 2.0,
                'min_confidence': 0.70,
            },
            'days': 30
        },
        {
            'name': 'LOW Volatility - 60 Days - BTC/ETH/BNB',
            'symbols': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
            'volatility': 'LOW',
            'params': {
                'long_rsi_min': 25.0,
                'long_rsi_max': 35.0,
                'short_rsi_min': 65.0,
                'short_rsi_max': 75.0,
                'long_adx_min': 20.0,
                'short_adx_min': 20.0,
                'sl_atr_multiplier': 1.0,
                'tp_atr_multiplier': 2.0,
                'min_confidence': 0.70,
            },
            'days': 60
        },
        {
            'name': 'LOW Volatility - 90 Days - BTC/ETH',
            'symbols': ['BTCUSDT', 'ETHUSDT'],
            'volatility': 'LOW',
            'params': {
                'long_rsi_min': 25.0,
                'long_rsi_max': 35.0,
                'short_rsi_min': 65.0,
                'short_rsi_max': 75.0,
                'long_adx_min': 20.0,
                'short_adx_min': 20.0,
                'sl_atr_multiplier': 1.0,
                'tp_atr_multiplier': 2.0,
                'min_confidence': 0.70,
            },
            'days': 90
        },
    ]

    created_backtests = []
    end_date = timezone.now()

    for scenario in scenarios:
        start_date = end_date - timedelta(days=scenario['days'])

        print(f"Creating backtest: {scenario['name']}")
        print(f"  Volatility: {scenario['volatility']}")
        print(f"  Symbols: {', '.join(scenario['symbols'])}")
        print(f"  Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print(f"  Config: SL={scenario['params']['sl_atr_multiplier']}x, TP={scenario['params']['tp_atr_multiplier']}x, ADX={scenario['params']['long_adx_min']}")

        try:
            backtest = BacktestRun.objects.create(
                name=scenario['name'],
                symbols=scenario['symbols'],
                timeframe='5m',
                start_date=start_date,
                end_date=end_date,
                initial_capital=10000.0,
                position_size=1000.0,
                strategy_params=scenario['params'],
                status='PENDING'
            )

            created_backtests.append({
                'id': backtest.id,
                'name': scenario['name'],
                'volatility': scenario['volatility'],
                'symbols': scenario['symbols']
            })

            print(f"  ✅ Created backtest ID: {backtest.id}")
            print()

        except Exception as e:
            print(f"  ❌ Error creating backtest: {e}")
            print()

    return created_backtests


def run_all_backtests(backtest_configs):
    """Run all created backtests"""

    print("=" * 100)
    print("RUNNING BACKTESTS")
    print("=" * 100)
    print()

    results = []

    for config in backtest_configs:
        print(f"Starting backtest: {config['name']} (ID: {config['id']})")

        try:
            # Queue the backtest task
            task = run_backtest_async.delay(config['id'])

            print(f"  Task queued: {task.id}")
            print(f"  Waiting for completion...")

            # Wait for task to complete (with timeout)
            result = task.get(timeout=600)  # 10 minute timeout

            print(f"  ✅ Completed!")
            print(f"     Total Trades: {result.get('total_trades', 0)}")
            print(f"     Win Rate: {result.get('win_rate', 0):.1f}%")
            print(f"     Profit Factor: {result.get('profit_factor', 0):.2f}")
            print()

            results.append({
                'config': config,
                'result': result
            })

        except Exception as e:
            print(f"  ❌ Error running backtest: {e}")
            print()

    return results


def display_summary(backtest_configs):
    """Display summary of all backtest results"""

    print("=" * 100)
    print("BACKTEST RESULTS SUMMARY")
    print("=" * 100)
    print()

    # Fetch all completed backtests
    backtest_ids = [config['id'] for config in backtest_configs]
    backtests = BacktestRun.objects.filter(id__in=backtest_ids, status='COMPLETED')

    if not backtests.exists():
        print("No completed backtests found.")
        return

    # Group by volatility
    volatility_groups = {}
    for config in backtest_configs:
        vol = config['volatility']
        if vol not in volatility_groups:
            volatility_groups[vol] = []

        # Find matching backtest
        backtest = backtests.filter(id=config['id']).first()
        if backtest:
            volatility_groups[vol].append({
                'config': config,
                'backtest': backtest
            })

    # Display by volatility level
    for vol_level in ['HIGH', 'MEDIUM', 'LOW']:
        if vol_level not in volatility_groups:
            continue

        group = volatility_groups[vol_level]
        print(f"\n{vol_level} Volatility Results:")
        print("-" * 80)

        total_trades = sum(item['backtest'].total_trades or 0 for item in group)
        avg_win_rate = sum(float(item['backtest'].win_rate or 0) for item in group) / len(group) if group else 0
        avg_profit_factor = sum(float(item['backtest'].profit_factor or 0) for item in group) / len(group) if group else 0
        avg_roi = sum(float(item['backtest'].roi or 0) for item in group) / len(group) if group else 0

        print(f"Total Backtests: {len(group)}")
        print(f"Total Trades: {total_trades}")
        print(f"Average Win Rate: {avg_win_rate:.1f}%")
        print(f"Average Profit Factor: {avg_profit_factor:.2f}")
        print(f"Average ROI: {avg_roi:.2f}%")

        # Show individual results
        print(f"\nIndividual Results:")
        for item in group:
            bt = item['backtest']
            print(f"  {item['config']['name']}")
            print(f"    Trades: {bt.total_trades}, Win Rate: {bt.win_rate:.1f}%, "
                  f"Profit Factor: {bt.profit_factor:.2f}, ROI: {bt.roi:.2f}%")

    # Overall summary
    print("\n" + "=" * 100)
    print("OVERALL SUMMARY")
    print("=" * 100)

    all_backtests = list(backtests)
    total_trades = sum(bt.total_trades or 0 for bt in all_backtests)
    overall_win_rate = sum(float(bt.win_rate or 0) for bt in all_backtests) / len(all_backtests) if all_backtests else 0
    overall_profit_factor = sum(float(bt.profit_factor or 0) for bt in all_backtests) / len(all_backtests) if all_backtests else 0
    overall_roi = sum(float(bt.roi or 0) for bt in all_backtests) / len(all_backtests) if all_backtests else 0

    print(f"Total Backtests Completed: {len(all_backtests)}")
    print(f"Total Trades Executed: {total_trades}")
    print(f"Overall Average Win Rate: {overall_win_rate:.1f}%")
    print(f"Overall Average Profit Factor: {overall_profit_factor:.2f}")
    print(f"Overall Average ROI: {overall_roi:.2f}%")

    print("\n✅ View detailed results in the database or admin panel")
    print("=" * 100)


if __name__ == '__main__':
    try:
        print("\n🚀 Starting Comprehensive Volatility-Aware Backtesting Suite\n")

        # Step 1: Create backtest configurations
        backtest_configs = create_backtest_configs()

        if not backtest_configs:
            print("❌ No backtests created. Exiting.")
            exit(1)

        print(f"\n✅ Created {len(backtest_configs)} backtest configurations")
        print("\n" + "=" * 100)
        print("NOTE: Backtests will run asynchronously via Celery")
        print("You can monitor progress in the database or admin panel")
        print("Or wait for them to complete here...")
        print("=" * 100)

        # Ask user if they want to wait for results
        response = input("\nDo you want to wait for all backtests to complete? (y/n): ")

        if response.lower() == 'y':
            # Step 2: Run backtests and wait for results
            run_all_backtests(backtest_configs)

            # Step 3: Display summary
            display_summary(backtest_configs)
        else:
            print("\n✅ Backtests queued! Check status with:")
            print("   docker-compose exec backend python manage.py shell")
            print("   >>> from signals.models_backtest import BacktestRun")
            print("   >>> BacktestRun.objects.filter(status='COMPLETED').count()")

            # Queue all backtests
            for config in backtest_configs:
                task = run_backtest_async.delay(config['id'])
                print(f"Queued: {config['name']} (Task: {task.id})")

            print(f"\n✅ All {len(backtest_configs)} backtests queued successfully!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
