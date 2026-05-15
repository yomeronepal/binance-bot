"""
Manually trigger the monthly balance rebalance.

Useful for first-run verification before letting Celery beat take over.

Usage:
    python manage.py rebalance_now
    python manage.py rebalance_now --dry-run
"""
import json

from django.core.management.base import BaseCommand

from signals.services.balance_rebalancer import rebalance_from_futures_balance


class Command(BaseCommand):
    help = 'Rebalance futures trade_amount / max_concurrent from live Binance balance.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Compute the new values but do not write FuturesTradingSettings.',
        )

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no writes will happen.'))

        summary = rebalance_from_futures_balance(dry_run=dry_run)

        self.stdout.write(json.dumps(summary, indent=2, default=str))

        if not summary['ok']:
            self.stdout.write(self.style.ERROR(f"Did not apply: {summary['reason']}"))
            return

        if summary['applied']:
            self.stdout.write(self.style.SUCCESS('Settings updated.'))
        else:
            self.stdout.write(self.style.WARNING(summary['reason']))
