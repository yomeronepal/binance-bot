"""
Walk-Forward Optimization API Views
REST API endpoints for walk-forward optimization.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q
import logging

from signals.models_walkforward import (
    WalkForwardOptimization,
    WalkForwardWindow,
    WalkForwardMetric
)
from signals.serializers_walkforward import (
    WalkForwardOptimizationSerializer,
    WalkForwardOptimizationCreateSerializer,
    WalkForwardWindowSerializer,
    WalkForwardMetricSerializer
)

logger = logging.getLogger(__name__)


class WalkForwardOptimizationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Walk-Forward Optimization.

    Endpoints:
    - GET    /api/walkforward/              List all walk-forward runs
    - POST   /api/walkforward/              Create and queue new run
    - GET    /api/walkforward/:id/          Get details
    - DELETE /api/walkforward/:id/          Delete run
    - GET    /api/walkforward/:id/windows/  Get window results
    - GET    /api/walkforward/:id/metrics/  Get metrics for charts
    - POST   /api/walkforward/:id/retry/    Retry failed run
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get walk-forward runs for current user."""
        user = self.request.user
        if user.is_staff:
            return WalkForwardOptimization.objects.all()
        return WalkForwardOptimization.objects.filter(user=user)

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return WalkForwardOptimizationCreateSerializer
        return WalkForwardOptimizationSerializer

    def create(self, request, *args, **kwargs):
        """
        Create and queue a new walk-forward optimization run.
        POST /api/walkforward/
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create walk-forward optimization record
        walkforward = serializer.save(user=request.user, status='PENDING')

        try:
            # Queue the task
            from scanner.tasks.walkforward_tasks import run_walkforward_optimization_async
            task = run_walkforward_optimization_async.delay(walkforward.id)

            logger.info(
                f"Walk-forward optimization {walkforward.id} queued "
                f"(task: {task.id})"
            )

            # Return created walk-forward with task info
            response_serializer = WalkForwardOptimizationSerializer(walkforward)
            return Response(
                {
                    **response_serializer.data,
                    'task_id': task.id
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            # If task queueing fails, mark as failed
            walkforward.status = 'FAILED'
            walkforward.error_message = f"Failed to queue task: {str(e)}"
            walkforward.save()

            logger.error(
                f"Failed to queue walk-forward optimization {walkforward.id}: {e}",
                exc_info=True
            )

            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def list(self, request, *args, **kwargs):
        """
        List all walk-forward optimization runs.
        GET /api/walkforward/
        """
        queryset = self.get_queryset().order_by('-created_at')

        # Optional filters
        status_filter = request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """
        Get detailed walk-forward optimization results.
        GET /api/walkforward/:id/
        """
        walkforward = self.get_object()
        serializer = self.get_serializer(walkforward)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        Delete a walk-forward optimization run.
        DELETE /api/walkforward/:id/
        """
        walkforward = self.get_object()

        # Prevent deletion of running walks
        if walkforward.status == 'RUNNING':
            return Response(
                {'error': 'Cannot delete running walk-forward optimization'},
                status=status.HTTP_400_BAD_REQUEST
            )

        walkforward_id = walkforward.id
        walkforward.delete()

        logger.info(f"Walk-forward optimization {walkforward_id} deleted")

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'])
    def windows(self, request, pk=None):
        """
        Get window results for a walk-forward optimization.
        GET /api/walkforward/:id/windows/
        """
        walkforward = self.get_object()
        windows = walkforward.windows.all().order_by('window_number')
        serializer = WalkForwardWindowSerializer(windows, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        """
        Get metrics and chart data for a walk-forward optimization.
        GET /api/walkforward/:id/metrics/

        Returns:
        - Performance comparison data (in-sample vs out-of-sample by window)
        - Cumulative P/L over time
        - Consistency metrics
        """
        walkforward = self.get_object()

        # Get all windows
        windows = walkforward.windows.all().order_by('window_number')

        # Performance comparison data
        performance_comparison = []
        for window in windows:
            performance_comparison.append({
                'window_number': window.window_number,
                'window_label': f"W{window.window_number}",
                'in_sample_roi': float(window.in_sample_roi),
                'out_sample_roi': float(window.out_sample_roi),
                'in_sample_win_rate': float(window.in_sample_win_rate),
                'out_sample_win_rate': float(window.out_sample_win_rate),
                'performance_drop': float(window.performance_drop_pct),
                'training_period': f"{window.training_start.strftime('%Y-%m-%d')} to {window.training_end.strftime('%Y-%m-%d')}",
                'testing_period': f"{window.testing_start.strftime('%Y-%m-%d')} to {window.testing_end.strftime('%Y-%m-%d')}"
            })

        # Cumulative metrics
        metrics = walkforward.metrics.all().order_by('window_number', 'window_type')
        cumulative_data = []
        for metric in metrics:
            cumulative_data.append({
                'window_number': metric.window_number,
                'window_type': metric.window_type,
                'cumulative_pnl': float(metric.cumulative_pnl),
                'cumulative_roi': float(metric.cumulative_roi),
                'cumulative_trades': metric.cumulative_trades,
                'window_pnl': float(metric.window_pnl),
                'window_win_rate': float(metric.window_win_rate)
            })

        # Consistency data (for box plot or distribution chart)
        out_sample_rois = [float(w.out_sample_roi) for w in windows]
        out_sample_win_rates = [float(w.out_sample_win_rate) for w in windows]

        # Parameter stability (how parameters change over windows)
        parameter_evolution = []
        for window in windows:
            param_entry = {
                'window_number': window.window_number,
                'window_label': f"W{window.window_number}",
            }
            # Add each parameter from best_params
            if window.best_params:
                for key, value in window.best_params.items():
                    param_entry[key] = value
            parameter_evolution.append(param_entry)

        return Response({
            'performance_comparison': performance_comparison,
            'cumulative_data': cumulative_data,
            'consistency': {
                'out_sample_rois': out_sample_rois,
                'out_sample_win_rates': out_sample_win_rates,
                'consistency_score': float(walkforward.consistency_score),
                'avg_roi': float(walkforward.avg_out_sample_roi),
                'std_roi': self._calculate_std(out_sample_rois) if out_sample_rois else 0
            },
            'parameter_evolution': parameter_evolution,
            'summary': {
                'total_windows': walkforward.total_windows,
                'completed_windows': walkforward.completed_windows,
                'avg_in_sample_roi': float(walkforward.avg_in_sample_roi),
                'avg_out_sample_roi': float(walkforward.avg_out_sample_roi),
                'performance_degradation': float(walkforward.performance_degradation),
                'consistency_score': float(walkforward.consistency_score),
                'is_robust': walkforward.is_robust,
                'robustness_notes': walkforward.robustness_notes
            }
        })

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """
        Retry a failed or stuck walk-forward optimization.
        POST /api/walkforward/:id/retry/
        """
        walkforward = self.get_object()

        # Only allow retry for FAILED or PENDING
        if walkforward.status not in ['FAILED', 'PENDING']:
            return Response(
                {'error': f'Cannot retry walk-forward with status {walkforward.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Reset walk-forward state
            walkforward.status = 'PENDING'
            walkforward.error_message = None
            walkforward.started_at = None
            walkforward.completed_at = None
            walkforward.total_windows = 0
            walkforward.completed_windows = 0

            # Reset aggregate metrics
            walkforward.avg_in_sample_win_rate = 0
            walkforward.avg_out_sample_win_rate = 0
            walkforward.avg_in_sample_roi = 0
            walkforward.avg_out_sample_roi = 0
            walkforward.performance_degradation = 0
            walkforward.consistency_score = 0
            walkforward.is_robust = False
            walkforward.robustness_notes = None

            walkforward.save()

            # Delete previous windows and metrics
            walkforward.windows.all().delete()
            walkforward.metrics.all().delete()

            # Queue the task
            from scanner.tasks.walkforward_tasks import run_walkforward_optimization_async
            task = run_walkforward_optimization_async.delay(walkforward.id)

            logger.info(
                f"Walk-forward optimization {walkforward.id} retry queued "
                f"(task: {task.id})"
            )

            return Response({
                'id': walkforward.id,
                'status': 'PENDING',
                'message': 'Walk-forward optimization queued for retry',
                'task_id': task.id
            })

        except Exception as e:
            logger.error(
                f"Error retrying walk-forward optimization {walkforward.id}: {e}",
                exc_info=True
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _calculate_std(self, values):
        """Calculate standard deviation of a list of values."""
        if not values or len(values) < 2:
            return 0

        import statistics
        try:
            return statistics.stdev(values)
        except Exception:
            return 0
