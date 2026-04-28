"""
Backfill TopPerformingSymbol snapshots for past calendar months.

Usage:
    python manage.py backfill_top_performers --months 12
    python manage.py backfill_top_performers --start 2025-06 --end 2026-04
    python manage.py backfill_top_performers --month 2025-09 --dry-run

Useful right after deploying the model so the table isn't empty for
a month while waiting for the Celery cron to fire on day 1.
"""
import calendar
from datetime import date
from typing import List

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as dj_timezone

from signals.services.top_performers_calculator import (
    calendar_month_bounds,
    compute_and_snapshot,
    compute_top_n,
)


def _parse_yyyy_mm(value):
    try:
        year_s, month_s = value.split('-')
        return int(year_s), int(month_s)
    except (ValueError, AttributeError):
        raise CommandError(f"Invalid YYYY-MM value: {value!r}")


def _month_iter(start: tuple[int, int], end: tuple[int, int]) -> List[tuple[int, int]]:
    """Inclusive month range from (year, month) to (year, month)."""
    out = []
    y, m = start
    end_idx = end[0] * 12 + end[1]
    while y * 12 + m <= end_idx:
        out.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _previous_month_tuple(today: date) -> tuple[int, int]:
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


class Command(BaseCommand):
    help = "Backfill TopPerformingSymbol snapshots from PaperTrade data."

    def add_arguments(self, parser):
        parser.add_argument(
            '--months', type=int, default=None,
            help="Number of *completed* months to backfill ending with the previous month.",
        )
        parser.add_argument(
            '--start', type=str, default=None,
            help="Start month YYYY-MM (inclusive). Use with --end.",
        )
        parser.add_argument(
            '--end', type=str, default=None,
            help="End month YYYY-MM (inclusive). Use with --start.",
        )
        parser.add_argument(
            '--month', type=str, default=None,
            help="A single month YYYY-MM to backfill.",
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
            '--dry-run', action='store_true',
            help="Compute and print, but do not write to the database.",
        )

    def _resolve_range(self, opts) -> List[tuple[int, int]]:
        single = opts.get('month')
        start = opts.get('start')
        end = opts.get('end')
        months = opts.get('months')

        flags = sum(1 for v in (single, (start and end), months) if v)
        if flags != 1:
            raise CommandError(
                "Specify exactly one of: --month YYYY-MM, "
                "--start YYYY-MM --end YYYY-MM, or --months N"
            )

        if single:
            return [_parse_yyyy_mm(single)]
        if start and end:
            return _month_iter(_parse_yyyy_mm(start), _parse_yyyy_mm(end))
        # months
        today = dj_timezone.now().date()
        py, pm = _previous_month_tuple(today)
        # walk back ``months-1`` months from (py, pm)
        rng = []
        y, m = py, pm
        for _ in range(months):
            rng.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        return list(reversed(rng))

    def handle(self, *args, **opts):
        months_to_run = self._resolve_range(opts)
        n = opts['n']
        min_trades = opts['min_trades']
        dry = opts['dry_run']

        self.stdout.write(self.style.NOTICE(
            f"Backfilling {len(months_to_run)} month(s); n={n}, min_trades={min_trades}, "
            f"dry_run={dry}"
        ))

        for year, month in months_to_run:
            ps, pe = calendar_month_bounds(year, month)
            label = f"{year:04d}-{month:02d}"

            if dry:
                rows = compute_top_n(ps, pe, n=n, min_trades=min_trades)
                self.stdout.write(f"\n[{label}] {len(rows)} symbols qualify")
                for i, r in enumerate(rows, start=1):
                    self.stdout.write(
                        f"  #{i:2d} {r.symbol:14s} "
                        f"trades={r.total_trades:4d} "
                        f"wins={r.wins:4d} "
                        f"win%={float(r.win_rate):5.1f} "
                        f"pnl={float(r.total_pnl):+10.2f} "
                        f"avg%={float(r.avg_pnl_pct):+6.2f}"
                    )
            else:
                summary = compute_and_snapshot(ps, pe, n=n, min_trades=min_trades)
                self.stdout.write(self.style.SUCCESS(
                    f"[{label}] persisted {summary['ranked']} rows"
                ))

        self.stdout.write(self.style.SUCCESS("Done."))
