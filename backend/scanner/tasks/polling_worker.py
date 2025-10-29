"""Binance data polling worker with async support."""
import asyncio
import logging
from typing import List, Dict, Set
from datetime import datetime
import sys
import os

# Django will be set up before import
logger = logging.getLogger(__name__)


class BinancePollingWorker:
    """Async worker for polling Binance data and generating signals."""

    def __init__(
        self,
        interval: str = '5m',
        batch_size: int = 20,
        poll_interval: int = 60,
        min_confidence: float = 0.7,
        top_pairs: int = 50
    ):
        """
        Initialize polling worker.

        Args:
            interval: Candlestick interval ('5m', '15m', etc.)
            batch_size: Number of symbols to process concurrently
            poll_interval: Seconds between polling cycles
            min_confidence: Minimum confidence for signal generation
            top_pairs: Number of top volume pairs to monitor
        """
        self.interval = interval
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self.top_pairs = top_pairs
        self.min_confidence = min_confidence
        self.client = None
        self.signal_generator = None
        self.dispatcher = None
        self.processed_signals: Set[str] = set()
        self.running = False

    async def start(self):
        """Start the polling worker."""
        from scanner.services.binance_client import BinanceClient
        from scanner.strategies.signal_generator import SignalGenerator
        from scanner.services.dispatcher import signal_dispatcher

        self.client = BinanceClient()
        self.signal_generator = SignalGenerator(min_confidence=self.min_confidence)
        self.dispatcher = signal_dispatcher
        self.running = True

        logger.info(
            f"Starting Binance polling worker "
            f"(interval={self.interval}, min_confidence={self.min_confidence})"
        )

        try:
            async with self.client:
                # Get all USDT pairs
                usdt_pairs = await self.client.get_usdt_pairs()
                logger.info(f"Found {len(usdt_pairs)} USDT pairs")

                # Filter to top volume pairs
                top_pairs = await self._get_top_volume_pairs(usdt_pairs)
                logger.info(f"Selected top {len(top_pairs)} pairs by 24h volume")

                # Broadcast status
                self.dispatcher.broadcast_scanner_status(
                    'running',
                    f"Monitoring {len(top_pairs)} pairs"
                )

                # Start polling loop
                while self.running:
                    try:
                        await self._polling_cycle(top_pairs)
                        logger.info(
                            f"Polling cycle completed. "
                            f"Sleeping for {self.poll_interval}s"
                        )
                        await asyncio.sleep(self.poll_interval)
                    except Exception as e:
                        logger.error(f"Error in polling cycle: {e}", exc_info=True)
                        await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"Fatal error in polling worker: {e}", exc_info=True)
            self.dispatcher.broadcast_scanner_status('error', str(e))
        finally:
            logger.info("Polling worker stopped")
            self.dispatcher.broadcast_scanner_status('stopped')

    async def stop(self):
        """Stop the polling worker."""
        logger.info("Stopping polling worker...")
        self.running = False

    async def _get_top_volume_pairs(self, pairs: List[str]) -> List[str]:
        """Get top N pairs by 24h quote volume."""
        try:
            volume_data = []

            # Fetch 24h ticker data in batches
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

            # Sort by volume and return top N
            volume_data.sort(key=lambda x: x[1], reverse=True)
            top_symbols = [symbol for symbol, _ in volume_data[:self.top_pairs]]

            logger.info(
                f"Top 3 pairs by volume: "
                f"{', '.join([f'{s} (${v/1e6:.1f}M)' for s, v in volume_data[:3]])}"
            )

            return top_symbols

        except Exception as e:
            logger.error(f"Error getting top volume pairs: {e}")
            return pairs[:self.top_pairs]

    async def _polling_cycle(self, symbols: List[str]):
        """Execute one polling cycle for all symbols."""
        from scanner.indicators.indicator_utils import (
            klines_to_dataframe,
            calculate_all_indicators
        )

        cycle_start = datetime.now()
        logger.info(f"Starting polling cycle at {cycle_start.strftime('%H:%M:%S')}")

        # Fetch klines for all symbols
        klines_data = await self.client.batch_get_klines(
            symbols,
            interval=self.interval,
            limit=200,  # Need enough data for EMA200
            batch_size=self.batch_size
        )

        logger.info(f"Fetched klines for {len(klines_data)}/{len(symbols)} symbols")

        # Process each symbol
        signals_generated = 0
        errors = 0

        for symbol, klines in klines_data.items():
            try:
                # Convert to DataFrame
                df = klines_to_dataframe(klines)

                if len(df) < 200:
                    logger.debug(f"{symbol}: Not enough data ({len(df)} candles)")
                    continue

                # Calculate indicators
                df = calculate_all_indicators(df)

                # Generate signal
                signal = self.signal_generator.generate_signal(
                    symbol,
                    df,
                    self.interval
                )

                if signal:
                    # Check for duplicate
                    signal_key = (
                        f"{symbol}_{signal['direction']}_{signal['timeframe']}"
                    )

                    if signal_key not in self.processed_signals:
                        self.processed_signals.add(signal_key)
                        signals_generated += 1

                        logger.info(
                            f"🚀 {signal['direction']} signal for {symbol}: "
                            f"Entry=${signal['entry']}, "
                            f"Confidence={float(signal['confidence'])*100:.1f}%"
                        )

                        # Broadcast via WebSocket
                        self.dispatcher.broadcast_signal(signal)

                        # Save to database
                        await self._save_signal_to_db(signal)
                    else:
                        logger.debug(f"Skipping duplicate: {signal_key}")

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                errors += 1
                continue

        # Clean up old signals from tracking set
        if len(self.processed_signals) > 1000:
            self.processed_signals = set(list(self.processed_signals)[-500:])

        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        logger.info(
            f"✅ Cycle completed in {cycle_duration:.2f}s. "
            f"Signals: {signals_generated}, Errors: {errors}"
        )

    async def _save_signal_to_db(self, signal_data: Dict):
        """Save signal to database using Django ORM."""
        try:
            from asgiref.sync import sync_to_async
            from signals.models import Signal, Symbol

            @sync_to_async
            def get_or_create_symbol(symbol_name):
                symbol, _ = Symbol.objects.get_or_create(
                    symbol=symbol_name,
                    defaults={
                        'base_asset': symbol_name[:-4],  # Remove 'USDT'
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

            logger.debug(f"Saved {signal_data['symbol']} to database")

        except Exception as e:
            logger.error(f"Error saving signal to DB: {e}")


async def run_worker():
    """Main entry point for running the worker."""
    import django
    import os

    # Setup Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

    # Create worker with environment config
    worker = BinancePollingWorker(
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
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
