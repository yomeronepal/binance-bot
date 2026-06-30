"""Run the day-trade trading-session optimizer on demand.

Analyzes closed day-trade paper trades and refreshes the DayTradeSession
windows (analytics only). Dry-run by default.

Usage:
    python manage.py optimize_daytrade_sessions
    python manage.py optimize_daytrade_sessions --apply
    python manage.py optimize_daytrade_sessions --apply --min-trades 3 --min-win-rate 50
"""
import json

from django.core.management.base import BaseCommand

from signals.services.daytrade_session_analyzer import run_optimization


class Command(BaseCommand):
    help = 'Optimize day-trade trading sessions from closed paper-trade history'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Persist sessions (default: dry-run)')
        parser.add_argument('--min-trades', type=int, default=5, help='Min trades per hour bucket')
        parser.add_argument('--min-win-rate', type=float, default=60.0, help='Min win rate %% to qualify (sessions kept only above this)')
        parser.add_argument('--min-trades-weekday', type=int, default=3, help='Min trades per hour-weekday bucket')

    def handle(self, *args, **options):
        result = run_optimization(
            min_trades=options['min_trades'],
            min_win_rate=options['min_win_rate'],
            min_trades_weekday=options['min_trades_weekday'],
            dry_run=not options['apply'],
        )
        self.stdout.write(json.dumps(result, indent=2, default=str))
        if result['status'] == 'skipped':
            self.stdout.write(self.style.WARNING(result['reason']))
        elif options['apply']:
            self.stdout.write(self.style.SUCCESS(
                f"Applied: {len(result['changes']['created'])} created, "
                f"{len(result['changes']['updated'])} updated, "
                f"{len(result['changes']['deactivated'])} deactivated."
            ))
        else:
            self.stdout.write("Dry run — re-run with --apply to persist.")
