"""
One-shot initializer for the TopPerformingSymbol snapshot table.

Designed for deploy hooks and first-time setup. Computes top-10
performers for the last N completed calendar months (default 6),
skipping any month that already has a snapshot — so it is safe to
re-run on every deploy.

Differences vs. ``backfill_top_performers``:
  * No required args; sensible defaults.
  * Idempotent: existing snapshots are NOT recalculated by default.
    Pass ``--force`` to force a recompute (e.g. after fixing a bug
    in the calculator).
  * Quiet, deploy-friendly output.

Usage::

    # Default: last 6 completed months, skip months already on file
    python manage.py init_top_performers

    # Last 12 months
    python manage.py init_top_performers --months 12

    # Recompute every month even if a snapshot already exists
    python manage.py init_top_performers --force

    # Quiet mode (only summary line; safe for CI logs)
    python manage.py init_top_performers --quiet
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone

from signals.models.top_performers import TopPerformingSymbol
from signals.services.top_performers_calculator import (
    calendar_month_bounds,
    compute_and_snapshot,
)


def _previous_completed_month(today: date) -> tuple[int, int]:
    """The (year, month) tuple for the last fully-completed calendar month."""
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def _walk_back(start_year: int, start_month: int, count: int):
    """Yield the last ``count`` (year, month) tuples ending at start, oldest first."""
    pairs = []
    y, m = start_year, start_month
    for _ in range(count):
        pairs.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(pairs))


class Command(BaseCommand):
    help = (
        "Initialize the TopPerformingSymbol snapshot table by backfilling "
        "the last N completed calendar months. Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--months', type=int, default=6,
            help="Number of completed calendar months to populate (default 6).",
        )
        parser.add_argument(
            '--n', type=int, default=10,
            help="Top-N to keep per month (default 10).",
        )
        parser.add_argument(
            '--min-trades', type=int, default=5,
            help="Minimum closed trades per symbol to qualify (default 5).",
        )
        parser.add_argument(
            '--force', action='store_true',
            help="Recompute snapshots even for months that already have one.",
        )
        parser.add_argument(
            '--quiet', action='store_true',
            help="Suppress per-month output; print only a summary line.",
        )

    def handle(self, *args, **opts):
        months_back = max(int(opts['months']), 1)
        n = int(opts['n'])
        min_trades = int(opts['min_trades'])
        force = bool(opts['force'])
        quiet = bool(opts['quiet'])

        today = dj_timezone.now().date()
        py, pm = _previous_completed_month(today)
        targets = _walk_back(py, pm, months_back)

        existing_periods = set(
            TopPerformingSymbol.objects
            .values_list('period_start', flat=True)
            .distinct()
        )

        created = 0
        skipped = 0
        rewrote = 0

        for year, month in targets:
            period_start, period_end = calendar_month_bounds(year, month)
            label = f"{year:04d}-{month:02d}"
            already = period_start in existing_periods

            if already and not force:
                skipped += 1
                if not quiet:
                    self.stdout.write(f"[{label}] skip (already on file)")
                continue

            summary = compute_and_snapshot(
                period_start, period_end, n=n, min_trades=min_trades,
            )
            if already:
                rewrote += 1
                tag = 'recomputed'
            else:
                created += 1
                tag = 'created'

            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"[{label}] {tag}: ranked={summary['ranked']}"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"init_top_performers done — created={created}, "
            f"recomputed={rewrote}, skipped={skipped}, "
            f"requested_months={months_back}, n={n}, min_trades={min_trades}"
        ))
