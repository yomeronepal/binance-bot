"""
Monte Carlo Simulation Models

Monte Carlo simulation provides statistical robustness testing by running
thousands of simulations with randomized parameters to understand the
probability distribution of outcomes.

Key Metrics:
- Expected Value (Mean Return)
- Standard Deviation (Risk)
- Confidence Intervals (95%, 99%)
- Probability of Profit
- Value at Risk (VaR)
- Maximum Drawdown Distribution
- Win Rate Distribution
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import json

User = get_user_model()


class MonteCarloSimulation(models.Model):
    """
    Monte Carlo Simulation - Statistical Robustness Testing

    Runs N simulations with randomized parameters to assess strategy robustness
    through statistical analysis.
    """

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    # Basic Information
    name = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='montecarlo_simulations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    # Simulation Parameters
    symbols = models.JSONField(default=list, help_text="List of trading symbols")
    timeframe = models.CharField(max_length=10, default='5m', help_text="Candle timeframe (e.g., 5m, 15m, 1h)")
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    # Monte Carlo Configuration
    num_simulations = models.IntegerField(default=1000, help_text="Number of simulation runs (typically 1000-10000)")

    # Strategy Parameters (base values)
    strategy_params = models.JSONField(default=dict, help_text="Base strategy parameters")

    # Parameter Randomization (how much to vary each parameter)
    randomization_config = models.JSONField(
        default=dict,
        help_text="Randomization ranges for each parameter (e.g., {'rsi_oversold': {'min': 25, 'max': 35}})"
    )

    # Capital Configuration
    initial_capital = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('10000.00'))
    position_size = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('100.00'))

    # Statistical Results - Central Tendency
    mean_return = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Average ROI across all simulations")
    median_return = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Median ROI")

    # Statistical Results - Dispersion
    std_deviation = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Standard deviation of returns")
    variance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Variance of returns")

    # Confidence Intervals
    confidence_95_lower = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    confidence_95_upper = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    confidence_99_lower = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    confidence_99_upper = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Probability Metrics
    probability_of_profit = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="% of simulations with positive ROI")
    probability_of_loss = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="% of simulations with negative ROI")

    # Risk Metrics
    value_at_risk_95 = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="VaR at 95% confidence")
    value_at_risk_99 = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="VaR at 99% confidence")

    # Drawdown Statistics
    mean_max_drawdown = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    worst_case_drawdown = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    best_case_drawdown = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Best/Worst Cases
    best_case_return = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    worst_case_return = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Sharpe Ratio Statistics
    mean_sharpe_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    median_sharpe_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    # Win Rate Statistics
    mean_win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    median_win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    # Execution Tracking
    completed_simulations = models.IntegerField(default=0)
    failed_simulations = models.IntegerField(default=0)

    # Robustness Assessment
    is_statistically_robust = models.BooleanField(default=False)
    robustness_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="0-100 robustness score")
    robustness_reasons = models.TextField(blank=True, help_text="Explanation of robustness assessment")

    # Task Management
    task_id = models.CharField(max_length=255, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'montecarlo_simulations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['completed_at']),
        ]

    def __str__(self):
        return f"MC Simulation #{self.id}: {self.name} ({self.status})"

    def execution_time_seconds(self):
        """Calculate execution time in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def progress_percentage(self):
        """Calculate progress percentage."""
        if self.num_simulations > 0:
            return int((self.completed_simulations / self.num_simulations) * 100)
        return 0


class MonteCarloRun(models.Model):
    """
    Individual Monte Carlo Simulation Run

    Stores results from each individual simulation with randomized parameters.
    """

    simulation = models.ForeignKey(MonteCarloSimulation, on_delete=models.CASCADE, related_name='runs')
    run_number = models.IntegerField(help_text="Simulation run number (1 to N)")

    # Randomized Parameters Used
    parameters_used = models.JSONField(default=dict, help_text="The randomized parameters for this run")

    # Performance Metrics
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    losing_trades = models.IntegerField(default=0)
    win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    # Returns
    total_profit_loss = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    roi = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Risk Metrics
    max_drawdown = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    max_drawdown_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    sharpe_ratio = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
    profit_factor = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'montecarlo_runs'
        ordering = ['run_number']
        indexes = [
            models.Index(fields=['simulation', 'run_number']),
            models.Index(fields=['simulation', 'roi']),
        ]
        unique_together = [['simulation', 'run_number']]

    def __str__(self):
        return f"MC Run #{self.run_number} (Simulation {self.simulation.id}): ROI {self.roi}%"


class MonteCarloDistribution(models.Model):
    """
    Distribution Data for Visualization

    Stores histogram data for various metrics to enable distribution charts.
    """

    METRIC_CHOICES = [
        ('ROI', 'ROI Distribution'),
        ('DRAWDOWN', 'Max Drawdown Distribution'),
        ('WIN_RATE', 'Win Rate Distribution'),
        ('SHARPE', 'Sharpe Ratio Distribution'),
        ('PROFIT_FACTOR', 'Profit Factor Distribution'),
        ('TOTAL_TRADES', 'Total Trades Distribution'),
    ]

    simulation = models.ForeignKey(MonteCarloSimulation, on_delete=models.CASCADE, related_name='distributions')
    metric = models.CharField(max_length=20, choices=METRIC_CHOICES)

    # Histogram Data
    bins = models.JSONField(default=list, help_text="List of bin edges")
    frequencies = models.JSONField(default=list, help_text="List of frequencies for each bin")

    # Distribution Statistics
    mean = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    median = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    std_dev = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Percentiles
    percentile_5 = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    percentile_25 = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    percentile_75 = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    percentile_95 = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        db_table = 'montecarlo_distributions'
        unique_together = [['simulation', 'metric']]
        indexes = [
            models.Index(fields=['simulation', 'metric']),
        ]

    def __str__(self):
        return f"Distribution: {self.metric} (Simulation {self.simulation.id})"
