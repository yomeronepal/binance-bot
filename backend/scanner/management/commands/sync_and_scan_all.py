"""Django management command to sync all Binance symbols and scan them."""
import asyncio
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from scanner.services.binance_client import BinanceClient
from signals.models import Symbol
from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig
from scanner.services.klines_to_df import klines_to_dataframe, calculate_all_indicators

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync all Binance USDT symbols to database and scan them for signals'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fetch-only',
            action='store_true',
            help='Only fetch and save symbols, do not scan'
        )
        parser.add_argument(
            '--scan-only',
            action='store_true',
            help='Only scan existing symbols, do not fetch new ones'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of symbols to scan (for testing)'
        )
        parser.add_argument(
            '--interval',
            type=str,
            default='1h',
            help='Timeframe for scanning (default: 1h)'
        )

    def handle(self, *args, **options):
        """Main handler."""
        self.stdout.write(
            self.style.SUCCESS('=' * 70)
        )
        self.stdout.write(
            self.style.SUCCESS('🚀 Binance Symbol Sync & Scanner')
        )
        self.stdout.write(
            self.style.SUCCESS('=' * 70)
        )

        try:
            # Step 1: Fetch and save symbols (unless scan-only)
            if not options['scan_only']:
                symbols = asyncio.run(self.fetch_and_save_symbols())

                if not symbols:
                    self.stdout.write(
                        self.style.ERROR('❌ No symbols fetched. Aborting.')
                    )
                    return
            else:
                # Get existing symbols from database
                symbols = list(Symbol.objects.filter(active=True).values_list('symbol', flat=True))
                self.stdout.write(
                    self.style.SUCCESS(f'📊 Found {len(symbols)} active symbols in database')
                )

            # Step 2: Scan symbols (unless fetch-only)
            if not options['fetch_only']:
                # Apply limit if specified
                if options['limit']:
                    symbols = symbols[:options['limit']]
                    self.stdout.write(
                        self.style.WARNING(f'⚠️  Limiting scan to {options["limit"]} symbols')
                    )

                asyncio.run(self.scan_symbols(symbols, options['interval']))

            self.stdout.write(
                self.style.SUCCESS('\n' + '=' * 70)
            )
            self.stdout.write(
                self.style.SUCCESS('✅ Operation Complete!')
            )
            self.stdout.write(
                self.style.SUCCESS('=' * 70)
            )

        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('\n⚠️  Operation cancelled by user')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Error: {e}')
            )
            import traceback
            traceback.print_exc()
            raise

    async def fetch_and_save_symbols(self):
        """Fetch all USDT symbols from Binance and save to database."""
        self.stdout.write('\n' + '─' * 70)
        self.stdout.write('📡 STEP 1: Fetching Symbols from Binance')
        self.stdout.write('─' * 70)

        async with BinanceClient() as client:
            # Check connectivity
            self.stdout.write('🔌 Checking Binance API connectivity...')
            if not await client.check_connectivity():
                raise ConnectionError("❌ Cannot connect to Binance API")

            self.stdout.write(self.style.SUCCESS('✅ Connected to Binance API'))

            # Get all USDT pairs
            self.stdout.write('\n📊 Fetching all USDT trading pairs...')
            symbols = await client.get_usdt_pairs()

            self.stdout.write(
                self.style.SUCCESS(f'✅ Fetched {len(symbols)} USDT pairs from Binance')
            )

            # Get volume data for sorting
            self.stdout.write('\n💹 Fetching volume data for sorting...')
            volume_data = await self._get_volume_data(client, symbols)

            # Sort by volume
            volume_data.sort(key=lambda x: x[1], reverse=True)
            sorted_symbols = [symbol for symbol, _ in volume_data]

            self.stdout.write(
                self.style.SUCCESS(f'✅ Sorted {len(sorted_symbols)} symbols by volume')
            )

        # Save to database
        self.stdout.write('\n💾 Saving symbols to database...')
        saved, updated = self.save_symbols_with_upsert(sorted_symbols)

        self.stdout.write(
            self.style.SUCCESS(
                f'\n📊 Database Update:\n'
                f'  ├─ New symbols: {saved}\n'
                f'  ├─ Updated symbols: {updated}\n'
                f'  ├─ Total symbols: {len(sorted_symbols)}\n'
                f'  └─ Database total: {Symbol.objects.count()}'
            )
        )

        return sorted_symbols

    async def _get_volume_data(self, client, symbols):
        """Fetch 24h volume data for all symbols."""
        volume_data = []
        batch_size = 50

        total_batches = (len(symbols) + batch_size - 1) // batch_size

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            batch_num = (i // batch_size) + 1

            self.stdout.write(f'  Batch {batch_num}/{total_batches}: Fetching {len(batch)} symbols...')

            tasks = [client.get_24h_ticker(symbol) for symbol in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for symbol, result in zip(batch, results):
                if isinstance(result, dict):
                    try:
                        volume = float(result.get('quoteVolume', 0))
                        volume_data.append((symbol, volume))
                    except (ValueError, TypeError):
                        volume_data.append((symbol, 0))
                else:
                    volume_data.append((symbol, 0))

            # Rate limiting delay
            if i + batch_size < len(symbols):
                await asyncio.sleep(0.5)

        return volume_data

    def save_symbols_with_upsert(self, symbols):
        """Save symbols using bulk upsert for performance."""
        saved_count = 0
        updated_count = 0

        # Use transaction for better performance
        with transaction.atomic():
            for symbol in symbols:
                try:
                    symbol_obj, created = Symbol.objects.update_or_create(
                        symbol=symbol,
                        defaults={
                            'exchange': 'BINANCE',
                            'active': True
                        }
                    )

                    if created:
                        saved_count += 1
                        if saved_count <= 10:  # Only show first 10
                            self.stdout.write(f'    ✅ Created: {symbol}')
                    else:
                        updated_count += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'    ⚠️  Error with {symbol}: {e}')
                    )
                    continue

        if saved_count > 10:
            self.stdout.write(f'    ... and {saved_count - 10} more')

        return saved_count, updated_count

    async def scan_symbols(self, symbols, interval='1h'):
        """Scan all symbols for trading signals."""
        self.stdout.write('\n' + '─' * 70)
        self.stdout.write('🔍 STEP 2: Scanning Symbols for Signals')
        self.stdout.write('─' * 70)

        self.stdout.write(
            f'\n📊 Scanning {len(symbols)} symbols on {interval} timeframe...\n'
        )

        # Initialize signal engine
        config = SignalConfig()
        engine = SignalDetectionEngine(config, use_volatility_aware=False)

        async with BinanceClient() as client:
            # Fetch klines for all symbols
            self.stdout.write('📈 Fetching candlestick data...')

            klines_data = await client.batch_get_klines(
                symbols,
                interval=interval,
                limit=200,
                batch_size=5,
                delay_between_batches=1.5
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Fetched data for {len(klines_data)}/{len(symbols)} symbols\n'
                )
            )

            # Process each symbol
            signals_found = 0
            processed = 0

            for symbol, klines in klines_data.items():
                try:
                    processed += 1

                    # Update engine cache
                    engine.update_candles(symbol, klines)

                    # Process symbol
                    result = engine.process_symbol(symbol, interval)

                    if result and result.get('action') == 'created':
                        signals_found += 1
                        signal_data = result['signal']

                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  🆕 [{processed}/{len(klines_data)}] {symbol}: '
                                f'{signal_data["direction"]} signal at ${signal_data["entry_price"]:.2f} '
                                f'(Confidence: {signal_data["confidence"]:.0%})'
                            )
                        )

                    # Show progress every 50 symbols
                    if processed % 50 == 0:
                        self.stdout.write(
                            f'  📊 Progress: {processed}/{len(klines_data)} symbols processed, '
                            f'{signals_found} signals found'
                        )

                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠️  Error processing {symbol}: {e}')
                    )
                    continue

        self.stdout.write(
            self.style.SUCCESS(
                f'\n📊 Scan Results:\n'
                f'  ├─ Symbols processed: {processed}\n'
                f'  ├─ Signals found: {signals_found}\n'
                f'  └─ Success rate: {(processed/len(symbols)*100):.1f}%'
            )
        )
