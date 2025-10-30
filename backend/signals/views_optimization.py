"""
API Views for Strategy Optimization & Continuous Learning
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db.models import Avg, Count, Q
from datetime import timedelta
import logging

from signals.models_optimization import (
    StrategyConfigHistory,
    OptimizationRun,
    TradeCounter
)
from signals.serializers import (
    StrategyConfigHistorySerializer,
    OptimizationRunSerializer,
    TradeCounterSerializer
)
from signals.tasks_optimization import auto_optimize_strategy
from signals.services.optimizer_service import compare_configs, update_config_if_better

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def optimization_history(request):
    """
    Get optimization history with filters.

    Query params:
        - volatility: Filter by volatility level (HIGH, MEDIUM, LOW, ALL)
        - time_range: Filter by time (7d, 30d, 90d, all)
        - improvement_only: Show only runs that found improvements (true/false)
        - limit: Number of results (default 50)
    """
    volatility = request.GET.get('volatility')
    time_range = request.GET.get('time_range', '30d')
    improvement_only = request.GET.get('improvement_only', 'false').lower() == 'true'
    limit = int(request.GET.get('limit', 50))

    # Base query
    runs = OptimizationRun.objects.all()

    # Apply filters
    if volatility:
        runs = runs.filter(volatility_level=volatility)

    if improvement_only:
        runs = runs.filter(improvement_found=True)

    # Time range filter
    if time_range != 'all':
        days_map = {'7d': 7, '30d': 30, '90d': 90}
        days = days_map.get(time_range, 30)
        cutoff = timezone.now() - timedelta(days=days)
        runs = runs.filter(started_at__gte=cutoff)

    # Order and limit
    runs = runs.order_by('-started_at')[:limit]

    serializer = OptimizationRunSerializer(runs, many=True)

    # Calculate summary stats
    total_runs = runs.count()
    improvements_found = runs.filter(improvement_found=True).count()
    avg_improvement = runs.filter(improvement_found=True).aggregate(
        avg=Avg('improvement_percentage')
    )['avg'] or 0

    return Response({
        'runs': serializer.data,
        'summary': {
            'total_runs': total_runs,
            'improvements_found': improvements_found,
            'success_rate': (improvements_found / total_runs * 100) if total_runs > 0 else 0,
            'avg_improvement_pct': round(avg_improvement, 2)
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def config_history(request):
    """
    Get strategy configuration history.

    Query params:
        - volatility: Filter by volatility level
        - status: Filter by status (ACTIVE, TESTING, ARCHIVED, FAILED)
        - improved_only: Show only improved configs (true/false)
        - limit: Number of results (default 50)
    """
    volatility = request.GET.get('volatility')
    config_status = request.GET.get('status')
    improved_only = request.GET.get('improved_only', 'false').lower() == 'true'
    limit = int(request.GET.get('limit', 50))

    configs = StrategyConfigHistory.objects.all()

    if volatility:
        configs = configs.filter(volatility_level=volatility)

    if config_status:
        configs = configs.filter(status=config_status)

    if improved_only:
        configs = configs.filter(improved=True)

    configs = configs.order_by('-created_at')[:limit]

    serializer = StrategyConfigHistorySerializer(configs, many=True)

    return Response({
        'configs': serializer.data,
        'count': configs.count()
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def active_configs(request):
    """
    Get currently active configurations for all volatility levels.
    """
    configs = StrategyConfigHistory.objects.filter(status='ACTIVE').order_by('volatility_level')

    serializer = StrategyConfigHistorySerializer(configs, many=True)

    return Response({
        'active_configs': serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trade_counter_status(request):
    """
    Get current trade counter status for all volatility levels.
    Shows progress towards next optimization trigger.
    """
    from signals.services.optimizer_service import TradeCounterService

    counters_data = TradeCounterService.get_counter_status()

    return Response({
        'counters': counters_data,
        'timestamp': timezone.now().isoformat()
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def trigger_manual_optimization(request):
    """
    Manually trigger optimization for specific volatility level.

    POST body:
        {
            "volatility_level": "HIGH",  // or MEDIUM, LOW, ALL
            "lookback_days": 30
        }
    """
    volatility_level = request.data.get('volatility_level', 'ALL')
    lookback_days = int(request.data.get('lookback_days', 30))

    # Validate volatility level
    valid_levels = ['HIGH', 'MEDIUM', 'LOW', 'ALL']
    if volatility_level not in valid_levels:
        return Response(
            {'error': f'Invalid volatility_level. Must be one of: {valid_levels}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate lookback days
    if lookback_days < 7 or lookback_days > 365:
        return Response(
            {'error': 'lookback_days must be between 7 and 365'},
            status=status.HTTP_400_BAD_REQUEST
        )

    logger.info(f"Manual optimization triggered by {request.user.username}")
    logger.info(f"  Volatility: {volatility_level}")
    logger.info(f"  Lookback: {lookback_days} days")

    # Trigger optimization task
    task = auto_optimize_strategy.delay(
        volatility_level=volatility_level,
        lookback_days=lookback_days,
        trigger='MANUAL'
    )

    return Response({
        'status': 'triggered',
        'task_id': task.id,
        'volatility_level': volatility_level,
        'lookback_days': lookback_days,
        'message': f'Optimization task started for {volatility_level} volatility'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def optimization_run_detail(request, run_id):
    """
    Get detailed information about specific optimization run.
    """
    try:
        opt_run = OptimizationRun.objects.get(run_id=run_id)
        serializer = OptimizationRunSerializer(opt_run)

        return Response(serializer.data)

    except OptimizationRun.DoesNotExist:
        return Response(
            {'error': f'Optimization run {run_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def config_comparison(request):
    """
    Compare two configurations.

    Query params:
        - config_a_id: ID of first config
        - config_b_id: ID of second config
    """
    config_a_id = request.GET.get('config_a_id')
    config_b_id = request.GET.get('config_b_id')

    if not config_a_id or not config_b_id:
        return Response(
            {'error': 'Both config_a_id and config_b_id are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        config_a = StrategyConfigHistory.objects.get(id=config_a_id)
        config_b = StrategyConfigHistory.objects.get(id=config_b_id)

        comparison = compare_configs(config_a, config_b)

        return Response(comparison)

    except StrategyConfigHistory.DoesNotExist as e:
        return Response(
            {'error': 'One or both configs not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def learning_metrics(request):
    """
    Get overall learning/optimization metrics and statistics.
    """
    # Total runs
    total_runs = OptimizationRun.objects.count()
    successful_runs = OptimizationRun.objects.filter(status='COMPLETED').count()
    improvement_runs = OptimizationRun.objects.filter(improvement_found=True).count()

    # Average metrics
    avg_improvement = OptimizationRun.objects.filter(
        improvement_found=True
    ).aggregate(avg=Avg('improvement_percentage'))['avg'] or 0

    avg_candidates = OptimizationRun.objects.aggregate(
        avg=Avg('candidates_tested')
    )['avg'] or 0

    # Recent activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_runs = OptimizationRun.objects.filter(started_at__gte=thirty_days_ago).count()
    recent_improvements = OptimizationRun.objects.filter(
        started_at__gte=thirty_days_ago,
        improvement_found=True
    ).count()

    # Active configs
    active_configs = StrategyConfigHistory.objects.filter(status='ACTIVE').count()

    # Config versions
    total_configs = StrategyConfigHistory.objects.count()

    # Performance by volatility
    volatility_stats = []
    for vol_level in ['HIGH', 'MEDIUM', 'LOW']:
        runs_count = OptimizationRun.objects.filter(volatility_level=vol_level).count()
        improvements = OptimizationRun.objects.filter(
            volatility_level=vol_level,
            improvement_found=True
        ).count()

        volatility_stats.append({
            'volatility': vol_level,
            'total_runs': runs_count,
            'improvements_found': improvements,
            'success_rate': (improvements / runs_count * 100) if runs_count > 0 else 0
        })

    return Response({
        'overview': {
            'total_optimization_runs': total_runs,
            'successful_runs': successful_runs,
            'improvements_found': improvement_runs,
            'success_rate': (improvement_runs / total_runs * 100) if total_runs > 0 else 0,
            'avg_improvement_pct': round(avg_improvement, 2),
            'avg_candidates_tested': round(avg_candidates, 1)
        },
        'recent_activity': {
            'runs_last_30_days': recent_runs,
            'improvements_last_30_days': recent_improvements
        },
        'configurations': {
            'total_configs': total_configs,
            'active_configs': active_configs
        },
        'by_volatility': volatility_stats,
        'timestamp': timezone.now().isoformat()
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def apply_config(request, config_id):
    """
    Manually apply a specific configuration.

    POST /api/optimization/config/{config_id}/apply/
    """
    try:
        config = StrategyConfigHistory.objects.get(id=config_id)

        # Mark as active
        config.mark_as_active()

        logger.info(f"Configuration {config.config_name} v{config.version} applied by {request.user.username}")

        return Response({
            'status': 'success',
            'message': f'Configuration {config.config_name} v{config.version} is now active',
            'config': StrategyConfigHistorySerializer(config).data
        })

    except StrategyConfigHistory.DoesNotExist:
        return Response(
            {'error': f'Configuration {config_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
