"""
Django management command to monitor backtest progress and generate reports
"""
from django.core.management.base import BaseCommand
from signals.models_backtest import BacktestRun
import time
from datetime import datetime


class Command(BaseCommand):
    help = 'Monitor backtest progress and generate comprehensive report'

    def add_arguments(self, parser):
        parser.add_argument(
            'backtest_ids',
            nargs='+',
            type=str,
            help='Backtest IDs to monitor (e.g., 1 2 3 or 1-10 for range)',
        )
        parser.add_argument(
            '--no-wait',
            action='store_true',
            help='Don\'t wait for completion, just show current status',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=5,
            help='Check interval in seconds (default: 5)',
        )

    def handle(self, *args, **options):
        """Main command handler"""
        # Parse backtest IDs
        backtest_ids = self.parse_ids(options['backtest_ids'])

        self.stdout.write(self.style.SUCCESS(f"Monitoring {len(backtest_ids)} backtests: {backtest_ids}"))
        self.stdout.write("")

        # Monitor progress
        if not options['no_wait']:
            self.monitor_backtests(backtest_ids, options['interval'])

        # Generate report
        self.generate_report(backtest_ids)

    def parse_ids(self, id_args):
        """Parse backtest IDs from arguments"""
        backtest_ids = []
        for arg in id_args:
            if '-' in arg:
                start, end = map(int, arg.split('-'))
                backtest_ids.extend(list(range(start, end + 1)))
            else:
                backtest_ids.append(int(arg))
        return backtest_ids

    def monitor_backtests(self, backtest_ids, interval):
        """Monitor backtest progress"""
        self.stdout.write("=" * 100)
        self.stdout.write(self.style.SUCCESS("MONITORING BACKTEST PROGRESS"))
        self.stdout.write("=" * 100)
        self.stdout.write("")

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
            progress_str = (f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Completed: {completed}/{total} | "
                          f"Running: {status_counts['RUNNING']} | "
                          f"Pending: {status_counts['PENDING']} | "
                          f"Failed: {status_counts['FAILED']}")

            self.stdout.write(f"\r{progress_str}", ending='')
            self.stdout.flush()

            if completed < total:
                time.sleep(interval)
            else:
                self.stdout.write("")  # New line after completion
                break

        self.stdout.write(self.style.SUCCESS("\n✅ All backtests completed!"))

    def generate_report(self, backtest_ids):
        """Generate comprehensive report"""
        self.stdout.write("\n" + "=" * 100)
        self.stdout.write(self.style.SUCCESS("COMPREHENSIVE BACKTEST RESULTS REPORT"))
        self.stdout.write("=" * 100)
        self.stdout.write("")

        backtests = BacktestRun.objects.filter(id__in=backtest_ids, status='COMPLETED').order_by('name')

        if not backtests.exists():
            self.stdout.write(self.style.ERROR("❌ No completed backtests found"))
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
        for vol_level in ['HIGH', 'MEDIUM', 'LOW']:
            group = volatility_groups[vol_level]

            if not group:
                continue

            self.stdout.write(f"\n{'=' * 100}")
            self.stdout.write(self.style.SUCCESS(f"{vol_level} VOLATILITY RESULTS"))
            self.stdout.write(f"{'=' * 100}\n")

            # Get config from first backtest
            sample_config = group[0].strategy_params
            self.stdout.write("Configuration:")
            self.stdout.write(f"  SL ATR Multiplier: {sample_config.get('sl_atr_multiplier')}x")
            self.stdout.write(f"  TP ATR Multiplier: {sample_config.get('tp_atr_multiplier')}x")
            self.stdout.write(f"  ADX Threshold: {sample_config.get('long_adx_min')}")
            self.stdout.write(f"  Min Confidence: {sample_config.get('min_confidence', 0.7):.0%}")
            self.stdout.write("")

            # Calculate averages
            total_trades = sum(bt.total_trades for bt in group)
            avg_win_rate = sum(float(bt.win_rate) for bt in group) / len(group)
            avg_profit_factor = sum(float(bt.profit_factor or 0) for bt in group) / len(group)
            avg_roi = sum(float(bt.roi) for bt in group) / len(group)
            avg_sharpe = sum(float(bt.sharpe_ratio or 0) for bt in group) / len(group)
            avg_drawdown = sum(float(bt.max_drawdown) for bt in group) / len(group)

            self.stdout.write("Summary Statistics:")
            self.stdout.write(f"  Number of Backtests: {len(group)}")
            self.stdout.write(f"  Total Trades: {total_trades}")
            self.stdout.write(f"  Average Win Rate: {avg_win_rate:.1f}%")
            self.stdout.write(f"  Average Profit Factor: {avg_profit_factor:.2f}")
            self.stdout.write(f"  Average ROI: {avg_roi:.2f}%")
            self.stdout.write(f"  Average Sharpe Ratio: {avg_sharpe:.2f}")
            self.stdout.write(f"  Average Max Drawdown: {avg_drawdown:.2f}%")
            self.stdout.write("")

            # Individual results
            self.stdout.write("Individual Backtest Results:")
            self.stdout.write(f"{'-' * 100}")
            self.stdout.write(f"{'Name':<50} {'Trades':>8} {'Win Rate':>10} {'P.Factor':>10} {'ROI':>10} {'Sharpe':>10}")
            self.stdout.write(f"{'-' * 100}")

            for bt in group:
                self.stdout.write(f"{bt.name[:48]:<50} "
                              f"{bt.total_trades:>8} "
                              f"{float(bt.win_rate):>9.1f}% "
                              f"{float(bt.profit_factor or 0):>10.2f} "
                              f"{float(bt.roi):>9.1f}% "
                              f"{float(bt.sharpe_ratio or 0):>10.2f}")

            self.stdout.write("")

            # Best performers
            best_pf = max(group, key=lambda x: float(x.profit_factor or 0))
            self.stdout.write(self.style.SUCCESS("🏆 Best Performer (Profit Factor):"))
            self.stdout.write(f"  {best_pf.name}")
            self.stdout.write(f"  Win Rate: {float(best_pf.win_rate):.1f}%, "
                          f"Profit Factor: {float(best_pf.profit_factor):.2f}, "
                          f"ROI: {float(best_pf.roi):.2f}%")
            self.stdout.write("")

        # Overall summary
        self.stdout.write("=" * 100)
        self.stdout.write(self.style.SUCCESS("OVERALL SUMMARY - ALL VOLATILITY LEVELS"))
        self.stdout.write("=" * 100)
        self.stdout.write("")

        all_backtests = list(backtests)
        total_trades = sum(bt.total_trades for bt in all_backtests)
        overall_win_rate = sum(float(bt.win_rate) for bt in all_backtests) / len(all_backtests)
        overall_profit_factor = sum(float(bt.profit_factor or 0) for bt in all_backtests) / len(all_backtests)
        overall_roi = sum(float(bt.roi) for bt in all_backtests) / len(all_backtests)
        overall_sharpe = sum(float(bt.sharpe_ratio or 0) for bt in all_backtests) / len(all_backtests)

        self.stdout.write(f"Total Backtests Completed: {len(all_backtests)}")
        self.stdout.write(f"Total Trades Executed: {total_trades}")
        self.stdout.write(f"Overall Average Win Rate: {overall_win_rate:.1f}%")
        self.stdout.write(f"Overall Average Profit Factor: {overall_profit_factor:.2f}")
        self.stdout.write(f"Overall Average ROI: {overall_roi:.2f}%")
        self.stdout.write(f"Overall Average Sharpe Ratio: {overall_sharpe:.2f}")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 100))
        self.stdout.write(self.style.SUCCESS("✅ BACKTEST ANALYSIS COMPLETE"))
        self.stdout.write(self.style.SUCCESS("=" * 100))
