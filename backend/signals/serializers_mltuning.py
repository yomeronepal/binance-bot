"""
ML Tuning Serializers

Serializers for ML-based parameter tuning API endpoints.
"""

from rest_framework import serializers
from signals.models_mltuning import MLTuningJob, MLTuningSample, MLPrediction, MLModel
from decimal import Decimal


class MLTuningSampleSerializer(serializers.ModelSerializer):
    """Serializer for ML tuning samples."""

    class Meta:
        model = MLTuningSample
        fields = [
            'id', 'sample_number', 'parameters', 'features',
            'roi', 'sharpe_ratio', 'profit_factor', 'win_rate',
            'max_drawdown', 'total_trades', 'target_value',
            'split_set', 'created_at'
        ]


class MLTuningJobListSerializer(serializers.ModelSerializer):
    """Serializer for ML tuning job list view."""

    username = serializers.CharField(source='user.username', read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    execution_time = serializers.SerializerMethodField()
    quality_label = serializers.SerializerMethodField()

    class Meta:
        model = MLTuningJob
        fields = [
            'id', 'name', 'username', 'status',
            'ml_algorithm', 'optimization_metric',
            'symbols', 'timeframe',
            'num_training_samples', 'samples_evaluated',
            'progress_percentage',
            'training_score', 'validation_score',
            'is_production_ready', 'model_confidence',
            'quality_label',
            'created_at', 'completed_at', 'execution_time'
        ]

    def get_progress_percentage(self, obj):
        return obj.progress_percentage()

    def get_execution_time(self, obj):
        return obj.execution_time_seconds()

    def get_quality_label(self, obj):
        score = float(obj.model_confidence)
        if score >= 80:
            return "EXCELLENT"
        elif score >= 60:
            return "GOOD"
        elif score >= 40:
            return "FAIR"
        else:
            return "POOR"


class MLTuningJobDetailSerializer(serializers.ModelSerializer):
    """Serializer for ML tuning job detail view."""

    username = serializers.CharField(source='user.username', read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    execution_time = serializers.SerializerMethodField()
    quality_label = serializers.SerializerMethodField()

    class Meta:
        model = MLTuningJob
        fields = [
            'id', 'name', 'username', 'status',
            'symbols', 'timeframe',
            'training_start_date', 'training_end_date',
            'validation_start_date', 'validation_end_date',

            'ml_algorithm', 'optimization_metric',
            'parameter_space', 'ml_hyperparameters',

            'use_technical_indicators', 'use_market_conditions',
            'use_temporal_features', 'custom_features',

            'num_training_samples', 'train_test_split',
            'cross_validation_folds',
            'initial_capital', 'position_size',

            'best_parameters', 'predicted_performance',

            'training_score', 'validation_score', 'test_score',

            'out_of_sample_roi', 'out_of_sample_sharpe',
            'out_of_sample_win_rate', 'out_of_sample_max_drawdown',

            'feature_importance', 'parameter_sensitivity',

            'model_file_path', 'scaler_file_path',

            'samples_evaluated', 'samples_successful', 'samples_failed',
            'progress_percentage',

            'overfitting_score', 'model_confidence',
            'is_production_ready', 'quality_label',

            'task_id', 'error_message',

            'created_at', 'started_at', 'completed_at', 'execution_time'
        ]

    def get_progress_percentage(self, obj):
        return obj.progress_percentage()

    def get_execution_time(self, obj):
        return obj.execution_time_seconds()

    def get_quality_label(self, obj):
        score = float(obj.model_confidence)
        if score >= 80:
            return "EXCELLENT"
        elif score >= 60:
            return "GOOD"
        elif score >= 40:
            return "FAIR"
        else:
            return "POOR"


class MLTuningJobCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ML tuning jobs."""

    class Meta:
        model = MLTuningJob
        fields = [
            'name', 'symbols', 'timeframe',
            'training_start_date', 'training_end_date',
            'validation_start_date', 'validation_end_date',
            'ml_algorithm', 'optimization_metric',
            'parameter_space', 'ml_hyperparameters',
            'use_technical_indicators', 'use_market_conditions',
            'use_temporal_features', 'custom_features',
            'num_training_samples', 'train_test_split',
            'cross_validation_folds',
            'initial_capital', 'position_size'
        ]

    def validate_symbols(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one symbol is required")
        return value

    def validate_num_training_samples(self, value):
        if value < 100:
            raise serializers.ValidationError("Minimum 100 training samples required")
        if value > 10000:
            raise serializers.ValidationError("Maximum 10000 training samples allowed")
        return value

    def validate(self, data):
        if data['training_start_date'] >= data['training_end_date']:
            raise serializers.ValidationError("training_start_date must be before training_end_date")

        if data.get('validation_start_date') and data.get('validation_end_date'):
            if data['validation_start_date'] >= data['validation_end_date']:
                raise serializers.ValidationError("validation_start_date must be before validation_end_date")

        return data


class MLPredictionSerializer(serializers.ModelSerializer):
    """Serializer for ML predictions."""

    class Meta:
        model = MLPrediction
        fields = [
            'id', 'parameters', 'features',
            'predicted_value', 'prediction_confidence',
            'actual_value', 'prediction_error',
            'created_at', 'verified_at'
        ]


class MLModelSerializer(serializers.ModelSerializer):
    """Serializer for saved ML models."""

    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = MLModel
        fields = [
            'id', 'name', 'username',
            'ml_algorithm', 'optimization_metric',
            'feature_set',
            'training_score', 'validation_score', 'test_score',
            'model_file_path', 'scaler_file_path',
            'times_used', 'last_used_at',
            'is_active', 'is_production_ready',
            'created_at', 'updated_at'
        ]
