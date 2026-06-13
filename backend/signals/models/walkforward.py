"""
Walk-Forward Optimization Models
Database models for walk-forward analysis results.
"""
from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()


class WalkForwardOptimization(models.Model):
    """
    Represents a walk-forward optimization run.
    Tests strategy robustness by optimizing on rolling windows.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    # Metadata
    name = models.CharField(max_length=100, help_text="Descriptive name")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    # Configuration
    symbols = models.JSONField(help_text="List of symbols to test", default=list)
    timeframe = models.CharField(max_length=10, default='5m')
    start_date = models.DateTimeField(help_text="Overall start date")
    end_date = models.DateTimeField(help_text="Overall end date")

    # Walk-Forward Parameters
    training_window_days = models.IntegerField(
        default=90,
        help_text="Training period duration in days"
    )
    testing_window_days = models.IntegerField(
        default=30,
        help_text="Out-of-sample testing period in days"
    )
    step_days = models.IntegerField(
        default=30,
        help_text="How many days to roll forward each iteration"
    )

    # Strategy Parameters to Optimize
    parameter_ranges = models.JSONField(
        help_text="Parameter ranges to test in optimization phase",
        default=dict
    )
    optimization_method = models.CharField(
        max_length=20,
        default='grid',
        choices=[('grid', 'Grid Search'), ('random', 'Random Search')]
    )

    # Trading Parameters
    initial_capital = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('10000.00')
    )
    position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('100.00')
    )

    # Execution Info
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    # Overall Results (aggregated from all windows)
    total_windows = models.IntegerField(default=0)
    completed_windows = models.IntegerField(default=0)

    # Aggregate Performance
    avg_in_sample_win_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    avg_out_sample_win_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    avg_in_sample_roi = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    avg_out_sample_roi = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00')
    )

    # Performance Degradation Metric
    performance_degradation = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="% drop from in-sample to out-of-sample performance"
    )

    # Consistency Score (0-100)
    consistency_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="How consistent results are across windows"
    )

    # Overall Verdict
    is_robust = models.BooleanField(
        default=False,
        help_text="True if strategy passes robustness checks"
    )
    robustness_notes = models.TextField(
        null=True,
        blank=True,
        help_text="Explanation of robustness verdict"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"Walk-Forward: {self.name} ({self.status})"

    def duration_seconds(self):
        """Calculate execution duration."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None


class WalkForwardWindow(models.Model):
    """
    Represents a single window in walk-forward optimization.
    Each window has an optimization phase (in-sample) and testing phase (out-of-sample).
    """
    walk_forward = models.ForeignKey(
        WalkForwardOptimization,
        on_delete=models.CASCADE,
        related_name='windows'
    )

    # Window Identification
    window_number = models.IntegerField(help_text="Sequential window number")

    # Date Ranges
    training_start = models.DateTimeField(help_text="In-sample optimization start")
    training_end = models.DateTimeField(help_text="In-sample optimization end")
    testing_start = models.DateTimeField(help_text="Out-of-sample testing start")
    testing_end = models.DateTimeField(help_text="Out-of-sample testing end")

    # Optimization Results (In-Sample)
    in_sample_backtest_id = models.IntegerField(null=True, blank=True)
    best_params = models.JSONField(
        help_text="Best parameters found during optimization",
        default=dict
    )
    in_sample_total_trades = models.IntegerField(default=0)
    in_sample_win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    in_sample_roi = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    in_sample_sharpe = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    in_sample_max_drawdown = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Testing Results (Out-of-Sample)
    out_sample_backtest_id = models.IntegerField(null=True, blank=True)
    out_sample_total_trades = models.IntegerField(default=0)
    out_sample_win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    out_sample_roi = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    out_sample_sharpe = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    out_sample_max_drawdown = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Performance Comparison
    performance_drop_pct = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="% performance drop from in-sample to out-of-sample"
    )

    # Window Status
    status = models.CharField(
        max_length=20,
        default='PENDING',
        choices=[
            ('PENDING', 'Pending'),
            ('OPTIMIZING', 'Optimizing'),
            ('TESTING', 'Testing'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed')
        ]
    )
    error_message = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['walk_forward', 'window_number']
        unique_together = ['walk_forward', 'window_number']
        indexes = [
            models.Index(fields=['walk_forward', 'window_number']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Window {self.window_number} - {self.walk_forward.name}"


class WalkForwardMetric(models.Model):
    """
    Time-series metrics for walk-forward optimization.
    Tracks cumulative performance across windows.
    """
    walk_forward = models.ForeignKey(
        WalkForwardOptimization,
        on_delete=models.CASCADE,
        related_name='metrics'
    )

    window_number = models.IntegerField()
    window_type = models.CharField(
        max_length=20,
        choices=[('in_sample', 'In-Sample'), ('out_sample', 'Out-of-Sample')]
    )

    # Cumulative Metrics
    cumulative_trades = models.IntegerField(default=0)
    cumulative_pnl = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0.00'))
    cumulative_roi = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Window-Specific Metrics
    window_trades = models.IntegerField(default=0)
    window_pnl = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0.00'))
    window_win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['walk_forward', 'window_number', 'window_type']
        indexes = [
            models.Index(fields=['walk_forward', 'window_number']),
        ]

    def __str__(self):
        return f"Metrics W{self.window_number} ({self.window_type}) - {self.walk_forward.name}"
