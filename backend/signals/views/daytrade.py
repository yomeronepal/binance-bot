"""Public API for the day-trade (15m Market Structure) system.

Mirrors the public paper-trading endpoints but for the isolated DayTrade*
models, so the day-trade bot is monitored separately.
"""
import asyncio
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Sum, Count, Q, Avg, Max, Min
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from signals.models.daytrade import (
    DayTradeSignal,
    DayTradePaperTrade,
    DayTradeTradeExit,
    DayTradePaperAccount,
)
from signals.serializers.daytrade import (
    DayTradeSignalSerializer,
    DayTradePaperTradeSerializer,
    DayTradePaperAccountSerializer,
)

OPEN_TRADE_STATUSES = ['PENDING', 'OPEN', 'PARTIAL']


def _paginator():
    """Return a configured page-number paginator."""
    paginator = PageNumberPagination()
    paginator.page_size = 20
    paginator.page_size_query_param = 'page_size'
    paginator.max_page_size = 100
    return paginator


NEPAL_OFFSET = timedelta(hours=5, minutes=45)


def _active_sessions():
    """Active auto-generated day-trade session windows."""
    from signals.models.daytrade import DayTradeSession
    return list(DayTradeSession.objects.filter(is_active=True))


def _in_session_ids(queryset, sessions):
    """IDs of trades whose NPT entry time falls inside any of the given sessions."""
    matched = []
    for tid, entry_time in queryset.values_list('id', 'entry_time'):
        if entry_time is None:
            continue
        npt = entry_time + NEPAL_OFFSET
        if any(s.covers(npt.hour, npt.weekday()) for s in sessions):
            matched.append(tid)
    return matched


def _apply_session_filter(queryset, request):
    """Filter by optimized session window: ?window=ai (inside) or outside."""
    window = request.query_params.get('window')
    if window not in ('ai', 'outside'):
        return queryset
    sessions = _active_sessions()
    if not sessions:
        return queryset.filter(is_priority=True) if window == 'ai' else queryset
    matched = _in_session_ids(queryset, sessions)
    if window == 'ai':
        return queryset.filter(Q(id__in=matched) | Q(is_priority=True))
    return queryset.exclude(id__in=matched)


def _apply_trade_filters(queryset, request):
    """Apply optional symbol/direction/status + NPT time + session-window filters.

    Time filters (weekday/hour/month/year) reuse the v1 helpers so day-trade
    slices trades exactly the way the v1 Bot Performance page does. The
    session-window filter (?window=ai|outside) restricts to the optimizer's
    discovered windows.
    """
    from signals.views.public_paper_trading import _apply_time_filters

    symbol = request.query_params.get('symbol')
    direction = request.query_params.get('direction')
    trade_status = request.query_params.get('status')
    if symbol:
        queryset = queryset.filter(symbol__icontains=symbol)
    if direction and direction != 'ALL':
        queryset = queryset.filter(direction=direction.upper())
    if trade_status:
        queryset = queryset.filter(status=trade_status.upper())
    min_confidence = request.query_params.get('min_confidence')
    if min_confidence:
        try:
            queryset = queryset.filter(confidence__gte=float(min_confidence))
        except (TypeError, ValueError):
            pass
    if request.query_params.get('priority', '').lower() == 'true':
        queryset = queryset.filter(is_priority=True)
    queryset = _apply_time_filters(queryset, request.query_params)
    queryset = _apply_session_filter(queryset, request)
    return queryset


def _bot_account():
    """Return the system-wide day-trade account, or None."""
    return DayTradePaperAccount.objects.filter(user__isnull=True).first()


async def _fetch_prices_async(symbols):
    """Fetch futures prices for the requested symbols in a single all-tickers call."""
    from scanner.services.binance_futures_client import BinanceFuturesClient
    wanted = set(symbols)
    prices = {}
    async with BinanceFuturesClient() as client:
        try:
            tickers = await client._request('GET', '/fapi/v1/ticker/price')
            for ticker in tickers:
                if ticker['symbol'] in wanted:
                    prices[ticker['symbol']] = Decimal(str(ticker['price']))
        except Exception:
            pass
    return prices


def _cache_get(key):
    """cache.get that treats any cache backend failure as a miss."""
    try:
        return cache.get(key)
    except Exception:
        return None


def _cache_set(key, value, ttl):
    """cache.set that never raises if the cache backend is unavailable."""
    try:
        cache.set(key, value, ttl)
    except Exception:
        pass


def _live_prices(symbols):
    """Return current prices for symbols, briefly cached to limit API calls.

    Cache access is best-effort: if Redis is down or read-only the prices are
    fetched live rather than failing the request.
    """
    if not symbols:
        return {}
    result = {}
    missing = []
    for symbol in symbols:
        cached = _cache_get(f'daytrade:price:{symbol}')
        if cached is not None:
            result[symbol] = Decimal(str(cached))
        else:
            missing.append(symbol)
    if missing:
        fetched = asyncio.run(_fetch_prices_async(missing))
        for symbol, price in fetched.items():
            _cache_set(f'daytrade:price:{symbol}', str(price), 5)
            result[symbol] = price
    return result


def _unrealized_pnl(direction, entry, current, remaining_qty):
    """Mark-to-market P/L for the still-open quantity of a position."""
    if direction == 'LONG':
        return (current - entry) * remaining_qty
    return (entry - current) * remaining_qty


def _attach_live_pnl(positions):
    """Annotate serialized open positions with current price + unrealized P/L.

    Returns (positions, total_unrealized_pnl).
    """
    symbols = list({p['symbol'] for p in positions})
    prices = _live_prices(symbols)
    total_unrealized = Decimal('0')
    for p in positions:
        price = prices.get(p['symbol'])
        if price is None:
            continue
        entry = Decimal(str(p['entry_price']))
        remaining = Decimal(str(p['remaining_quantity']))
        realized = Decimal(str(p.get('realized_pnl') or 0))
        unrealized = _unrealized_pnl(p['direction'], entry, price, remaining)
        live = realized + unrealized
        margin = Decimal(str(p['position_size'] or 0))
        p['current_price'] = float(price)
        p['unrealized_pnl'] = float(unrealized)
        p['profit_loss'] = float(live)
        p['profit_loss_percentage'] = float(live / margin * 100) if margin else 0
        p['trade_id'] = p['id']
        p['current_value'] = float(margin + live)
        p['asset_class'] = p.get('asset_class', 'CRYPTO')
        p['take_profit'] = p.get('tp1_price')
        p['has_real_time_price'] = True
        p['unrealized_pnl_pct'] = float(unrealized / margin * 100) if margin else 0
        p['price_change_pct'] = float((price - entry) / entry * 100) if entry else 0
        total_unrealized += unrealized
    return positions, total_unrealized


@api_view(['GET'])
@permission_classes([AllowAny])
def daytrade_signals_list(request):
    """Paginated list of day-trade signals.

    GET /api/daytrade/signals/?status=ACTIVE&symbol=BTCUSDT
    """
    queryset = DayTradeSignal.objects.all()
    symbol = request.query_params.get('symbol')
    signal_status = request.query_params.get('status')
    direction = request.query_params.get('direction')
    min_confidence = request.query_params.get('min_confidence')
    if min_confidence is None:
        from signals.models.daytrade import DayTradeStrategyConfig
        min_confidence = DayTradeStrategyConfig.get_active().min_confidence
    if symbol:
        queryset = queryset.filter(symbol=symbol.upper())
    if signal_status:
        queryset = queryset.filter(status=signal_status.upper())
    if direction and direction != 'ALL':
        queryset = queryset.filter(direction=direction.upper())
    try:
        queryset = queryset.filter(confidence__gte=float(min_confidence))
    except (TypeError, ValueError):
        pass

    queryset = queryset.order_by('-created_at')
    paginator = _paginator()
    page = paginator.paginate_queryset(queryset, request)
    serializer = DayTradeSignalSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def daytrade_trades_list(request):
    """Paginated list of day-trade paper trades.

    GET /api/daytrade/trades/?status=OPEN&symbol=BTCUSDT
    """
    queryset = DayTradePaperTrade.objects.filter(user__isnull=True)
    queryset = _apply_trade_filters(queryset, request)
    queryset = queryset.prefetch_related('exits').order_by('-entry_time')
    paginator = _paginator()
    page = paginator.paginate_queryset(queryset, request)
    serializer = DayTradePaperTradeSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def daytrade_sessions_list(request):
    """Active optimized day-trade session windows (for the perf-page filter tabs).

    GET /api/daytrade/sessions/
    """
    sessions = [
        {
            'name': s.name,
            'session_type': s.session_type,
            'start_hour': s.start_hour,
            'end_hour': s.end_hour,
            'active_days': s.active_days,
            'win_rate': s.win_rate,
            'total_trades_analyzed': s.total_trades_analyzed,
            'last_optimized_at': s.last_optimized_at.isoformat() if s.last_optimized_at else None,
        }
        for s in _active_sessions()
    ]
    return Response({'count': len(sessions), 'sessions': sessions})


@api_view(['GET'])
@permission_classes([AllowAny])
def daytrade_open_positions(request):
    """All currently open day-trade positions.

    GET /api/daytrade/positions/
    """
    queryset = (
        DayTradePaperTrade.objects
        .filter(user__isnull=True, status__in=OPEN_TRADE_STATUSES)
        .prefetch_related('exits')
        .order_by('-entry_time')
    )
    queryset = _apply_trade_filters(queryset, request)
    positions = list(DayTradePaperTradeSerializer(queryset, many=True).data)
    positions, unrealized = _attach_live_pnl(positions)
    total_investment = sum(float(p['position_size'] or 0) for p in positions)
    total_current_value = sum(float(p.get('current_value') or 0) for p in positions)
    return Response({
        'count': len(positions),
        'positions': positions,
        'total_unrealized_pnl': float(unrealized),
        'total_investment': round(total_investment, 2),
        'total_current_value': round(total_current_value, 2),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def daytrade_summary(request):
    """Day-trade bot performance summary.

    GET /api/daytrade/summary/
    """
    from signals.models.daytrade import DayTradeStrategyConfig
    from signals.views.public_paper_trading import _compute_performance_metrics

    base = DayTradePaperTrade.objects.filter(user__isnull=True)
    base = _apply_trade_filters(base, request)
    metrics = _compute_performance_metrics(base)

    open_positions = list(
        DayTradePaperTradeSerializer(base.filter(status__in=OPEN_TRADE_STATUSES), many=True).data
    )
    _attached, unrealized = _attach_live_pnl(open_positions)
    unrealized_pnl = round(float(unrealized), 2)
    realized_pnl = metrics['total_profit_loss']
    total_pnl = round(realized_pnl + unrealized_pnl, 2)
    metrics['unrealized_pnl'] = unrealized_pnl
    metrics['total_pnl'] = total_pnl

    from scanner.tasks.daytrade_live import live_trading_status
    config = DayTradeStrategyConfig.get_active()
    account = _bot_account()
    initial_balance = float(account.initial_balance) if account else 10000.0
    live_status = live_trading_status('daytrade')

    recent_closed = base.filter(status__startswith='CLOSED').order_by('-exit_time')[:10]
    recent_closed_data = DayTradePaperTradeSerializer(recent_closed, many=True).data

    summary = {
        'performance': metrics,
        'open_trades_count': metrics['open_trades'],
        'recent_closed_trades': recent_closed_data,
        'bot_total_pnl': total_pnl,
        'bot_win_rate': metrics['win_rate'],
        'bot_total_trades': metrics['total_trades'],
        'bot_realized_pnl': realized_pnl,
        'bot_unrealized_pnl': unrealized_pnl,
        'total_trades': metrics['total_trades'],
        'open_trades': metrics['open_trades'],
        'win_rate': metrics['win_rate'],
        'profitable_trades': metrics['profitable_trades'],
        'losing_trades': metrics['losing_trades'],
        'realized_pnl': realized_pnl,
        'unrealized_pnl': unrealized_pnl,
        'total_profit_loss': total_pnl,
        'avg_profit_loss': metrics['avg_profit_loss'],
        'best_trade': metrics['best_trade'],
        'worst_trade': metrics['worst_trade'],
        'initial_balance': initial_balance,
        'roi_percent': round((total_pnl / initial_balance * 100), 2) if initial_balance else 0,
        'min_confidence': config.min_confidence,
        **live_status,
    }
    if account:
        summary['account'] = DayTradePaperAccountSerializer(account).data
    return Response(summary)


def _dt_top_trades(closed_qs, winners=True, limit=5):
    """Top winning/losing day-trade trades (day-trade has no is_priority field)."""
    if winners:
        qs = closed_qs.filter(profit_loss__gt=0).order_by('-profit_loss')[:limit]
    else:
        qs = closed_qs.filter(profit_loss__lt=0).order_by('profit_loss')[:limit]
    rows = list(qs.values('id', 'symbol', 'direction', 'entry_price', 'exit_price',
                          'profit_loss', 'profit_loss_percentage'))
    for row in rows:
        for k in ['entry_price', 'exit_price', 'profit_loss', 'profit_loss_percentage']:
            row[k] = float(row[k] or 0)
    return rows


@api_view(['GET'])
@permission_classes([AllowAny])
def daytrade_report(request):
    """Day-trade performance report (breakdowns + daily PnL + streaks).

    Mirrors the v1 public report shape so the shared Report/Graphs tabs render.
    GET /api/daytrade/report/
    """
    from signals.views.public_paper_trading import (
        _aggregate_by_field, _build_daily_pnl, _compute_streaks,
        _compute_performance_metrics,
    )

    base = DayTradePaperTrade.objects.filter(user__isnull=True)
    filtered = _apply_trade_filters(base, request)
    closed = filtered.filter(status__startswith='CLOSED')

    report = {
        'overall': _compute_performance_metrics(filtered),
        'by_symbol': _aggregate_by_field(closed, 'symbol'),
        'by_direction': _aggregate_by_field(closed, 'direction'),
        'by_timeframe': _aggregate_by_field(closed, 'timeframe'),
        'by_priority': [],
        'daily_pnl': _build_daily_pnl(closed),
        'top_winners': _dt_top_trades(closed, winners=True),
        'top_losers': _dt_top_trades(closed, winners=False),
        'streaks': _compute_streaks(closed),
    }
    return Response(report)


def _compute_close_pnl(trade, exit_price):
    """Return realized P/L for closing the remaining quantity of ``trade``."""
    entry = float(trade.entry_price)
    price = float(exit_price)
    qty = float(trade.remaining_quantity)
    if trade.direction == 'LONG':
        pnl = (price - entry) * qty
    else:
        pnl = (entry - price) * qty
    if trade.market_type == 'FUTURES' and trade.leverage:
        pnl *= trade.leverage
    return pnl


@api_view(['POST'])
@permission_classes([IsAdminUser])
def daytrade_close_trade(request, trade_id):
    """Admin: manually close the remaining quantity of a day-trade.

    POST /api/daytrade/trades/<id>/close/  {"exit_price": 0.1700}
    """
    try:
        trade = DayTradePaperTrade.objects.get(id=trade_id)
    except DayTradePaperTrade.DoesNotExist:
        return Response({'error': 'Trade not found'}, status=status.HTTP_404_NOT_FOUND)

    if not trade.is_open:
        return Response({'error': 'Trade is already closed'}, status=status.HTTP_400_BAD_REQUEST)

    exit_price = request.data.get('exit_price') or trade.entry_price
    exit_price = Decimal(str(exit_price))
    now = timezone.now()
    leg_pnl = _compute_close_pnl(trade, exit_price)

    DayTradeTradeExit.objects.create(
        trade=trade,
        exit_type='MANUAL',
        price=exit_price,
        quantity=trade.remaining_quantity,
        pnl=Decimal(str(leg_pnl)),
        exit_time=now,
    )

    trade.realized_pnl = trade.realized_pnl + Decimal(str(leg_pnl))
    trade.profit_loss = trade.realized_pnl
    if trade.position_size:
        trade.profit_loss_percentage = (trade.profit_loss / trade.position_size) * 100
    trade.remaining_quantity = Decimal('0')
    trade.exit_price = exit_price
    trade.exit_time = now
    trade.status = 'CLOSED_MANUAL'
    trade.save()

    account = _bot_account()
    if account:
        account.update_metrics()

    return Response(DayTradePaperTradeSerializer(trade).data)
