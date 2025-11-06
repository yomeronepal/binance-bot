"""
Backtesting API Views
REST API endpoints for backtesting system.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from decimal import Decimal
from datetime import datetime
import logging

from signals.models_backtest import (
    BacktestRun,
    BacktestTrade,
    StrategyOptimization,
    OptimizationRecommendation
)
from signals.serializers_backtest import (
    BacktestRunSerializer,
    BacktestTradeSerializer,
    StrategyOptimizationSerializer,
    OptimizationRecommendationSerializer
)

logger = logging.getLogger(__name__)


class BacktestViewSet(viewsets.ModelViewSet):
    """
    Backtesting API endpoints.

    Endpoints:
    - GET /api/backtest/ - List user's backtests
    - POST /api/backtest/ - Create/run new backtest
    - GET /api/backtest/:id/ - Get backtest details
    - DELETE /api/backtest/:id/ - Delete backtest
    - POST /api/backtest/:id/run/ - Trigger backtest execution
    - GET /api/backtest/:id/trades/ - Get backtest trades
    - GET /api/backtest/:id/metrics/ - Get backtest metrics
    """

    queryset = BacktestRun.objects.all()
    serializer_class = BacktestRunSerializer
    permission_classes = [AllowAny]  # Allow public access

    def get_queryset(self):
        """Return all backtests (public access)."""
        return BacktestRun.objects.all().order_by('-created_at')

    def create(self, request):
        """
        Create and queue a new backtest.

        Request body:
        {
            "name": "BTC Strategy Test",
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "timeframe": "5m",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T23:59:59Z",
            "strategy_params": {
                "rsi_period": 14,
                "ema_fast": 10,
                "ema_slow": 50,
                ...
            },
            "initial_capital": 10000,
            "position_size": 100
        }
        """
        try:
            data = request.data

            # Create backtest run
            backtest_run = BacktestRun.objects.create(
                user=request.user if request.user.is_authenticated else None,
                name=data.get('name', 'Unnamed Backtest'),
                symbols=data.get('symbols', []),
                timeframe=data.get('timeframe', '5m'),
                start_date=datetime.fromisoformat(data['start_date'].replace('Z', '+00:00')),
                end_date=datetime.fromisoformat(data['end_date'].replace('Z', '+00:00')),
                strategy_params=data.get('strategy_params', {}),
                initial_capital=Decimal(str(data.get('initial_capital', 10000))),
                position_size=Decimal(str(data.get('position_size', 100))),
                status='PENDING'
            )

            # Queue for execution
            from scanner.tasks.backtest_tasks import run_backtest_async
            task = run_backtest_async.delay(backtest_run.id)

            logger.info(f"Backtest {backtest_run.id} queued (task: {task.id})")

            return Response({
                'id': backtest_run.id,
                'status': 'PENDING',
                'message': 'Backtest queued for execution',
                'task_id': task.id
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating backtest: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def trades(self, request, pk=None):
        """
        Get all trades for a backtest.

        GET /api/backtest/:id/trades/
        """
        backtest_run = self.get_object()
        trades = backtest_run.trades.all()

        # Apply filters
        direction = request.query_params.get('direction')
        if direction:
            trades = trades.filter(direction=direction)

        status_filter = request.query_params.get('status')
        if status_filter:
            trades = trades.filter(status=status_filter)

        symbol = request.query_params.get('symbol')
        if symbol:
            trades = trades.filter(symbol=symbol)

        serializer = BacktestTradeSerializer(trades, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        """
        Get metrics and equity curve for a backtest.

        GET /api/backtest/:id/metrics/
        """
        backtest_run = self.get_object()

        return Response({
            'id': backtest_run.id,
            'name': backtest_run.name,
            'status': backtest_run.status,
            'metrics': {
                'total_trades': backtest_run.total_trades,
                'winning_trades': backtest_run.winning_trades,
                'losing_trades': backtest_run.losing_trades,
                'win_rate': float(backtest_run.win_rate),
                'total_profit_loss': float(backtest_run.total_profit_loss),
                'roi': float(backtest_run.roi),
                'max_drawdown': float(backtest_run.max_drawdown),
                'max_drawdown_amount': float(backtest_run.max_drawdown_amount),
                'avg_trade_duration_hours': float(backtest_run.avg_trade_duration_hours),
                'avg_profit_per_trade': float(backtest_run.avg_profit_per_trade),
                'sharpe_ratio': float(backtest_run.sharpe_ratio) if backtest_run.sharpe_ratio else None,
                'profit_factor': float(backtest_run.profit_factor) if backtest_run.profit_factor else None,
            },
            'equity_curve': backtest_run.equity_curve,
            'started_at': backtest_run.started_at,
            'completed_at': backtest_run.completed_at,
            'duration_seconds': backtest_run.duration_seconds()
        })

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get summary of all backtests for current user.

        GET /api/backtest/summary/
        """
        backtests = self.get_queryset()

        total_backtests = backtests.count()
        completed = backtests.filter(status='COMPLETED').count()
        running = backtests.filter(status='RUNNING').count()
        failed = backtests.filter(status='FAILED').count()

        # Get best performing backtest
        best_backtest = backtests.filter(status='COMPLETED').order_by('-roi').first()

        return Response({
            'total_backtests': total_backtests,
            'completed': completed,
            'running': running,
            'failed': failed,
            'best_backtest': {
                'id': best_backtest.id,
                'name': best_backtest.name,
                'roi': float(best_backtest.roi),
                'win_rate': float(best_backtest.win_rate)
            } if best_backtest else None
        })

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """
        Retry a failed or stuck backtest.

        POST /api/backtest/:id/retry/
        """
        backtest_run = self.get_object()

        # Only allow retry for FAILED or PENDING backtests
        if backtest_run.status not in ['FAILED', 'PENDING']:
            return Response(
                {'error': f'Cannot retry backtest with status {backtest_run.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Reset backtest to PENDING
            backtest_run.status = 'PENDING'
            backtest_run.error_message = None
            backtest_run.save()

            # Queue for execution
            from scanner.tasks.backtest_tasks import run_backtest_async
            task = run_backtest_async.delay(backtest_run.id)

            logger.info(f"Backtest {backtest_run.id} retry queued (task: {task.id})")

            return Response({
                'id': backtest_run.id,
                'status': 'PENDING',
                'message': 'Backtest queued for retry',
                'task_id': task.id
            })

        except Exception as e:
            logger.error(f"Error retrying backtest: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OptimizationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Strategy Optimization API endpoints.

    Endpoints:
    - GET /api/optimization/ - List optimizations
    - GET /api/optimization/:id/ - Get optimization details
    - POST /api/optimization/run/ - Run parameter optimization
    - GET /api/optimization/best/ - Get best parameters
    """

    queryset = StrategyOptimization.objects.all()
    serializer_class = StrategyOptimizationSerializer
    permission_classes = [AllowAny]  # Allow public access

    def get_queryset(self):
        """Return all optimizations (public access)."""
        return StrategyOptimization.objects.all().order_by('-optimization_score')

    @action(detail=False, methods=['post'])
    def run(self, request):
        """
        Run parameter optimization.

        POST /api/optimization/run/

        Request body:
        {
            "name": "RSI Optimization",
            "symbols": ["BTCUSDT"],
            "timeframe": "5m",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T23:59:59Z",
            "parameter_ranges": {
                "rsi_period": [14, 20, 25, 30],
                "ema_fast": [5, 10, 15, 20],
                "ema_slow": [20, 30, 50, 100]
            },
            "search_method": "grid",
            "max_combinations": 100
        }
        """
        try:
            data = request.data

            # Queue optimization task
            from scanner.tasks.backtest_tasks import run_optimization_async
            task = run_optimization_async.delay(
                user_id=request.user.id if request.user.is_authenticated else None if request.user.is_authenticated else None,
                name=data.get('name', 'Optimization Run'),
                symbols=data.get('symbols', []),
                timeframe=data.get('timeframe', '5m'),
                start_date=data['start_date'],
                end_date=data['end_date'],
                parameter_ranges=data.get('parameter_ranges', {}),
                search_method=data.get('search_method', 'grid'),
                max_combinations=data.get('max_combinations', 100)
            )

            logger.info(f"Optimization task queued: {task.id}")

            return Response({
                'task_id': task.id,
                'status': 'RUNNING',
                'message': 'Optimization task started'
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            logger.error(f"Error starting optimization: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def best(self, request):
        """
        Get best performing parameters.

        GET /api/optimization/best/?top=5
        """
        top_n = int(request.query_params.get('top', 5))
        optimizations = self.get_queryset()[:top_n]

        serializer = self.get_serializer(optimizations, many=True)
        return Response(serializer.data)


class RecommendationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    AI Recommendations API endpoints.

    Endpoints:
    - GET /api/recommendations/ - List recommendations
    - GET /api/recommendations/:id/ - Get recommendation details
    - POST /api/recommendations/generate/ - Generate new recommendations
    - POST /api/recommendations/:id/accept/ - Accept recommendation
    - POST /api/recommendations/:id/reject/ - Reject recommendation
    """

    queryset = OptimizationRecommendation.objects.all()
    serializer_class = OptimizationRecommendationSerializer
    permission_classes = [AllowAny]  # Allow public access

    def get_queryset(self):
        """Return all recommendations (public access)."""
        queryset = OptimizationRecommendation.objects.all()

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.order_by('-confidence_score', '-created_at')

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Generate new recommendations based on recent optimizations.

        POST /api/recommendations/generate/

        Request body:
        {
            "lookback_days": 90,
            "min_samples": 10
        }
        """
        try:
            lookback_days = request.data.get('lookback_days', 90)
            min_samples = request.data.get('min_samples', 10)

            # Queue task to generate recommendations
            from scanner.tasks.backtest_tasks import generate_recommendations_async
            task = generate_recommendations_async.delay(
                user_id=request.user.id if request.user.is_authenticated else None,
                lookback_days=lookback_days,
                min_samples=min_samples
            )

            logger.info(f"Recommendation generation task queued: {task.id}")

            return Response({
                'task_id': task.id,
                'status': 'RUNNING',
                'message': 'Recommendation generation started'
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """
        Accept a recommendation.

        POST /api/recommendations/:id/accept/
        """
        recommendation = self.get_object()
        recommendation.status = 'ACCEPTED'
        recommendation.save()

        logger.info(f"Recommendation {pk} accepted by user {request.user.id if request.user.is_authenticated else None}")

        return Response({
            'message': 'Recommendation accepted',
            'status': recommendation.status
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject a recommendation.

        POST /api/recommendations/:id/reject/

        Request body (optional):
        {
            "feedback_notes": "Reason for rejection"
        }
        """
        recommendation = self.get_object()
        recommendation.status = 'REJECTED'
        recommendation.feedback_notes = request.data.get('feedback_notes', '')
        recommendation.save()

        logger.info(f"Recommendation {pk} rejected by user {request.user.id if request.user.is_authenticated else None}")

        return Response({
            'message': 'Recommendation rejected',
            'status': recommendation.status
        })

    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """
        Mark recommendation as applied to strategy.

        POST /api/recommendations/:id/apply/
        """
        recommendation = self.get_object()
        recommendation.status = 'APPLIED'
        recommendation.applied_at = datetime.now()
        recommendation.save()

        logger.info(f"Recommendation {pk} applied by user {request.user.id if request.user.is_authenticated else None}")

        return Response({
            'message': 'Recommendation marked as applied',
            'status': recommendation.status,
            'applied_at': recommendation.applied_at
        })
