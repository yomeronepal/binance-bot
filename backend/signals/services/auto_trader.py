"""
Auto-Trading Service
Automatically executes paper trades when new signals are created.
"""
import logging
from decimal import Decimal
from typing import Optional
from django.utils import timezone
from django.db import transaction

from signals.models import Signal, PaperTrade, PaperAccount
from signals.services.paper_trader import paper_trading_service

logger = logging.getLogger(__name__)


class AutoTradingService:
    """
    Service for automatically executing paper trades based on signals.
    """

    def execute_signal(self, signal: Signal) -> Optional[PaperTrade]:
        """
        Automatically execute a trade for a given signal.

        Args:
            signal: Signal to execute trade for

        Returns:
            PaperTrade instance if trade was executed, None otherwise
        """
        # Get all accounts with auto-trading enabled
        accounts = PaperAccount.objects.filter(auto_trading_enabled=True)

        if not accounts.exists():
            logger.debug("No accounts with auto-trading enabled")
            return None

        trades_executed = []

        for account in accounts:
            try:
                trade = self._execute_for_account(account, signal)
                if trade:
                    trades_executed.append(trade)
            except Exception as e:
                logger.error(f"Error executing trade for account {account.id}: {e}", exc_info=True)
                continue

        # Return first successful trade (for logging/notification)
        return trades_executed[0] if trades_executed else None

    def _execute_for_account(self, account: PaperAccount, signal: Signal) -> Optional[PaperTrade]:
        """
        Execute trade for a specific account.

        Args:
            account: PaperAccount to execute trade for
            signal: Signal to trade

        Returns:
            PaperTrade instance if executed, None otherwise
        """
        # Check if signal meets criteria
        if not self._should_trade_signal(account, signal):
            return None

        # Get symbol string
        if hasattr(signal.symbol, 'symbol'):
            symbol_str = signal.symbol.symbol
        else:
            symbol_str = str(signal.symbol)

        # Check if can open trade (no duplicates, within limits)
        if not account.can_open_trade(symbol_str, signal.direction):
            logger.debug(
                f"Cannot open trade for {symbol_str} {signal.direction}: "
                f"duplicate or max trades reached"
            )
            return None

        # Calculate position size
        position_size = account.calculate_position_size(
            signal_confidence=float(signal.confidence)
        )

        # Execute trade using paper trading service
        try:
            with transaction.atomic():
                # Create paper trade
                trade = paper_trading_service.create_paper_trade(
                    signal=signal,
                    user=account.user,
                    position_size=float(position_size)
                )

                # Add position to account
                account.add_position(trade)

                logger.info(
                    f"🤖 AUTO-TRADE: {trade.direction} {trade.symbol} @ {trade.entry_price} "
                    f"(Size: ${position_size}, Conf: {signal.confidence:.0%})"
                )

                return trade

        except ValueError as e:
            # Duplicate trade error
            logger.warning(f"Duplicate trade prevented: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to execute auto-trade: {e}", exc_info=True)
            return None

    def _should_trade_signal(self, account: PaperAccount, signal: Signal) -> bool:
        """
        Check if signal meets account's criteria for auto-trading.

        Args:
            account: PaperAccount with trading settings
            signal: Signal to check

        Returns:
            bool: True if signal should be traded
        """
        # Check if signal is active
        if signal.status != 'ACTIVE':
            return False

        # Check market type
        if signal.market_type == 'SPOT' and not account.auto_trade_spot:
            return False
        if signal.market_type == 'FUTURES' and not account.auto_trade_futures:
            return False

        # Check confidence threshold
        if signal.confidence < float(account.min_signal_confidence):
            logger.debug(
                f"Signal confidence {signal.confidence:.2%} below threshold "
                f"{account.min_signal_confidence:.2%}"
            )
            return False

        return True

    def update_account_equity(self, account: PaperAccount, current_prices: dict):
        """
        Update account equity based on current prices.

        Args:
            account: PaperAccount to update
            current_prices: Dict of symbol: current_price
        """
        from signals.models import PaperTrade

        # Get open trades for this account
        open_trades = PaperTrade.objects.filter(
            user=account.user,
            status='OPEN'
        )

        # Calculate unrealized P/L
        total_unrealized = Decimal('0')
        for trade in open_trades:
            current_price = current_prices.get(trade.symbol)
            if current_price:
                unrealized_pnl, _ = trade.calculate_profit_loss(current_price)
                total_unrealized += Decimal(str(unrealized_pnl))

        # Update account
        account.unrealized_pnl = total_unrealized
        account.update_metrics()

    def close_trade_and_update_account(self, trade: PaperTrade, exit_price: Decimal, status: str):
        """
        Close a trade and update the associated account.

        Args:
            trade: PaperTrade to close
            exit_price: Exit price
            status: Close status (CLOSED_TP, CLOSED_SL, etc.)
        """
        # Close the trade
        trade.close_trade(exit_price, status=status)

        # Update account if user has one
        if trade.user:
            try:
                account = PaperAccount.objects.get(user=trade.user)

                # Remove position from account
                account.remove_position(trade.id)

                # Update account metrics
                account.update_metrics()

                logger.info(
                    f"📊 Account updated: Balance=${account.balance}, "
                    f"Equity=${account.equity}, Total P/L=${account.total_pnl}"
                )

            except PaperAccount.DoesNotExist:
                pass  # User doesn't have auto-trading account


# Global instance
auto_trading_service = AutoTradingService()
