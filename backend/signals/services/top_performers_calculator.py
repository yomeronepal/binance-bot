"""
Compute the top-N performing symbols for a given calendar month from
Bot Performance (PaperTrade) data, and look up whether a given symbol
is a current top performer.

The Bot Performance page (``/bot-performance``) renders aggregates over
``signals.PaperTrade`` rows via ``/api/public/paper-trading/...``. This
calculator runs the same source through a per-symbol group-by, ranks by
total realized PnL (sum of ``profit_loss``), and snapshots the result
into ``TopPerformingSymbol`` so admin and users can see "top 10
performers of <month>" without recomputing on every page load.

Pure functions; no Celery / no DB writes here. The Celery task at
``signals.tasks_top_performers.compute_monthly_top_performers`` calls
``compute_top_n`` then persists via ``snapshot_top_performers``.
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional

from django.db import transaction
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.utils import timezone as dj_timezone

from ..models import PaperTrade
from ..models_top_performers import TopPerformingSymbol

logger = logging.getLogger(__name__)


# Symbols with fewer than this many closed trades in the period are
# excluded from ranking — a single lucky trade should not put a symbol
# at #1. Tunable; kept as a module constant so it's discoverable.
DEFAULT_MIN_TRADES = 5


@dataclass(frozen=True)
class PerformerRow:
    """Per-symbol aggregate for a single period. PnL stored as Decimal."""
    symbol: str
    total_trades: int
    wins: int
    losses: int
    win_rate: Decimal           # 0..100, 1 d.p.
    total_pnl: Decimal
    total_pnl_pct: Decimal
    avg_pnl_pct: Decimal
    best_trade_pct: Decimal
    worst_trade_pct: Decimal


def calendar_month_bounds(year: int, month: int) -> tuple[date, date]:
    """Return (first_day, last_day) for the given calendar month."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def previous_month_bounds(today: Optional[date] = None) -> tuple[date, date]:
    """First and last day of the calendar month *before* ``today`` (UTC)."""
    if today is None:
        today = dj_timezone.now().date()
    if today.month == 1:
        return calendar_month_bounds(today.year - 1, 12)
    return calendar_month_bounds(today.year, today.month - 1)


def _aggregate_qs_for_period(period_start: date, period_end: date):
    """
    Group PaperTrade rows by symbol over the given period.

    Includes only rows that *closed* inside the period — a trade opened
    in the previous month but exited in the current month belongs to
    the current month for performance attribution.
    ``PaperTrade.status`` uses ``CLOSED_TP`` / ``CLOSED_SL`` /
    ``CLOSED_MANUAL`` (there is no plain ``'CLOSED'`` value), so the
    filter is a prefix match. ``exit_time__isnull=False`` excludes the
    rare row that's marked closed without a settle time.
    """
    return (
        PaperTrade.objects
        .filter(
            status__startswith='CLOSED',
            exit_time__isnull=False,
            exit_time__date__gte=period_start,
            exit_time__date__lte=period_end,
        )
        .values('symbol')
        .annotate(
            total_trades=Count('id'),
            wins=Count('id', filter=Q(profit_loss__gt=0)),
            losses=Count('id', filter=Q(profit_loss__lt=0)),
            total_pnl=Sum('profit_loss'),
            total_pnl_pct=Sum('profit_loss_percentage'),
            avg_pnl_pct=Avg('profit_loss_percentage'),
            best_trade_pct=Max('profit_loss_percentage'),
            worst_trade_pct=Min('profit_loss_percentage'),
        )
    )


def _row_from_agg(agg: dict) -> PerformerRow:
    total = int(agg['total_trades'] or 0)
    wins = int(agg['wins'] or 0)
    win_rate = Decimal(round((wins / total) * 100, 1)) if total else Decimal('0')
    return PerformerRow(
        symbol=agg['symbol'],
        total_trades=total,
        wins=wins,
        losses=int(agg['losses'] or 0),
        win_rate=win_rate,
        total_pnl=Decimal(agg['total_pnl'] or 0),
        total_pnl_pct=Decimal(agg['total_pnl_pct'] or 0),
        avg_pnl_pct=Decimal(agg['avg_pnl_pct'] or 0),
        best_trade_pct=Decimal(agg['best_trade_pct'] or 0),
        worst_trade_pct=Decimal(agg['worst_trade_pct'] or 0),
    )


def compute_top_n(
    period_start: date,
    period_end: date,
    n: int = 10,
    min_trades: int = DEFAULT_MIN_TRADES,
) -> List[PerformerRow]:
    """
    Return up to ``n`` symbols ranked by total realized PnL for the period.

    Symbols with fewer than ``min_trades`` closed trades in the period
    are excluded — they're noise, not performance. Ties are broken by
    win rate (higher wins) then trade count (more is more reliable).
    """
    aggregates = list(_aggregate_qs_for_period(period_start, period_end))
    if not aggregates:
        return []

    rows = [
        _row_from_agg(a) for a in aggregates
        if int(a['total_trades'] or 0) >= min_trades
    ]
    rows.sort(
        key=lambda r: (r.total_pnl, r.win_rate, r.total_trades),
        reverse=True,
    )
    return rows[:n]


@transaction.atomic
def snapshot_top_performers(
    period_start: date,
    period_end: date,
    rows: List[PerformerRow],
) -> int:
    """
    Persist ``rows`` to ``TopPerformingSymbol``, replacing any prior
    snapshot for this period. ``update_or_create`` keyed on
    ``(symbol, period_start)`` makes re-running the cron idempotent;
    rows that drop out of the top-N on recalculation are removed.
    """
    written = 0
    seen_symbols = set()
    for rank, row in enumerate(rows, start=1):
        TopPerformingSymbol.objects.update_or_create(
            symbol=row.symbol,
            period_start=period_start,
            defaults={
                'period_end': period_end,
                'rank': rank,
                'total_trades': row.total_trades,
                'wins': row.wins,
                'losses': row.losses,
                'win_rate': row.win_rate,
                'total_pnl': row.total_pnl,
                'total_pnl_pct': row.total_pnl_pct,
                'avg_pnl_pct': row.avg_pnl_pct,
                'best_trade_pct': row.best_trade_pct,
                'worst_trade_pct': row.worst_trade_pct,
            },
        )
        seen_symbols.add(row.symbol)
        written += 1

    # Drop stale rows for this period that didn't make this run's top-N.
    stale = (
        TopPerformingSymbol.objects
        .filter(period_start=period_start)
        .exclude(symbol__in=seen_symbols)
    )
    deleted, _ = stale.delete()
    if deleted:
        logger.info(
            "snapshot_top_performers: removed %d stale rows for %s",
            deleted, period_start,
        )

    return written


# Per-process cache of the latest top-performer symbol set. The set is
# invalidated when ``cache_seconds`` elapse, so a fresh monthly snapshot
# (or a backfill) propagates to running workers within the cache window
# without restart. ``invalidate_top_performer_cache()`` is the explicit
# bust path for tests / for the snapshot task.
_TOP_PERFORMER_CACHE: dict = {'symbols': None, 'fetched_at': None,
                                 'period_start': None}
_TOP_PERFORMER_CACHE_SECONDS = 300  # 5 minutes


def invalidate_top_performer_cache() -> None:
    """Drop the cached top-performer symbol set (used after a snapshot run)."""
    _TOP_PERFORMER_CACHE['symbols'] = None
    _TOP_PERFORMER_CACHE['fetched_at'] = None
    _TOP_PERFORMER_CACHE['period_start'] = None


def latest_top_performer_symbols(n: int = 10) -> set[str]:
    """
    Return the symbol set from the most recent ``TopPerformingSymbol``
    snapshot, capped to ``n`` rows. Cached per-process for 5 minutes.

    Returns an empty set if no snapshot exists yet (e.g. fresh deploy
    before the first month-end run and before any backfill). The caller
    should treat that as "no symbol qualifies" rather than "everything
    qualifies" — fail closed.
    """
    cached_at = _TOP_PERFORMER_CACHE['fetched_at']
    now = dj_timezone.now()
    if (
        _TOP_PERFORMER_CACHE['symbols'] is not None
        and cached_at is not None
        and (now - cached_at).total_seconds() < _TOP_PERFORMER_CACHE_SECONDS
    ):
        return _TOP_PERFORMER_CACHE['symbols']

    latest_period = (
        TopPerformingSymbol.objects
        .order_by('-period_start')
        .values_list('period_start', flat=True)
        .first()
    )
    if latest_period is None:
        symbols: set[str] = set()
    else:
        symbols = set(
            TopPerformingSymbol.objects
            .filter(period_start=latest_period)
            .order_by('rank')
            .values_list('symbol', flat=True)[:n]
        )

    _TOP_PERFORMER_CACHE['symbols'] = symbols
    _TOP_PERFORMER_CACHE['fetched_at'] = now
    _TOP_PERFORMER_CACHE['period_start'] = latest_period
    return symbols


def is_top_performer(symbol: str, n: int = 10) -> bool:
    """True iff ``symbol`` is in the latest snapshot's top-N."""
    if not symbol:
        return False
    return symbol in latest_top_performer_symbols(n=n)


def compute_and_snapshot(
    period_start: date,
    period_end: date,
    n: int = 10,
    min_trades: int = DEFAULT_MIN_TRADES,
) -> dict:
    """
    Convenience: compute_top_n + snapshot in one call. Returns a small
    summary dict suitable for logging or returning from the Celery task.
    """
    rows = compute_top_n(period_start, period_end, n=n, min_trades=min_trades)
    written = snapshot_top_performers(period_start, period_end, rows)
    invalidate_top_performer_cache()
    logger.info(
        "compute_and_snapshot: period=%s..%s ranked=%d (min_trades=%d, n=%d)",
        period_start, period_end, written, min_trades, n,
    )
    return {
        'period_start': period_start.isoformat(),
        'period_end': period_end.isoformat(),
        'ranked': written,
        'min_trades': min_trades,
        'n': n,
    }
