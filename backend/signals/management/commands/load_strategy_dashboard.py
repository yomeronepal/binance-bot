"""
Management command to manually load/refresh strategy dashboard data
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.utils import timezone
from signals.tasks_strategy_performance import aggregate_strategy_performance
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Load and cache strategy performance data for the dashboard'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Clear existing cache before loading new data',
        )
        parser.add_argument(
            '--time-range',
            type=str,
            default='all',
            choices=['7d', '30d', '90d', 'all'],
            help='Time range to load (default: all)',
        )
        parser.add_argument(
            '--async',
            action='store_true',
            dest='run_async',
            help='Run aggregation as Celery task (async)',
        )

    def handle(self, *args, **options):
        clear_cache = options['clear_cache']
        time_range = options['time_range']
        run_async = options['run_async']

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Strategy Dashboard Data Loader'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')

        # Clear cache if requested
        if clear_cache:
            self.stdout.write('🗑️  Clearing cache...')
            time_ranges = ['7d', '30d', '90d', 'all']
            for tr in time_ranges:
                cache_key = f'strategy_performance_{tr}'
                cache.delete(cache_key)
            self.stdout.write(self.style.SUCCESS('   ✅ Cache cleared'))
            self.stdout.write('')

        # Run aggregation
        if run_async:
            self.stdout.write(f'🚀 Triggering async aggregation for {time_range}...')
            result = aggregate_strategy_performance.delay()
            self.stdout.write(self.style.SUCCESS(f'   ✅ Task started (ID: {result.id})'))
            self.stdout.write(self.style.WARNING('   ⏳ Check Celery worker logs for progress'))
        else:
            self.stdout.write(f'🔄 Running aggregation for {time_range}...')
            result = aggregate_strategy_performance()

            if result['status'] == 'success':
                self.stdout.write(self.style.SUCCESS('   ✅ Aggregation complete'))
                self.stdout.write(f'   Time ranges processed: {result["time_ranges_processed"]}')
            else:
                self.stdout.write(self.style.ERROR(f'   ❌ Error: {result["error"]}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Done!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        self.stdout.write('Next steps:')
        self.stdout.write('  1. Open http://localhost:3000/strategy-dashboard')
        self.stdout.write('  2. Data will auto-refresh every hour')
        self.stdout.write('  3. Use ?force_refresh=true to bypass cache')
        self.stdout.write('')
