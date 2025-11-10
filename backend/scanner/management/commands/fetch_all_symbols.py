"""Django management command to fetch and save all Binance USDT symbols."""
import asyncio
import logging
from django.core.management.base import BaseCommand
from scanner.services.binance_client import BinanceClient
from signals.models import Symbol

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fetch and save all Binance USDT trading pairs to database'

    def handle(self, *args, **options):
        """Fetch all symbols from Binance and save to database."""
        self.stdout.write(
            self.style.SUCCESS('🔄 Fetching all Binance USDT pairs...')
        )

        try:
            # Run async fetch
            symbols = asyncio.run(self.fetch_symbols())

            if not symbols:
                self.stdout.write(
                    self.style.ERROR('❌ No symbols fetched from Binance')
                )
                return

            self.stdout.write(
                self.style.SUCCESS(f'✅ Fetched {len(symbols)} USDT pairs from Binance')
            )

            # Save to database
            saved, updated = self.save_symbols(symbols)

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n📊 Database Update Complete:\n'
                    f'  - New symbols: {saved}\n'
                    f'  - Updated symbols: {updated}\n'
                    f'  - Total in DB: {Symbol.objects.count()}'
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error: {e}')
            )
            raise

    async def fetch_symbols(self):
        """Fetch all USDT pairs from Binance."""
        async with BinanceClient() as client:
            # Check connectivity
            if not await client.check_connectivity():
                raise ConnectionError("Cannot connect to Binance API")

            # Get all USDT pairs
            symbols = await client.get_usdt_pairs()
            return symbols

    def save_symbols(self, symbols):
        """Save symbols to database."""
        self.stdout.write('💾 Saving symbols to database...')

        saved_count = 0
        updated_count = 0

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
                    self.stdout.write(f'  ✅ Created: {symbol}')
                else:
                    updated_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'  ⚠️  Error saving {symbol}: {e}')
                )
                continue

        return saved_count, updated_count
