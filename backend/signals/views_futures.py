"""
API views for Futures Trading management.

Trade-listing endpoints are scoped per requester:
- Superusers see ALL trades (central bot account + every user's trades).
- Regular authenticated users see ONLY their own trades (rows where
  ``FuturesTrade.user == request.user``).

Settings endpoints (``futures_settings``, ``toggle_futures_trading``)
remain admin-only because they configure the central bot account that
governs every fan-out trade — slice 2 will introduce per-user trading
settings as a separate surface.
"""
import logging
from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from django.db.models import Sum, Count, Q, Avg, Max, Min
from django.utils import timezone

from .models_futures import FuturesTradingSettings, FuturesTrade
from .serializers_futures import (
    FuturesTradingSettingsSerializer,
    FuturesTradeSerializer,
    FuturesTradeListSerializer
)

logger = logging.getLogger(__name__)


def _resolve_scope_filter(request):
    """
    Decide which trades the requester should see and return filter kwargs
    suitable for ``.filter(**kwargs)`` (or ``None`` meaning "no filter").

    Rules:
    - Regular user: forced to their own trades; the ``user_id`` query
      param is ignored (cannot be used to look at central or other-user
      trades).
    - Superuser, no ``user_id``: sees everything.
    - Superuser, ``?user_id=N``: sees only that user's trades.
    - Superuser, ``?user_id=central``: sees only central-account trades
      (``user`` FK is NULL).
    - Superuser, malformed ``user_id``: silently falls back to "all" —
      the admin gets useful data instead of a 400.
    """
    user = request.user
    if not user.is_superuser:
        return {'user': user}

    raw = request.query_params.get('user_id')
    if not raw:
        return None
    if raw == 'central':
        return {'user__isnull': True}
    try:
        return {'user_id': int(raw)}
    except (TypeError, ValueError):
        return None


def _scope_trades(queryset, request):
    """
    Restrict a FuturesTrade queryset to what ``request.user`` may see.

    Superusers see every row by default and may narrow with
    ``?user_id=N`` or ``?user_id=central``. Regular users always see
    only the rows tagged with their own ``user`` FK; the central
    account's trades are never visible to them.
    """
    f = _resolve_scope_filter(request)
    if f is None:
        return queryset
    return queryset.filter(**f)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAdminUser])
def futures_settings(request):
    """
    Get or update futures trading settings.

    GET: Return current settings
    PUT/PATCH: Update settings

    Default settings:
    - trade_amount: $5
    - leverage: 10x
    - max_concurrent_trades: 1
    - is_enabled: False (disabled by default for safety)
    """
    settings_obj = FuturesTradingSettings.get_settings()

    if request.method == 'GET':
        serializer = FuturesTradingSettingsSerializer(settings_obj)
        return Response(serializer.data)

    serializer = FuturesTradingSettingsSerializer(
        settings_obj,
        data=request.data,
        partial=(request.method == 'PATCH')
    )

    if serializer.is_valid():
        serializer.save()
        logger.info(f"Futures settings updated: {request.data}")
        return Response(serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def toggle_futures_trading(request):
    """
    Enable or disable futures trading.

    POST body:
    {
        "enabled": true/false
    }
    """
    enabled = request.data.get('enabled')

    if enabled is None:
        return Response(
            {'error': 'enabled field is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    settings_obj = FuturesTradingSettings.get_settings()
    settings_obj.is_enabled = bool(enabled)
    settings_obj.save()

    action = "enabled" if enabled else "disabled"
    logger.info(f"Futures trading {action}")

    return Response({
        'success': True,
        'message': f'Futures trading {action}',
        'is_enabled': settings_obj.is_enabled
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def futures_trades_list(request):
    """
    List futures trades with optional filtering.

    Scope:
    - Superuser: every trade (central + all users).
    - Regular user: only their own trades.

    Query params:
    - status: OPEN, CLOSED_TP, CLOSED_SL, CLOSED_MANUAL, FAILED
    - symbol: Filter by symbol (e.g., BTCUSDT)
    - limit: Number of records (default 50)
    """
    trades = _scope_trades(
        FuturesTrade.objects.select_related('signal', 'user').all(),
        request,
    )

    status_filter = request.query_params.get('status')
    if status_filter:
        if status_filter == 'OPEN':
            trades = trades.filter(status='OPEN')
        elif status_filter.startswith('CLOSED'):
            trades = trades.filter(status__startswith='CLOSED')
        else:
            trades = trades.filter(status=status_filter)

    symbol = request.query_params.get('symbol')
    if symbol:
        trades = trades.filter(symbol=symbol)

    priority_filter = request.query_params.get('priority')
    if priority_filter == 'true':
        trades = trades.filter(signal__is_priority=True)
    elif priority_filter == 'false':
        trades = trades.filter(Q(signal__is_priority=False) | Q(signal__isnull=True))

    limit = int(request.query_params.get('limit', 50))
    trades = trades.order_by('-created_at')[:limit]

    serializer = FuturesTradeListSerializer(trades, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def futures_open_positions(request):
    """
    Open futures positions.

    Scope: superuser sees all; regular user sees only their own.
    """
    open_trades = _scope_trades(
        FuturesTrade.objects.select_related('signal', 'user').filter(status='OPEN'),
        request,
    ).order_by('-entry_time')
    serializer = FuturesTradeSerializer(open_trades, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def close_futures_trade(request, trade_id):
    """
    Manually close a futures trade.

    Authorisation:
    - Superuser may close any trade (central or any user's).
    - Regular user may only close trades on their own connected account.

    POST /api/futures/trades/{trade_id}/close/
    """
    try:
        trade = FuturesTrade.objects.get(id=trade_id)
    except FuturesTrade.DoesNotExist:
        return Response(
            {'error': 'Trade not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not request.user.is_superuser and trade.user_id != request.user.id:
        # Hide existence of central / other-users' trades from non-admins.
        return Response(
            {'error': 'Trade not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not trade.is_open:
        return Response(
            {'error': f'Trade is already closed (status: {trade.status})'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        from .services.futures_trader import futures_trading_service

        success = futures_trading_service.close_trade(trade)

        if success:
            trade.refresh_from_db()
            serializer = FuturesTradeSerializer(trade)
            return Response({
                'success': True,
                'message': f'Trade closed successfully',
                'trade': serializer.data
            })
        else:
            return Response(
                {'error': 'Failed to close trade on Binance'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Exception as e:
        logger.error(f"Error closing futures trade {trade_id}: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def futures_summary(request):
    """
    Get futures trading summary statistics.

    Scope: superuser sees aggregate over all trades; regular user sees
    aggregate over only their own trades. The ``settings`` block is the
    central configuration that governs every fan-out trade — it's
    read-only here so users can see the trade size that will be applied
    to their connected account; mutation of settings is admin-only via
    ``PUT /api/futures/settings/``.

    Returns:
    - Total trades
    - Win rate
    - Total P/L
    - Open positions count
    - Settings status
    """
    settings_obj = FuturesTradingSettings.get_settings()

    all_trades = _scope_trades(
        FuturesTrade.objects.select_related('signal', 'user').all(),
        request,
    )
    closed_trades = all_trades.filter(status__startswith='CLOSED')
    open_trades = all_trades.filter(status='OPEN')

    total_trades = closed_trades.count()
    winning_trades = closed_trades.filter(profit_loss__gt=0).count()
    losing_trades = closed_trades.filter(profit_loss__lt=0).count()

    win_rate = 0
    if total_trades > 0:
        win_rate = (winning_trades / total_trades) * 100

    total_pnl = closed_trades.aggregate(
        total=Sum('profit_loss')
    )['total'] or Decimal('0')

    # Calculate unrealized PnL from open positions
    unrealized_pnl = open_trades.aggregate(
        total=Sum('unrealized_pnl')
    )['total'] or Decimal('0')

    # Get open positions with their live data
    priority_closed = closed_trades.filter(signal__is_priority=True)
    priority_total = priority_closed.count()
    priority_wins = priority_closed.filter(profit_loss__gt=0).count()
    priority_pnl = priority_closed.aggregate(total=Sum('profit_loss'))['total'] or Decimal('0')

    open_positions_data = []
    for trade in open_trades:
        is_priority = getattr(trade.signal, 'is_priority', False) if trade.signal_id else False
        open_positions_data.append({
            'id': trade.id,
            'symbol': trade.symbol,
            'direction': trade.direction,
            'leverage': trade.leverage,
            'entry_price': str(trade.entry_price),
            'mark_price': str(trade.mark_price) if trade.mark_price else None,
            'quantity': str(trade.quantity),
            'position_size_usdt': str(trade.position_size_usdt),
            'unrealized_pnl': str(trade.unrealized_pnl),
            'unrealized_pnl_percentage': str(trade.unrealized_pnl_percentage),
            'liquidation_price': str(trade.liquidation_price) if trade.liquidation_price else None,
            'stop_loss': str(trade.stop_loss),
            'take_profit': str(trade.take_profit),
            'is_priority': is_priority,
            'last_sync_time': trade.last_sync_time.isoformat() if trade.last_sync_time else None,
        })

    return Response({
        'settings': {
            'is_enabled': settings_obj.is_enabled,
            'trade_amount': str(settings_obj.trade_amount),
            'leverage': settings_obj.leverage,
            'effective_position_size': str(settings_obj.effective_position_size),
            'max_concurrent_trades': settings_obj.max_concurrent_trades,
            'allowed_symbols': settings_obj.allowed_symbols,
            'gw_auto_trader_enabled': settings_obj.gw_auto_trader_enabled,
            'total_trading_capital': str(settings_obj.total_trading_capital),
            'max_active_gw_trades': settings_obj.max_active_gw_trades,
        },
        'statistics': {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'realized_pnl': str(total_pnl),
            'unrealized_pnl': str(unrealized_pnl),
            'total_pnl': str(total_pnl + unrealized_pnl),
            'open_positions_count': open_trades.count(),
            'priority_trades': priority_total,
            'priority_wins': priority_wins,
            'priority_win_rate': round((priority_wins / priority_total) * 100, 2) if priority_total > 0 else 0,
            'priority_pnl': str(priority_pnl),
        },
        'open_positions': open_positions_data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def futures_trade_detail(request, trade_id):
    """
    Get details of a specific futures trade.

    Scope: superuser may fetch any trade; regular user may fetch only
    trades that belong to them. Non-matching IDs return 404 (not 403)
    so the existence of central / other-user trades is not leaked.
    """
    try:
        trade = (
            FuturesTrade.objects
            .select_related('signal', 'user')
            .get(id=trade_id)
        )
    except FuturesTrade.DoesNotExist:
        return Response(
            {'error': 'Trade not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not request.user.is_superuser and trade.user_id != request.user.id:
        return Response(
            {'error': 'Trade not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = FuturesTradeSerializer(trade)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def fear_greed_status(request):
    """
    Get current Fear & Greed Index and its effect on trading.

    GET /api/futures/fear-greed/
    """
    from .services.fear_greed import fetch_fear_greed_index, check_direction_allowed

    settings_obj = FuturesTradingSettings.get_settings()
    fg_data = fetch_fear_greed_index()

    if not fg_data:
        return Response({
            'available': False,
            'enabled': settings_obj.fear_greed_enabled,
            'message': 'Fear & Greed Index temporarily unavailable',
        })

    long_allowed, long_reason = check_direction_allowed(
        'LONG', fg_data['value'],
        settings_obj.fear_greed_short_threshold,
        settings_obj.fear_greed_long_threshold,
    )
    short_allowed, short_reason = check_direction_allowed(
        'SHORT', fg_data['value'],
        settings_obj.fear_greed_short_threshold,
        settings_obj.fear_greed_long_threshold,
    )

    return Response({
        'available': True,
        'enabled': settings_obj.fear_greed_enabled,
        'value': fg_data['value'],
        'classification': fg_data['classification'],
        'source': fg_data.get('source', 'unknown'),
        'components': fg_data.get('components', {}),
        'thresholds': {
            'short_below': settings_obj.fear_greed_short_threshold,
            'long_above': settings_obj.fear_greed_long_threshold,
        },
        'trading_impact': {
            'long_allowed': long_allowed,
            'long_reason': long_reason,
            'short_allowed': short_allowed,
            'short_reason': short_reason,
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def futures_report(request):
    """
    Futures trading report with breakdowns.

    Scope: superuser sees a report computed over every trade;
    regular user sees a report over only their own trades.

    GET /api/futures/report/
    """
    base_qs = _scope_trades(
        FuturesTrade.objects.select_related('signal', 'user'),
        request,
    )
    closed = base_qs.filter(status__startswith='CLOSED')
    all_trades = base_qs

    total_closed = closed.count()
    winners = closed.filter(profit_loss__gt=0).count()
    losers = closed.filter(profit_loss__lt=0).count()

    stats = closed.aggregate(
        pnl=Sum('profit_loss'), avg_pnl=Avg('profit_loss'),
        best=Max('profit_loss'), worst=Min('profit_loss'),
    )

    open_trades = all_trades.filter(status='OPEN')
    unrealized = open_trades.aggregate(total=Sum('unrealized_pnl'))['total'] or Decimal('0')

    overall = {
        'total_trades': total_closed,
        'open_trades': open_trades.count(),
        'win_rate': round((winners / total_closed) * 100, 1) if total_closed > 0 else 0,
        'total_pnl': float(stats['pnl'] or 0),
        'unrealized_pnl': float(unrealized),
        'avg_pnl': float(stats['avg_pnl'] or 0),
        'best_trade': float(stats['best'] or 0),
        'worst_trade': float(stats['worst'] or 0),
        'profitable_trades': winners,
        'losing_trades': losers,
    }

    def _agg(qs, field):
        rows = list(qs.values(field).annotate(
            total=Count('id'), wins=Count('id', filter=Q(profit_loss__gt=0)),
            losses=Count('id', filter=Q(profit_loss__lt=0)), pnl=Sum('profit_loss'),
            avg_pnl=Avg('profit_loss'), best=Max('profit_loss'), worst=Min('profit_loss'),
        ).order_by('-pnl'))
        for r in rows:
            r['win_rate'] = round((r['wins'] / r['total']) * 100, 1) if r['total'] > 0 else 0
            for k in ['pnl', 'avg_pnl', 'best', 'worst']:
                r[k] = float(r[k] or 0)
        return rows

    priority_closed = closed.filter(signal__is_priority=True)
    non_priority_closed = closed.filter(Q(signal__is_priority=False) | Q(signal__isnull=True))

    def _prio_stats(qs):
        s = qs.aggregate(total=Count('id'), wins=Count('id', filter=Q(profit_loss__gt=0)), pnl=Sum('profit_loss'))
        t = s['total'] or 0
        return {'total': t, 'wins': s['wins'] or 0,
                'win_rate': round(((s['wins'] or 0) / t) * 100, 1) if t > 0 else 0,
                'pnl': float(s['pnl'] or 0)}

    daily = list(
        closed.filter(exit_time__isnull=False)
        .extra(select={'day': "DATE(exit_time)"})
        .values('day')
        .annotate(trades=Count('id'), pnl=Sum('profit_loss'), wins=Count('id', filter=Q(profit_loss__gt=0)))
        .order_by('day')
    )
    cum = 0
    for d in daily:
        d['pnl'] = float(d['pnl'] or 0)
        cum += d['pnl']
        d['cumulative_pnl'] = round(cum, 2)
        d['day'] = str(d['day'])

    def _top(qs, asc=False, limit=5):
        order = 'profit_loss' if asc else '-profit_loss'
        filt = Q(profit_loss__lt=0) if asc else Q(profit_loss__gt=0)
        rows = list(qs.filter(filt).order_by(order)[:limit].values(
            'id', 'symbol', 'direction', 'leverage', 'entry_price', 'exit_price',
            'profit_loss', 'profit_loss_percentage'))
        for t in rows:
            for k in ['entry_price', 'exit_price', 'profit_loss', 'profit_loss_percentage']:
                t[k] = float(t[k] or 0)
        return rows

    pnl_list = list(closed.order_by('exit_time').values_list('profit_loss', flat=True))
    max_win = max_lose = streak = 0
    for p in pnl_list:
        if p and p > 0:
            streak = streak + 1 if streak > 0 else 1
            max_win = max(max_win, streak)
        elif p and p < 0:
            streak = streak - 1 if streak < 0 else -1
            max_lose = max(max_lose, abs(streak))

    return Response({
        'overall': overall,
        'by_symbol': _agg(closed, 'symbol'),
        'by_direction': _agg(closed, 'direction'),
        'by_priority': {'priority': _prio_stats(priority_closed), 'non_priority': _prio_stats(non_priority_closed)},
        'daily_pnl': daily,
        'top_winners': _top(closed),
        'top_losers': _top(closed, asc=True),
        'streaks': {'current': streak, 'max_win': max_win, 'max_loss': max_lose},
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def futures_users_overview(request):
    """
    Admin view: per-user summary of futures trading activity.

    Returns one row per relevant account so an operator can see at a
    glance which users are trading, how their connection is doing, and
    their basic PnL — then drill into any specific user via the
    existing endpoints with ``?user_id=N``.

    The first row in the response is always the **central account**
    (``user_id=null``, ``label='central'``) so admin can compare its
    performance side-by-side with users without a separate tab.
    """
    from django.contrib.auth import get_user_model
    from .models_user_connection import UserBinanceConnection

    User = get_user_model()

    def _row_for(qs, label, user_id, username, email,
                  connection=None):
        closed = qs.filter(status__startswith='CLOSED')
        open_trades = qs.filter(status='OPEN')
        total_closed = closed.count()
        wins = closed.filter(profit_loss__gt=0).count()
        losses = closed.filter(profit_loss__lt=0).count()
        realized = closed.aggregate(total=Sum('profit_loss'))['total'] or Decimal('0')
        unrealized = open_trades.aggregate(total=Sum('unrealized_pnl'))['total'] or Decimal('0')
        return {
            'label': label,
            'user_id': user_id,
            'username': username,
            'email': email,
            'connection': {
                'status': connection.status if connection else None,
                'api_key_hint': connection.api_key_hint if connection else '',
                'ip_check_passed': connection.ip_check_passed if connection else None,
                'last_check_at': (
                    connection.last_check_at.isoformat()
                    if connection and connection.last_check_at else None
                ),
                'last_error': connection.last_error if connection else '',
            },
            'stats': {
                'total_trades': qs.count(),
                'closed_trades': total_closed,
                'open_positions': open_trades.count(),
                'wins': wins,
                'losses': losses,
                'win_rate': round((wins / total_closed) * 100, 1) if total_closed > 0 else 0,
                'realized_pnl': float(realized),
                'unrealized_pnl': float(unrealized),
                'total_pnl': float(realized + unrealized),
            },
        }

    rows = []

    # Central account row (always first).
    rows.append(_row_for(
        FuturesTrade.objects.filter(user__isnull=True),
        label='central', user_id=None, username='central',
        email='', connection=None,
    ))

    # One row per user that either has a Binance connection on file or
    # has any FuturesTrade rows tagged to them. Users with neither do
    # not appear — the page is about trading activity, not auth records.
    user_ids_with_trades = set(
        FuturesTrade.objects
        .filter(user__isnull=False)
        .values_list('user_id', flat=True)
    )
    user_ids_with_connections = set(
        UserBinanceConnection.objects.values_list('user_id', flat=True)
    )
    relevant_user_ids = user_ids_with_trades | user_ids_with_connections

    if relevant_user_ids:
        users = User.objects.filter(id__in=relevant_user_ids)
        connections = {
            c.user_id: c for c in UserBinanceConnection.objects.filter(
                user_id__in=relevant_user_ids
            )
        }
        for u in users:
            rows.append(_row_for(
                FuturesTrade.objects.filter(user=u),
                label='user',
                user_id=u.id,
                username=u.username,
                email=u.email,
                connection=connections.get(u.id),
            ))

    # Sort users (after central) by realized+unrealized PnL desc.
    central, *user_rows = rows
    user_rows.sort(key=lambda r: r['stats']['total_pnl'], reverse=True)
    return Response([central, *user_rows])
