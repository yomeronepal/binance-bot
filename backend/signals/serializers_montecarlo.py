"""
Monte Carlo Simulation Serializers

Serializers for Monte Carlo simulation API endpoints.
"""

from rest_framework import serializers
from signals.models_montecarlo import MonteCarloSimulation, MonteCarloRun, MonteCarloDistribution
from decimal import Decimal


class MonteCarloRunSerializer(serializers.ModelSerializer):
    """Serializer for individual Monte Carlo simulation runs."""

    roi_formatted = serializers.SerializerMethodField()
    max_drawdown_formatted = serializers.SerializerMethodField()
    win_rate_formatted = serializers.SerializerMethodField()

    class Meta:
        model = MonteCarloRun
        fields = [
            'id',
            'run_number',
            'parameters_used',
            'total_trades',
            'winning_trades',
            'losing_trades',
            'win_rate',
            'win_rate_formatted',
            'total_profit_loss',
            'roi',
            'roi_formatted',
            'max_drawdown',
            'max_drawdown_amount',
            'max_drawdown_formatted',
            'sharpe_ratio',
            'profit_factor',
            'created_at',
        ]

    def get_roi_formatted(self, obj):
        """Format ROI with sign."""
        roi = float(obj.roi)
        sign = '+' if roi >= 0 else ''
        return f"{sign}{roi:.2f}%"

    def get_max_drawdown_formatted(self, obj):
        """Format max drawdown."""
        dd_pct = float(obj.max_drawdown)
        dd_amount = float(obj.max_drawdown_amount)
        return f"${dd_amount:.2f} ({dd_pct:.2f}%)"

    def get_win_rate_formatted(self, obj):
        """Format win rate."""
        return f"{float(obj.win_rate):.2f}%"


class MonteCarloDistributionSerializer(serializers.ModelSerializer):
    """Serializer for distribution data."""

    class Meta:
        model = MonteCarloDistribution
        fields = [
            'id',
            'metric',
            'bins',
            'frequencies',
            'mean',
            'median',
            'std_dev',
            'percentile_5',
            'percentile_25',
            'percentile_75',
            'percentile_95',
        ]


class MonteCarloSimulationListSerializer(serializers.ModelSerializer):
    """Serializer for Monte Carlo simulation list view."""

    username = serializers.CharField(source='user.username', read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    execution_time = serializers.SerializerMethodField()
    mean_return_formatted = serializers.SerializerMethodField()
    robustness_label = serializers.SerializerMethodField()

    class Meta:
        model = MonteCarloSimulation
        fields = [
            'id',
            'name',
            'username',
            'status',
            'symbols',
            'timeframe',
            'num_simulations',
            'completed_simulations',
            'failed_simulations',
            'progress_percentage',
            'mean_return',
            'mean_return_formatted',
            'probability_of_profit',
            'is_statistically_robust',
            'robustness_score',
            'robustness_label',
            'created_at',
            'started_at',
            'completed_at',
            'execution_time',
        ]

    def get_progress_percentage(self, obj):
        """Get progress percentage."""
        return obj.progress_percentage()

    def get_execution_time(self, obj):
        """Get execution time in seconds."""
        return obj.execution_time_seconds()

    def get_mean_return_formatted(self, obj):
        """Format mean return with sign."""
        mean_ret = float(obj.mean_return)
        sign = '+' if mean_ret >= 0 else ''
        return f"{sign}{mean_ret:.2f}%"

    def get_robustness_label(self, obj):
        """Get robustness label."""
        score = float(obj.robustness_score)
        if score >= 80:
            return "ROBUST"
        elif score >= 60:
            return "MODERATE"
        else:
            return "WEAK"


class MonteCarloSimulationDetailSerializer(serializers.ModelSerializer):
    """Serializer for Monte Carlo simulation detail view."""

    username = serializers.CharField(source='user.username', read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    execution_time = serializers.SerializerMethodField()

    # Formatted fields
    mean_return_formatted = serializers.SerializerMethodField()
    median_return_formatted = serializers.SerializerMethodField()
    confidence_95_formatted = serializers.SerializerMethodField()
    confidence_99_formatted = serializers.SerializerMethodField()
    probability_of_profit_formatted = serializers.SerializerMethodField()
    probability_of_loss_formatted = serializers.SerializerMethodField()
    var_95_formatted = serializers.SerializerMethodField()
    var_99_formatted = serializers.SerializerMethodField()
    robustness_label = serializers.SerializerMethodField()

    class Meta:
        model = MonteCarloSimulation
        fields = [
            'id',
            'name',
            'username',
            'status',
            'symbols',
            'timeframe',
            'start_date',
            'end_date',

            # Simulation config
            'num_simulations',
            'completed_simulations',
            'failed_simulations',
            'progress_percentage',

            # Strategy parameters
            'strategy_params',
            'randomization_config',
            'initial_capital',
            'position_size',

            # Statistical results - central tendency
            'mean_return',
            'mean_return_formatted',
            'median_return',
            'median_return_formatted',

            # Statistical results - dispersion
            'std_deviation',
            'variance',

            # Confidence intervals
            'confidence_95_lower',
            'confidence_95_upper',
            'confidence_95_formatted',
            'confidence_99_lower',
            'confidence_99_upper',
            'confidence_99_formatted',

            # Probability
            'probability_of_profit',
            'probability_of_profit_formatted',
            'probability_of_loss',
            'probability_of_loss_formatted',

            # Risk
            'value_at_risk_95',
            'var_95_formatted',
            'value_at_risk_99',
            'var_99_formatted',

            # Extremes
            'best_case_return',
            'worst_case_return',

            # Drawdown
            'mean_max_drawdown',
            'worst_case_drawdown',
            'best_case_drawdown',

            # Performance metrics
            'mean_sharpe_ratio',
            'median_sharpe_ratio',
            'mean_win_rate',
            'median_win_rate',

            # Robustness
            'is_statistically_robust',
            'robustness_score',
            'robustness_label',
            'robustness_reasons',

            # Timestamps
            'created_at',
            'started_at',
            'completed_at',
            'execution_time',

            # Error handling
            'error_message',
        ]

    def get_progress_percentage(self, obj):
        """Get progress percentage."""
        return obj.progress_percentage()

    def get_execution_time(self, obj):
        """Get execution time in seconds."""
        return obj.execution_time_seconds()

    def get_mean_return_formatted(self, obj):
        """Format mean return."""
        mean_ret = float(obj.mean_return)
        sign = '+' if mean_ret >= 0 else ''
        return f"{sign}{mean_ret:.2f}%"

    def get_median_return_formatted(self, obj):
        """Format median return."""
        median_ret = float(obj.median_return)
        sign = '+' if median_ret >= 0 else ''
        return f"{sign}{median_ret:.2f}%"

    def get_confidence_95_formatted(self, obj):
        """Format 95% confidence interval."""
        lower = float(obj.confidence_95_lower)
        upper = float(obj.confidence_95_upper)
        return f"[{lower:.2f}%, {upper:.2f}%]"

    def get_confidence_99_formatted(self, obj):
        """Format 99% confidence interval."""
        lower = float(obj.confidence_99_lower)
        upper = float(obj.confidence_99_upper)
        return f"[{lower:.2f}%, {upper:.2f}%]"

    def get_probability_of_profit_formatted(self, obj):
        """Format probability of profit."""
        return f"{float(obj.probability_of_profit):.1f}%"

    def get_probability_of_loss_formatted(self, obj):
        """Format probability of loss."""
        return f"{float(obj.probability_of_loss):.1f}%"

    def get_var_95_formatted(self, obj):
        """Format VaR at 95%."""
        return f"{float(obj.value_at_risk_95):.2f}%"

    def get_var_99_formatted(self, obj):
        """Format VaR at 99%."""
        return f"{float(obj.value_at_risk_99):.2f}%"

    def get_robustness_label(self, obj):
        """Get robustness label."""
        score = float(obj.robustness_score)
        if score >= 80:
            return "STATISTICALLY ROBUST"
        elif score >= 60:
            return "MODERATELY ROBUST"
        else:
            return "NOT ROBUST"


class MonteCarloSimulationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new Monte Carlo simulations."""

    class Meta:
        model = MonteCarloSimulation
        fields = [
            'name',
            'symbols',
            'timeframe',
            'start_date',
            'end_date',
            'num_simulations',
            'strategy_params',
            'randomization_config',
            'initial_capital',
            'position_size',
        ]

    def validate_symbols(self, value):
        """Validate symbols list."""
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one symbol is required")
        return value

    def validate_num_simulations(self, value):
        """Validate number of simulations."""
        if value < 10:
            raise serializers.ValidationError("Minimum 10 simulations required")
        if value > 10000:
            raise serializers.ValidationError("Maximum 10000 simulations allowed")
        return value

    def validate(self, data):
        """Validate date range."""
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError("start_date must be before end_date")
        return data
