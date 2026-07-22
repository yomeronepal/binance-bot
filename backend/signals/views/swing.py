"""Public read-only API for the 4h swing engine (paper harness).

Mirrors the day-trade endpoints' response shapes so the shared BotPerformance
frontend component can render swing without changes.
"""
from decimal import Decimal

from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from signals.models.swing import SwingPaperTrade
from signals.serializers.swing import SwingPaperTradeSerializer, SwingSignalSerializer
from signals.views.public_paper_trading import _compute_performance_metrics
from signals.views.daytrade import _live_prices

OPEN_STATUSES = ['OPEN']


def _paginator():
    paginator = PageNumberPagination()
    paginator.page_size = 20
    paginator.page_size_query_param = 'page_size'
    paginator.max_page_size = 100
    return paginator


def _apply_filters(queryset, request):
    """Optional symbol/direction/status filters."""
    symbol = request.query_params.get('symbol')
    direction = request.query_params.get('direction')
    status = request.query_params.get('status')
    if symbol:
        queryset = queryset.filter(symbol=symbol.upper())
    if direction and direction != 'ALL':
        queryset = queryset.filter(direction=direction.upper())
    if status:
        queryset = queryset.filter(status=status.upper())
    return queryset


def _attach_live_pnl(positions):
    """Annotate open swing positions with current price + unrealized P/L."""
    symbols = list({p['symbol'] for p in positions})
    prices = _live_prices(symbols)
    total_unrealized = Decimal('0')
    for p in positions:
        price = prices.get(p['symbol'])
        if price is None:
            continue
        entry = Decimal(str(p['entry_price']))
        qty = Decimal(str(p['quantity']))
        unrealized = (price - entry) * qty if p['direction'] == 'LONG' else (entry - price) * qty
        margin = Decimal(str(p['position_size'] or 0))
        p['current_price'] = float(price)
        p['unrealized_pnl'] = float(unrealized)
        p['profit_loss'] = float(unrealized)
        p['profit_loss_percentage'] = float(unrealized / margin * 100) if margin else 0
        p['trade_id'] = p['id']
        p['current_value'] = float(margin + unrealized)
        p['has_real_time_price'] = True
        total_unrealized += unrealized
    return positions, total_unrealized


@api_view(['GET'])
@permission_classes([AllowAny])
def swing_signals_list(request):
    """Paginated list of detected 4h swing signals. GET /api/swing/signals/"""
    from signals.models.swing import SwingSignal
    queryset = SwingSignal.objects.all()
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
    return paginator.get_paginated_response(SwingSignalSerializer(page, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def swing_trades_list(request):
    """Paginated list of swing paper trades. GET /api/swing/trades/"""
    queryset = _apply_filters(SwingPaperTrade.objects.all(), request).order_by('-entry_time')
    paginator = _paginator()
    page = paginator.paginate_queryset(queryset, request)
    serializer = SwingPaperTradeSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def swing_open_positions(request):
    """Open swing positions with live P/L. GET /api/swing/positions/"""
    queryset = _apply_filters(
        SwingPaperTrade.objects.filter(status__in=OPEN_STATUSES), request
    ).order_by('-entry_time')
    positions = list(SwingPaperTradeSerializer(queryset, many=True).data)
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


@api_view(['POST'])
@permission_classes([IsAdminUser])
def swing_close_trade(request, trade_id):
    """Admin: close an open swing trade at the current price, net of cost."""
    from signals.models.swing import SwingStrategyConfig
    try:
        trade = SwingPaperTrade.objects.get(id=trade_id, status='OPEN')
    except SwingPaperTrade.DoesNotExist:
        return Response({'detail': 'Open swing trade not found'}, status=http_status.HTTP_404_NOT_FOUND)

    prices = _live_prices([trade.symbol])
    price = prices.get(trade.symbol)
    if price is None:
        return Response({'detail': 'No live price available'}, status=http_status.HTTP_503_SERVICE_UNAVAILABLE)

    config = SwingStrategyConfig.get_active()
    qty = trade.quantity
    gross = (price - trade.entry_price) * qty if trade.direction == 'LONG' else (trade.entry_price - price) * qty
    turnover = qty * trade.entry_price + qty * price
    cost = turnover * (config.fee_rate + config.slippage_rate)
    trade.exit_price = price
    trade.exit_time = timezone.now()
    trade.status = 'CLOSED_TP' if gross >= 0 else 'CLOSED_SL'
    trade.fees_paid = cost
    trade.profit_loss = gross - cost
    if trade.position_size:
        trade.profit_loss_percentage = (trade.profit_loss / trade.position_size) * Decimal('100')
    trade.save()
    return Response(SwingPaperTradeSerializer(trade).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def swing_summary(request):
    """Swing bot performance summary. GET /api/swing/summary/"""
    from signals.models.swing import SwingStrategyConfig

    base = _apply_filters(SwingPaperTrade.objects.all(), request)
    metrics = _compute_performance_metrics(base)

    open_positions = list(
        SwingPaperTradeSerializer(base.filter(status__in=OPEN_STATUSES), many=True).data
    )
    _attached, unrealized = _attach_live_pnl(open_positions)
    unrealized_pnl = round(float(unrealized), 2)
    realized_pnl = metrics['total_profit_loss']
    total_pnl = round(realized_pnl + unrealized_pnl, 2)
    metrics['unrealized_pnl'] = unrealized_pnl
    metrics['total_pnl'] = total_pnl

    initial_balance = 10000.0
    config = SwingStrategyConfig.get_active()
    recent_closed = base.filter(status__startswith='CLOSED').order_by('-exit_time')[:10]
    recent_closed_data = SwingPaperTradeSerializer(recent_closed, many=True).data

    return Response({
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
        'enabled': config.enabled,
    })
