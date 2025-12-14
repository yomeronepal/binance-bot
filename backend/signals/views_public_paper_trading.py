"""
Public Paper Trading View - Mirror of User Dashboard
No authentication required - shows ALL paper trading activity.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from decimal import Decimal
from django.db.models import Sum, Avg
import asyncio
import logging

from signals.models import PaperTrade
from signals.serializers import PaperTradeSerializer
from signals.services.paper_trader import paper_trading_service
from signals.models_blacklist import BlacklistedSymbol

logger = logging.getLogger(__name__)


def handle_failing_symbol(symbol, error_msg, trade=None):
    """
    Handle symbols that fail price fetching.
    1. Blacklist the symbol
    2. Close the trade if provided

    Args:
        symbol: The failing symbol (e.g., 'BSVUSDT')
        error_msg: Error message from API
        trade: PaperTrade object to close (optional)
    """
    try:
        # Check if already blacklisted
        if BlacklistedSymbol.is_blacklisted(symbol):
            logger.info(f"⏭️  {symbol} already blacklisted, skipping")
            return

        # Add to blacklist
        blacklist_entry = BlacklistedSymbol.objects.create(
            symbol=symbol,
            reason='DELISTED',
            notes=f'Auto-blacklisted: {error_msg}. Coin likely delisted or unavailable on Binance.',
            active=True
        )
        logger.warning(f"🚫 Auto-blacklisted {symbol} due to API error: {error_msg}")

        # Close the trade if provided
        if trade and trade.status == 'OPEN':
            trade.status = 'CLOSED_MANUAL'
            trade.exit_price = trade.entry_price  # Close at entry (no profit/loss)
            trade.profit_loss = Decimal('0')
            trade.profit_loss_percentage = Decimal('0')
            from django.utils import timezone
            trade.exit_time = timezone.now()
            trade.save()
            logger.info(f"✅ Closed failing trade {trade.id} for {symbol} at entry price")

    except Exception as e:
        logger.error(f"❌ Error handling failing symbol {symbol}: {e}")


from rest_framework.pagination import PageNumberPagination

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

    golden_window = request.query_params.get('golden_window')
    if golden_window and golden_window.lower() == 'true':
        queryset = queryset.filter(is_priority=True)

    golden_window_2 = request.query_params.get('golden_window_2')
    if golden_window_2 and golden_window_2.lower() == 'true':
        queryset = queryset.filter(is_golden_2=True)

    outside_golden_window = request.query_params.get('outside_golden_window')
    if outside_golden_window and outside_golden_window.lower() == 'true':
        queryset = queryset.filter(is_priority=False, is_golden_2=False)

    queryset = queryset.select_related('signal').order_by('-created_at')

    # Pagination
    paginator = PageNumberPagination()
    paginator.page_size = 20
    paginator.page_size_query_param = 'page_size'
    paginator.max_page_size = 100
    
    result_page = paginator.paginate_queryset(queryset, request)
    serializer = PaperTradeSerializer(result_page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_performance(request):
    """
    PUBLIC - Performance metrics for SYSTEM paper trades only.
    Shows bot's performance on automatically generated signals.

    GET /api/public/paper-trading/performance/?days=7&direction=ALL|LONG|SHORT

    Query Parameters:
        - days: Limit to last N days
        - direction: Filter by trade direction (ALL, LONG, SHORT). Default: ALL
        - golden_window: Filter Golden Window 1 trades
        - golden_window_2: Filter Golden Window 2 trades
        - outside_golden_window: Filter trades outside Golden Windows
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

    golden_window = request.query_params.get('golden_window')
    if golden_window and golden_window.lower() == 'true':
        queryset = queryset.filter(is_priority=True)

    golden_window_2 = request.query_params.get('golden_window_2')
    if golden_window_2 and golden_window_2.lower() == 'true':
        queryset = queryset.filter(is_golden_2=True)

    outside_golden_window = request.query_params.get('outside_golden_window')
    if outside_golden_window and outside_golden_window.lower() == 'true':
        queryset = queryset.filter(is_priority=False, is_golden_2=False)

    # Filter by direction (ALL, LONG, SHORT)
    direction = request.query_params.get('direction', 'ALL').upper()
    if direction == 'LONG':
        queryset = queryset.filter(direction='LONG')
    elif direction == 'SHORT':
        queryset = queryset.filter(direction='SHORT')
    # If 'ALL', no filter applied

    closed_trades = queryset.filter(status__startswith='CLOSED')

    # Calculate basic metrics
    total_trades = closed_trades.count()
    winning_trades = closed_trades.filter(profit_loss__gt=0).count()
    losing_trades = closed_trades.filter(profit_loss__lt=0).count()

    # Calculate Max Drawdown
    # Order by exit time to simulate equity curve
    equity_curve = closed_trades.order_by('exit_time').values_list('profit_loss', flat=True)
    current_pnl = Decimal('0')
    peak_pnl = Decimal('0')
    max_drawdown = Decimal('0')

    for trade_pnl in equity_curve:
        if trade_pnl is not None:
            current_pnl += trade_pnl
            if current_pnl > peak_pnl:
                peak_pnl = current_pnl
            
            # Drawdown is peak - current
            drawdown = peak_pnl - current_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown

    metrics = {
        'total_trades': queryset.count(),
        'open_trades': queryset.filter(status='OPEN').count(),
        'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
        'total_profit_loss': float(closed_trades.aggregate(total=Sum('profit_loss'))['total'] or 0),
        'avg_profit_loss': float(closed_trades.aggregate(avg=Avg('profit_loss'))['avg'] or 0),
        'best_trade': float(closed_trades.aggregate(best=Sum('profit_loss'))['best'] or 0),
        'worst_trade': float(closed_trades.aggregate(worst=Sum('profit_loss'))['worst'] or 0),
        'avg_duration_hours': 0,  # Calculate if needed
        'max_drawdown': float(max_drawdown),
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
                failed_symbols = {}
                for symbol in symbols:
                    try:
                        price_data = await binance_client.get_price(symbol)
                        if price_data and 'price' in price_data:
                            prices[symbol] = Decimal(str(price_data['price']))
                    except Exception as e:
                        error_msg = str(e)
                        # Check if it's a 400 error (likely delisted coin)
                        if '400' in error_msg or 'Bad Request' in error_msg:
                            failed_symbols[symbol] = error_msg
                            logger.error(f"❌ Request failed: {error_msg}")
                return prices, failed_symbols

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                current_prices, failed_symbols = loop.run_until_complete(fetch_prices())

                # Handle failed symbols - blacklist and close trades
                for symbol, error_msg in failed_symbols.items():
                    # Find all open trades for this symbol
                    failing_trades = open_trades_queryset.filter(symbol=symbol)
                    for trade in failing_trades:
                        handle_failing_symbol(symbol, error_msg, trade)

            finally:
                # Properly close the client session
                loop.run_until_complete(binance_client.close())
                loop.close()

            # Calculate unrealized P/L (skip failed symbols)
            total_unrealized_pnl = Decimal('0')
            for trade in open_trades_queryset.filter(status='OPEN'):
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
    queryset = PaperTrade.objects.filter(status='OPEN', user__isnull=True)

    golden_window = request.query_params.get('golden_window')
    if golden_window and golden_window.lower() == 'true':
        queryset = queryset.filter(is_priority=True)

    golden_window_2 = request.query_params.get('golden_window_2')
    if golden_window_2 and golden_window_2.lower() == 'true':
        queryset = queryset.filter(is_golden_2=True)

    outside_golden_window = request.query_params.get('outside_golden_window')
    if outside_golden_window and outside_golden_window.lower() == 'true':
        queryset = queryset.filter(is_priority=False, is_golden_2=False)

    open_trades = list(queryset)

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
            failed_symbols = {}
            for symbol in symbols:
                try:
                    price_data = await binance_client.get_price(symbol)
                    if price_data and 'price' in price_data:
                        prices[symbol] = Decimal(str(price_data['price']))
                except Exception as e:
                    error_msg = str(e)
                    # Check if it's a 400 error (likely delisted coin)
                    if '400' in error_msg or 'Bad Request' in error_msg:
                        failed_symbols[symbol] = error_msg
                        logger.error(f"❌ Request failed: {error_msg}")
            return prices, failed_symbols

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            current_prices, failed_symbols = loop.run_until_complete(fetch_prices())

            # Handle failed symbols - blacklist and close trades
            for symbol, error_msg in failed_symbols.items():
                # Find all open trades for this symbol
                failing_trades = [t for t in open_trades if t.symbol == symbol]
                for trade in failing_trades:
                    handle_failing_symbol(symbol, error_msg, trade)
                    # Remove from open_trades list
                    open_trades.remove(trade)

        finally:
            # Properly close the client session
            loop.run_until_complete(binance_client.close())
            loop.close()

    except Exception as e:
        logger.error(f"❌ Error fetching prices: {e}")
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


from rest_framework.permissions import IsAdminUser
@api_view(['POST'])
@permission_classes([IsAdminUser])
def public_close_trade(request, trade_id):
    """
    PUBLIC - Manually close a SYSTEM paper trade at current market price.

    POST /api/public/paper-trading/<trade_id>/close/
    """
    try:
        trade = PaperTrade.objects.get(id=trade_id, user__isnull=True, status='OPEN')
    except PaperTrade.DoesNotExist:
        return Response(
            {'error': 'Trade not found or not open'},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        from scanner.services.binance_client import BinanceClient

        binance_client = BinanceClient()

        async def fetch_price():
            try:
                price_data = await binance_client.get_price(trade.symbol)
                if price_data and 'price' in price_data:
                    return Decimal(str(price_data['price'])), None
            except Exception as e:
                error_msg = str(e)
                # Check if it's a 400 error (likely delisted coin)
                if '400' in error_msg or 'Bad Request' in error_msg:
                    logger.error(f"❌ Request failed: {error_msg}")
                    return None, error_msg
            return None, None

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            current_price, error_msg = loop.run_until_complete(fetch_price())
        finally:
            loop.run_until_complete(binance_client.close())
            loop.close()

        if not current_price:
            # If 400 error, blacklist and close at entry price
            if error_msg and ('400' in error_msg or 'Bad Request' in error_msg):
                handle_failing_symbol(trade.symbol, error_msg, trade)
                return Response({
                    'message': f'Symbol {trade.symbol} blacklisted and trade closed due to API error',
                    'error': error_msg
                }, status=status.HTTP_200_OK)

            return Response(
                {'error': 'Could not fetch current price'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        pnl, _ = trade.calculate_profit_loss(current_price)

        if pnl >= 0:
            close_status = 'CLOSED_TP'
        else:
            close_status = 'CLOSED_SL'

        trade.close_trade(current_price, status=close_status)

        serializer = PaperTradeSerializer(trade)
        return Response({
            'message': f'Trade closed successfully at ${float(current_price):.4f}',
            'trade': serializer.data,
            'exit_price': float(current_price),
            'profit_loss': float(trade.profit_loss) if trade.profit_loss else 0,
            'profit_loss_pct': float(trade.profit_loss_percentage) if trade.profit_loss_percentage else 0,
        })

    except Exception as e:
        return Response(
            {'error': f'Failed to close trade: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def public_summary(request):
    """
    PUBLIC - Comprehensive summary of SYSTEM paper trades.
    Shows bot's performance on automatically generated signals.

    GET /api/public/paper-trading/summary/?direction=ALL|LONG|SHORT

    Query Parameters:
        - direction: Filter by trade direction (ALL, LONG, SHORT). Default: ALL
        - golden_window: Filter Golden Window 1 trades
        - golden_window_2: Filter Golden Window 2 trades
        - outside_golden_window: Filter trades outside Golden Windows
    """
    # Get SYSTEM trades only (user=null)
    queryset = PaperTrade.objects.filter(user__isnull=True)

    golden_window = request.query_params.get('golden_window')
    if golden_window and golden_window.lower() == 'true':
        queryset = queryset.filter(is_priority=True)

    golden_window_2 = request.query_params.get('golden_window_2')
    if golden_window_2 and golden_window_2.lower() == 'true':
        queryset = queryset.filter(is_golden_2=True)

    outside_golden_window = request.query_params.get('outside_golden_window')
    if outside_golden_window and outside_golden_window.lower() == 'true':
        queryset = queryset.filter(is_priority=False, is_golden_2=False)

    # Filter by direction (ALL, LONG, SHORT)
    direction = request.query_params.get('direction', 'ALL').upper()
    if direction == 'LONG':
        queryset = queryset.filter(direction='LONG')
    elif direction == 'SHORT':
        queryset = queryset.filter(direction='SHORT')
    # If 'ALL', no filter applied

    closed_trades = queryset.filter(status__startswith='CLOSED')

    total_trades = closed_trades.count()
    winning_trades = closed_trades.filter(profit_loss__gt=0).count()
    losing_trades = closed_trades.filter(profit_loss__lt=0).count()

    # Calculate Max Drawdown
    equity_curve = closed_trades.order_by('exit_time').values_list('profit_loss', flat=True)
    current_pnl = Decimal('0')
    peak_pnl = Decimal('0')
    max_drawdown = Decimal('0')

    for trade_pnl in equity_curve:
        if trade_pnl is not None:
            current_pnl += trade_pnl
            if current_pnl > peak_pnl:
                peak_pnl = current_pnl
            
            drawdown = peak_pnl - current_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown

    # Calculate duration stats
    from django.db.models import F, ExpressionWrapper, DurationField
    
    avg_duration_seconds = 0
    if total_trades > 0:
        duration_agg = closed_trades.filter(
            entry_time__isnull=False, 
            exit_time__isnull=False
        ).annotate(
            duration=ExpressionWrapper(F('exit_time') - F('entry_time'), output_field=DurationField())
        ).aggregate(
            avg_duration=Avg('duration')
        )
        
        avg_td = duration_agg['avg_duration']
        if avg_td:
            avg_duration_seconds = avg_td.total_seconds()

    metrics = {
        'total_trades': queryset.count(),
        'open_trades': queryset.filter(status='OPEN').count(),
        'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
        'total_profit_loss': float(closed_trades.aggregate(total=Sum('profit_loss'))['total'] or 0),
        'avg_profit_loss': float(closed_trades.aggregate(avg=Avg('profit_loss'))['avg'] or 0),
        'best_trade': float(closed_trades.aggregate(best=Sum('profit_loss'))['best'] or 0),
        'worst_trade': float(closed_trades.aggregate(worst=Sum('profit_loss'))['worst'] or 0),
        'avg_duration_hours': round(avg_duration_seconds / 3600, 2),
        'max_drawdown': float(max_drawdown),
        'profitable_trades': winning_trades,
        'losing_trades': losing_trades,
    }

    # Get SYSTEM open trades only
    open_trades_queryset = PaperTrade.objects.filter(status='OPEN', user__isnull=True)
    
    if golden_window and golden_window.lower() == 'true':
        open_trades_queryset = open_trades_queryset.filter(is_priority=True)

    golden_window_2 = request.query_params.get('golden_window_2')
    if golden_window_2 and golden_window_2.lower() == 'true':
        open_trades_queryset = open_trades_queryset.filter(is_golden_2=True)

    if request.query_params.get('outside_golden_window') and request.query_params.get('outside_golden_window').lower() == 'true':
        open_trades_queryset = open_trades_queryset.filter(is_priority=False, is_golden_2=False)

    # Get recent SYSTEM closed trades
    recent_closed_queryset = PaperTrade.objects.filter(
        status__startswith='CLOSED',
        user__isnull=True
    )

    if golden_window and golden_window.lower() == 'true':
        recent_closed_queryset = recent_closed_queryset.filter(is_priority=True)
    
    golden_window_2 = request.query_params.get('golden_window_2')
    if golden_window_2 and golden_window_2.lower() == 'true':
        recent_closed_queryset = recent_closed_queryset.filter(is_golden_2=True)

    if request.query_params.get('outside_golden_window') and request.query_params.get('outside_golden_window').lower() == 'true':
        recent_closed_queryset = recent_closed_queryset.filter(is_priority=False, is_golden_2=False)
        
    recent_closed = recent_closed_queryset.order_by('-exit_time')[:10]

    # Note: We rely on the frontend to fetch 'public_open_positions' which gets real-time prices
    # and calculates the exact live unrealized PNL. The summary endpoint should just return
    # the base database state to be fast.
    
    # Return 0 for live PnL here, frontend will patch it with data from open-positions endpoint
    metrics['unrealized_pnl'] = 0.0
    metrics['total_pnl'] = metrics['total_profit_loss']

    summary = {
        'performance': metrics,
        'open_trades_count': open_trades_queryset.count(),
        'recent_closed_trades': PaperTradeSerializer(recent_closed, many=True).data,

        # Add bot-wide metrics at top level for easier access
        'bot_total_pnl': metrics['total_pnl'],
        'bot_win_rate': metrics['win_rate'],
        'bot_total_trades': metrics['total_trades'],
        'bot_realized_pnl': metrics['total_profit_loss'],
        'bot_unrealized_pnl': metrics['unrealized_pnl'],
    }

    return Response(summary)
