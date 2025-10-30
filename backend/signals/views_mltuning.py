"""
ML Tuning API Views

RESTful API endpoints for ML-based parameter tuning.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
import joblib
import os

from signals.models_mltuning import MLTuningJob, MLTuningSample, MLPrediction, MLModel
from signals.serializers_mltuning import (
    MLTuningJobListSerializer,
    MLTuningJobDetailSerializer,
    MLTuningJobCreateSerializer,
    MLTuningSampleSerializer,
    MLPredictionSerializer,
    MLModelSerializer,
)


class MLTuningJobViewSet(viewsets.ModelViewSet):
    """
    ViewSet for ML tuning jobs.

    Endpoints:
        GET    /api/mltuning/                      - List all jobs
        POST   /api/mltuning/                      - Create new job
        GET    /api/mltuning/:id/                  - Get job details
        DELETE /api/mltuning/:id/                  - Delete job
        GET    /api/mltuning/:id/samples/          - Get training samples
        GET    /api/mltuning/:id/feature_importance/ - Get feature importance
        GET    /api/mltuning/:id/sensitivity/      - Get parameter sensitivity
        POST   /api/mltuning/:id/predict/          - Predict for new parameters
        POST   /api/mltuning/:id/find_optimal/     - Find optimal parameters
        POST   /api/mltuning/:id/retry/            - Retry failed job
    """

    permission_classes = [IsAuthenticated]
    queryset = MLTuningJob.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return MLTuningJobListSerializer
        elif self.action == 'create':
            return MLTuningJobCreateSerializer
        else:
            return MLTuningJobDetailSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return MLTuningJob.objects.all()
        return MLTuningJob.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        Create and queue new ML tuning job.

        POST /api/mltuning/
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create job
        tuning_job = serializer.save(
            user=request.user,
            status='PENDING'
        )

        # Queue Celery task
        from scanner.tasks.mltuning_tasks import run_ml_tuning_async
        task = run_ml_tuning_async.delay(tuning_job.id)

        tuning_job.task_id = task.id
        tuning_job.save()

        # Return response
        response_serializer = MLTuningJobDetailSerializer(tuning_job)

        return Response({
            **response_serializer.data,
            'message': 'ML tuning job queued for execution',
            'task_id': task.id
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def samples(self, request, pk=None):
        """
        Get training samples.

        GET /api/mltuning/:id/samples/?limit=100&offset=0&split=TRAIN
        """
        tuning_job = self.get_object()

        limit = int(request.query_params.get('limit', 100))
        offset = int(request.query_params.get('offset', 0))
        split = request.query_params.get('split', None)

        samples = tuning_job.samples.all()

        if split:
            samples = samples.filter(split_set=split)

        samples = samples.order_by('sample_number')[offset:offset+limit]

        serializer = MLTuningSampleSerializer(samples, many=True)

        return Response({
            'count': tuning_job.samples.count(),
            'limit': limit,
            'offset': offset,
            'samples': serializer.data
        })

    @action(detail=True, methods=['get'])
    def feature_importance(self, request, pk=None):
        """
        Get feature importance from trained model.

        GET /api/mltuning/:id/feature_importance/
        """
        tuning_job = self.get_object()

        if tuning_job.status != 'COMPLETED':
            return Response(
                {'error': 'Job must be completed to view feature importance'},
                status=status.HTTP_400_BAD_REQUEST
            )

        feature_importance = tuning_job.feature_importance

        # Sort by importance
        sorted_importance = sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return Response({
            'feature_importance': dict(sorted_importance),
            'top_10': dict(sorted_importance[:10])
        })

    @action(detail=True, methods=['get'])
    def sensitivity(self, request, pk=None):
        """
        Get parameter sensitivity analysis.

        GET /api/mltuning/:id/sensitivity/
        """
        tuning_job = self.get_object()

        if tuning_job.status != 'COMPLETED':
            return Response(
                {'error': 'Job must be completed to view sensitivity'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'parameter_sensitivity': tuning_job.parameter_sensitivity
        })

    @action(detail=True, methods=['post'])
    def predict(self, request, pk=None):
        """
        Predict performance for given parameters.

        POST /api/mltuning/:id/predict/

        Body:
        {
            "parameters": {
                "rsi_oversold": 28,
                "rsi_overbought": 72,
                "adx_min": 22
            }
        }

        Response:
        {
            "predicted_value": 2.45,
            "confidence": 87.5,
            "metric": "SHARPE_RATIO"
        }
        """
        tuning_job = self.get_object()

        if tuning_job.status != 'COMPLETED':
            return Response(
                {'error': 'Job must be completed to make predictions'},
                status=status.HTTP_400_BAD_REQUEST
            )

        parameters = request.data.get('parameters')
        if not parameters:
            return Response(
                {'error': 'parameters field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Load model and scaler
            model = joblib.load(tuning_job.model_file_path)
            scaler = joblib.load(tuning_job.scaler_file_path)

            # Create ML engine and load model
            from scanner.services.ml_tuning_engine import MLTuningEngine
            ml_engine = MLTuningEngine(ml_algorithm=tuning_job.ml_algorithm)
            ml_engine.model = model
            ml_engine.scaler = scaler

            # Get feature names from first sample
            sample = tuning_job.samples.first()
            if sample and sample.features:
                ml_engine.feature_names = list(sample.features.keys())

            # Make prediction
            predicted_value, confidence = ml_engine.predict(parameters)

            # Save prediction
            prediction = MLPrediction.objects.create(
                tuning_job=tuning_job,
                parameters=parameters,
                predicted_value=predicted_value,
                prediction_confidence=confidence
            )

            return Response({
                'prediction_id': prediction.id,
                'predicted_value': float(predicted_value),
                'confidence': float(confidence),
                'metric': tuning_job.optimization_metric,
                'parameters': parameters
            })

        except Exception as e:
            return Response(
                {'error': f'Prediction failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def find_optimal(self, request, pk=None):
        """
        Find optimal parameters using trained model.

        POST /api/mltuning/:id/find_optimal/

        Body:
        {
            "num_candidates": 10000,
            "top_n": 10
        }

        Response:
        {
            "recommendations": [
                {
                    "rank": 1,
                    "parameters": {...},
                    "predicted_value": 2.85,
                    "confidence": 92.3
                },
                ...
            ]
        }
        """
        tuning_job = self.get_object()

        if tuning_job.status != 'COMPLETED':
            return Response(
                {'error': 'Job must be completed to find optimal parameters'},
                status=status.HTTP_400_BAD_REQUEST
            )

        num_candidates = request.data.get('num_candidates', 10000)
        top_n = request.data.get('top_n', 10)

        try:
            # Load model and scaler
            model = joblib.load(tuning_job.model_file_path)
            scaler = joblib.load(tuning_job.scaler_file_path)

            # Create ML engine and load model
            from scanner.services.ml_tuning_engine import MLTuningEngine
            ml_engine = MLTuningEngine(ml_algorithm=tuning_job.ml_algorithm)
            ml_engine.model = model
            ml_engine.scaler = scaler

            # Get feature names
            sample = tuning_job.samples.first()
            if sample and sample.features:
                ml_engine.feature_names = list(sample.features.keys())

            # Find optimal parameters
            optimal_candidates = ml_engine.find_optimal_parameters(
                parameter_space=tuning_job.parameter_space,
                num_candidates=num_candidates
            )

            # Format response
            recommendations = []
            for rank, (params, pred_value, conf) in enumerate(optimal_candidates[:top_n], 1):
                recommendations.append({
                    'rank': rank,
                    'parameters': params,
                    'predicted_value': float(pred_value),
                    'confidence': float(conf)
                })

            return Response({
                'metric': tuning_job.optimization_metric,
                'num_candidates_evaluated': num_candidates,
                'recommendations': recommendations
            })

        except Exception as e:
            return Response(
                {'error': f'Optimization failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """
        Retry a failed ML tuning job.

        POST /api/mltuning/:id/retry/
        """
        tuning_job = self.get_object()

        if tuning_job.status not in ['FAILED', 'PENDING']:
            return Response(
                {'error': f'Cannot retry job with status {tuning_job.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Reset job state
        tuning_job.status = 'PENDING'
        tuning_job.error_message = None
        tuning_job.samples_evaluated = 0
        tuning_job.samples_successful = 0
        tuning_job.samples_failed = 0

        # Delete old samples
        tuning_job.samples.all().delete()

        tuning_job.save()

        # Queue new task
        from scanner.tasks.mltuning_tasks import run_ml_tuning_async
        task = run_ml_tuning_async.delay(tuning_job.id)

        tuning_job.task_id = task.id
        tuning_job.save()

        return Response({
            'id': tuning_job.id,
            'status': 'PENDING',
            'message': 'ML tuning job queued for retry',
            'task_id': task.id
        })

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """
        Get quick summary of ML tuning results.

        GET /api/mltuning/:id/summary/
        """
        tuning_job = self.get_object()

        return Response({
            'id': tuning_job.id,
            'name': tuning_job.name,
            'status': tuning_job.status,
            'ml_algorithm': tuning_job.ml_algorithm,
            'optimization_metric': tuning_job.optimization_metric,

            'training': {
                'samples': tuning_job.samples_successful,
                'r2_score': float(tuning_job.training_score),
                'validation_r2': float(tuning_job.validation_score),
                'overfitting': float(tuning_job.overfitting_score),
            },

            'best_parameters': tuning_job.best_parameters,
            'predicted_performance': float(tuning_job.predicted_performance),

            'out_of_sample': {
                'roi': float(tuning_job.out_of_sample_roi),
                'sharpe': float(tuning_job.out_of_sample_sharpe),
                'win_rate': float(tuning_job.out_of_sample_win_rate),
            },

            'quality': {
                'score': float(tuning_job.model_confidence),
                'production_ready': tuning_job.is_production_ready,
            },

            'execution_time': tuning_job.execution_time_seconds()
        })


class MLModelViewSet(viewsets.ModelViewSet):
    """ViewSet for saved ML models."""

    permission_classes = [IsAuthenticated]
    queryset = MLModel.objects.all()
    serializer_class = MLModelSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return MLModel.objects.all()
        return MLModel.objects.filter(user=self.request.user)
