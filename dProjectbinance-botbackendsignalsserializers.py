


# ============================================================================
# Optimization & Learning Serializers
# ============================================================================

class StrategyConfigHistorySerializer(BaseModelSerializer):
    """
    Strategy configuration history serializer.
    Shows config versions, parameters, and performance metrics.
    """
    fitness_score = serializers.SerializerMethodField()
    baseline_config_name = serializers.SerializerMethodField()
    
    class Meta:
        model = StrategyConfigHistory
        fields = [
            "id", "config_name", "volatility_level", "version",
            "parameters", "metrics", "improved", "improvement_percentage",
            "status", "applied_at", "trades_evaluated",
            "fitness_score", "baseline_config_name",
            "created_at", "updated_at", "notes"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
    
    def get_fitness_score(self, obj):
        """Calculate fitness score for this config."""
        return obj.calculate_fitness_score()
    
    def get_baseline_config_name(self, obj):
        """Get baseline config name if exists."""
        if obj.baseline_config:
            return f"{obj.baseline_config.config_name} v{obj.baseline_config.version}"
        return None


class OptimizationRunSerializer(BaseModelSerializer):
    """
    Optimization run serializer.
    Shows detailed information about optimization cycles.
    """
    baseline_config_name = serializers.SerializerMethodField()
    winning_config_name = serializers.SerializerMethodField()
    duration_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = OptimizationRun
        fields = [
            "id", "run_id", "trigger", "volatility_level",
            "baseline_config", "baseline_config_name",
            "winning_config", "winning_config_name",
            "candidates_tested", "improvement_found",
            "baseline_score", "best_score", "improvement_percentage",
            "status", "started_at", "completed_at",
            "duration_seconds", "duration_formatted",
            "trades_analyzed", "lookback_days",
            "results", "logs", "error_message",
            "notification_sent", "notification_sent_at"
        ]
        read_only_fields = ["id", "started_at"]
    
    def get_baseline_config_name(self, obj):
        """Get baseline config name."""
        if obj.baseline_config:
            return f"{obj.baseline_config.config_name} v{obj.baseline_config.version}"
        return None
    
    def get_winning_config_name(self, obj):
        """Get winning config name."""
        if obj.winning_config:
            return f"{obj.winning_config.config_name} v{obj.winning_config.version}"
        return None
    
    def get_duration_formatted(self, obj):
        """Format duration for display."""
        if obj.duration_seconds:
            minutes = obj.duration_seconds // 60
            seconds = obj.duration_seconds % 60
            return f"{minutes}m {seconds}s"
        return None


class TradeCounterSerializer(BaseModelSerializer):
    """
    Trade counter serializer.
    Shows progress towards optimization threshold.
    """
    percentage = serializers.SerializerMethodField()
    should_optimize = serializers.SerializerMethodField()
    
    class Meta:
        model = TradeCounter
        fields = [
            "id", "volatility_level", "trade_count", "threshold",
            "percentage", "should_optimize",
            "last_optimization", "last_reset"
        ]
        read_only_fields = ["id", "last_reset"]
    
    def get_percentage(self, obj):
        """Calculate percentage towards threshold."""
        if obj.threshold > 0:
            return round((obj.trade_count / obj.threshold) * 100, 1)
        return 0.0
    
    def get_should_optimize(self, obj):
        """Check if optimization should be triggered."""
        return obj.should_optimize()


# ============================================================================
# Optimization & Learning Serializers
# ============================================================================

class StrategyConfigHistorySerializer(BaseModelSerializer):
    """Strategy configuration history serializer."""
    fitness_score = serializers.SerializerMethodField()
    baseline_config_name = serializers.SerializerMethodField()
    
    class Meta:
        model = StrategyConfigHistory
        fields = [
            "id", "config_name", "volatility_level", "version",
            "parameters", "metrics", "improved", "improvement_percentage",
            "status", "applied_at", "trades_evaluated",
            "fitness_score", "baseline_config_name",
            "created_at", "updated_at", "notes"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
    
    def get_fitness_score(self, obj):
        return obj.calculate_fitness_score()
    
    def get_baseline_config_name(self, obj):
        if obj.baseline_config:
            return f"{obj.baseline_config.config_name} v{obj.baseline_config.version}"
        return None


class OptimizationRunSerializer(BaseModelSerializer):
    """Optimization run serializer."""
    baseline_config_name = serializers.SerializerMethodField()
    winning_config_name = serializers.SerializerMethodField()
    duration_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = OptimizationRun
        fields = [
            "id", "run_id", "trigger", "volatility_level",
            "baseline_config", "baseline_config_name",
            "winning_config", "winning_config_name",
            "candidates_tested", "improvement_found",
            "baseline_score", "best_score", "improvement_percentage",
            "status", "started_at", "completed_at",
            "duration_seconds", "duration_formatted",
            "trades_analyzed", "lookback_days",
            "results", "logs", "error_message",
            "notification_sent", "notification_sent_at"
        ]
        read_only_fields = ["id", "started_at"]
    
    def get_baseline_config_name(self, obj):
        if obj.baseline_config:
            return f"{obj.baseline_config.config_name} v{obj.baseline_config.version}"
        return None
    
    def get_winning_config_name(self, obj):
        if obj.winning_config:
            return f"{obj.winning_config.config_name} v{obj.winning_config.version}"
        return None
    
    def get_duration_formatted(self, obj):
        if obj.duration_seconds:
            minutes = obj.duration_seconds // 60
            seconds = obj.duration_seconds % 60
            return f"{minutes}m {seconds}s"
        return None


class TradeCounterSerializer(BaseModelSerializer):
    """Trade counter serializer."""
    percentage = serializers.SerializerMethodField()
    should_optimize = serializers.SerializerMethodField()
    
    class Meta:
        model = TradeCounter
        fields = [
            "id", "volatility_level", "trade_count", "threshold",
            "percentage", "should_optimize",
            "last_optimization", "last_reset"
        ]
        read_only_fields = ["id", "last_reset"]
    
    def get_percentage(self, obj):
        if obj.threshold > 0:
            return round((obj.trade_count / obj.threshold) * 100, 1)
        return 0.0
    
    def get_should_optimize(self, obj):
        return obj.should_optimize()
