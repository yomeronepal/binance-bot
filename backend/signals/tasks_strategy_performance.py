"""
Strategy Performance Celery Tasks
Aggregate and cache performance data for the strategy dashboard
"""
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import logging

from signals.services.strategy_performance_service import (
    aggregate_by_volatility,
    aggregate_by_symbol,
    aggregate_by_configuration,
    calculate_sharpe_over_time,
    generate_performance_heatmap,
    get_ml_optimization_results
)
from signals.models_backtest import BacktestRun

logger = logging.getLogger(__name__)


@shared_task(name='signals.aggregate_strategy_performance')
def aggregate_strategy_performance():
    """
    Aggregate strategy performance data and cache it
    Runs periodically to keep dashboard data fresh
    """
    try:
        logger.info("🔄 Starting strategy performance aggregation...")

        # Time ranges to cache
        time_ranges = ['7d', '30d', '90d', 'all']

        for time_range in time_ranges:
            logger.info(f"   Processing time range: {time_range}")

            # Calculate date range
            now = timezone.now()
            if time_range == '7d':
                start_date = now - timedelta(days=7)
            elif time_range == '30d':
                start_date = now - timedelta(days=30)
            elif time_range == '90d':
                start_date = now - timedelta(days=90)
            else:  # all
                start_date = None

            # Get completed backtests
            backtests_query = BacktestRun.objects.filter(status='COMPLETED')
            if start_date:
                backtests_query = backtests_query.filter(created_at__gte=start_date)

            backtests = backtests_query.all()

            if not backtests.exists():
                logger.warning(f"   No completed backtests found for {time_range}")
                continue

            logger.info(f"   Found {backtests.count()} completed backtests")

            # Aggregate data
            try:
                volatility_data = aggregate_by_volatility(backtests)
                symbol_data = aggregate_by_symbol(backtests)
                config_data = aggregate_by_configuration(backtests)
                sharpe_data = calculate_sharpe_over_time(backtests)
                heatmap_data = generate_performance_heatmap(backtests)
                ml_data = get_ml_optimization_results()

                # Cache the results
                cache_key = f'strategy_performance_{time_range}'
                cache_data = {
                    'byVolatility': volatility_data,
                    'bySymbol': symbol_data,
                    'configurations': config_data,
                    'sharpeOverTime': sharpe_data,
                    'heatmap': heatmap_data,
                    'mlOptimization': ml_data,
                    'last_updated': timezone.now().isoformat(),
                    'backtest_count': backtests.count()
                }

                # Cache for 1 hour
                cache.set(cache_key, cache_data, timeout=3600)
                logger.info(f"   ✅ Cached data for {time_range} (expires in 1h)")

            except Exception as e:
                logger.error(f"   ❌ Error aggregating data for {time_range}: {str(e)}")
                continue

        logger.info("✅ Strategy performance aggregation complete")
        return {
            'status': 'success',
            'time_ranges_processed': time_ranges,
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Strategy performance aggregation failed: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='signals.invalidate_strategy_cache')
def invalidate_strategy_cache():
    """
    Invalidate strategy performance cache
    Call this after new backtests complete
    """
    try:
        logger.info("🗑️  Invalidating strategy performance cache...")

        time_ranges = ['7d', '30d', '90d', 'all']
        for time_range in time_ranges:
            cache_key = f'strategy_performance_{time_range}'
            cache.delete(cache_key)

        logger.info("✅ Cache invalidated - will refresh on next request")
        return {'status': 'success', 'timestamp': timezone.now().isoformat()}

    except Exception as e:
        logger.error(f"❌ Cache invalidation failed: {str(e)}")
        return {'status': 'error', 'error': str(e)}


@shared_task(name='signals.refresh_strategy_dashboard')
def refresh_strategy_dashboard(time_range='30d'):
    """
    Refresh strategy dashboard data for specific time range
    Can be called manually or after backtest completion
    """
    try:
        logger.info(f"🔄 Refreshing strategy dashboard for {time_range}...")

        # Invalidate cache
        cache_key = f'strategy_performance_{time_range}'
        cache.delete(cache_key)

        # Aggregate new data
        result = aggregate_strategy_performance.delay()

        logger.info(f"✅ Dashboard refresh triggered (task_id: {result.id})")
        return {
            'status': 'success',
            'task_id': result.id,
            'time_range': time_range,
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Dashboard refresh failed: {str(e)}")
        return {'status': 'error', 'error': str(e)}


@shared_task(name='signals.check_stale_cache')
def check_stale_cache():
    """
    Check if cached data is stale and refresh if needed
    Runs every hour to ensure fresh data
    """
    try:
        logger.info("🔍 Checking for stale cache...")

        time_ranges = ['7d', '30d', '90d', 'all']
        refresh_needed = []

        for time_range in time_ranges:
            cache_key = f'strategy_performance_{time_range}'
            cached_data = cache.get(cache_key)

            if not cached_data:
                logger.info(f"   Cache miss for {time_range} - needs refresh")
                refresh_needed.append(time_range)
            else:
                last_updated = cached_data.get('last_updated')
                logger.info(f"   Cache hit for {time_range} (updated: {last_updated})")

        if refresh_needed:
            logger.info(f"🔄 Refreshing stale caches: {refresh_needed}")
            aggregate_strategy_performance.delay()
        else:
            logger.info("✅ All caches are fresh")

        return {
            'status': 'success',
            'refresh_needed': refresh_needed,
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Stale cache check failed: {str(e)}")
        return {'status': 'error', 'error': str(e)}
