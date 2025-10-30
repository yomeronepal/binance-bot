"""
Strategy Optimization Models
Track configuration versions, performance metrics, and learning history
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json


class StrategyConfigHistory(models.Model):
    """
    Stores historical strategy configurations and their performance metrics.
    Used for auto-optimization and continuous learning.
    """
    VOLATILITY_CHOICES = [
        ('HIGH', 'High Volatility'),
        ('MEDIUM', 'Medium Volatility'),
        ('LOW', 'Low Volatility'),
        ('ALL', 'All Volatility Levels'),
    ]

    STATUS_CHOICES = [
        ('TESTING', 'Testing'),
        ('ACTIVE', 'Active'),
        ('ARCHIVED', 'Archived'),
        ('FAILED', 'Failed'),
    ]

    # Identification
    config_name = models.CharField(max_length=100, help_text="Configuration name/version")
    volatility_level = models.CharField(max_length=10, choices=VOLATILITY_CHOICES, default='ALL')
    version = models.IntegerField(default=1)

    # Configuration Parameters
    parameters = models.JSONField(
        help_text="Strategy parameters (RSI, ADX, SL/TP multipliers, etc.)"
    )

    # Performance Metrics
    metrics = models.JSONField(
        help_text="Performance metrics (win_rate, profit_factor, sharpe_ratio, etc.)",
        null=True,
        blank=True
    )

    # Optimization Info
    improved = models.BooleanField(
        default=False,
        help_text="Whether this config improved over previous baseline"
    )
    improvement_percentage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage improvement over baseline"
    )
    baseline_config = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='improvements',
        help_text="Previous config this was compared against"
    )

    # Status & Metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TESTING')
    applied_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this config was applied to live/paper trading"
    )

    # Backtest Reference
    backtest_run = models.ForeignKey(
        'BacktestRun',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='config_versions',
        help_text="Backtest run used to evaluate this config"
    )

    # Trade Count Tracking
    trades_evaluated = models.IntegerField(
        default=0,
        help_text="Number of trades used to evaluate this config"
    )

    # User & Timestamps
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='strategy_configs'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Notes
    notes = models.TextField(blank=True, help_text="Optimization notes or comments")

    class Meta:
        db_table = 'strategy_config_history'
        ordering = ['-created_at']
        verbose_name = 'Strategy Config History'
        verbose_name_plural = 'Strategy Config Histories'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['volatility_level', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['improved', '-created_at']),
        ]

    def __str__(self):
        return f"{self.config_name} v{self.version} ({self.volatility_level}) - {self.status}"

    def get_metric(self, key, default=None):
        """Get specific metric from metrics JSON"""
        if self.metrics:
            return self.metrics.get(key, default)
        return default

    def get_parameter(self, key, default=None):
        """Get specific parameter from parameters JSON"""
        if self.parameters:
            return self.parameters.get(key, default)
        return default

    def calculate_fitness_score(self):
        """
        Calculate overall fitness score for this configuration.
        Used for comparison and optimization.

        Score = (win_rate * 0.3) + (profit_factor * 0.25) + (sharpe_ratio * 0.2)
                + (roi * 0.15) - (max_drawdown * 0.1)
        """
        if not self.metrics:
            return 0.0

        win_rate = float(self.metrics.get('win_rate', 0))
        profit_factor = float(self.metrics.get('profit_factor', 0))
        sharpe_ratio = float(self.metrics.get('sharpe_ratio', 0))
        roi = float(self.metrics.get('roi', 0))
        max_drawdown = abs(float(self.metrics.get('max_drawdown', 0)))

        # Normalize and weight components
        score = (
            (win_rate * 0.3) +  # Win rate (0-100)
            (min(profit_factor, 5) * 20 * 0.25) +  # Profit factor (normalize to 0-100)
            (min(sharpe_ratio, 3) * 33.33 * 0.2) +  # Sharpe ratio (normalize to 0-100)
            (min(roi, 100) * 0.15) +  # ROI percentage
            (-max_drawdown * 0.1)  # Penalty for drawdown
        )

        return round(score, 2)

    def mark_as_active(self):
        """Mark this config as active and archive others for same volatility"""
        # Archive other active configs for same volatility
        StrategyConfigHistory.objects.filter(
            volatility_level=self.volatility_level,
            status='ACTIVE'
        ).exclude(id=self.id).update(status='ARCHIVED')

        # Activate this config
        self.status = 'ACTIVE'
        self.applied_at = timezone.now()
        self.save()


class OptimizationRun(models.Model):
    """
    Tracks each optimization cycle run.
    Records what was tested, results, and decisions made.
    """
    TRIGGER_CHOICES = [
        ('TRADE_COUNT', 'Trade Count Threshold'),
        ('SCHEDULED', 'Scheduled Run'),
        ('MANUAL', 'Manual Trigger'),
        ('PERFORMANCE_DROP', 'Performance Drop Detected'),
    ]

    STATUS_CHOICES = [
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    # Run Info
    run_id = models.CharField(max_length=50, unique=True, help_text="Unique run identifier")
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES)
    volatility_level = models.CharField(max_length=10, default='ALL')

    # Baseline & Results
    baseline_config = models.ForeignKey(
        StrategyConfigHistory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='baseline_for_runs',
        help_text="Config being compared against"
    )
    winning_config = models.ForeignKey(
        StrategyConfigHistory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_runs',
        help_text="Best performing config from this run"
    )

    # Candidates Tested
    candidates_tested = models.IntegerField(default=0)
    improvement_found = models.BooleanField(default=False)

    # Performance Comparison
    baseline_score = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    best_score = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    improvement_percentage = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Execution Details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RUNNING')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)

    # Trade Context
    trades_analyzed = models.IntegerField(default=0)
    lookback_days = models.IntegerField(default=30)

    # Results & Logs
    results = models.JSONField(
        null=True,
        blank=True,
        help_text="Detailed results including all candidate scores"
    )
    logs = models.TextField(blank=True, help_text="Execution logs")
    error_message = models.TextField(blank=True)

    # Notifications
    notification_sent = models.BooleanField(default=False)
    notification_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'optimization_run'
        ordering = ['-started_at']
        verbose_name = 'Optimization Run'
        verbose_name_plural = 'Optimization Runs'
        indexes = [
            models.Index(fields=['-started_at']),
            models.Index(fields=['status', '-started_at']),
            models.Index(fields=['improvement_found', '-started_at']),
        ]

    def __str__(self):
        return f"OptimizationRun {self.run_id} - {self.status}"

    def mark_completed(self, winning_config=None):
        """Mark run as completed and calculate duration"""
        from datetime import datetime

        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.duration_seconds = int((self.completed_at - self.started_at).total_seconds())

        if winning_config:
            self.winning_config = winning_config
            self.improvement_found = True

            if self.baseline_config:
                baseline_score = self.baseline_config.calculate_fitness_score()
                winning_score = winning_config.calculate_fitness_score()

                self.baseline_score = baseline_score
                self.best_score = winning_score

                if baseline_score > 0:
                    self.improvement_percentage = (
                        (winning_score - baseline_score) / baseline_score * 100
                    )

        self.save()


class TradeCounter(models.Model):
    """
    Tracks trade counts to trigger optimization cycles.
    One record per volatility level.
    """
    volatility_level = models.CharField(max_length=10, unique=True)
    trade_count = models.IntegerField(default=0)
    threshold = models.IntegerField(default=200, help_text="Trigger optimization after N trades")
    last_optimization = models.DateTimeField(null=True, blank=True)
    last_reset = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trade_counter'
        verbose_name = 'Trade Counter'
        verbose_name_plural = 'Trade Counters'

    def __str__(self):
        return f"{self.volatility_level}: {self.trade_count}/{self.threshold}"

    def increment(self):
        """Increment counter and check if optimization should be triggered"""
        self.trade_count += 1
        self.save()
        return self.should_optimize()

    def should_optimize(self):
        """Check if trade count has reached threshold"""
        return self.trade_count >= self.threshold

    def reset(self):
        """Reset counter after optimization"""
        self.trade_count = 0
        self.last_optimization = timezone.now()
        self.last_reset = timezone.now()
        self.save()
