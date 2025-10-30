"""
Backtesting Serializers
DRF serializers for backtest models.
"""
from rest_framework import serializers
from signals.models_backtest import (
    BacktestRun,
    BacktestTrade,
    StrategyOptimization,
    OptimizationRecommendation,
    BacktestMetric
)


class BacktestTradeSerializer(serializers.ModelSerializer):
    """Serializer for individual backtest trades."""

    profit_loss_formatted = serializers.SerializerMethodField()
    duration_formatted = serializers.SerializerMethodField()

    class Meta:
        model = BacktestTrade
        fields = [
            'id', 'symbol', 'direction', 'market_type',
            'entry_price', 'exit_price', 'stop_loss', 'take_profit',
            'position_size', 'quantity', 'leverage',
            'profit_loss', 'profit_loss_formatted', 'profit_loss_percentage',
            'opened_at', 'closed_at', 'duration_hours', 'duration_formatted',
            'status', 'signal_confidence', 'signal_indicators',
            'risk_reward_ratio', 'created_at'
        ]

    def get_profit_loss_formatted(self, obj):
        """Format P/L as currency string."""
        pnl = float(obj.profit_loss)
        sign = '+' if pnl >= 0 else ''
        return f"{sign}${pnl:.2f}"

    def get_duration_formatted(self, obj):
        """Format duration as human-readable string."""
        hours = float(obj.duration_hours)
        if hours < 1:
            return f"{int(hours * 60)}m"
        elif hours < 24:
            return f"{hours:.1f}h"
        else:
            days = hours / 24
            return f"{days:.1f}d"


class BacktestMetricSerializer(serializers.ModelSerializer):
    """Serializer for backtest metrics (equity curve points)."""

    class Meta:
        model = BacktestMetric
        fields = [
            'id', 'timestamp', 'equity', 'cash',
            'open_positions_value', 'total_pnl',
            'unrealized_pnl', 'realized_pnl',
            'total_trades', 'winning_trades', 'losing_trades',
            'open_trades', 'peak_equity', 'drawdown',
            'drawdown_percentage'
        ]


class BacktestRunSerializer(serializers.ModelSerializer):
    """Serializer for backtest runs."""

    duration_seconds = serializers.SerializerMethodField()
    win_rate_formatted = serializers.SerializerMethodField()
    roi_formatted = serializers.SerializerMethodField()
    max_drawdown_formatted = serializers.SerializerMethodField()

    class Meta:
        model = BacktestRun
        fields = [
            'id', 'name', 'status', 'user',
            'symbols', 'timeframe', 'start_date', 'end_date',
            'strategy_params', 'initial_capital', 'position_size',
            'started_at', 'completed_at', 'duration_seconds',
            'error_message',
            # Metrics
            'total_trades', 'winning_trades', 'losing_trades',
            'win_rate', 'win_rate_formatted',
            'total_profit_loss', 'roi', 'roi_formatted',
            'max_drawdown', 'max_drawdown_amount', 'max_drawdown_formatted',
            'avg_trade_duration_hours', 'avg_profit_per_trade',
            'sharpe_ratio', 'profit_factor',
            'equity_curve',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'status', 'started_at', 'completed_at',
            'total_trades', 'winning_trades', 'losing_trades',
            'win_rate', 'total_profit_loss', 'roi',
            'max_drawdown', 'max_drawdown_amount',
            'avg_trade_duration_hours', 'avg_profit_per_trade',
            'sharpe_ratio', 'profit_factor', 'equity_curve',
            'created_at', 'updated_at'
        ]

    def get_duration_seconds(self, obj):
        """Get backtest execution duration in seconds."""
        return obj.duration_seconds()

    def get_win_rate_formatted(self, obj):
        """Format win rate as percentage string."""
        return f"{float(obj.win_rate):.2f}%"

    def get_roi_formatted(self, obj):
        """Format ROI as percentage string."""
        roi = float(obj.roi)
        sign = '+' if roi >= 0 else ''
        return f"{sign}{roi:.2f}%"

    def get_max_drawdown_formatted(self, obj):
        """Format max drawdown as currency and percentage."""
        dd_pct = float(obj.max_drawdown)  # This is the percentage
        dd_amount = float(obj.max_drawdown_amount)  # This is the dollar amount
        return f"${dd_amount:.2f} ({dd_pct:.2f}%)"


class StrategyOptimizationSerializer(serializers.ModelSerializer):
    """Serializer for strategy optimization results."""

    win_rate_formatted = serializers.SerializerMethodField()
    roi_formatted = serializers.SerializerMethodField()
    score_formatted = serializers.SerializerMethodField()

    class Meta:
        model = StrategyOptimization
        fields = [
            'id', 'name', 'user',
            'symbols', 'timeframe', 'date_range_start', 'date_range_end',
            'params', 'total_trades',
            'win_rate', 'win_rate_formatted',
            'roi', 'roi_formatted',
            'total_profit_loss', 'max_drawdown',
            'sharpe_ratio', 'profit_factor',
            'optimization_score', 'score_formatted',
            'backtest_run', 'tested_at'
        ]

    def get_win_rate_formatted(self, obj):
        """Format win rate as percentage string."""
        return f"{float(obj.win_rate):.2f}%"

    def get_roi_formatted(self, obj):
        """Format ROI as percentage string."""
        roi = float(obj.roi)
        sign = '+' if roi >= 0 else ''
        return f"{sign}{roi:.2f}%"

    def get_score_formatted(self, obj):
        """Format optimization score."""
        return f"{float(obj.optimization_score):.2f}/100"


class OptimizationRecommendationSerializer(serializers.ModelSerializer):
    """Serializer for AI-generated recommendations."""

    confidence_formatted = serializers.SerializerMethodField()
    improvement_summary = serializers.SerializerMethodField()

    class Meta:
        model = OptimizationRecommendation
        fields = [
            'id', 'type', 'title', 'description',
            'current_params', 'recommended_params',
            'expected_win_rate_improvement', 'expected_roi_improvement',
            'confidence_score', 'confidence_formatted',
            'improvement_summary',
            'status', 'user', 'applied_at',
            'feedback_notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def get_confidence_formatted(self, obj):
        """Format confidence score as percentage."""
        return f"{float(obj.confidence_score):.1f}%"

    def get_improvement_summary(self, obj):
        """Generate human-readable improvement summary."""
        win_rate_imp = float(obj.expected_win_rate_improvement)
        roi_imp = float(obj.expected_roi_improvement)

        parts = []
        if win_rate_imp > 0:
            parts.append(f"+{win_rate_imp:.1f}% win rate")
        if roi_imp > 0:
            parts.append(f"+{roi_imp:.1f}% ROI")

        return ", ".join(parts) if parts else "No improvement data"
