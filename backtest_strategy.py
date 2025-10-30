#!/usr/bin/env python3
"""
Simple Backtest Engine for Mean Reversion Strategy
Uses downloaded Binance historical data
"""

import csv
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict
import json


@dataclass
class Trade:
    """Represents a single trade"""
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime]
    exit_price: Optional[float]
    direction: str  # 'LONG' or 'SHORT'
    size: float
    stop_loss: float
    take_profit: float
    exit_reason: Optional[str]  # 'TP', 'SL', 'SIGNAL_CLOSE'
    pnl: Optional[float]
    pnl_pct: Optional[float]

    def is_closed(self) -> bool:
        return self.exit_time is not None


@dataclass
class BacktestConfig:
    """Backtest configuration"""
    symbol: str
    volatility_level: str
    initial_capital: float = 1000.0
    position_size_pct: float = 0.95  # Use 95% of capital per trade

    # Mean reversion strategy parameters
    long_rsi_min: float = 25.0
    long_rsi_max: float = 35.0
    short_rsi_min: float = 65.0
    short_rsi_max: float = 75.0
    adx_min: float = 22.0

    # Risk management (volatility-aware)
    sl_atr_multiplier: float = 1.5
    tp_atr_multiplier: float = 2.5


class Indicators:
    """Calculate technical indicators"""

    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return None

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        if len(gains) < period:
            return None

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
        """Calculate ATR"""
        if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
            return None

        true_ranges = []
        for i in range(1, len(closes)):
            high = highs[i]
            low = lows[i]
            prev_close = closes[i-1]

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return None

        return sum(true_ranges[-period:]) / period

    @staticmethod
    def adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
        """Calculate ADX (simplified)"""
        if len(highs) < period + 1:
            return None

        # Calculate directional movement
        plus_dm = []
        minus_dm = []

        for i in range(1, len(highs)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]

            plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0)
            minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0)

        if len(plus_dm) < period:
            return None

        # Calculate ATR for normalization
        atr = Indicators.atr(highs, lows, closes, period)
        if atr is None or atr == 0:
            return None

        # Calculate directional indicators
        plus_di = (sum(plus_dm[-period:]) / period) / atr * 100
        minus_di = (sum(minus_dm[-period:]) / period) / atr * 100

        # Calculate DX
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0

        return dx


class BacktestEngine:
    """Main backtest engine"""

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.capital = config.initial_capital
        self.trades: List[Trade] = []
        self.open_trade: Optional[Trade] = None

        # Price history for indicators
        self.closes = []
        self.highs = []
        self.lows = []
        self.opens = []
        self.timestamps = []

    def load_data(self, csv_path: str) -> List[Dict]:
        """Load historical data from CSV"""
        data = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append({
                    'datetime': datetime.fromisoformat(row['datetime']),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume'])
                })
        return data

    def check_signal(self) -> Optional[str]:
        """Check if there's a trading signal"""
        if len(self.closes) < 50:  # Need enough data for indicators
            return None

        rsi = Indicators.rsi(self.closes)
        adx = Indicators.adx(self.highs, self.lows, self.closes)

        if rsi is None or adx is None:
            return None

        # Check ADX threshold
        if adx < self.config.adx_min:
            return None

        # LONG signal: RSI oversold (mean reversion)
        if self.config.long_rsi_min <= rsi <= self.config.long_rsi_max:
            return 'LONG'

        # SHORT signal: RSI overbought (mean reversion)
        if self.config.short_rsi_min <= rsi <= self.config.short_rsi_max:
            return 'SHORT'

        return None

    def open_position(self, candle: Dict, direction: str):
        """Open a new position"""
        if self.open_trade is not None:
            return  # Already have open position

        atr = Indicators.atr(self.highs, self.lows, self.closes)
        if atr is None:
            return

        entry_price = candle['close']

        # Calculate position size
        position_value = self.capital * self.config.position_size_pct
        size = position_value / entry_price

        # Calculate SL and TP based on ATR
        if direction == 'LONG':
            stop_loss = entry_price - (atr * self.config.sl_atr_multiplier)
            take_profit = entry_price + (atr * self.config.tp_atr_multiplier)
        else:  # SHORT
            stop_loss = entry_price + (atr * self.config.sl_atr_multiplier)
            take_profit = entry_price - (atr * self.config.tp_atr_multiplier)

        self.open_trade = Trade(
            entry_time=candle['datetime'],
            entry_price=entry_price,
            exit_time=None,
            exit_price=None,
            direction=direction,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            exit_reason=None,
            pnl=None,
            pnl_pct=None
        )

    def check_exit(self, candle: Dict) -> bool:
        """Check if position should be closed"""
        if self.open_trade is None:
            return False

        current_price = candle['close']
        high = candle['high']
        low = candle['low']

        if self.open_trade.direction == 'LONG':
            # Check stop loss
            if low <= self.open_trade.stop_loss:
                self.close_position(self.open_trade.stop_loss, candle['datetime'], 'SL')
                return True

            # Check take profit
            if high >= self.open_trade.take_profit:
                self.close_position(self.open_trade.take_profit, candle['datetime'], 'TP')
                return True

        else:  # SHORT
            # Check stop loss
            if high >= self.open_trade.stop_loss:
                self.close_position(self.open_trade.stop_loss, candle['datetime'], 'SL')
                return True

            # Check take profit
            if low <= self.open_trade.take_profit:
                self.close_position(self.open_trade.take_profit, candle['datetime'], 'TP')
                return True

        # Check for opposite signal (early exit)
        signal = self.check_signal()
        if signal and signal != self.open_trade.direction:
            self.close_position(current_price, candle['datetime'], 'SIGNAL_CLOSE')
            return True

        return False

    def close_position(self, exit_price: float, exit_time: datetime, reason: str):
        """Close the open position"""
        if self.open_trade is None:
            return

        # Calculate PnL
        if self.open_trade.direction == 'LONG':
            pnl_pct = (exit_price - self.open_trade.entry_price) / self.open_trade.entry_price * 100
        else:  # SHORT
            pnl_pct = (self.open_trade.entry_price - exit_price) / self.open_trade.entry_price * 100

        pnl = self.capital * (pnl_pct / 100)

        # Update capital
        self.capital += pnl

        # Update trade
        self.open_trade.exit_time = exit_time
        self.open_trade.exit_price = exit_price
        self.open_trade.exit_reason = reason
        self.open_trade.pnl = pnl
        self.open_trade.pnl_pct = pnl_pct

        self.trades.append(self.open_trade)
        self.open_trade = None

    def run(self, csv_path: str):
        """Run the backtest"""
        print(f"\n{'='*70}")
        print(f"BACKTESTING: {self.config.symbol} ({self.config.volatility_level} VOLATILITY)")
        print(f"{'='*70}")

        data = self.load_data(csv_path)
        print(f"Loaded {len(data)} candles from {data[0]['datetime']} to {data[-1]['datetime']}")
        print(f"Initial capital: ${self.config.initial_capital:.2f}")
        print(f"Strategy: Mean Reversion (RSI {self.config.long_rsi_min}-{self.config.long_rsi_max} / {self.config.short_rsi_min}-{self.config.short_rsi_max})")
        print(f"Risk: SL={self.config.sl_atr_multiplier}x ATR, TP={self.config.tp_atr_multiplier}x ATR, ADX>{self.config.adx_min}")
        print()

        # Process each candle
        for i, candle in enumerate(data):
            # Update price history
            self.timestamps.append(candle['datetime'])
            self.closes.append(candle['close'])
            self.highs.append(candle['high'])
            self.lows.append(candle['low'])
            self.opens.append(candle['open'])

            # Check if we need to exit open position
            if self.open_trade:
                self.check_exit(candle)

            # Check for new signal (only if no open position)
            if self.open_trade is None:
                signal = self.check_signal()
                if signal:
                    self.open_position(candle, signal)

        # Close any remaining open position at last price
        if self.open_trade:
            self.close_position(data[-1]['close'], data[-1]['datetime'], 'END_OF_DATA')

        # Generate report
        self.print_results()

    def print_results(self):
        """Print backtest results"""
        if not self.trades:
            print("[WARNING] No trades executed during backtest period")
            print("This could mean:")
            print("  - RSI never reached extreme levels (25-35 for LONG, 65-75 for SHORT)")
            print("  - ADX was below threshold (no strong trends)")
            print("  - Consider adjusting strategy parameters")
            return

        # Calculate statistics
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]

        win_rate = len(winning_trades) / total_trades * 100
        total_pnl = sum(t.pnl for t in self.trades)
        total_pnl_pct = (self.capital - self.config.initial_capital) / self.config.initial_capital * 100

        avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0

        profit_factor = abs(sum(t.pnl for t in winning_trades) / sum(t.pnl for t in losing_trades)) if losing_trades and sum(t.pnl for t in losing_trades) != 0 else float('inf')

        # Calculate max drawdown
        peak_capital = self.config.initial_capital
        max_drawdown = 0
        running_capital = self.config.initial_capital

        for trade in self.trades:
            running_capital += trade.pnl
            if running_capital > peak_capital:
                peak_capital = running_capital
            drawdown = (peak_capital - running_capital) / peak_capital * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # Exit reasons
        tp_exits = len([t for t in self.trades if t.exit_reason == 'TP'])
        sl_exits = len([t for t in self.trades if t.exit_reason == 'SL'])
        signal_exits = len([t for t in self.trades if t.exit_reason == 'SIGNAL_CLOSE'])

        # Print summary
        print(f"{'='*70}")
        print(f"BACKTEST RESULTS")
        print(f"{'='*70}")
        print()

        print(f"PERFORMANCE SUMMARY:")
        print(f"  Initial Capital:     ${self.config.initial_capital:.2f}")
        print(f"  Final Capital:       ${self.capital:.2f}")
        print(f"  Total PnL:           ${total_pnl:.2f} ({total_pnl_pct:+.2f}%)")
        print(f"  Max Drawdown:        {max_drawdown:.2f}%")
        print()

        print(f"TRADE STATISTICS:")
        print(f"  Total Trades:        {total_trades}")
        print(f"  Winning Trades:      {len(winning_trades)} ({win_rate:.1f}%)")
        print(f"  Losing Trades:       {len(losing_trades)} ({100-win_rate:.1f}%)")
        print(f"  Average Win:         ${avg_win:.2f}")
        print(f"  Average Loss:        ${avg_loss:.2f}")
        print(f"  Profit Factor:       {profit_factor:.2f}")
        print()

        print(f"EXIT ANALYSIS:")
        print(f"  Take Profit:         {tp_exits} ({tp_exits/total_trades*100:.1f}%)")
        print(f"  Stop Loss:           {sl_exits} ({sl_exits/total_trades*100:.1f}%)")
        print(f"  Signal Close:        {signal_exits} ({signal_exits/total_trades*100:.1f}%)")
        print()

        # Print individual trades
        print(f"TRADE HISTORY:")
        print(f"{'No':<4} {'Direction':<6} {'Entry':<20} {'Exit':<20} {'PnL':<10} {'Reason':<12}")
        print(f"{'-'*70}")

        for i, trade in enumerate(self.trades[:20], 1):  # Show first 20 trades
            print(f"{i:<4} {trade.direction:<6} "
                  f"{trade.entry_time.strftime('%Y-%m-%d %H:%M'):<20} "
                  f"{trade.exit_time.strftime('%Y-%m-%d %H:%M'):<20} "
                  f"${trade.pnl:>+7.2f} ({trade.pnl_pct:>+5.1f}%)  {trade.exit_reason:<12}")

        if len(self.trades) > 20:
            print(f"... ({len(self.trades) - 20} more trades)")

        print(f"{'='*70}")


def run_backtest_suite():
    """Run backtests for all downloaded symbols"""

    print("="*70)
    print("BINANCE FUTURES STRATEGY BACKTEST SUITE")
    print("Mean Reversion Strategy with Volatility-Aware Parameters")
    print("="*70)

    # Configuration for each volatility level
    configs = [
        # High volatility (DOGE)
        BacktestConfig(
            symbol='DOGEUSDT',
            volatility_level='HIGH',
            initial_capital=1000.0,
            sl_atr_multiplier=2.0,  # Wider stops for high volatility
            tp_atr_multiplier=3.5,  # Larger targets
            adx_min=18.0  # Lower ADX threshold
        ),

        # Medium volatility (SOL, ADA)
        BacktestConfig(
            symbol='SOLUSDT',
            volatility_level='MEDIUM',
            initial_capital=1000.0,
            sl_atr_multiplier=1.5,  # OPTIMAL for medium volatility
            tp_atr_multiplier=2.5,
            adx_min=22.0
        ),
        BacktestConfig(
            symbol='ADAUSDT',
            volatility_level='MEDIUM',
            initial_capital=1000.0,
            sl_atr_multiplier=1.5,
            tp_atr_multiplier=2.5,
            adx_min=22.0
        ),

        # Low volatility (BTC, ETH)
        BacktestConfig(
            symbol='BTCUSDT',
            volatility_level='LOW',
            initial_capital=1000.0,
            sl_atr_multiplier=1.0,  # Tighter stops for low volatility
            tp_atr_multiplier=2.0,  # Smaller targets
            adx_min=20.0
        ),
        BacktestConfig(
            symbol='ETHUSDT',
            volatility_level='LOW',
            initial_capital=1000.0,
            sl_atr_multiplier=1.0,
            tp_atr_multiplier=2.0,
            adx_min=20.0
        ),
    ]

    results = []

    for config in configs:
        # Find CSV file
        csv_path = Path('backtest_data') / config.volatility_level.lower() / f'{config.symbol}_5m.csv'

        if not csv_path.exists():
            print(f"\n[ERROR] Data file not found: {csv_path}")
            continue

        # Run backtest
        engine = BacktestEngine(config)
        engine.run(str(csv_path))

        # Store results
        if engine.trades:
            total_pnl_pct = (engine.capital - config.initial_capital) / config.initial_capital * 100
            win_rate = len([t for t in engine.trades if t.pnl > 0]) / len(engine.trades) * 100

            results.append({
                'symbol': config.symbol,
                'volatility': config.volatility_level,
                'trades': len(engine.trades),
                'win_rate': win_rate,
                'final_capital': engine.capital,
                'total_pnl_pct': total_pnl_pct
            })

    # Print comparison summary
    if results:
        print("\n")
        print("="*70)
        print("BACKTEST COMPARISON SUMMARY")
        print("="*70)
        print()
        print(f"{'Symbol':<12} {'Volatility':<10} {'Trades':<8} {'Win Rate':<12} {'PnL':<12}")
        print(f"{'-'*70}")

        for r in results:
            print(f"{r['symbol']:<12} {r['volatility']:<10} {r['trades']:<8} "
                  f"{r['win_rate']:>6.1f}%      ${r['final_capital']:.2f} ({r['total_pnl_pct']:+.1f}%)")

        print(f"{'='*70}")

        # Calculate averages
        avg_win_rate = sum(r['win_rate'] for r in results) / len(results)
        avg_pnl = sum(r['total_pnl_pct'] for r in results) / len(results)

        print()
        print(f"OVERALL AVERAGES:")
        print(f"  Average Win Rate: {avg_win_rate:.1f}%")
        print(f"  Average PnL:      {avg_pnl:+.1f}%")
        print()


if __name__ == '__main__':
    run_backtest_suite()
