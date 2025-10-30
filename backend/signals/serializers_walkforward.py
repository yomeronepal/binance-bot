"""
Walk-Forward Optimization Serializers
DRF serializers for walk-forward models.
"""
from rest_framework import serializers
from signals.models_walkforward import (
    WalkForwardOptimization,
    WalkForwardWindow,
    WalkForwardMetric
)


class WalkForwardWindowSerializer(serializers.ModelSerializer):
    """Serializer for individual walk-forward windows."""

    performance_drop_formatted = serializers.SerializerMethodField()
    in_sample_win_rate_formatted = serializers.SerializerMethodField()
    out_sample_win_rate_formatted = serializers.SerializerMethodField()
    in_sample_roi_formatted = serializers.SerializerMethodField()
    out_sample_roi_formatted = serializers.SerializerMethodField()

    class Meta:
        model = WalkForwardWindow
        fields = [
            'id', 'window_number',
            'training_start', 'training_end',
            'testing_start', 'testing_end',
            # In-sample results
            'best_params',
            'in_sample_backtest_id',
            'in_sample_total_trades',
            'in_sample_win_rate', 'in_sample_win_rate_formatted',
            'in_sample_roi', 'in_sample_roi_formatted',
            'in_sample_sharpe',
            'in_sample_max_drawdown',
            # Out-of-sample results
            'out_sample_backtest_id',
            'out_sample_total_trades',
            'out_sample_win_rate', 'out_sample_win_rate_formatted',
            'out_sample_roi', 'out_sample_roi_formatted',
            'out_sample_sharpe',
            'out_sample_max_drawdown',
            # Performance comparison
            'performance_drop_pct', 'performance_drop_formatted',
            'status', 'error_message',
            'created_at', 'updated_at'
        ]

    def get_performance_drop_formatted(self, obj):
        """Format performance drop as percentage."""
        drop = float(obj.performance_drop_pct)
        return f"{drop:.1f}%"

    def get_in_sample_win_rate_formatted(self, obj):
        """Format in-sample win rate."""
        return f"{float(obj.in_sample_win_rate):.2f}%"

    def get_out_sample_win_rate_formatted(self, obj):
        """Format out-of-sample win rate."""
        return f"{float(obj.out_sample_win_rate):.2f}%"

    def get_in_sample_roi_formatted(self, obj):
        """Format in-sample ROI."""
        roi = float(obj.in_sample_roi)
        sign = '+' if roi >= 0 else ''
        return f"{sign}{roi:.2f}%"

    def get_out_sample_roi_formatted(self, obj):
        """Format out-of-sample ROI."""
        roi = float(obj.out_sample_roi)
        sign = '+' if roi >= 0 else ''
        return f"{sign}{roi:.2f}%"


class WalkForwardMetricSerializer(serializers.ModelSerializer):
    """Serializer for walk-forward metrics (time-series data)."""

    class Meta:
        model = WalkForwardMetric
        fields = [
            'id', 'window_number', 'window_type',
            'cumulative_trades', 'cumulative_pnl', 'cumulative_roi',
            'window_trades', 'window_pnl', 'window_win_rate',
            'timestamp'
        ]


class WalkForwardOptimizationSerializer(serializers.ModelSerializer):
    """Serializer for walk-forward optimization runs."""

    duration_seconds = serializers.SerializerMethodField()
    avg_in_sample_win_rate_formatted = serializers.SerializerMethodField()
    avg_out_sample_win_rate_formatted = serializers.SerializerMethodField()
    avg_in_sample_roi_formatted = serializers.SerializerMethodField()
    avg_out_sample_roi_formatted = serializers.SerializerMethodField()
    performance_degradation_formatted = serializers.SerializerMethodField()
    consistency_score_formatted = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = WalkForwardOptimization
        fields = [
            'id', 'name', 'status', 'user',
            'symbols', 'timeframe', 'start_date', 'end_date',
            # Window parameters
            'training_window_days', 'testing_window_days', 'step_days',
            # Strategy parameters
            'parameter_ranges', 'optimization_method',
            # Trading parameters
            'initial_capital', 'position_size',
            # Execution info
            'started_at', 'completed_at', 'duration_seconds',
            'error_message',
            # Progress
            'total_windows', 'completed_windows', 'progress_percentage',
            # Aggregate metrics
            'avg_in_sample_win_rate', 'avg_in_sample_win_rate_formatted',
            'avg_out_sample_win_rate', 'avg_out_sample_win_rate_formatted',
            'avg_in_sample_roi', 'avg_in_sample_roi_formatted',
            'avg_out_sample_roi', 'avg_out_sample_roi_formatted',
            'performance_degradation', 'performance_degradation_formatted',
            'consistency_score', 'consistency_score_formatted',
            # Robustness
            'is_robust', 'robustness_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'status', 'started_at', 'completed_at',
            'total_windows', 'completed_windows',
            'avg_in_sample_win_rate', 'avg_out_sample_win_rate',
            'avg_in_sample_roi', 'avg_out_sample_roi',
            'performance_degradation', 'consistency_score',
            'is_robust', 'robustness_notes',
            'created_at', 'updated_at'
        ]

    def get_duration_seconds(self, obj):
        """Get walk-forward execution duration in seconds."""
        return obj.duration_seconds()

    def get_avg_in_sample_win_rate_formatted(self, obj):
        """Format average in-sample win rate."""
        return f"{float(obj.avg_in_sample_win_rate):.2f}%"

    def get_avg_out_sample_win_rate_formatted(self, obj):
        """Format average out-of-sample win rate."""
        return f"{float(obj.avg_out_sample_win_rate):.2f}%"

    def get_avg_in_sample_roi_formatted(self, obj):
        """Format average in-sample ROI."""
        roi = float(obj.avg_in_sample_roi)
        sign = '+' if roi >= 0 else ''
        return f"{sign}{roi:.2f}%"

    def get_avg_out_sample_roi_formatted(self, obj):
        """Format average out-of-sample ROI."""
        roi = float(obj.avg_out_sample_roi)
        sign = '+' if roi >= 0 else ''
        return f"{sign}{roi:.2f}%"

    def get_performance_degradation_formatted(self, obj):
        """Format performance degradation."""
        deg = float(obj.performance_degradation)
        return f"{deg:.1f}%"

    def get_consistency_score_formatted(self, obj):
        """Format consistency score."""
        score = float(obj.consistency_score)
        return f"{score:.0f}/100"

    def get_progress_percentage(self, obj):
        """Calculate progress percentage."""
        if obj.total_windows == 0:
            return 0
        return int((obj.completed_windows / obj.total_windows) * 100)


class WalkForwardOptimizationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new walk-forward optimization runs."""

    class Meta:
        model = WalkForwardOptimization
        fields = [
            'name', 'symbols', 'timeframe',
            'start_date', 'end_date',
            'training_window_days', 'testing_window_days', 'step_days',
            'parameter_ranges', 'optimization_method',
            'initial_capital', 'position_size'
        ]

    def validate_symbols(self, value):
        """Validate symbols list."""
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one symbol is required")
        return value

    def validate(self, data):
        """Validate walk-forward configuration."""
        # Date validation
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError({
                'end_date': 'End date must be after start date'
            })

        # Window validation
        if data['training_window_days'] <= 0:
            raise serializers.ValidationError({
                'training_window_days': 'Training window must be positive'
            })
        if data['testing_window_days'] <= 0:
            raise serializers.ValidationError({
                'testing_window_days': 'Testing window must be positive'
            })
        if data['step_days'] <= 0:
            raise serializers.ValidationError({
                'step_days': 'Step size must be positive'
            })

        # Check if date range is sufficient
        total_days = (data['end_date'] - data['start_date']).days
        min_required = data['training_window_days'] + data['testing_window_days']
        if total_days < min_required:
            raise serializers.ValidationError(
                f"Date range ({total_days} days) is too short. "
                f"Minimum required: {min_required} days "
                f"(training: {data['training_window_days']} + testing: {data['testing_window_days']})"
            )

        # Capital validation
        if data['initial_capital'] <= 0:
            raise serializers.ValidationError({
                'initial_capital': 'Initial capital must be positive'
            })
        if data['position_size'] <= 0:
            raise serializers.ValidationError({
                'position_size': 'Position size must be positive'
            })
        if data['position_size'] > data['initial_capital']:
            raise serializers.ValidationError({
                'position_size': 'Position size cannot exceed initial capital'
            })

        return data
