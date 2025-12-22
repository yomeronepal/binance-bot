"""
API views for Futures Trading management.
"""
import logging
from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from django.db.models import Sum, Count, Q
from django.utils import timezone

from .models_futures import FuturesTradingSettings, FuturesTrade
from .serializers_futures import (
    FuturesTradingSettingsSerializer,
    FuturesTradeSerializer,
    FuturesTradeListSerializer
)

logger = logging.getLogger(__name__)


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
@permission_classes([IsAdminUser])
def futures_trades_list(request):
    """
    List all futures trades with optional filtering.

    Query params:
    - status: OPEN, CLOSED_TP, CLOSED_SL, CLOSED_MANUAL, FAILED
    - symbol: Filter by symbol (e.g., BTCUSDT)
    - limit: Number of records (default 50)
    """
    trades = FuturesTrade.objects.all()

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

    limit = int(request.query_params.get('limit', 50))
    trades = trades[:limit]

    serializer = FuturesTradeListSerializer(trades, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def futures_open_positions(request):
    """Get all open futures positions."""
    open_trades = FuturesTrade.objects.filter(status='OPEN')
    serializer = FuturesTradeSerializer(open_trades, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def close_futures_trade(request, trade_id):
    """
    Manually close a futures trade.

    POST /api/futures/trades/{trade_id}/close/
    """
    try:
        trade = FuturesTrade.objects.get(id=trade_id)
    except FuturesTrade.DoesNotExist:
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
@permission_classes([IsAdminUser])
def futures_summary(request):
    """
    Get futures trading summary statistics.

    Returns:
    - Total trades
    - Win rate
    - Total P/L
    - Open positions count
    - Settings status
    """
    settings_obj = FuturesTradingSettings.get_settings()

    all_trades = FuturesTrade.objects.all()
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
    open_positions_data = []
    for trade in open_trades:
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
        },
        'open_positions': open_positions_data,
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def futures_trade_detail(request, trade_id):
    """Get details of a specific futures trade."""
    try:
        trade = FuturesTrade.objects.get(id=trade_id)
        serializer = FuturesTradeSerializer(trade)
        return Response(serializer.data)
    except FuturesTrade.DoesNotExist:
        return Response(
            {'error': 'Trade not found'},
            status=status.HTTP_404_NOT_FOUND
        )
