"""
Strategy Performance Views
Provides aggregated performance analytics from backtest results
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import logging

from signals.models_backtest import BacktestRun
from signals.services.strategy_performance_service import (
    aggregate_by_volatility,
    aggregate_by_symbol,
    aggregate_by_configuration,
    calculate_sharpe_over_time,
    generate_performance_heatmap,
    get_ml_optimization_results
)

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def strategy_performance(request):
    """
    Get aggregated strategy performance analytics
    Uses cached data for performance, falls back to live aggregation
    """
    time_range = request.GET.get('time_range', '30d')
    force_refresh = request.GET.get('force_refresh', 'false').lower() == 'true'

    # Check cache first (unless force refresh)
    cache_key = f'strategy_performance_{time_range}'
    if not force_refresh:
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"✅ Returning cached data for {time_range}")
            return Response(cached_data)

    logger.info(f"🔄 Aggregating fresh data for {time_range}...")

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
        empty_response = {
            'byVolatility': [],
            'bySymbol': [],
            'configurations': [],
            'sharpeOverTime': [],
            'heatmap': [],
            'mlOptimization': None,
            'last_updated': timezone.now().isoformat(),
            'backtest_count': 0
        }
        return Response(empty_response)

    # Aggregate by volatility level
    volatility_data = aggregate_by_volatility(backtests)

    # Aggregate by symbol
    symbol_data = aggregate_by_symbol(backtests)

    # Configuration comparison
    config_data = aggregate_by_configuration(backtests)

    # Sharpe ratio over time
    sharpe_data = calculate_sharpe_over_time(backtests)

    # Performance heatmap
    heatmap_data = generate_performance_heatmap(backtests)

    # ML optimization results (if available)
    ml_data = get_ml_optimization_results()

    response_data = {
        'byVolatility': volatility_data,
        'bySymbol': symbol_data,
        'configurations': config_data,
        'sharpeOverTime': sharpe_data,
        'heatmap': heatmap_data,
        'mlOptimization': ml_data,
        'last_updated': timezone.now().isoformat(),
        'backtest_count': backtests.count()
    }

    # Cache the response for 1 hour
    cache.set(cache_key, response_data, timeout=3600)
    logger.info(f"✅ Cached fresh data for {time_range}")

    return Response(response_data)
