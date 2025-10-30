"""
Monte Carlo Simulation API Views

RESTful API endpoints for Monte Carlo simulations.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from signals.models_montecarlo import MonteCarloSimulation, MonteCarloRun, MonteCarloDistribution
from signals.serializers_montecarlo import (
    MonteCarloSimulationListSerializer,
    MonteCarloSimulationDetailSerializer,
    MonteCarloSimulationCreateSerializer,
    MonteCarloRunSerializer,
    MonteCarloDistributionSerializer,
)


class MonteCarloSimulationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Monte Carlo simulations.

    Endpoints:
        GET    /api/montecarlo/              - List all simulations
        POST   /api/montecarlo/              - Create new simulation
        GET    /api/montecarlo/:id/          - Get simulation details
        DELETE /api/montecarlo/:id/          - Delete simulation
        GET    /api/montecarlo/:id/runs/     - Get all simulation runs
        GET    /api/montecarlo/:id/distributions/ - Get distribution data
        POST   /api/montecarlo/:id/retry/    - Retry failed simulation
    """

    permission_classes = [IsAuthenticated]
    queryset = MonteCarloSimulation.objects.all()

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return MonteCarloSimulationListSerializer
        elif self.action == 'create':
            return MonteCarloSimulationCreateSerializer
        else:
            return MonteCarloSimulationDetailSerializer

    def get_queryset(self):
        """Filter queryset by user."""
        if self.request.user.is_staff:
            return MonteCarloSimulation.objects.all()
        return MonteCarloSimulation.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        Create and queue new Monte Carlo simulation.

        POST /api/montecarlo/

        Body:
        {
            "name": "Strategy Robustness Test",
            "symbols": ["BTCUSDT"],
            "timeframe": "5m",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T23:59:59Z",
            "num_simulations": 1000,
            "strategy_params": {
                "rsi_oversold": 30,
                "rsi_overbought": 70,
                "adx_min": 20,
                "volume_multiplier": 1.2
            },
            "randomization_config": {
                "rsi_oversold": {"min": 25, "max": 35, "type": "uniform"},
                "rsi_overbought": {"min": 65, "max": 75, "type": "uniform"},
                "adx_min": {"min": 15, "max": 25, "type": "uniform"},
                "volume_multiplier": {"min": 1.0, "max": 1.5, "type": "uniform"}
            },
            "initial_capital": 10000,
            "position_size": 100
        }

        Response:
        {
            "id": 1,
            "status": "PENDING",
            "message": "Monte Carlo simulation queued",
            "task_id": "abc123..."
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create simulation
        simulation = serializer.save(
            user=request.user,
            status='PENDING'
        )

        # Queue Celery task
        from scanner.tasks.montecarlo_tasks import run_montecarlo_simulation_async
        task = run_montecarlo_simulation_async.delay(simulation.id)

        simulation.task_id = task.id
        simulation.save()

        # Return response
        response_serializer = MonteCarloSimulationDetailSerializer(simulation)

        return Response({
            **response_serializer.data,
            'message': 'Monte Carlo simulation queued for execution',
            'task_id': task.id
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def runs(self, request, pk=None):
        """
        Get all simulation runs.

        GET /api/montecarlo/:id/runs/

        Query Parameters:
            - limit: Number of runs to return (default: 100)
            - offset: Offset for pagination (default: 0)
            - sort_by: Field to sort by (roi, win_rate, sharpe_ratio, run_number)
            - order: asc or desc (default: asc)

        Response:
        {
            "count": 1000,
            "runs": [
                {
                    "run_number": 1,
                    "roi": 5.23,
                    "win_rate": 58.5,
                    ...
                },
                ...
            ]
        }
        """
        simulation = self.get_object()

        # Get query parameters
        limit = int(request.query_params.get('limit', 100))
        offset = int(request.query_params.get('offset', 0))
        sort_by = request.query_params.get('sort_by', 'run_number')
        order = request.query_params.get('order', 'asc')

        # Validate sort field
        valid_sort_fields = ['run_number', 'roi', 'win_rate', 'sharpe_ratio', 'total_trades']
        if sort_by not in valid_sort_fields:
            sort_by = 'run_number'

        # Apply sorting
        order_prefix = '-' if order == 'desc' else ''
        runs = simulation.runs.all().order_by(f'{order_prefix}{sort_by}')[offset:offset+limit]

        serializer = MonteCarloRunSerializer(runs, many=True)

        return Response({
            'count': simulation.runs.count(),
            'limit': limit,
            'offset': offset,
            'runs': serializer.data
        })

    @action(detail=True, methods=['get'])
    def distributions(self, request, pk=None):
        """
        Get distribution data for visualization.

        GET /api/montecarlo/:id/distributions/

        Response:
        {
            "roi_distribution": {
                "bins": [...],
                "frequencies": [...],
                "mean": 5.23,
                "median": 4.85,
                ...
            },
            "drawdown_distribution": {...},
            "win_rate_distribution": {...},
            ...
        }
        """
        simulation = self.get_object()
        distributions = simulation.distributions.all()

        result = {}
        for dist in distributions:
            serializer = MonteCarloDistributionSerializer(dist)
            key = dist.metric.lower() + '_distribution'
            result[key] = serializer.data

        return Response(result)

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """
        Get summary statistics for quick view.

        GET /api/montecarlo/:id/summary/

        Response:
        {
            "expected_return": "5.23%",
            "risk": "2.15%",
            "probability_of_profit": "72.5%",
            "value_at_risk_95": "3.45%",
            "sharpe_ratio": "1.85",
            "robustness": "STATISTICALLY ROBUST",
            "robustness_score": 85
        }
        """
        simulation = self.get_object()

        return Response({
            'expected_return': f"{float(simulation.mean_return):.2f}%",
            'risk': f"{float(simulation.std_deviation):.2f}%",
            'probability_of_profit': f"{float(simulation.probability_of_profit):.1f}%",
            'value_at_risk_95': f"{float(simulation.value_at_risk_95):.2f}%",
            'sharpe_ratio': f"{float(simulation.mean_sharpe_ratio):.2f}",
            'robustness': 'STATISTICALLY ROBUST' if simulation.is_statistically_robust else 'NOT ROBUST',
            'robustness_score': float(simulation.robustness_score),
            'confidence_interval_95': f"[{float(simulation.confidence_95_lower):.2f}%, {float(simulation.confidence_95_upper):.2f}%]",
            'worst_case': f"{float(simulation.worst_case_return):.2f}%",
            'best_case': f"{float(simulation.best_case_return):.2f}%",
        })

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """
        Retry a failed Monte Carlo simulation.

        POST /api/montecarlo/:id/retry/

        Response:
        {
            "id": 1,
            "status": "PENDING",
            "message": "Monte Carlo simulation queued for retry",
            "task_id": "xyz789..."
        }
        """
        simulation = self.get_object()

        # Only allow retry for FAILED simulations
        if simulation.status not in ['FAILED', 'PENDING']:
            return Response(
                {'error': f'Cannot retry simulation with status {simulation.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Reset simulation state
        simulation.status = 'PENDING'
        simulation.error_message = None
        simulation.completed_simulations = 0
        simulation.failed_simulations = 0

        # Delete old runs and distributions
        simulation.runs.all().delete()
        simulation.distributions.all().delete()

        simulation.save()

        # Queue new task
        from scanner.tasks.montecarlo_tasks import run_montecarlo_simulation_async
        task = run_montecarlo_simulation_async.delay(simulation.id)

        simulation.task_id = task.id
        simulation.save()

        return Response({
            'id': simulation.id,
            'status': 'PENDING',
            'message': 'Monte Carlo simulation queued for retry',
            'task_id': task.id
        })

    @action(detail=True, methods=['get'])
    def best_worst_runs(self, request, pk=None):
        """
        Get best and worst performing simulation runs.

        GET /api/montecarlo/:id/best_worst_runs/

        Query Parameters:
            - n: Number of best/worst to return (default: 10)

        Response:
        {
            "best_runs": [...],
            "worst_runs": [...]
        }
        """
        simulation = self.get_object()
        n = int(request.query_params.get('n', 10))

        # Get best runs (highest ROI)
        best_runs = simulation.runs.all().order_by('-roi')[:n]
        best_serializer = MonteCarloRunSerializer(best_runs, many=True)

        # Get worst runs (lowest ROI)
        worst_runs = simulation.runs.all().order_by('roi')[:n]
        worst_serializer = MonteCarloRunSerializer(worst_runs, many=True)

        return Response({
            'best_runs': best_serializer.data,
            'worst_runs': worst_serializer.data
        })

    @action(detail=True, methods=['get'])
    def parameter_impact(self, request, pk=None):
        """
        Analyze which parameters have the most impact on performance.

        GET /api/montecarlo/:id/parameter_impact/

        Response:
        {
            "parameter_correlations": {
                "rsi_oversold": -0.45,
                "rsi_overbought": 0.32,
                ...
            }
        }
        """
        simulation = self.get_object()
        runs = simulation.runs.all()

        if runs.count() < 10:
            return Response({'error': 'Not enough runs for parameter analysis'}, status=400)

        # Extract parameter values and ROIs
        import numpy as np
        from scipy import stats

        parameter_correlations = {}

        # Get first run to know which parameters exist
        first_run = runs.first()
        if not first_run or not first_run.parameters_used:
            return Response({'error': 'No parameter data available'}, status=400)

        param_names = list(first_run.parameters_used.keys())

        for param_name in param_names:
            # Extract values for this parameter across all runs
            param_values = []
            rois = []

            for run in runs:
                if param_name in run.parameters_used:
                    param_values.append(run.parameters_used[param_name])
                    rois.append(float(run.roi))

            # Calculate correlation
            if len(param_values) >= 10:
                correlation, p_value = stats.pearsonr(param_values, rois)
                parameter_correlations[param_name] = {
                    'correlation': round(correlation, 3),
                    'p_value': round(p_value, 4),
                    'significant': p_value < 0.05
                }

        return Response({
            'parameter_correlations': parameter_correlations,
            'interpretation': 'Positive correlation = higher parameter value leads to better ROI. Negative = opposite.'
        })
