"""
Management command to trigger forex signal scanning
"""
from django.core.management.base import BaseCommand
from scanner.tasks.forex_scanner import (
    scan_forex_signals,
    scan_major_forex_pairs,
    scan_all_forex_pairs,
    scan_forex_scalping
)


class Command(BaseCommand):
    help = 'Scan forex pairs for trading signals'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            type=str,
            default='major',
            choices=['major', 'all', 'scalping', 'custom'],
            help='Scanning mode: major (default), all, scalping, or custom'
        )
        parser.add_argument(
            '--timeframes',
            type=str,
            nargs='+',
            default=None,
            help='Timeframes to scan (15m, 1h, 4h, 1d). Used with --mode=custom'
        )
        parser.add_argument(
            '--pairs',
            type=str,
            nargs='+',
            default=None,
            choices=['major', 'minor', 'exotic'],
            help='Pair types to scan. Used with --mode=custom'
        )
        parser.add_argument(
            '--async',
            action='store_true',
            help='Run task asynchronously via Celery (default: run synchronously)'
        )

    def handle(self, *args, **options):
        mode = options['mode']
        run_async = options['async']

        self.stdout.write(self.style.SUCCESS(f'\n🔍 Starting Forex Signal Scanner (mode: {mode})'))

        try:
            if mode == 'major':
                # Scan major pairs (4h and 1d)
                self.stdout.write('📊 Scanning major forex pairs (4h, 1d timeframes)...')
                if run_async:
                    result = scan_major_forex_pairs.delay()
                    self.stdout.write(self.style.SUCCESS(f'✅ Task queued: {result.id}'))
                    self.stdout.write('Use: docker logs binancebot_celery -f to monitor progress')
                else:
                    result = scan_major_forex_pairs()
                    self._display_results(result)

            elif mode == 'all':
                # Scan all pairs (major + minor)
                self.stdout.write('📊 Scanning all forex pairs (1h, 4h, 1d timeframes)...')
                if run_async:
                    result = scan_all_forex_pairs.delay()
                    self.stdout.write(self.style.SUCCESS(f'✅ Task queued: {result.id}'))
                else:
                    result = scan_all_forex_pairs()
                    self._display_results(result)

            elif mode == 'scalping':
                # Scan for scalping signals
                self.stdout.write('📊 Scanning major pairs for scalping (15m, 1h timeframes)...')
                if run_async:
                    result = scan_forex_scalping.delay()
                    self.stdout.write(self.style.SUCCESS(f'✅ Task queued: {result.id}'))
                else:
                    result = scan_forex_scalping()
                    self._display_results(result)

            elif mode == 'custom':
                # Custom scan
                timeframes = options['timeframes'] or ['4h', '1d']
                pair_types = options['pairs'] or ['major']

                self.stdout.write(
                    f'📊 Custom scan: {", ".join(timeframes)} timeframes, '
                    f'{", ".join(pair_types)} pairs...'
                )

                if run_async:
                    result = scan_forex_signals.delay(timeframes=timeframes, pair_types=pair_types)
                    self.stdout.write(self.style.SUCCESS(f'✅ Task queued: {result.id}'))
                else:
                    result = scan_forex_signals(timeframes=timeframes, pair_types=pair_types)
                    self._display_results(result)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {str(e)}'))
            raise

    def _display_results(self, result):
        """Display scan results"""
        if not result:
            self.stdout.write(self.style.WARNING('\n⚠️  No results returned'))
            return

        if not result.get('success', False):
            error = result.get('error', 'Unknown error')
            self.stdout.write(self.style.ERROR(f'\n❌ Scan failed: {error}'))
            return

        self.stdout.write(self.style.SUCCESS('\n✅ Scan completed successfully!'))
        self.stdout.write(f'\n📊 Summary:')
        self.stdout.write(f'   Pairs scanned: {result.get("pairs_scanned", 0)}')
        self.stdout.write(f'   Timeframes: {", ".join(result.get("timeframes", []))}')
        self.stdout.write(f'   Total signals created: {result.get("total_created", 0)}')
        self.stdout.write(f'   Total signals updated: {result.get("total_updated", 0)}')
        self.stdout.write(f'   Total signals invalidated: {result.get("total_invalidated", 0)}')

        # Show per-timeframe details
        details = result.get('details', {})
        if details:
            self.stdout.write(f'\n📈 Details by timeframe:')
            for timeframe, counts in details.items():
                self.stdout.write(
                    f'   {timeframe}: {counts["created"]} created, '
                    f'{counts["updated"]} updated, {counts["invalidated"]} invalidated'
                )

        self.stdout.write('')
