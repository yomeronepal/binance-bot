"""Django management command to run the Binance scanner."""
import asyncio
import logging
from django.core.management.base import BaseCommand
from scanner.tasks.polling_worker import BinancePollingWorker

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run the Binance data polling and signal generation scanner'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=str,
            default='5m',
            help='Candlestick interval (5m, 15m, 1h, etc.)'
        )
        parser.add_argument(
            '--poll-interval',
            type=int,
            default=60,
            help='Seconds between polling cycles'
        )
        parser.add_argument(
            '--min-confidence',
            type=float,
            default=0.7,
            help='Minimum confidence score (0.0-1.0)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=20,
            help='Number of concurrent API requests'
        )
        parser.add_argument(
            '--top-pairs',
            type=int,
            default=50,
            help='Number of top volume pairs to monitor'
        )

    def handle(self, *args, **options):
        """Run the scanner."""
        self.stdout.write(
            self.style.SUCCESS('Starting Binance Scanner...')
        )
        self.stdout.write(
            f"Configuration:\n"
            f"  Interval: {options['interval']}\n"
            f"  Poll Interval: {options['poll_interval']}s\n"
            f"  Min Confidence: {options['min_confidence']}\n"
            f"  Batch Size: {options['batch_size']}\n"
            f"  Top Pairs: {options['top_pairs']}\n"
        )

        # Create worker
        worker = BinancePollingWorker(
            interval=options['interval'],
            batch_size=options['batch_size'],
            poll_interval=options['poll_interval'],
            min_confidence=options['min_confidence'],
            top_pairs=options['top_pairs']
        )

        # Run async worker
        try:
            asyncio.run(worker.start())
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('\nShutting down scanner...')
            )
            asyncio.run(worker.stop())
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            )
            raise

        self.stdout.write(
            self.style.SUCCESS('Scanner stopped')
        )
