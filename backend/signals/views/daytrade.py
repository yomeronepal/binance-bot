"""Public API for the day-trade (15m Market Structure) system.

Mirrors the public paper-trading endpoints but for the isolated DayTrade*
models, so the day-trade bot is monitored separately.
"""
from decimal import Decimal

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


def _apply_trade_filters(queryset, request):
    """Apply optional symbol/direction/status filters to a trade queryset."""
    symbol = request.query_params.get('symbol')
    direction = request.query_params.get('direction')
    trade_status = request.query_params.get('status')
    if symbol:
        queryset = queryset.filter(symbol=symbol.upper())
    if direction and direction != 'ALL':
        queryset = queryset.filter(direction=direction.upper())
    if trade_status:
        queryset = queryset.filter(status=trade_status.upper())
    return queryset


def _bot_account():
    """Return the system-wide day-trade account, or None."""
    return DayTradePaperAccount.objects.filter(user__isnull=True).first()


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
    if symbol:
        queryset = queryset.filter(symbol=symbol.upper())
    if signal_status:
        queryset = queryset.filter(status=signal_status.upper())
    if direction and direction != 'ALL':
        queryset = queryset.filter(direction=direction.upper())

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
    serializer = DayTradePaperTradeSerializer(queryset, many=True)
    return Response({'count': queryset.count(), 'positions': serializer.data})


@api_view(['GET'])
@permission_classes([AllowAny])
def daytrade_summary(request):
    """Day-trade bot performance summary.

    GET /api/daytrade/summary/
    """
    trades = DayTradePaperTrade.objects.filter(user__isnull=True)
    closed = trades.filter(status__startswith='CLOSED')

    stats = closed.aggregate(
        total_closed=Count('id'),
        winners=Count('id', filter=Q(profit_loss__gt=0)),
        losers=Count('id', filter=Q(profit_loss__lt=0)),
        total_pnl=Sum('profit_loss'),
        avg_pnl=Avg('profit_loss'),
        best=Max('profit_loss'),
        worst=Min('profit_loss'),
    )
    total_closed = stats['total_closed'] or 0
    winners = stats['winners'] or 0
    open_count = trades.filter(status__in=OPEN_TRADE_STATUSES).count()

    account = _bot_account()
    initial_balance = float(account.initial_balance) if account else 10000.0
    total_pnl = float(stats['total_pnl'] or 0)

    summary = {
        'total_trades': total_closed,
        'open_trades': open_count,
        'win_rate': round((winners / total_closed * 100), 2) if total_closed else 0,
        'profitable_trades': winners,
        'losing_trades': stats['losers'] or 0,
        'total_profit_loss': round(total_pnl, 2),
        'avg_profit_loss': round(float(stats['avg_pnl'] or 0), 2),
        'best_trade': round(float(stats['best'] or 0), 2),
        'worst_trade': round(float(stats['worst'] or 0), 2),
        'initial_balance': initial_balance,
        'roi_percent': round((total_pnl / initial_balance * 100), 2) if initial_balance else 0,
    }
    if account:
        summary['account'] = DayTradePaperAccountSerializer(account).data
    return Response(summary)


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
