"""
Backtesting Engine
Simulates trading strategy on historical data to evaluate performance.
"""
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BacktestPosition:
    """Represents an open position during backtest."""
    symbol: str
    direction: str
    entry_price: Decimal
    entry_time: datetime
    quantity: Decimal
    position_size: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    leverage: Optional[int] = None
    signal_confidence: Optional[Decimal] = None
    signal_indicators: Dict = field(default_factory=dict)


@dataclass
class BacktestState:
    """Current state of the backtest."""
    equity: Decimal
    cash: Decimal
    open_positions: List[BacktestPosition] = field(default_factory=list)
    closed_trades: List[Dict] = field(default_factory=list)
    peak_equity: Decimal = Decimal('0')
    current_drawdown: Decimal = Decimal('0')
    max_drawdown: Decimal = Decimal('0')


class BacktestEngine:
    """
    Core backtesting engine that simulates trading on historical data.

    Features:
    - Simulates LONG/SHORT trades
    - Tracks stop loss and take profit
    - Calculates performance metrics
    - Handles position sizing
    - Tracks equity curve
    """

    def __init__(
        self,
        initial_capital: Decimal,
        position_size: Decimal,
        strategy_params: Dict,
        max_open_positions: int = 5
    ):
        """
        Initialize backtest engine.

        Args:
            initial_capital: Starting capital in USDT
            position_size: Position size per trade in USDT
            strategy_params: Strategy indicator parameters
            max_open_positions: Maximum simultaneous open positions
        """
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.strategy_params = strategy_params
        self.max_open_positions = max_open_positions

        self.state = BacktestState(
            equity=initial_capital,
            cash=initial_capital,
            peak_equity=initial_capital
        )

        self.metrics_history = []  # For equity curve
        self.trade_count = 0

    def run_backtest(
        self,
        symbols_data: Dict[str, List[Dict]],
        signals: List[Dict]
    ) -> Dict:
        """
        Run backtest on historical data with generated signals.

        Args:
            symbols_data: Dict mapping symbol to list of OHLCV candles
            signals: List of trading signals to execute

        Returns:
            Dictionary with backtest results and metrics
        """
        logger.info(f"🚀 Starting backtest with {len(signals)} signals across {len(symbols_data)} symbols")

        # Sort signals by timestamp
        sorted_signals = sorted(signals, key=lambda s: s['timestamp'])

        # Process each signal chronologically
        for signal in sorted_signals:
            self._process_signal(signal, symbols_data)

        # Close all remaining open positions at end of backtest
        self._close_all_positions(symbols_data)

        # Calculate final metrics
        results = self._calculate_final_metrics()

        logger.info(f"✅ Backtest completed: {results['total_trades']} trades, Win Rate: {results['win_rate']}%")

        return results

    def _process_signal(self, signal: Dict, symbols_data: Dict[str, List[Dict]]):
        """
        Process a trading signal - open position if conditions are met.

        Args:
            signal: Signal dictionary with entry, sl, tp, etc.
            symbols_data: Historical price data for all symbols
        """
        symbol = signal['symbol']

        # Check if we can open new position
        if len(self.state.open_positions) >= self.max_open_positions:
            logger.debug(f"Max positions reached, skipping {symbol}")
            return

        if self.state.cash < self.position_size:
            logger.debug(f"Insufficient cash (${self.state.cash}), skipping {symbol}")
            return

        # Create position - convert signal floats to Decimal for type safety
        entry_price = Decimal(str(signal['entry']))
        stop_loss = Decimal(str(signal['sl']))
        take_profit = Decimal(str(signal['tp']))

        position = BacktestPosition(
            symbol=symbol,
            direction=signal['direction'],
            entry_price=entry_price,
            entry_time=signal['timestamp'],
            quantity=self.position_size / entry_price,
            position_size=self.position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            signal_confidence=Decimal(str(signal.get('confidence', 0.7))),
            signal_indicators=signal.get('indicators', {})
        )

        # Update state
        self.state.open_positions.append(position)
        self.state.cash -= self.position_size

        logger.debug(
            f"📈 Opened {position.direction} {symbol} @ ${position.entry_price} "
            f"(TP: ${position.take_profit}, SL: ${position.stop_loss})"
        )

        # Check all open positions against subsequent price action
        self._update_positions(symbol, symbols_data, signal['timestamp'])

    def _update_positions(self, symbol: str, symbols_data: Dict[str, List[Dict]], current_time: datetime):
        """
        Check open positions against current prices and close if TP/SL hit.

        Args:
            symbol: Current symbol being processed
            symbols_data: All historical price data
            current_time: Current backtest timestamp
        """
        positions_to_close = []

        for position in self.state.open_positions:
            # Get price data for this position's symbol
            if position.symbol not in symbols_data:
                continue

            candles = symbols_data[position.symbol]

            # Find candles after position entry
            relevant_candles = [
                c for c in candles
                if c['timestamp'] >= position.entry_time and c['timestamp'] >= current_time
            ]

            # Check each candle for TP/SL hit
            for candle in relevant_candles:
                # Ensure all price values are Decimal for consistent comparisons
                high = Decimal(str(candle['high'])) if not isinstance(candle['high'], Decimal) else candle['high']
                low = Decimal(str(candle['low'])) if not isinstance(candle['low'], Decimal) else candle['low']
                close_price = Decimal(str(candle['close'])) if not isinstance(candle['close'], Decimal) else candle['close']
                timestamp = candle['timestamp']

                exit_price = None
                exit_status = None

                if position.direction == 'LONG':
                    # Check stop loss first (pessimistic)
                    if low <= position.stop_loss:
                        exit_price = position.stop_loss
                        exit_status = 'CLOSED_SL'
                    # Then check take profit
                    elif high >= position.take_profit:
                        exit_price = position.take_profit
                        exit_status = 'CLOSED_TP'

                elif position.direction == 'SHORT':
                    # Check stop loss first (pessimistic)
                    if high >= position.stop_loss:
                        exit_price = position.stop_loss
                        exit_status = 'CLOSED_SL'
                    # Then check take profit
                    elif low <= position.take_profit:
                        exit_price = position.take_profit
                        exit_status = 'CLOSED_TP'

                # Close position if TP/SL hit
                if exit_price:
                    self._close_position(position, exit_price, timestamp, exit_status)
                    positions_to_close.append(position)
                    break  # Position closed, stop checking candles

        # Remove closed positions
        for position in positions_to_close:
            if position in self.state.open_positions:
                self.state.open_positions.remove(position)

    def _close_position(
        self,
        position: BacktestPosition,
        exit_price: Decimal,
        exit_time: datetime,
        status: str
    ):
        """
        Close a position and record trade results.

        Args:
            position: Position to close
            exit_price: Exit price
            exit_time: Exit timestamp
            status: Close reason (CLOSED_TP, CLOSED_SL, etc.)
        """
        self.trade_count += 1

        # Calculate P/L
        if position.direction == 'LONG':
            pnl = (exit_price - position.entry_price) * position.quantity
        else:  # SHORT
            pnl = (position.entry_price - exit_price) * position.quantity

        pnl_percentage = (pnl / position.position_size) * 100

        # Duration
        duration = exit_time - position.entry_time
        duration_hours = duration.total_seconds() / 3600

        # Calculate risk/reward ratio
        if position.direction == 'LONG':
            risk = position.entry_price - position.stop_loss
            reward = position.take_profit - position.entry_price
        else:  # SHORT
            risk = position.stop_loss - position.entry_price
            reward = position.entry_price - position.take_profit

        risk_reward_ratio = reward / risk if risk > 0 else Decimal('0')

        # Record trade
        # Convert timestamps to datetime objects for Django compatibility
        opened_at = position.entry_time if isinstance(position.entry_time, datetime) else position.entry_time.to_pydatetime()
        closed_at = exit_time if isinstance(exit_time, datetime) else exit_time.to_pydatetime()

        trade = {
            'symbol': position.symbol,
            'direction': position.direction,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'stop_loss': position.stop_loss,
            'take_profit': position.take_profit,
            'position_size': position.position_size,
            'quantity': position.quantity,
            'profit_loss': pnl,
            'profit_loss_percentage': pnl_percentage,
            'opened_at': opened_at,
            'closed_at': closed_at,
            'duration_hours': Decimal(str(duration_hours)),
            'status': status,
            'signal_confidence': position.signal_confidence,
            'signal_indicators': position.signal_indicators,
            'risk_reward_ratio': risk_reward_ratio,
            'leverage': position.leverage,
        }

        self.state.closed_trades.append(trade)

        # Update cash and equity
        self.state.cash += position.position_size + pnl
        self.state.equity = self.state.cash + self._calculate_open_positions_value()

        # Update drawdown
        if self.state.equity > self.state.peak_equity:
            self.state.peak_equity = self.state.equity
            self.state.current_drawdown = Decimal('0')
        else:
            self.state.current_drawdown = self.state.peak_equity - self.state.equity
            if self.state.current_drawdown > self.state.max_drawdown:
                self.state.max_drawdown = self.state.current_drawdown

        # Record metrics snapshot
        # Convert timestamp to ISO format string for JSON serialization
        timestamp_str = exit_time.isoformat() if hasattr(exit_time, 'isoformat') else str(exit_time)
        self.metrics_history.append({
            'timestamp': timestamp_str,
            'equity': float(self.state.equity),
            'cash': float(self.state.cash),
            'open_positions': len(self.state.open_positions),
            'total_trades': self.trade_count,
            'drawdown': float(self.state.current_drawdown)
        })

        logger.debug(
            f"{'✅' if pnl > 0 else '❌'} Closed {position.direction} {position.symbol} @ ${exit_price} "
            f"| P/L: ${pnl:.2f} ({pnl_percentage:.2f}%) | Status: {status}"
        )

    def _close_all_positions(self, symbols_data: Dict[str, List[Dict]]):
        """
        Close all remaining open positions at end of backtest.

        Args:
            symbols_data: Historical price data
        """
        for position in list(self.state.open_positions):
            # Get last available price for this symbol
            if position.symbol in symbols_data:
                candles = symbols_data[position.symbol]
                if candles:
                    last_candle = candles[-1]
                    close_price = Decimal(str(last_candle['close'])) if not isinstance(last_candle['close'], Decimal) else last_candle['close']
                    self._close_position(
                        position,
                        close_price,
                        last_candle['timestamp'],
                        'CLOSED_END'
                    )

        self.state.open_positions = []

    def _calculate_open_positions_value(self) -> Decimal:
        """Calculate current value of all open positions."""
        # For simplicity in backtest, use position size
        # In real scenario, would need current market prices
        return sum(pos.position_size for pos in self.state.open_positions)

    def _calculate_final_metrics(self) -> Dict:
        """
        Calculate comprehensive performance metrics.

        Returns:
            Dictionary with all backtest metrics
        """
        trades = self.state.closed_trades
        total_trades = len(trades)

        if total_trades == 0:
            return self._empty_metrics()

        # Win/Loss counts
        winning_trades = [t for t in trades if t['profit_loss'] > 0]
        losing_trades = [t for t in trades if t['profit_loss'] <= 0]

        # Win rate
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

        # P/L
        total_pnl = sum(t['profit_loss'] for t in trades)
        roi = (total_pnl / self.initial_capital * 100) if self.initial_capital > 0 else 0

        # Avg trade metrics
        avg_profit = sum(t['profit_loss'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['profit_loss'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        avg_trade_duration = sum(t['duration_hours'] for t in trades) / total_trades if trades else 0

        # Drawdown
        max_drawdown_pct = (self.state.max_drawdown / self.initial_capital * 100) if self.initial_capital > 0 else 0

        # Profit factor
        gross_profit = sum(t['profit_loss'] for t in winning_trades) if winning_trades else Decimal('0')
        gross_loss = abs(sum(t['profit_loss'] for t in losing_trades)) if losing_trades else Decimal('0')
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else Decimal('0')

        # Sharpe ratio (simplified - assume 0% risk-free rate)
        returns = [float(t['profit_loss_percentage']) for t in trades]
        avg_return = sum(returns) / len(returns) if returns else 0
        std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5 if returns else 1
        sharpe_ratio = (avg_return / std_return) if std_return > 0 else 0

        # Best/Worst trades
        best_trade = max(trades, key=lambda t: t['profit_loss'])
        worst_trade = min(trades, key=lambda t: t['profit_loss'])

        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': Decimal(str(win_rate)),
            'total_profit_loss': total_pnl,
            'roi': Decimal(str(roi)),
            'final_equity': self.state.equity,
            'initial_capital': self.initial_capital,
            'max_drawdown': self.state.max_drawdown,
            'max_drawdown_percentage': Decimal(str(max_drawdown_pct)),
            'avg_profit_per_trade': total_pnl / total_trades if total_trades > 0 else Decimal('0'),
            'avg_winning_trade': Decimal(str(avg_profit)),
            'avg_losing_trade': Decimal(str(avg_loss)),
            'avg_trade_duration_hours': Decimal(str(avg_trade_duration)),
            'profit_factor': profit_factor,
            'sharpe_ratio': Decimal(str(sharpe_ratio)),
            'best_trade': {
                'symbol': best_trade['symbol'],
                'pnl': best_trade['profit_loss'],
                'pnl_pct': best_trade['profit_loss_percentage']
            },
            'worst_trade': {
                'symbol': worst_trade['symbol'],
                'pnl': worst_trade['profit_loss'],
                'pnl_pct': worst_trade['profit_loss_percentage']
            },
            'equity_curve': self.metrics_history,
            'closed_trades': trades,
        }

    def _empty_metrics(self) -> Dict:
        """Return empty metrics when no trades executed."""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': Decimal('0'),
            'total_profit_loss': Decimal('0'),
            'roi': Decimal('0'),
            'final_equity': self.initial_capital,
            'initial_capital': self.initial_capital,
            'max_drawdown': Decimal('0'),
            'max_drawdown_percentage': Decimal('0'),
            'avg_profit_per_trade': Decimal('0'),
            'avg_winning_trade': Decimal('0'),
            'avg_losing_trade': Decimal('0'),
            'avg_trade_duration_hours': Decimal('0'),
            'profit_factor': Decimal('0'),
            'sharpe_ratio': Decimal('0'),
            'equity_curve': [],
            'closed_trades': [],
        }
