"""
Public Paper Trading Dashboard API
No authentication required - open to all users.

This provides a READ-ONLY view of all paper trading activity.
Perfect for showcasing the trading bot's performance to visitors.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from decimal import Decimal
from django.db.models import Sum, Avg, Count
from django.utils import timezone
from datetime import timedelta

from signals.models import PaperTrade, PaperAccount, Signal


@api_view(['GET'])
@permission_classes([AllowAny])
def public_paper_trading_dashboard(request):
    """
    PUBLIC ENDPOINT - No authentication required.

    Complete paper trading dashboard with real-time data.
    Shows all paper trading activity across all users (aggregated).

    GET /api/paper-trading/dashboard/

    Returns:
    {
        "overview": {
            "total_accounts": 5,
            "active_accounts": 3,
            "total_balance": 5000.00,
            "total_equity": 5250.75,
            "total_pnl": 250.75,
            "total_trades": 150,
            "avg_win_rate": 65.5
        },
        "open_positions": [...],
        "recent_trades": [...],
        "performance_metrics": {...},
        "top_performers": [...]
    }
    """
    try:
        from scanner.services.binance_client import BinanceClient
        import asyncio

        # Get all PaperAccounts
        all_accounts = PaperAccount.objects.all()
        active_accounts = all_accounts.filter(auto_trading_enabled=True)

        # Aggregate account metrics
        overview = {
            'total_accounts': all_accounts.count(),
            'active_accounts': active_accounts.count(),
            'total_balance': float(all_accounts.aggregate(Sum('balance'))['balance__sum'] or 0),
            'total_equity': float(all_accounts.aggregate(Sum('equity'))['equity__sum'] or 0),
            'total_pnl': float(all_accounts.aggregate(Sum('total_pnl'))['total_pnl__sum'] or 0),
            'total_trades': all_accounts.aggregate(Sum('total_trades'))['total_trades__sum'] or 0,
            'avg_win_rate': float(all_accounts.aggregate(Avg('win_rate'))['win_rate__avg'] or 0),
        }

        # Get all open positions
        open_trades = PaperTrade.objects.filter(status='OPEN').order_by('-created_at')

        # Fetch real-time prices for open trades
        if open_trades.exists():
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
                # Properly close the client session
                loop.run_until_complete(binance_client.close())
                loop.close()
        else:
            current_prices = {}

        # Build open positions with real-time prices
        open_positions = []
        for trade in open_trades[:20]:  # Limit to 20 most recent
            current_price = current_prices.get(trade.symbol)

            position = {
                'trade_id': trade.id,
                'symbol': trade.symbol,
                'direction': trade.direction,
                'market_type': trade.market_type,
                'entry_price': float(trade.entry_price),
                'entry_time': trade.entry_time.isoformat() if trade.entry_time else None,
                'position_size': float(trade.position_size),
                'stop_loss': float(trade.stop_loss),
                'take_profit': float(trade.take_profit),
                'leverage': trade.leverage,
            }

            if current_price:
                unrealized_pnl, unrealized_pnl_pct = trade.calculate_profit_loss(current_price)
                price_change = float(current_price - trade.entry_price)
                price_change_pct = (price_change / float(trade.entry_price)) * 100

                position.update({
                    'current_price': float(current_price),
                    'unrealized_pnl': float(unrealized_pnl),
                    'unrealized_pnl_pct': float(unrealized_pnl_pct),
                    'price_change': round(price_change, 8),
                    'price_change_pct': round(price_change_pct, 2),
                    'has_real_time_price': True
                })
            else:
                position.update({
                    'current_price': None,
                    'unrealized_pnl': 0.0,
                    'unrealized_pnl_pct': 0.0,
                    'price_change': 0.0,
                    'price_change_pct': 0.0,
                    'has_real_time_price': False
                })

            open_positions.append(position)

        # Get recent closed trades
        recent_trades = PaperTrade.objects.filter(
            status__startswith='CLOSED'
        ).order_by('-exit_time')[:20]

        recent_trades_data = []
        for trade in recent_trades:
            recent_trades_data.append({
                'trade_id': trade.id,
                'symbol': trade.symbol,
                'direction': trade.direction,
                'entry_price': float(trade.entry_price),
                'exit_price': float(trade.exit_price) if trade.exit_price else None,
                'profit_loss': float(trade.profit_loss),
                'profit_loss_percentage': float(trade.profit_loss_percentage),
                'status': trade.status,
                'entry_time': trade.entry_time.isoformat() if trade.entry_time else None,
                'exit_time': trade.exit_time.isoformat() if trade.exit_time else None,
            })

        # Calculate performance metrics
        all_closed_trades = PaperTrade.objects.filter(status__startswith='CLOSED')

        performance_metrics = {
            'total_closed_trades': all_closed_trades.count(),
            'profitable_trades': all_closed_trades.filter(profit_loss__gt=0).count(),
            'losing_trades': all_closed_trades.filter(profit_loss__lt=0).count(),
            'total_profit': float(all_closed_trades.filter(profit_loss__gt=0).aggregate(Sum('profit_loss'))['profit_loss__sum'] or 0),
            'total_loss': float(all_closed_trades.filter(profit_loss__lt=0).aggregate(Sum('profit_loss'))['profit_loss__sum'] or 0),
            'avg_profit': float(all_closed_trades.filter(profit_loss__gt=0).aggregate(Avg('profit_loss'))['profit_loss__avg'] or 0),
            'avg_loss': float(all_closed_trades.filter(profit_loss__lt=0).aggregate(Avg('profit_loss'))['profit_loss__avg'] or 0),
        }

        if all_closed_trades.count() > 0:
            performance_metrics['win_rate'] = (performance_metrics['profitable_trades'] / all_closed_trades.count()) * 100
        else:
            performance_metrics['win_rate'] = 0.0

        # Get top performing accounts
        top_performers = []
        for account in all_accounts.order_by('-total_pnl')[:5]:
            top_performers.append({
                'user_id': account.user.id,
                'username': account.user.username,
                'balance': float(account.balance),
                'equity': float(account.equity),
                'total_pnl': float(account.total_pnl),
                'win_rate': float(account.win_rate),
                'total_trades': account.total_trades,
            })

        # Get trading statistics by timeframe
        now = timezone.now()
        today_trades = PaperTrade.objects.filter(created_at__gte=now - timedelta(days=1))
        week_trades = PaperTrade.objects.filter(created_at__gte=now - timedelta(days=7))

        trading_stats = {
            'today': {
                'total_trades': today_trades.count(),
                'open_trades': today_trades.filter(status='OPEN').count(),
                'closed_trades': today_trades.filter(status__startswith='CLOSED').count(),
            },
            'this_week': {
                'total_trades': week_trades.count(),
                'open_trades': week_trades.filter(status='OPEN').count(),
                'closed_trades': week_trades.filter(status__startswith='CLOSED').count(),
            }
        }

        return Response({
            'overview': overview,
            'open_positions': open_positions,
            'recent_trades': recent_trades_data,
            'performance_metrics': performance_metrics,
            'top_performers': top_performers,
            'trading_stats': trading_stats,
            'timestamp': timezone.now().isoformat(),
        })

    except Exception as e:
        return Response(
            {
                "error": "Failed to fetch dashboard data",
                "detail": str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
