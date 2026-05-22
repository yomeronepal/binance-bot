"""
Sync the monthly Celery beat tasks into the django-celery-beat
DatabaseScheduler.

The project's ``CELERY_BEAT_SCHEDULER`` is set to
``django_celery_beat.schedulers:DatabaseScheduler``, which means the
``app.conf.beat_schedule`` dict in ``config/celery.py`` is informational
only — the live scheduler reads the ``PeriodicTask`` DB table.

This command upserts two rows so each runs at 00:00 UTC on the 1st of
every month:

    signals.monthly_balance_rebalance   (per_trade = balance / 3)
    signals.optimize_golden_windows     (regenerate AI trading sessions)

Idempotent — re-running just rewrites the schedule to match the
expected crontab, so it's safe to invoke after every deploy.

Usage:
    python manage.py sync_monthly_tasks
    python manage.py sync_monthly_tasks --dry-run
"""
import json

from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule


MONTHLY_TASKS = [
    {
        'name': 'monthly-balance-rebalance',
        'task': 'signals.monthly_balance_rebalance',
        'crontab': {
            'minute': '0',
            'hour': '0',
            'day_of_month': '1',
            'month_of_year': '*',
            'day_of_week': '*',
            'timezone': 'UTC',
        },
        'expires_seconds': 1800,
        'description': (
            'Resets futures trade_amount = balance / 3 and '
            'max_concurrent_trades = 2 from live Binance balance. '
            'Fires 00:00 UTC on the 1st of every month.'
        ),
    },
    {
        'name': 'optimize-trading-sessions-monthly',
        'task': 'signals.optimize_golden_windows',
        'crontab': {
            'minute': '30',
            'hour': '0',
            'day_of_month': '1',
            'month_of_year': '*',
            'day_of_week': '*',
            'timezone': 'UTC',
        },
        'expires_seconds': 3600,
        'description': (
            'Regenerates GW1/GW2 TradingSession rows from the prior '
            'month of PaperTrade data. Fires 00:30 UTC on the 1st of '
            'every month, after the balance rebalance.'
        ),
    },
]


def _get_or_create_crontab(spec):
    """Find or create a CrontabSchedule matching ``spec`` exactly."""
    crontab, _ = CrontabSchedule.objects.get_or_create(**spec)
    return crontab


def _upsert_task(entry, dry_run):
    """Create or update one PeriodicTask. Returns a per-row summary."""
    crontab = _get_or_create_crontab(entry['crontab'])
    expires_ms = entry['expires_seconds'] * 1000

    existing = PeriodicTask.objects.filter(name=entry['name']).first()
    if existing:
        previous = {
            'task': existing.task,
            'crontab_id': existing.crontab_id,
            'enabled': existing.enabled,
            'expires': str(existing.expires),
        }
        if dry_run:
            return {'action': 'would update', 'previous': previous, 'task': entry['name']}
        existing.task = entry['task']
        existing.interval = None
        existing.crontab = crontab
        existing.enabled = True
        existing.expire_seconds = entry['expires_seconds']
        existing.description = entry['description']
        existing.kwargs = json.dumps({})
        existing.args = json.dumps([])
        existing.save()
        return {'action': 'updated', 'previous': previous, 'task': entry['name']}

    if dry_run:
        return {'action': 'would create', 'task': entry['name']}

    PeriodicTask.objects.create(
        name=entry['name'],
        task=entry['task'],
        crontab=crontab,
        enabled=True,
        expire_seconds=entry['expires_seconds'],
        description=entry['description'],
        kwargs=json.dumps({}),
        args=json.dumps([]),
    )
    return {'action': 'created', 'task': entry['name']}


class Command(BaseCommand):
    help = 'Create or update the monthly Celery beat PeriodicTask rows.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without writing rows.',
        )

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no writes.'))

        for entry in MONTHLY_TASKS:
            summary = _upsert_task(entry, dry_run)
            self.stdout.write(json.dumps(summary, indent=2, default=str))

        self.stdout.write(self.style.SUCCESS('Done.'))
