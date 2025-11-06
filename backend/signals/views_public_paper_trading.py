"""
Public Paper Trading View - Mirror of User Dashboard
No authentication required - shows ALL paper trading activity.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from decimal import Decimal
from django.db.models import Sum, Avg
import asyncio

from signals.models import PaperTrade
from signals.serializers import PaperTradeSerializer
from signals.services.paper_trader import paper_trading_service


@api_view(['GET'])
@permission_classes([AllowAny])
def public_paper_trades_list(request):
    """
    PUBLIC - List all SYSTEM paper trades (automatically created from signals).
    Shows bot's performance on paper trading all generated signals.

    GET /api/public/paper-trading/
    """
    # Get ONLY system paper trades (user=null) - these are auto-created from signals
    queryset = PaperTrade.objects.filter(user__isnull=True)

    # Apply filters from query params
    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    market_type = request.query_params.get('market_type')
    if market_type:
        queryset = queryset.filter(market_type=market_type)

    symbol = request.query_params.get('symbol')
    if symbol:
        queryset = queryset.filter(symbol__icontains=symbol)

    direction = request.query_params.get('direction')
    if direction:
        queryset = queryset.filter(direction=direction)

    queryset = queryset.select_related('signal').order_by('-created_at')[:100]

    serializer = PaperTradeSerializer(queryset, many=True)
    return Response({
        'count': queryset.count(),
        'trades': serializer.data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def public_performance(request):
    """
    PUBLIC - Performance metrics for SYSTEM paper trades only.
    Shows bot's performance on automatically generated signals.

    GET /api/public/paper-trading/performance/?days=7
    """
    days = request.query_params.get('days')
    days = int(days) if days else None

    # Calculate metrics for SYSTEM trades only (user=null)
    from django.utils import timezone
    from datetime import timedelta

    queryset = PaperTrade.objects.filter(user__isnull=True)

    if days:
        cutoff_date = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(created_at__gte=cutoff_date)

    closed_trades = queryset.filter(status__startswith='CLOSED')

    # Calculate basic metrics
    total_trades = closed_trades.count()
    winning_trades = closed_trades.filter(profit_loss__gt=0).count()
    losing_trades = closed_trades.filter(profit_loss__lt=0).count()

    metrics = {
        'total_trades': queryset.count(),
        'open_trades': queryset.filter(status='OPEN').count(),
        'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
        'total_profit_loss': float(closed_trades.aggregate(total=Sum('profit_loss'))['total'] or 0),
        'avg_profit_loss': float(closed_trades.aggregate(avg=Avg('profit_loss'))['avg'] or 0),
        'best_trade': float(closed_trades.aggregate(best=Sum('profit_loss'))['best'] or 0),
        'worst_trade': float(closed_trades.aggregate(worst=Sum('profit_loss'))['worst'] or 0),
        'avg_duration_hours': 0,  # Calculate if needed
        'profitable_trades': winning_trades,
        'losing_trades': losing_trades,
    }

    # Fetch current prices and calculate unrealized P/L for open trades
    try:
        from scanner.services.binance_client import BinanceClient

        # Get SYSTEM open trades only (user=null)
        open_trades_queryset = PaperTrade.objects.filter(status='OPEN', user__isnull=True)

        if open_trades_queryset.exists():
            # Get unique symbols
            symbols = set(trade.symbol for trade in open_trades_queryset)

            # Fetch prices
            binance_client = BinanceClient()

            async def fetch_prices():
                prices = {}
                for symbol in symbols:
                    try:
                        price_data = await binance_client.get_price(symbol)
                        if price_data and 'price' in price_data:
                            prices[symbol] = Decimal(str(price_data['price']))
                    except Exception:
                        pass
                return prices

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                current_prices = loop.run_until_complete(fetch_prices())
            finally:
                loop.close()

            # Calculate unrealized P/L
            total_unrealized_pnl = Decimal('0')
            for trade in open_trades_queryset:
                current_price = current_prices.get(trade.symbol)
                if current_price:
                    unrealized_pnl, _ = trade.calculate_profit_loss(current_price)
                    total_unrealized_pnl += Decimal(str(unrealized_pnl))

            metrics['unrealized_pnl'] = float(total_unrealized_pnl)
            metrics['total_pnl'] = float(Decimal(str(metrics['total_profit_loss'])) + total_unrealized_pnl)
        else:
            metrics['unrealized_pnl'] = 0.0
            metrics['total_pnl'] = metrics['total_profit_loss']

    except Exception:
        # If price fetching fails, just return base metrics
        metrics['unrealized_pnl'] = 0.0
        metrics['total_pnl'] = metrics['total_profit_loss']

    return Response(metrics)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_open_positions(request):
    """
    PUBLIC - SYSTEM open positions with REAL-TIME prices.
    Shows bot's current paper trading positions from auto-generated signals.

    GET /api/public/paper-trading/open-positions/
    """
    # Get SYSTEM open trades only (user=null)
    open_trades = list(PaperTrade.objects.filter(status='OPEN', user__isnull=True))

    if not open_trades:
        return Response({
            'total_investment': 0,
            'total_current_value': 0,
            'total_unrealized_pnl': 0,
            'total_unrealized_pnl_pct': 0,
            'total_open_trades': 0,
            'positions': []
        })

    # Fetch real-time prices from Binance
    try:
        from scanner.services.binance_client import BinanceClient

        symbols = set(trade.symbol for trade in open_trades)
        binance_client = BinanceClient()

        async def fetch_prices():
            prices = {}
            for symbol in symbols:
                try:
                    price_data = await binance_client.get_price(symbol)
                    if price_data and 'price' in price_data:
                        prices[symbol] = Decimal(str(price_data['price']))
                except Exception:
                    pass
            return prices

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            current_prices = loop.run_until_complete(fetch_prices())
        finally:
            loop.close()

    except Exception:
        current_prices = {}

    # Calculate positions with real-time P/L
    positions_data = {
        'total_investment': Decimal('0'),
        'total_current_value': Decimal('0'),
        'total_unrealized_pnl': Decimal('0'),
        'total_open_trades': len(open_trades),
        'positions': []
    }

    for trade in open_trades:
        current_price = current_prices.get(trade.symbol)

        position_data = {
            'trade_id': trade.id,
            'user': trade.user.username if trade.user else 'System',
            'symbol': trade.symbol,
            'direction': trade.direction,
            'market_type': trade.market_type,
            'entry_price': float(trade.entry_price),
            'entry_time': trade.entry_time,
            'position_size': float(trade.position_size),
            'stop_loss': float(trade.stop_loss),
            'take_profit': float(trade.take_profit),
            'leverage': trade.leverage,
            'risk_reward_ratio': trade.risk_reward_ratio,
        }

        # Add real-time price data if available
        if current_price:
            unrealized_pnl, unrealized_pnl_pct = trade.calculate_profit_loss(current_price)

            # Calculate current value
            current_value = float(trade.position_size) * (1 + float(unrealized_pnl_pct) / 100)

            # Price change calculations
            price_change = float(current_price - trade.entry_price)
            price_change_pct = (price_change / float(trade.entry_price)) * 100

            position_data.update({
                'current_price': float(current_price),
                'current_value': round(current_value, 2),
                'unrealized_pnl': float(unrealized_pnl),
                'unrealized_pnl_pct': float(unrealized_pnl_pct),
                'price_change': round(price_change, 8),
                'price_change_pct': round(price_change_pct, 2),
                'has_real_time_price': True
            })

            # Update totals
            positions_data['total_current_value'] += Decimal(str(current_value))
            positions_data['total_unrealized_pnl'] += Decimal(str(unrealized_pnl))
        else:
            position_data.update({
                'current_price': None,
                'current_value': float(trade.position_size),
                'unrealized_pnl': 0.0,
                'unrealized_pnl_pct': 0.0,
                'price_change': 0.0,
                'price_change_pct': 0.0,
                'has_real_time_price': False
            })

        positions_data['total_investment'] += Decimal(str(trade.position_size))
        positions_data['positions'].append(position_data)

    # Calculate total unrealized P/L percentage
    if positions_data['total_investment'] > 0:
        positions_data['total_unrealized_pnl_pct'] = float(
            (positions_data['total_unrealized_pnl'] / positions_data['total_investment']) * 100
        )
    else:
        positions_data['total_unrealized_pnl_pct'] = 0.0

    # Convert Decimals to floats for JSON serialization
    positions_data['total_investment'] = float(positions_data['total_investment'])
    positions_data['total_current_value'] = float(positions_data['total_current_value'])
    positions_data['total_unrealized_pnl'] = float(positions_data['total_unrealized_pnl'])

    return Response(positions_data)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_summary(request):
    """
    PUBLIC - Comprehensive summary of SYSTEM paper trades.
    Shows bot's performance on automatically generated signals.

    GET /api/public/paper-trading/summary/
    """
    # Get SYSTEM trades only (user=null)
    queryset = PaperTrade.objects.filter(user__isnull=True)
    closed_trades = queryset.filter(status__startswith='CLOSED')

    total_trades = closed_trades.count()
    winning_trades = closed_trades.filter(profit_loss__gt=0).count()
    losing_trades = closed_trades.filter(profit_loss__lt=0).count()

    metrics = {
        'total_trades': queryset.count(),
        'open_trades': queryset.filter(status='OPEN').count(),
        'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
        'total_profit_loss': float(closed_trades.aggregate(total=Sum('profit_loss'))['total'] or 0),
        'avg_profit_loss': float(closed_trades.aggregate(avg=Avg('profit_loss'))['avg'] or 0),
        'best_trade': float(closed_trades.aggregate(best=Sum('profit_loss'))['best'] or 0),
        'worst_trade': float(closed_trades.aggregate(worst=Sum('profit_loss'))['worst'] or 0),
        'avg_duration_hours': 0,
        'profitable_trades': winning_trades,
        'losing_trades': losing_trades,
    }

    # Get SYSTEM open trades only
    open_trades = list(PaperTrade.objects.filter(status='OPEN', user__isnull=True))

    # Get recent SYSTEM closed trades
    recent_closed = PaperTrade.objects.filter(
        status__startswith='CLOSED',
        user__isnull=True
    ).order_by('-exit_time')[:10]

    # Calculate unrealized P/L from open positions
    try:
        from scanner.services.binance_client import BinanceClient

        if open_trades:
            symbols = set(trade.symbol for trade in open_trades)
            binance_client = BinanceClient()

            async def fetch_prices():
                prices = {}
                for symbol in symbols:
                    try:
                        price_data = await binance_client.get_price(symbol)
                        if price_data and 'price' in price_data:
                            prices[symbol] = Decimal(str(price_data['price']))
                    except Exception:
                        pass
                return prices

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                current_prices = loop.run_until_complete(fetch_prices())
            finally:
                loop.close()

            # Calculate unrealized P/L
            total_unrealized_pnl = Decimal('0')
            for trade in open_trades:
                current_price = current_prices.get(trade.symbol)
                if current_price:
                    unrealized_pnl, _ = trade.calculate_profit_loss(current_price)
                    total_unrealized_pnl += Decimal(str(unrealized_pnl))

            metrics['unrealized_pnl'] = float(total_unrealized_pnl)
            metrics['total_pnl'] = float(Decimal(str(metrics['total_profit_loss'])) + total_unrealized_pnl)
        else:
            metrics['unrealized_pnl'] = 0.0
            metrics['total_pnl'] = metrics['total_profit_loss']
    except Exception:
        metrics['unrealized_pnl'] = 0.0
        metrics['total_pnl'] = metrics['total_profit_loss']

    summary = {
        'performance': metrics,
        'open_trades_count': len(open_trades),
        'recent_closed_trades': PaperTradeSerializer(recent_closed, many=True).data,

        # Add bot-wide metrics at top level for easier access
        'bot_total_pnl': metrics['total_pnl'],
        'bot_win_rate': metrics['win_rate'],
        'bot_total_trades': metrics['total_trades'],
        'bot_realized_pnl': metrics['total_profit_loss'],
        'bot_unrealized_pnl': metrics['unrealized_pnl'],
    }

    return Response(summary)
