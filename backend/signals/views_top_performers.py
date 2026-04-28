"""
Read-only API for monthly top-performing symbols.

GET /api/top-performers/             -> latest month's top 10
GET /api/top-performers/?period=YYYY-MM   -> that specific month
GET /api/top-performers/?period=current   -> month-to-date for the current month
                                              (live computation, not a snapshot)
GET /api/top-performers/?period=previous  -> last completed calendar month
                                              (snapshot if cron has run, else live)

Available to any authenticated user — the data is aggregate per-symbol
performance, no per-user information.
"""
from datetime import date, datetime
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models_top_performers import TopPerformingSymbol
from .services.top_performers_calculator import (
    calendar_month_bounds,
    compute_top_n,
    previous_month_bounds,
)

logger = logging.getLogger(__name__)


def _serialize_snapshot(rows):
    """Format DB rows for JSON output."""
    return [
        {
            'rank': r.rank,
            'symbol': r.symbol,
            'period_start': r.period_start.isoformat(),
            'period_end': r.period_end.isoformat(),
            'total_trades': r.total_trades,
            'wins': r.wins,
            'losses': r.losses,
            'win_rate': float(r.win_rate),
            'total_pnl': float(r.total_pnl),
            'total_pnl_pct': float(r.total_pnl_pct),
            'avg_pnl_pct': float(r.avg_pnl_pct),
            'best_trade_pct': float(r.best_trade_pct),
            'worst_trade_pct': float(r.worst_trade_pct),
            'calculated_at': r.calculated_at.isoformat(),
            'source': 'snapshot',
        }
        for r in rows
    ]


def _serialize_live(period_start, period_end, rows):
    """Format calculator rows (live, not from DB) for JSON output."""
    return [
        {
            'rank': i,
            'symbol': r.symbol,
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'total_trades': r.total_trades,
            'wins': r.wins,
            'losses': r.losses,
            'win_rate': float(r.win_rate),
            'total_pnl': float(r.total_pnl),
            'total_pnl_pct': float(r.total_pnl_pct),
            'avg_pnl_pct': float(r.avg_pnl_pct),
            'best_trade_pct': float(r.best_trade_pct),
            'worst_trade_pct': float(r.worst_trade_pct),
            'calculated_at': None,
            'source': 'live',
        }
        for i, r in enumerate(rows, start=1)
    ]


def _resolve_period(param):
    """Map a ``?period=`` value to (period_start, period_end, prefer_snapshot)."""
    today = date.today()

    if param in (None, '', 'latest'):
        latest = TopPerformingSymbol.objects.values_list(
            'period_start', flat=True,
        ).first()
        if latest:
            return latest, calendar_month_bounds(latest.year, latest.month)[1], True
        # No snapshots yet — fall back to previous month live.
        ps, pe = previous_month_bounds(today)
        return ps, pe, False

    if param == 'previous':
        ps, pe = previous_month_bounds(today)
        return ps, pe, True

    if param == 'current':
        ps, pe = calendar_month_bounds(today.year, today.month)
        return ps, pe, False  # always live — month not done yet

    # YYYY-MM
    try:
        parsed = datetime.strptime(param, '%Y-%m').date()
        ps, pe = calendar_month_bounds(parsed.year, parsed.month)
        return ps, pe, True
    except ValueError:
        return None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def top_performers(request):
    """List the top 10 performing symbols for a calendar month."""
    raw_period = request.query_params.get('period')
    resolved = _resolve_period(raw_period)
    if resolved is None:
        return Response(
            {'error': "Invalid 'period'. Use 'latest', 'previous', 'current', or 'YYYY-MM'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    period_start, period_end, prefer_snapshot = resolved

    if prefer_snapshot:
        snap = list(TopPerformingSymbol.for_period(period_start)[:10])
        if snap:
            return Response({
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'source': 'snapshot',
                'count': len(snap),
                'results': _serialize_snapshot(snap),
            })

    # Either live mode or snapshot was empty — compute on the fly.
    rows = compute_top_n(period_start, period_end, n=10)
    return Response({
        'period_start': period_start.isoformat(),
        'period_end': period_end.isoformat(),
        'source': 'live',
        'count': len(rows),
        'results': _serialize_live(period_start, period_end, rows),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def top_performers_periods(request):
    """List every calendar month for which a snapshot exists, newest first."""
    periods = (
        TopPerformingSymbol.objects
        .order_by('-period_start')
        .values_list('period_start', flat=True)
        .distinct()
    )
    return Response({
        'periods': [p.isoformat() for p in periods],
    })
