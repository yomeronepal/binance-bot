"""
Paper Trading Service
Simulates live trades without executing real Binance orders.
"""
import logging
from decimal import Decimal
from typing import Dict, List, Optional
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from signals.models import Signal, PaperTrade

logger = logging.getLogger(__name__)


class PaperTradingService:
    """
    Service for managing paper trades - simulated trading without real execution.
    """

    def __init__(self, default_position_size=100.00):
        """
        Initialize paper trading service.

        Args:
            default_position_size: Default position size in USDT
        """
        self.default_position_size = Decimal(str(default_position_size))

    def create_paper_trade(self, signal: Signal, user=None, position_size=None) -> PaperTrade:
        """
        Create a new paper trade from a signal.

        Args:
            signal: Trading signal to create trade from
            user: User owning this trade (None for system-wide)
            position_size: Custom position size in USDT

        Returns:
            Created PaperTrade instance

        Raises:
            ValueError: If duplicate trade exists for this signal
        """
        # Check for duplicate - prevent creating multiple trades for same signal
        existing_trade = PaperTrade.objects.filter(
            signal=signal,
            user=user,
            status__in=['OPEN', 'PENDING']
        ).first()

        if existing_trade:
            raise ValueError(
                f"Duplicate trade detected: Trade #{existing_trade.id} already exists for this signal. "
                f"Status: {existing_trade.status}, Entry: {existing_trade.entry_price}"
            )

        if position_size is None:
            position_size = self.default_position_size
        else:
            position_size = Decimal(str(position_size))

        # Calculate quantity based on position size
        entry_price = Decimal(str(signal.entry))
        quantity = position_size / entry_price

        # Get symbol string - handle both ForeignKey and string cases
        if hasattr(signal.symbol, 'symbol'):
            symbol_str = signal.symbol.symbol
        else:
            symbol_str = str(signal.symbol)

        # Create paper trade
        paper_trade = PaperTrade.objects.create(
            signal=signal,
            user=user,
            symbol=symbol_str,
            direction=signal.direction,
            market_type=signal.market_type,
            entry_price=entry_price,
            entry_time=timezone.now(),  # Immediate entry for paper trading
            position_size=position_size,
            quantity=quantity,
            stop_loss=Decimal(str(signal.sl)),
            take_profit=Decimal(str(signal.tp)),
            leverage=signal.leverage if signal.market_type == 'FUTURES' else None,
            status='OPEN'
        )

        logger.info(f"📄 Created paper trade: {paper_trade.direction} {paper_trade.symbol} @ {paper_trade.entry_price}")
        return paper_trade

    def check_and_close_trades(self, current_prices: Dict[str, Decimal]) -> List[PaperTrade]:
        """
        Check all open paper trades against current prices and close if SL/TP hit.

        Args:
            current_prices: Dictionary of symbol: current_price

        Returns:
            List of closed trades
        """
        closed_trades = []
        open_trades = PaperTrade.objects.filter(status='OPEN')

        for trade in open_trades:
            current_price = current_prices.get(trade.symbol)
            if not current_price:
                continue

            current_price = Decimal(str(current_price))

            # Check Stop Loss
            if trade.check_stop_loss_hit(current_price):
                trade.close_trade(current_price, status='CLOSED_SL')
                logger.info(f"🔴 Stop Loss hit: {trade.symbol} @ {current_price} (Loss: {trade.profit_loss:.2f} USDT)")
                closed_trades.append(trade)

            # Check Take Profit
            elif trade.check_take_profit_hit(current_price):
                trade.close_trade(current_price, status='CLOSED_TP')
                logger.info(f"🟢 Take Profit hit: {trade.symbol} @ {current_price} (Profit: {trade.profit_loss:.2f} USDT)")
                closed_trades.append(trade)

        return closed_trades

    def close_trade_manually(self, trade_id: int, current_price: Decimal) -> Optional[PaperTrade]:
        """
        Manually close a paper trade.

        Args:
            trade_id: ID of trade to close
            current_price: Current market price

        Returns:
            Closed PaperTrade or None
        """
        try:
            trade = PaperTrade.objects.get(id=trade_id, status='OPEN')
            trade.close_trade(Decimal(str(current_price)), status='CLOSED_MANUAL')
            logger.info(f"✋ Manually closed: {trade.symbol} @ {current_price}")
            return trade
        except PaperTrade.DoesNotExist:
            logger.error(f"Trade {trade_id} not found or not open")
            return None

    def cancel_trade(self, trade_id: int) -> Optional[PaperTrade]:
        """
        Cancel a pending paper trade.

        Args:
            trade_id: ID of trade to cancel

        Returns:
            Cancelled PaperTrade or None
        """
        try:
            trade = PaperTrade.objects.get(id=trade_id, status='PENDING')
            trade.status = 'CANCELLED'
            trade.save()
            logger.info(f"❌ Cancelled trade: {trade.symbol}")
            return trade
        except PaperTrade.DoesNotExist:
            logger.error(f"Trade {trade_id} not found or not pending")
            return None

    def get_open_trades(self, user=None) -> List[PaperTrade]:
        """
        Get all open paper trades.

        Args:
            user: Filter by user (None for all system trades)

        Returns:
            List of open PaperTrades
        """
        queryset = PaperTrade.objects.filter(status='OPEN')
        if user:
            queryset = queryset.filter(user=user)
        return list(queryset)

    def get_trade_history(self, user=None, limit=100) -> List[PaperTrade]:
        """
        Get trade history.

        Args:
            user: Filter by user
            limit: Maximum number of trades to return

        Returns:
            List of PaperTrades
        """
        queryset = PaperTrade.objects.all()
        if user:
            queryset = queryset.filter(user=user)
        return list(queryset[:limit])

    def calculate_performance_metrics(self, user=None, days=None) -> Dict:
        """
        Calculate performance metrics for paper trading.

        Args:
            user: Filter by user
            days: Filter by last N days

        Returns:
            Dictionary with performance metrics
        """
        queryset = PaperTrade.objects.all()

        if user:
            queryset = queryset.filter(user=user)

        if days:
            from datetime import timedelta
            start_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__gte=start_date)

        # Get closed trades for win rate calculation
        closed_trades = queryset.filter(status__startswith='CLOSED')

        total_trades = closed_trades.count()
        if total_trades == 0:
            return {
                'total_trades': 0,
                'open_trades': queryset.filter(status='OPEN').count(),
                'win_rate': 0,
                'total_profit_loss': 0,
                'avg_profit_loss': 0,
                'best_trade': 0,
                'worst_trade': 0,
                'avg_duration_hours': 0,
                'profitable_trades': 0,
                'losing_trades': 0,
            }

        # Calculate metrics
        profitable_trades = closed_trades.filter(profit_loss__gt=0).count()
        losing_trades = closed_trades.filter(profit_loss__lt=0).count()
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0

        aggregates = closed_trades.aggregate(
            total_pnl=Sum('profit_loss'),
            avg_pnl=Avg('profit_loss'),
        )

        # Get best and worst trades separately
        best_trade = closed_trades.order_by('-profit_loss').first()
        worst_trade = closed_trades.order_by('profit_loss').first()

        # Calculate average duration
        trades_with_duration = closed_trades.exclude(
            Q(entry_time__isnull=True) | Q(exit_time__isnull=True)
        )
        durations = [
            (t.exit_time - t.entry_time).total_seconds() / 3600
            for t in trades_with_duration
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            'total_trades': total_trades,
            'open_trades': queryset.filter(status='OPEN').count(),
            'win_rate': round(win_rate, 2),
            'total_profit_loss': float(aggregates['total_pnl'] or 0),
            'avg_profit_loss': float(aggregates['avg_pnl'] or 0),
            'best_trade': float(best_trade.profit_loss if best_trade else 0),
            'worst_trade': float(worst_trade.profit_loss if worst_trade else 0),
            'avg_duration_hours': round(avg_duration, 2),
            'profitable_trades': profitable_trades,
            'losing_trades': losing_trades,
        }

    def get_trades_by_symbol(self, symbol: str, user=None) -> List[PaperTrade]:
        """
        Get all trades for a specific symbol.

        Args:
            symbol: Trading pair symbol
            user: Filter by user

        Returns:
            List of PaperTrades
        """
        queryset = PaperTrade.objects.filter(symbol=symbol)
        if user:
            queryset = queryset.filter(user=user)
        return list(queryset)

    def get_current_positions_value(self, current_prices: Dict[str, Decimal], user=None) -> Dict:
        """
        Calculate current value of all open positions.

        Args:
            current_prices: Dictionary of symbol: current_price
            user: Filter by user

        Returns:
            Dictionary with position values and unrealized P/L
        """
        open_trades = self.get_open_trades(user)

        total_investment = Decimal('0')
        total_current_value = Decimal('0')
        positions = []

        for trade in open_trades:
            current_price = current_prices.get(trade.symbol)
            if not current_price:
                continue

            current_price = Decimal(str(current_price))
            unrealized_pnl, unrealized_pnl_pct = trade.calculate_profit_loss(current_price)

            total_investment += trade.position_size
            current_value = trade.position_size + Decimal(str(unrealized_pnl))
            total_current_value += current_value

            positions.append({
                'trade_id': trade.id,
                'symbol': trade.symbol,
                'direction': trade.direction,
                'entry_price': float(trade.entry_price),
                'current_price': float(current_price),
                'position_size': float(trade.position_size),
                'current_value': float(current_value),
                'unrealized_pnl': float(unrealized_pnl),
                'unrealized_pnl_pct': float(unrealized_pnl_pct),
            })

        return {
            'total_investment': float(total_investment),
            'total_current_value': float(total_current_value),
            'total_unrealized_pnl': float(total_current_value - total_investment),
            'positions': positions,
        }


# Global instance
paper_trading_service = PaperTradingService()
