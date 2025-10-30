#!/usr/bin/env python
"""
Monitor Backtest Progress and Generate Report
"""
import os
import django
import time
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from signals.models_backtest import BacktestRun

def monitor_backtests(backtest_ids):
    """Monitor backtest progress"""

    print("=" * 100)
    print("MONITORING BACKTEST PROGRESS")
    print("=" * 100)
    print()

    total = len(backtest_ids)
    completed = 0

    while completed < total:
        # Check status
        backtests = BacktestRun.objects.filter(id__in=backtest_ids)

        status_counts = {
            'PENDING': 0,
            'RUNNING': 0,
            'COMPLETED': 0,
            'FAILED': 0
        }

        for bt in backtests:
            status_counts[bt.status] += 1

        completed = status_counts['COMPLETED'] + status_counts['FAILED']

        # Display progress
        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] "
              f"Completed: {completed}/{total} | "
              f"Running: {status_counts['RUNNING']} | "
              f"Pending: {status_counts['PENDING']} | "
              f"Failed: {status_counts['FAILED']}", end='', flush=True)

        if completed < total:
            time.sleep(5)  # Check every 5 seconds
        else:
            print()  # New line after completion
            break

    print("\n✅ All backtests completed!")


def generate_report(backtest_ids):
    """Generate comprehensive report"""

    print("\n" + "=" * 100)
    print("COMPREHENSIVE BACKTEST RESULTS REPORT")
    print("=" * 100)
    print()

    backtests = BacktestRun.objects.filter(id__in=backtest_ids, status='COMPLETED').order_by('name')

    if not backtests.exists():
        print("❌ No completed backtests found")
        return

    # Group by volatility level
    volatility_groups = {
        'HIGH': [],
        'MEDIUM': [],
        'LOW': []
    }

    for bt in backtests:
        if 'HIGH' in bt.name:
            volatility_groups['HIGH'].append(bt)
        elif 'MEDIUM' in bt.name:
            volatility_groups['MEDIUM'].append(bt)
        elif 'LOW' in bt.name:
            volatility_groups['LOW'].append(bt)

    # Display results by volatility level
    all_results = []

    for vol_level in ['HIGH', 'MEDIUM', 'LOW']:
        group = volatility_groups[vol_level]

        if not group:
            continue

        print(f"\n{'=' * 100}")
        print(f"{vol_level} VOLATILITY RESULTS")
        print(f"{'=' * 100}\n")

        # Get config from first backtest
        sample_config = group[0].strategy_params
        print(f"Configuration:")
        print(f"  SL ATR Multiplier: {sample_config.get('sl_atr_multiplier')}x")
        print(f"  TP ATR Multiplier: {sample_config.get('tp_atr_multiplier')}x")
        print(f"  ADX Threshold: {sample_config.get('long_adx_min')}")
        print(f"  Min Confidence: {sample_config.get('min_confidence', 0.7):.0%}")
        print()

        # Calculate averages
        total_trades = sum(bt.total_trades for bt in group)
        avg_win_rate = sum(float(bt.win_rate) for bt in group) / len(group)
        avg_profit_factor = sum(float(bt.profit_factor or 0) for bt in group) / len(group)
        avg_roi = sum(float(bt.roi) for bt in group) / len(group)
        avg_sharpe = sum(float(bt.sharpe_ratio or 0) for bt in group) / len(group)
        avg_drawdown = sum(float(bt.max_drawdown) for bt in group) / len(group)

        print(f"Summary Statistics:")
        print(f"  Number of Backtests: {len(group)}")
        print(f"  Total Trades: {total_trades}")
        print(f"  Average Win Rate: {avg_win_rate:.1f}%")
        print(f"  Average Profit Factor: {avg_profit_factor:.2f}")
        print(f"  Average ROI: {avg_roi:.2f}%")
        print(f"  Average Sharpe Ratio: {avg_sharpe:.2f}")
        print(f"  Average Max Drawdown: {avg_drawdown:.2f}%")
        print()

        # Individual results
        print(f"Individual Backtest Results:")
        print(f"{'-' * 100}")
        print(f"{'Name':<50} {'Trades':>8} {'Win Rate':>10} {'P.Factor':>10} {'ROI':>10} {'Sharpe':>10}")
        print(f"{'-' * 100}")

        for bt in group:
            print(f"{bt.name[:48]:<50} "
                  f"{bt.total_trades:>8} "
                  f"{float(bt.win_rate):>9.1f}% "
                  f"{float(bt.profit_factor or 0):>10.2f} "
                  f"{float(bt.roi):>9.1f}% "
                  f"{float(bt.sharpe_ratio or 0):>10.2f}")

            all_results.append({
                'volatility': vol_level,
                'name': bt.name,
                'trades': bt.total_trades,
                'win_rate': float(bt.win_rate),
                'profit_factor': float(bt.profit_factor or 0),
                'roi': float(bt.roi),
                'sharpe': float(bt.sharpe_ratio or 0),
                'drawdown': float(bt.max_drawdown)
            })

        print()

        # Best performer
        best_pf = max(group, key=lambda x: float(x.profit_factor or 0))
        print(f"🏆 Best Performer (Profit Factor):")
        print(f"  {best_pf.name}")
        print(f"  Win Rate: {float(best_pf.win_rate):.1f}%, "
              f"Profit Factor: {float(best_pf.profit_factor):.2f}, "
              f"ROI: {float(best_pf.roi):.2f}%")
        print()

        best_wr = max(group, key=lambda x: float(x.win_rate))
        print(f"🎯 Best Win Rate:")
        print(f"  {best_wr.name}")
        print(f"  Win Rate: {float(best_wr.win_rate):.1f}%, "
              f"Profit Factor: {float(best_wr.profit_factor or 0):.2f}, "
              f"ROI: {float(best_wr.roi):.2f}%")
        print()

    # Overall summary
    print("=" * 100)
    print("OVERALL SUMMARY - ALL VOLATILITY LEVELS")
    print("=" * 100)
    print()

    all_backtests = list(backtests)
    total_trades = sum(bt.total_trades for bt in all_backtests)
    overall_win_rate = sum(float(bt.win_rate) for bt in all_backtests) / len(all_backtests)
    overall_profit_factor = sum(float(bt.profit_factor or 0) for bt in all_backtests) / len(all_backtests)
    overall_roi = sum(float(bt.roi) for bt in all_backtests) / len(all_backtests)
    overall_sharpe = sum(float(bt.sharpe_ratio or 0) for bt in all_backtests) / len(all_backtests)

    print(f"Total Backtests Completed: {len(all_backtests)}")
    print(f"Total Trades Executed: {total_trades}")
    print(f"Overall Average Win Rate: {overall_win_rate:.1f}%")
    print(f"Overall Average Profit Factor: {overall_profit_factor:.2f}")
    print(f"Overall Average ROI: {overall_roi:.2f}%")
    print(f"Overall Average Sharpe Ratio: {overall_sharpe:.2f}")
    print()

    # Volatility comparison
    print("=" * 100)
    print("VOLATILITY LEVEL COMPARISON")
    print("=" * 100)
    print()

    vol_stats = {}
    for vol_level in ['HIGH', 'MEDIUM', 'LOW']:
        group = volatility_groups[vol_level]
        if group:
            vol_stats[vol_level] = {
                'win_rate': sum(float(bt.win_rate) for bt in group) / len(group),
                'profit_factor': sum(float(bt.profit_factor or 0) for bt in group) / len(group),
                'roi': sum(float(bt.roi) for bt in group) / len(group),
                'sharpe': sum(float(bt.sharpe_ratio or 0) for bt in group) / len(group),
            }

    print(f"{'Volatility':<12} {'Win Rate':>12} {'Profit Factor':>15} {'ROI':>10} {'Sharpe':>10}")
    print(f"{'-' * 100}")
    for vol_level in ['HIGH', 'MEDIUM', 'LOW']:
        if vol_level in vol_stats:
            stats = vol_stats[vol_level]
            print(f"{vol_level:<12} "
                  f"{stats['win_rate']:>11.1f}% "
                  f"{stats['profit_factor']:>15.2f} "
                  f"{stats['roi']:>9.1f}% "
                  f"{stats['sharpe']:>10.2f}")

    print()
    print("=" * 100)
    print("KEY INSIGHTS")
    print("=" * 100)
    print()

    # Find best volatility level
    best_vol = max(vol_stats.items(), key=lambda x: x[1]['profit_factor'])[0]
    print(f"✅ {best_vol} volatility showed the best overall profit factor")

    # Check if expectations met
    expectations = {
        'HIGH': {'win_rate': 45, 'profit_factor': 2.0},
        'MEDIUM': {'win_rate': 52.5, 'profit_factor': 2.5},
        'LOW': {'win_rate': 60, 'profit_factor': 2.5}
    }

    print()
    print("Expectations vs Reality:")
    for vol_level in ['HIGH', 'MEDIUM', 'LOW']:
        if vol_level in vol_stats:
            stats = vol_stats[vol_level]
            exp = expectations[vol_level]

            wr_status = "✅" if stats['win_rate'] >= exp['win_rate'] else "❌"
            pf_status = "✅" if stats['profit_factor'] >= exp['profit_factor'] else "❌"

            print(f"  {vol_level}:")
            print(f"    {wr_status} Win Rate: Expected {exp['win_rate']:.0f}%, Got {stats['win_rate']:.1f}%")
            print(f"    {pf_status} Profit Factor: Expected {exp['profit_factor']:.1f}, Got {stats['profit_factor']:.2f}")

    print()
    print("=" * 100)
    print("✅ BACKTEST ANALYSIS COMPLETE")
    print("=" * 100)

    # Save detailed report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"backtest_report_{timestamp}.txt"

    with open(report_file, 'w') as f:
        f.write("VOLATILITY-AWARE STRATEGY BACKTEST REPORT\n")
        f.write("=" * 100 + "\n\n")

        for result in all_results:
            f.write(f"{result['name']}\n")
            f.write(f"  Volatility: {result['volatility']}\n")
            f.write(f"  Trades: {result['trades']}\n")
            f.write(f"  Win Rate: {result['win_rate']:.1f}%\n")
            f.write(f"  Profit Factor: {result['profit_factor']:.2f}\n")
            f.write(f"  ROI: {result['roi']:.2f}%\n")
            f.write(f"  Sharpe: {result['sharpe']:.2f}\n\n")

    print(f"\n📄 Detailed report saved to: {report_file}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python monitor_backtests.py <backtest_id1> <backtest_id2> ...")
        print("Or: python monitor_backtests.py 9-17  (for range)")
        sys.exit(1)

    # Parse backtest IDs
    arg = sys.argv[1]
    if '-' in arg:
        start, end = map(int, arg.split('-'))
        backtest_ids = list(range(start, end + 1))
    else:
        backtest_ids = [int(x) for x in sys.argv[1:]]

    print(f"Monitoring {len(backtest_ids)} backtests: {backtest_ids}")
    print()

    # Monitor progress
    monitor_backtests(backtest_ids)

    # Generate report
    generate_report(backtest_ids)
