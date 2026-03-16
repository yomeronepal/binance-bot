"""
Management command to analyze paper trades and optimize golden windows.

Usage:
    python manage.py optimize_golden_windows                    # Run optimization
    python manage.py optimize_golden_windows --dry-run          # Preview changes only
    python manage.py optimize_golden_windows --min-win-rate 55  # Lower threshold
    python manage.py optimize_golden_windows --min-trades 10    # Higher trade minimum
"""
from django.core.management.base import BaseCommand

from signals.services.golden_window_analyzer import (
    analyze_hourly_performance,
    analyze_hourly_weekday_performance,
    get_closed_trades,
    run_optimization,
)

DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


class Command(BaseCommand):
    help = 'Analyze paper trade performance and optimize golden trading windows'

    def add_arguments(self, parser):
        parser.add_argument('--min-trades', type=int, default=5, help='Min trades per hour for GW1 (default: 5)')
        parser.add_argument('--min-trades-weekday', type=int, default=3, help='Min trades per hour+day for GW2 (default: 3)')
        parser.add_argument('--min-win-rate', type=float, default=60.0, help='Min win rate %% to qualify (default: 60)')
        parser.add_argument('--dry-run', action='store_true', help='Preview changes without updating DB')

    def handle(self, *args, **options):
        min_trades = options['min_trades']
        min_wr = options['min_win_rate']
        min_trades_wd = options['min_trades_weekday']
        dry_run = options['dry_run']

        total = get_closed_trades().count()

        self._header(f"GOLDEN WINDOW OPTIMIZER {'(DRY RUN)' if dry_run else ''}")
        self._info(f"Total closed trades: {total}")
        self._info(f"Min trades/hour (GW1): {min_trades}")
        self._info(f"Min trades/hour+day (GW2): {min_trades_wd}")
        self._info(f"Min win rate: {min_wr}%")

        if total < min_trades:
            self._fail(f"Not enough trades ({total} < {min_trades}). Skipping.")
            return

        self._header("HOURLY WIN RATES (NPT)")
        hourly = analyze_hourly_performance(min_trades)
        self._print_hourly_table(hourly, min_wr)

        self._header("HOURLY + WEEKDAY WIN RATES (NPT)")
        hourly_wd = analyze_hourly_weekday_performance(min_trades_wd)
        self._print_weekday_table(hourly_wd, min_wr)

        self._header("RUNNING OPTIMIZATION")
        result = run_optimization(
            min_trades=min_trades,
            min_win_rate=min_wr,
            min_trades_weekday=min_trades_wd,
            dry_run=dry_run,
        )

        self._header("GW1 WINDOWS (Time Only, All Days)")
        if result['gw1_windows']:
            for w in result['gw1_windows']:
                self._ok(f"{w['start']:02d}:00 - {w['end']:02d}:00 NPT | Win rate: {w['win_rate']}% | Trades: {w['trades']}")
        else:
            self._info("No GW1 windows found meeting criteria")

        self._header("GW2 WINDOWS (Time + Specific Days)")
        if result['gw2_windows']:
            for w in result['gw2_windows']:
                days = ', '.join(DAY_NAMES[d] for d in w['active_days'])
                self._ok(
                    f"{w['start_hour']:02d}:00 - {w['end_hour']:02d}:00 NPT | "
                    f"Days: {days} | Win rate: {w['win_rate']}% | Trades: {w['total_trades']}"
                )
        else:
            self._info("No GW2 windows found meeting criteria")

        self._header("CHANGES")
        changes = result['changes']
        for name in changes['created']:
            self._ok(f"CREATED: {name}")
        for name in changes['updated']:
            self._info(f"UPDATED: {name}")
        for name in changes['deactivated']:
            self._fail(f"DEACTIVATED: {name}")

        if not any(changes.values()):
            self._info("No changes needed")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n  DRY RUN - No changes were written to the database"))

    def _print_hourly_table(self, hourly, min_wr):
        self.stdout.write(f"  {'Hour':>5} | {'Wins':>5} | {'Total':>5} | {'Win Rate':>8} | Status")
        self.stdout.write(f"  {'-'*5} | {'-'*5} | {'-'*5} | {'-'*8} | ------")
        for h in range(24):
            if h in hourly:
                d = hourly[h]
                wr = d['win_rate']
                status = "QUALIFIES" if wr >= min_wr else ""
                style = self.style.SUCCESS if wr >= min_wr else (self.style.WARNING if wr >= 50 else self.style.ERROR)
                self.stdout.write(style(
                    f"  {h:02d}:00 | {d['wins']:5d} | {d['total']:5d} | {wr:7.1f}% | {status}"
                ))

    def _print_weekday_table(self, hourly_wd, min_wr):
        self.stdout.write(f"  {'Hour':>5} | {'Day':>4} | {'Wins':>5} | {'Total':>5} | {'Win Rate':>8}")
        self.stdout.write(f"  {'-'*5} | {'-'*4} | {'-'*5} | {'-'*5} | {'-'*8}")
        for (h, wd), d in sorted(hourly_wd.items()):
            wr = d['win_rate']
            if wr >= min_wr:
                self.stdout.write(self.style.SUCCESS(
                    f"  {h:02d}:00 | {DAY_NAMES[wd]:>4} | {d['wins']:5d} | {d['total']:5d} | {wr:7.1f}%"
                ))

    def _header(self, text):
        self.stdout.write(f"\n{'=' * 60}")
        self.stdout.write(f"  {text}")
        self.stdout.write(f"{'=' * 60}")

    def _ok(self, text):
        self.stdout.write(self.style.SUCCESS(f"  [OK] {text}"))

    def _fail(self, text):
        self.stdout.write(self.style.ERROR(f"  [!!] {text}"))

    def _info(self, text):
        self.stdout.write(f"  [..] {text}")
