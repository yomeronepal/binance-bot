"""
Paper Trading API Views
Complete REST API for paper trading functionality.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from decimal import Decimal
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta

from signals.models import PaperTrade, Signal, PaperAccount
from signals.serializers import PaperTradeSerializer, PaperAccountSerializer
from signals.services.paper_trader import paper_trading_service


class PaperTradeViewSet(viewsets.ModelViewSet):
    """
    USER-SPECIFIC Paper Trading API endpoints.

    ⚠️ AUTHENTICATION REQUIRED - All endpoints require user login.
    Each user can only see and manage their own trades.

    Endpoints:
    - GET /api/paper-trades/ - List current user's paper trades
    - POST /api/paper-trades/ - Create paper trade for current user
    - GET /api/paper-trades/:id/ - Get specific trade (must be owned by user)
    - DELETE /api/paper-trades/:id/ - Delete trade (must be owned by user)
    - POST /api/paper-trades/create_from_signal/ - Create from signal
    - POST /api/paper-trades/:id/close_trade/ - Close trade manually
    - POST /api/paper-trades/:id/cancel_trade/ - Cancel pending trade
    - GET /api/paper-trades/performance/ - Get current user's metrics
    - GET /api/paper-trades/open_positions/ - Get current user's open positions
    """

    queryset = PaperTrade.objects.all()
    serializer_class = PaperTradeSerializer
    permission_classes = [IsAuthenticated]  # Require authentication

    def get_queryset(self):
        """
        Filter queryset to show only current user's trades.
        """
        # Only show trades belonging to the authenticated user
        queryset = PaperTrade.objects.filter(user=self.request.user)

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by market type
        market_type = self.request.query_params.get('market_type')
        if market_type:
            queryset = queryset.filter(market_type=market_type)

        # Filter by symbol
        symbol = self.request.query_params.get('symbol')
        if symbol:
            queryset = queryset.filter(symbol__icontains=symbol)

        # Filter by direction
        direction = self.request.query_params.get('direction')
        if direction:
            queryset = queryset.filter(direction=direction)

        return queryset.select_related('signal', 'signal__symbol').order_by('-created_at')

    @action(detail=False, methods=['post'])
    def create_from_signal(self, request):
        """
        Create a paper trade from an existing signal for current user.

        Request body:
        {
            "signal_id": 123,
            "position_size": 100  // optional, default 100 USDT
        }
        """
        signal_id = request.data.get('signal_id')
        position_size = request.data.get('position_size', 100)

        if not signal_id:
            return Response(
                {'error': 'signal_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            signal = Signal.objects.get(id=signal_id)

            # Create paper trade for authenticated user
            trade = paper_trading_service.create_paper_trade(
                signal=signal,
                user=request.user,
                position_size=position_size
            )

            serializer = self.get_serializer(trade)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Signal.DoesNotExist:
            return Response(
                {'error': f'Signal with id {signal_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def close_trade(self, request, pk=None):
        """
        Manually close an open paper trade.

        Request body:
        {
            "current_price": 50000.00  // required
        }
        """
        current_price = request.data.get('current_price')

        if not current_price:
            return Response(
                {'error': 'current_price is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            trade = paper_trading_service.close_trade_manually(
                trade_id=int(pk),
                current_price=Decimal(str(current_price))
            )

            if trade:
                serializer = self.get_serializer(trade)
                return Response(serializer.data)
            else:
                return Response(
                    {'error': 'Trade not found or cannot be closed'},
                    status=status.HTTP_404_NOT_FOUND
                )

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def cancel_trade(self, request, pk=None):
        """
        Cancel a pending paper trade.
        """
        try:
            trade = paper_trading_service.cancel_trade(trade_id=int(pk))

            if trade:
                serializer = self.get_serializer(trade)
                return Response(serializer.data)
            else:
                return Response(
                    {'error': 'Trade not found or cannot be cancelled'},
                    status=status.HTTP_404_NOT_FOUND
                )

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def performance(self, request):
        """
        Get performance metrics for paper trading.

        Query params:
        - days: Filter by last N days (optional)

        Returns:
        {
            "total_trades": 50,
            "open_trades": 5,
            "win_rate": 65.5,
            "total_profit_loss": 1234.56,
            "avg_profit_loss": 24.69,
            "best_trade": 500.00,
            "worst_trade": -150.00,
            "avg_duration_hours": 4.5,
            "profitable_trades": 30,
            "losing_trades": 15
        }
        """
        days = request.query_params.get('days')
        days = int(days) if days else None

        # Get performance metrics for authenticated user only
        metrics = paper_trading_service.calculate_performance_metrics(
            user=request.user,
            days=days
        )

        # Fetch current prices and calculate unrealized P/L for open trades
        try:
            from scanner.services.binance_client import BinanceClient
            from signals.models import PaperTrade
            from decimal import Decimal
            import asyncio

            # Get open trades for current user only
            open_trades_queryset = PaperTrade.objects.filter(
                status='OPEN',
                user=request.user
            )

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
                        except Exception as e:
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

        except Exception as e:
            # If price fetching fails, just return base metrics
            metrics['unrealized_pnl'] = 0.0
            metrics['total_pnl'] = metrics['total_profit_loss']

        return Response(metrics)

    @action(detail=False, methods=['get'])
    def open_positions(self, request):
        """
        Get all open positions with REAL-TIME prices and unrealized P/L.

        Returns:
        {
            "total_investment": 1000.00,
            "total_current_value": 1150.00,
            "total_unrealized_pnl": 150.00,
            "total_unrealized_pnl_pct": 15.00,
            "positions": [
                {
                    "trade_id": 1,
                    "symbol": "BTCUSDT",
                    "direction": "LONG",
                    "entry_price": 50000.00,
                    "current_price": 51000.00,
                    "position_size": 100.00,
                    "current_value": 102.00,
                    "unrealized_pnl": 2.00,
                    "unrealized_pnl_pct": 2.00,
                    "stop_loss": 49000.00,
                    "take_profit": 52000.00,
                    "price_change": 2.00,
                    "price_change_pct": 2.00
                }
            ]
        }
        """
        # Get open trades for authenticated user only
        open_trades = paper_trading_service.get_open_trades(user=request.user)

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
            import asyncio

            symbols = set(trade.symbol for trade in open_trades)
            binance_client = BinanceClient()

            async def fetch_prices():
                prices = {}
                for symbol in symbols:
                    try:
                        price_data = await binance_client.get_price(symbol)
                        if price_data and 'price' in price_data:
                            prices[symbol] = Decimal(str(price_data['price']))
                    except Exception as e:
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

        except Exception as e:
            # If price fetching fails, return positions without current prices
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

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get a comprehensive summary of paper trading activity.

        Returns:
        {
            "performance": {...},
            "open_trades_count": 5,
            "recent_closed_trades": [...],
            "best_performing_symbol": "BTCUSDT",
            "worst_performing_symbol": "ETHUSDT"
        }
        """
        # Get performance metrics for authenticated user
        metrics = paper_trading_service.calculate_performance_metrics(user=request.user)

        # Get open trades for authenticated user
        open_trades = paper_trading_service.get_open_trades(user=request.user)

        # Get recent closed trades for authenticated user
        recent_closed = PaperTrade.objects.filter(
            status__startswith='CLOSED',
            user=request.user
        ).order_by('-exit_time')[:10]

        summary = {
            'performance': metrics,
            'open_trades_count': len(open_trades),
            'recent_closed_trades': PaperTradeSerializer(recent_closed, many=True).data,
        }

        return Response(summary)


class PaperAccountViewSet(viewsets.ModelViewSet):
    """
    API endpoints for PaperAccount (Auto-Trading System).

    Developer API Endpoints:
    - POST /api/dev/paper/start/ - Start auto-trading with $1000 balance
    - POST /api/dev/paper/reset/ - Reset account to initial state
    - GET /api/dev/paper/status/ - Get account status (balance, equity, settings)
    - GET /api/dev/paper/trades/ - List all trades for this account
    - GET /api/dev/paper/summary/ - Get comprehensive performance summary
    - PATCH /api/dev/paper/settings/ - Update auto-trading settings
    """

    queryset = PaperAccount.objects.all()
    serializer_class = PaperAccountSerializer
    permission_classes = [AllowAny]  # For developer testing - add auth later

    def get_queryset(self):
        """Filter to current user's account if authenticated."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user=self.request.user)
        return queryset

    @action(detail=False, methods=['post'], url_path='start')
    def start_auto_trading(self, request):
        """
        Start auto-trading by creating or activating a PaperAccount.

        POST /api/dev/paper/start/
        Body: {
            "initial_balance": 1000.00,  // Optional, defaults to $1000
            "auto_trade_spot": true,
            "auto_trade_futures": true,
            "min_signal_confidence": 0.70,
            "max_position_size": 10.00,
            "max_open_trades": 5
        }

        Returns:
        {
            "id": 1,
            "user": 1,
            "balance": "$1,000.00",
            "equity": "$1,000.00",
            "auto_trading_enabled": true,
            "message": "Auto-trading started successfully"
        }
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Check if user already has an account
        account, created = PaperAccount.objects.get_or_create(
            user=request.user,
            defaults={
                'initial_balance': Decimal(request.data.get('initial_balance', '1000.00')),
                'balance': Decimal(request.data.get('initial_balance', '1000.00')),
                'equity': Decimal(request.data.get('initial_balance', '1000.00')),
                'auto_trading_enabled': True,
                'auto_trade_spot': request.data.get('auto_trade_spot', True),
                'auto_trade_futures': request.data.get('auto_trade_futures', True),
                'min_signal_confidence': Decimal(request.data.get('min_signal_confidence', '0.70')),
                'max_position_size': Decimal(request.data.get('max_position_size', '10.00')),
                'max_open_trades': request.data.get('max_open_trades', 5),
            }
        )

        if not created:
            # Account exists, just enable auto-trading
            account.auto_trading_enabled = True
            account.save()

        serializer = self.get_serializer(account)
        return Response({
            **serializer.data,
            'message': 'Auto-trading started successfully' if created else 'Auto-trading resumed'
        })

    @action(detail=False, methods=['post'], url_path='reset')
    def reset_account(self, request):
        """
        Reset paper account to initial state ($1000 balance, clear trades).

        POST /api/dev/paper/reset/

        Returns:
        {
            "id": 1,
            "balance": "$1,000.00",
            "equity": "$1,000.00",
            "total_pnl": "$0.00",
            "open_positions": [],
            "message": "Account reset to initial state"
        }
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            account = PaperAccount.objects.get(user=request.user)
            account.reset_account()

            serializer = self.get_serializer(account)
            return Response({
                **serializer.data,
                'message': 'Account reset to initial state'
            })
        except PaperAccount.DoesNotExist:
            return Response(
                {"error": "No paper account found. Please start auto-trading first."},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'], url_path='status')
    def get_status(self, request):
        """
        Get current account status (balance, equity, open positions).

        GET /api/dev/paper/status/

        Returns:
        {
            "id": 1,
            "balance": "$1,050.25",
            "equity": "$1,075.50",
            "total_pnl": "+$75.50",
            "realized_pnl": "+$50.25",
            "unrealized_pnl": "+$25.25",
            "open_positions_count": 3,
            "auto_trading_enabled": true,
            "win_rate": 75.00,
            "total_trades": 10,
            ...
        }
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            account = PaperAccount.objects.get(user=request.user)

            # Update account metrics with current prices
            try:
                from scanner.services.binance_client import BinanceClient
                import asyncio

                # Get open trades
                open_trades = PaperTrade.objects.filter(user=request.user, status='OPEN')
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
                        # Update account equity with current prices
                        from signals.services.auto_trader import auto_trading_service
                        auto_trading_service.update_account_equity(account, current_prices)
                    finally:
                        # Properly close the client session
                        loop.run_until_complete(binance_client.close())
                        loop.close()

            except Exception as e:
                # If price fetching fails, just return current state
                pass

            serializer = self.get_serializer(account)
            return Response(serializer.data)

        except PaperAccount.DoesNotExist:
            return Response(
                {"error": "No paper account found. Please start auto-trading first."},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'], url_path='trades')
    def list_trades(self, request):
        """
        List all trades for this paper account.

        GET /api/dev/paper/trades/?status=OPEN&limit=100

        Query params:
        - status: Filter by status (OPEN, CLOSED_TP, CLOSED_SL, etc.)
        - limit: Max trades to return (default: 100)

        Returns:
        {
            "count": 25,
            "open_trades": 5,
            "closed_trades": 20,
            "trades": [...]
        }
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get query params
        trade_status = request.query_params.get('status', None)
        limit = int(request.query_params.get('limit', 100))

        # Filter trades
        trades_queryset = PaperTrade.objects.filter(user=request.user)
        if trade_status:
            trades_queryset = trades_queryset.filter(status=trade_status)

        trades_queryset = trades_queryset.order_by('-created_at')[:limit]

        # Count statistics
        open_count = PaperTrade.objects.filter(user=request.user, status='OPEN').count()
        closed_count = PaperTrade.objects.filter(
            user=request.user,
            status__startswith='CLOSED'
        ).count()

        serializer = PaperTradeSerializer(trades_queryset, many=True)
        return Response({
            'count': trades_queryset.count(),
            'open_trades': open_count,
            'closed_trades': closed_count,
            'trades': serializer.data
        })

    @action(detail=False, methods=['get'], url_path='summary')
    def get_summary(self, request):
        """
        Get comprehensive performance summary for auto-trading account.

        GET /api/dev/paper/summary/

        Returns:
        {
            "account": {...},  // Full account details
            "performance": {...},  // Performance metrics
            "open_positions": [...],  // Current open positions
            "recent_trades": [...],  // Last 10 trades
            "equity_curve": [...]  // Historical equity data
        }
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            account = PaperAccount.objects.get(user=request.user)

            # Get performance metrics
            performance = paper_trading_service.calculate_performance_metrics(user=request.user)

            # Get open positions
            open_trades = PaperTrade.objects.filter(user=request.user, status='OPEN')

            # Get recent trades
            recent_trades = PaperTrade.objects.filter(user=request.user).order_by('-created_at')[:10]

            account_serializer = self.get_serializer(account)
            trades_serializer = PaperTradeSerializer(recent_trades, many=True)
            open_serializer = PaperTradeSerializer(open_trades, many=True)

            return Response({
                'account': account_serializer.data,
                'performance': performance,
                'open_positions': open_serializer.data,
                'recent_trades': trades_serializer.data,
            })

        except PaperAccount.DoesNotExist:
            return Response(
                {"error": "No paper account found. Please start auto-trading first."},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['patch'], url_path='settings')
    def update_settings(self, request):
        """
        Update auto-trading settings.

        PATCH /api/dev/paper/settings/
        Body: {
            "auto_trading_enabled": true,
            "auto_trade_spot": true,
            "auto_trade_futures": false,
            "min_signal_confidence": 0.75,
            "max_position_size": 15.00,
            "max_open_trades": 10
        }

        Returns:
        {
            "id": 1,
            "auto_trading_enabled": true,
            "message": "Settings updated successfully"
        }
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            account = PaperAccount.objects.get(user=request.user)

            # Update settings
            if 'auto_trading_enabled' in request.data:
                account.auto_trading_enabled = request.data['auto_trading_enabled']
            if 'auto_trade_spot' in request.data:
                account.auto_trade_spot = request.data['auto_trade_spot']
            if 'auto_trade_futures' in request.data:
                account.auto_trade_futures = request.data['auto_trade_futures']
            if 'min_signal_confidence' in request.data:
                account.min_signal_confidence = Decimal(str(request.data['min_signal_confidence']))
            if 'max_position_size' in request.data:
                account.max_position_size = Decimal(str(request.data['max_position_size']))
            if 'max_open_trades' in request.data:
                account.max_open_trades = request.data['max_open_trades']

            account.save()

            serializer = self.get_serializer(account)
            return Response({
                **serializer.data,
                'message': 'Settings updated successfully'
            })

        except PaperAccount.DoesNotExist:
            return Response(
                {"error": "No paper account found. Please start auto-trading first."},
                status=status.HTTP_404_NOT_FOUND
            )
