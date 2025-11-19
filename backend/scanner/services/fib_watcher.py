"""
Fibonacci Pullback Price Watcher

Monitors signals waiting for pullback and triggers entry when price enters golden zone.
"""
import logging
from decimal import Decimal
from typing import List, Dict, Optional
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class FibonacciPullbackWatcher:
    """
    Real-time price watcher for Fibonacci pullback signals.

    Monitors signals with status='WAITING_FOR_PULLBACK' and detects
    when current price enters the golden ratio zone (50-61.8%).
    """

    def __init__(self):
        self.dispatcher = None
        self.binance_client = None

    def _get_binance_client(self):
        """Lazy load Binance client to avoid import errors."""
        if self.binance_client is None:
            try:
                from scanner.services.binance_client import BinanceClient
                self.binance_client = BinanceClient()
            except ImportError:
                logger.error("BinanceClient not available")
                raise
        return self.binance_client

    def _get_dispatcher(self):
        """Lazy load dispatcher to avoid import errors."""
        if self.dispatcher is None:
            try:
                from scanner.services.dispatcher import SignalDispatcher
                self.dispatcher = SignalDispatcher()
            except ImportError:
                logger.error("SignalDispatcher not available")
                raise
        return self.dispatcher

    def get_waiting_signals(self) -> List:
        """
        Fetch all signals with status = 'WAITING_FOR_PULLBACK'.

        Returns:
            List of Signal objects
        """
        try:
            from signals.models import Signal
            return list(Signal.objects.filter(
                status='WAITING_FOR_PULLBACK'
            ).select_related('symbol'))
        except Exception as e:
            logger.error(f"Error fetching waiting signals: {e}")
            return []

    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current market price for a symbol.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')

        Returns:
            Current price as float, or None if error
        """
        try:
            client = self._get_binance_client()
            ticker = client.get_ticker_price(symbol)
            return float(ticker['price']) if ticker else None
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    def check_entry_zone(self, signal, current_price: float) -> bool:
        """
        Check if current price is in Fibonacci entry zone.

        For LONG: fib_61_8 <= price <= fib_50
        For SHORT: fib_50 <= price <= fib_61_8

        Args:
            signal: Signal object with Fibonacci metadata
            current_price: Current market price

        Returns:
            True if price in entry zone
        """
        meta = signal.meta
        if not meta or 'fib_50' not in meta or 'fib_61_8' not in meta:
            logger.warning(f"Signal {signal.id} missing Fibonacci metadata")
            return False

        try:
            fib_50 = float(meta['fib_50'])
            fib_61_8 = float(meta['fib_61_8'])

            if signal.direction == 'LONG':
                in_zone = fib_61_8 <= current_price <= fib_50
            else:
                in_zone = fib_50 <= current_price <= fib_61_8

            return in_zone

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error checking entry zone for signal {signal.id}: {e}")
            return False

    @transaction.atomic
    def trigger_entry(self, signal, current_price: float):
        """
        Trigger entry when price enters golden zone.

        Actions:
        1. Update signal status to 'ENTRY_ZONE_REACHED'
        2. Emit WebSocket event 'fib_entry_triggered'
        3. Auto-create paper trade

        Args:
            signal: Signal object
            current_price: Current market price
        """
        logger.info(
            f"🎯 FIBONACCI ENTRY TRIGGERED: {signal.symbol.symbol} {signal.direction} "
            f"at {current_price:.2f} (Zone: {signal.meta.get('fib_61_8'):.2f} - "
            f"{signal.meta.get('fib_50'):.2f})"
        )

        signal.status = 'ENTRY_ZONE_REACHED'
        signal.updated_at = timezone.now()
        signal.save(update_fields=['status', 'updated_at'])

        self.emit_entry_event(signal, current_price)

        paper_trade = self.create_paper_trade(signal, current_price)

        return paper_trade

    def emit_entry_event(self, signal, current_price: float):
        """
        Emit WebSocket event: fib_entry_triggered

        Args:
            signal: Signal object
            current_price: Current market price
        """
        event_data = {
            'type': 'fib_entry_triggered',
            'signal_id': signal.id,
            'symbol': signal.symbol.symbol,
            'side': signal.direction,
            'entry_price': float(current_price),
            'entry_zone': 'golden_ratio',
            'meta': signal.meta,
            'timeframe': signal.timeframe,
            'confidence': float(signal.confidence),
            'timestamp': timezone.now().isoformat()
        }

        try:
            dispatcher = self._get_dispatcher()
            dispatcher.broadcast_signal(event_data)
            logger.info(
                f"✅ Fibonacci entry event broadcasted for "
                f"{signal.symbol.symbol} {signal.direction}"
            )
        except Exception as e:
            logger.error(f"Error broadcasting Fibonacci entry event: {e}")

    def create_paper_trade(self, signal, current_price: float):
        """
        Auto-create paper trade when entry zone reached.

        SL Strategy: Use fib_78_6 level (more conservative)
        TP Strategy: Use standard 9% or Fibonacci extensions

        Args:
            signal: Signal object
            current_price: Entry price

        Returns:
            PaperTrade object or None
        """
        try:
            from signals.models import PaperTrade

            meta = signal.meta
            entry_decimal = Decimal(str(current_price))

            if 'fib_78_6' in meta:
                sl = Decimal(str(meta['fib_78_6']))
            else:
                if signal.direction == 'LONG':
                    sl = entry_decimal * Decimal('0.97')
                else:
                    sl = entry_decimal * Decimal('1.03')

            if signal.direction == 'LONG':
                tp = entry_decimal * Decimal('1.09')
            else:
                tp = entry_decimal * Decimal('0.91')

            paper_trade = PaperTrade.objects.create(
                signal=signal,
                symbol=signal.symbol.symbol,
                direction=signal.direction,
                entry_price=entry_decimal,
                stop_loss=sl,
                take_profit=tp,
                quantity=Decimal('100'),
                position_size=Decimal('10000'),
                status='OPEN',
                entry_time=timezone.now()
            )

            logger.info(
                f"📊 Paper trade created: {signal.symbol.symbol} {signal.direction} "
                f"Entry={current_price:.2f}, SL={sl:.2f}, TP={tp:.2f}"
            )

            return paper_trade

        except Exception as e:
            logger.error(f"Error creating paper trade for Fibonacci entry: {e}")
            return None

    def monitor(self):
        """
        Main monitoring loop - checks all waiting signals.

        Called by Celery task every 10-30 seconds.
        """
        waiting_signals = self.get_waiting_signals()

        if not waiting_signals:
            logger.debug("No signals waiting for Fibonacci pullback")
            return

        logger.info(f"🔍 Monitoring {len(waiting_signals)} Fibonacci pullback signals")

        entries_triggered = 0

        for signal in waiting_signals:
            try:
                current_price = self.get_current_price(signal.symbol.symbol)
                if current_price is None:
                    continue

                in_zone = self.check_entry_zone(signal, current_price)

                if in_zone:
                    self.trigger_entry(signal, current_price)
                    entries_triggered += 1
                else:
                    logger.debug(
                        f"{signal.symbol.symbol}: Price {current_price:.2f} "
                        f"outside zone [{signal.meta.get('fib_61_8'):.2f} - "
                        f"{signal.meta.get('fib_50'):.2f}]"
                    )

            except Exception as e:
                logger.error(f"Error monitoring signal {signal.id}: {e}")
                continue

        if entries_triggered > 0:
            logger.info(f"✅ Triggered {entries_triggered} Fibonacci entries")
