"""Enhanced Binance polling worker with signal engine integration."""
import asyncio
import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class EnhancedPollingWorker:
    """
    Enhanced async worker with signal engine integration.
    Supports dynamic signal updates and real-time broadcasting.
    """

    def __init__(
        self,
        interval: str = '5m',
        batch_size: int = 20,
        poll_interval: int = 60,
        min_confidence: float = 0.7,
        top_pairs: int = 50,
        use_volatility_aware: bool = True
    ):
        """Initialize enhanced polling worker."""
        self.interval = interval
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self.top_pairs = top_pairs
        self.min_confidence = min_confidence
        self.use_volatility_aware = use_volatility_aware
        self.client = None
        self.signal_engine = None
        self.dispatcher = None
        self.running = False
        self.cycle_count = 0

    async def start(self):
        """Start the enhanced polling worker."""
        from scanner.services.binance_client import BinanceClient
        from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig
        from scanner.services.dispatcher import signal_dispatcher

        # Initialize components
        self.client = BinanceClient()
        config = SignalConfig(min_confidence=self.min_confidence)
        self.signal_engine = SignalDetectionEngine(config, use_volatility_aware=self.use_volatility_aware)
        self.dispatcher = signal_dispatcher
        self.running = True

        logger.info(
            f"🚀 Starting Enhanced Polling Worker\n"
            f"   Interval: {self.interval}\n"
            f"   Min Confidence: {self.min_confidence}\n"
            f"   Top Pairs: {self.top_pairs}\n"
            f"   Poll Interval: {self.poll_interval}s\n"
            f"   Volatility Aware: {self.use_volatility_aware}"
        )

        try:
            async with self.client:
                # Get top volume pairs
                usdt_pairs = await self.client.get_usdt_pairs()
                top_pairs = await self._get_top_volume_pairs(usdt_pairs)

                logger.info(f"📊 Monitoring {len(top_pairs)} top volume pairs")

                # Broadcast startup
                self.dispatcher.broadcast_scanner_status(
                    'running',
                    f"Monitoring {len(top_pairs)} pairs with dynamic updates"
                )

                # Main polling loop
                while self.running:
                    try:
                        await self._polling_cycle(top_pairs)
                        self.cycle_count += 1

                        # Periodic cleanup
                        if self.cycle_count % 10 == 0:
                            expired = self.signal_engine.cleanup_expired_signals()
                            if expired:
                                for symbol in expired:
                                    self.dispatcher.broadcast_signal({
                                        'action': 'deleted',
                                        'signal_id': symbol,
                                        'reason': 'expired'
                                    })

                        await asyncio.sleep(self.poll_interval)

                    except Exception as e:
                        logger.error(f"❌ Error in polling cycle: {e}", exc_info=True)
                        await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"💥 Fatal error: {e}", exc_info=True)
            self.dispatcher.broadcast_scanner_status('error', str(e))
        finally:
            logger.info("🛑 Polling worker stopped")
            self.dispatcher.broadcast_scanner_status('stopped')

    async def stop(self):
        """Stop the polling worker."""
        logger.info("Stopping enhanced polling worker...")
        self.running = False

    async def _get_top_volume_pairs(self, pairs: List[str]) -> List[str]:
        """Get top N pairs by 24h quote volume."""
        try:
            volume_data = []

            for i in range(0, len(pairs), 50):
                batch = pairs[i:i+50]
                tasks = [self.client.get_24h_ticker(symbol) for symbol in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for symbol, result in zip(batch, results):
                    if isinstance(result, dict):
                        try:
                            volume = float(result.get('quoteVolume', 0))
                            volume_data.append((symbol, volume))
                        except (ValueError, TypeError):
                            pass

                await asyncio.sleep(0.5)

            volume_data.sort(key=lambda x: x[1], reverse=True)
            top_symbols = [symbol for symbol, _ in volume_data[:self.top_pairs]]

            if volume_data:
                logger.info(
                    f"💰 Top 3 by volume: {', '.join([f'{s} (${v/1e6:.1f}M)' for s, v in volume_data[:3]])}"
                )

            return top_symbols

        except Exception as e:
            logger.error(f"Error getting top pairs: {e}")
            return pairs[:self.top_pairs]

    async def _polling_cycle(self, symbols: List[str]):
        """Execute one enhanced polling cycle."""
        cycle_start = datetime.now()
        logger.info(f"🔄 Cycle #{self.cycle_count + 1} starting at {cycle_start.strftime('%H:%M:%S')}")

        # Fetch klines for all symbols
        klines_data = await self.client.batch_get_klines(
            symbols,
            interval=self.interval,
            limit=200,
            batch_size=self.batch_size
        )

        logger.info(f"📥 Fetched data for {len(klines_data)}/{len(symbols)} symbols")

        # Process each symbol through signal engine
        signals_created = 0
        signals_updated = 0
        signals_deleted = 0
        errors = 0

        for symbol, klines in klines_data.items():
            try:
                # Update candle cache
                self.signal_engine.update_candles(symbol, klines)

                # Process symbol and get signal update
                signal_update = self.signal_engine.process_symbol(symbol, self.interval)

                if signal_update:
                    action = signal_update.get('action')

                    if action == 'created':
                        signals_created += 1
                        signal_data = signal_update['signal']

                        # Broadcast new signal
                        self.dispatcher.broadcast_signal(signal_data)

                        # Save to database
                        await self._save_signal_to_db(signal_data)

                        logger.info(
                            f"🆕 {signal_data['direction']} {symbol}: "
                            f"Entry=${signal_data['entry']:.2f}, "
                            f"Conf={signal_data['confidence']:.0%}"
                        )

                    elif action == 'updated':
                        signals_updated += 1
                        signal_data = signal_update['signal']

                        # Broadcast update
                        self._broadcast_signal_update(signal_data)

                        logger.info(
                            f"🔄 Updated {signal_data['direction']} {symbol}: "
                            f"Conf={signal_data['confidence']:.0%}"
                        )

                    elif action == 'deleted':
                        signals_deleted += 1
                        signal_id = signal_update['signal_id']

                        # Broadcast deletion
                        self._broadcast_signal_deletion(signal_id)

                        logger.info(f"❌ Deleted signal: {signal_id}")

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                errors += 1
                continue

        # Cycle summary
        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        active_count = len(self.signal_engine.active_signals)

        logger.info(
            f"✅ Cycle #{self.cycle_count + 1} completed in {cycle_duration:.2f}s\n"
            f"   Created: {signals_created}, Updated: {signals_updated}, "
            f"Deleted: {signals_deleted}, Errors: {errors}\n"
            f"   Active Signals: {active_count}"
        )

        # Broadcast stats
        self.dispatcher.broadcast_scanner_status(
            'running',
            f"Cycle {self.cycle_count + 1}: {active_count} active signals"
        )

    def _broadcast_signal_update(self, signal_data: Dict):
        """Broadcast signal update to WebSocket clients."""
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    'signals_global',
                    {
                        'type': 'signal_updated',
                        'signal': signal_data
                    }
                )
        except Exception as e:
            logger.error(f"Failed to broadcast signal update: {e}")

    def _broadcast_signal_deletion(self, signal_id: str):
        """Broadcast signal deletion to WebSocket clients."""
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    'signals_global',
                    {
                        'type': 'signal_deleted',
                        'signal_id': signal_id
                    }
                )
        except Exception as e:
            logger.error(f"Failed to broadcast signal deletion: {e}")

    async def _save_signal_to_db(self, signal_data: Dict):
        """Save signal to database."""
        try:
            from asgiref.sync import sync_to_async
            from signals.models import Signal, Symbol

            @sync_to_async
            def get_or_create_symbol(symbol_name):
                symbol, _ = Symbol.objects.get_or_create(
                    symbol=symbol_name,
                    defaults={
                        'base_asset': symbol_name[:-4],
                        'quote_asset': 'USDT',
                        'is_active': True
                    }
                )
                return symbol

            @sync_to_async
            def create_signal(symbol_obj, data):
                return Signal.objects.create(
                    symbol=symbol_obj,
                    direction=data['direction'],
                    entry=data['entry'],
                    sl=data['sl'],
                    tp=data['tp'],
                    confidence=data['confidence'],
                    timeframe=data['timeframe'],
                    description=data.get('description', ''),
                    status='ACTIVE'
                )

            symbol_obj = await get_or_create_symbol(signal_data['symbol'])
            await create_signal(symbol_obj, signal_data)

        except Exception as e:
            logger.error(f"Error saving signal to DB: {e}")


async def run_enhanced_worker():
    """Main entry point for enhanced worker."""
    import django
    import os

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

    worker = EnhancedPollingWorker(
        interval=os.getenv('BINANCE_INTERVAL', '5m'),
        batch_size=int(os.getenv('BINANCE_BATCH_SIZE', '20')),
        poll_interval=int(os.getenv('POLLING_INTERVAL', '60')),
        min_confidence=float(os.getenv('MIN_CONFIDENCE', '0.7')),
        top_pairs=int(os.getenv('TOP_PAIRS', '50'))
    )

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        await worker.stop()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        asyncio.run(run_enhanced_worker())
    except KeyboardInterrupt:
        print("\n🛑 Shutting down gracefully...")
