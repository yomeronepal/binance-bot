"""
Backtesting Models
Database models for storing backtest results, trades, and optimization data.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

User = get_user_model()


class BacktestRun(models.Model):
    """
    Represents a single backtest execution.
    Stores configuration and overall results.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    # Metadata
    name = models.CharField(max_length=100, help_text="Descriptive name for this backtest")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    # Configuration
    symbols = models.JSONField(help_text="List of symbols to backtest", default=list)
    timeframe = models.CharField(max_length=10, default='5m', help_text="e.g., 1m, 5m, 15m, 1h, 4h, 1d")
    start_date = models.DateTimeField(help_text="Historical data start date")
    end_date = models.DateTimeField(help_text="Historical data end date")

    # Strategy Parameters
    strategy_params = models.JSONField(
        help_text="Strategy indicator parameters (RSI, EMA, MACD, etc.)",
        default=dict
    )

    # Initial Conditions
    initial_capital = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('10000.00'),
        help_text="Starting capital in USDT"
    )
    position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('100.00'),
        help_text="Position size per trade in USDT"
    )

    # Execution Info
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    # Performance Metrics (computed after backtest completes)
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    losing_trades = models.IntegerField(default=0)
    win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Percentage")

    total_profit_loss = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0.00'))
    roi = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Return on Investment %")

    max_drawdown = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Percentage")
    max_drawdown_amount = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0.00'))

    avg_trade_duration_hours = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    avg_profit_per_trade = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0.00'))

    sharpe_ratio = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    profit_factor = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    # Equity Curve (for charting)
    equity_curve = models.JSONField(
        default=list,
        help_text="List of {timestamp, equity} points"
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
        return f"Backtest: {self.name} ({self.status})"

    def duration_seconds(self):
        """Calculate backtest execution duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class BacktestTrade(models.Model):
    """
    Individual trade executed during a backtest.
    """
    DIRECTION_CHOICES = [
        ('LONG', 'Long'),
        ('SHORT', 'Short'),
    ]

    STATUS_CHOICES = [
        ('CLOSED_TP', 'Closed at Take Profit'),
        ('CLOSED_SL', 'Closed at Stop Loss'),
        ('CLOSED_MANUAL', 'Closed Manually'),
        ('CLOSED_END', 'Closed at End of Backtest'),
    ]

    # Foreign Keys
    backtest_run = models.ForeignKey(
        BacktestRun,
        on_delete=models.CASCADE,
        related_name='trades'
    )

    # Trade Info
    symbol = models.CharField(max_length=20)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    market_type = models.CharField(max_length=10, default='SPOT', help_text="SPOT or FUTURES")

    # Prices
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    exit_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8)

    # Position Details
    position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text="Position size in USDT"
    )
    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text="Quantity of asset"
    )
    leverage = models.IntegerField(null=True, blank=True)

    # Results
    profit_loss = models.DecimalField(max_digits=20, decimal_places=8)
    profit_loss_percentage = models.DecimalField(max_digits=10, decimal_places=4)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    # Timing
    opened_at = models.DateTimeField()
    closed_at = models.DateTimeField()
    duration_hours = models.DecimalField(max_digits=10, decimal_places=2)

    # Signal Data (for analysis)
    signal_confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    signal_indicators = models.JSONField(
        default=dict,
        help_text="Indicator values at signal time (RSI, MACD, etc.)"
    )

    # Risk Management
    risk_reward_ratio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['opened_at']
        indexes = [
            models.Index(fields=['backtest_run', 'opened_at']),
            models.Index(fields=['symbol']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.symbol} {self.direction} - ${self.profit_loss}"

    @property
    def is_profitable(self):
        return self.profit_loss > 0




class BacktestMetric(models.Model):
    """
    Time-series metrics during backtest execution.
    Used for equity curve, drawdown tracking, etc.
    """
    backtest_run = models.ForeignKey(
        BacktestRun,
        on_delete=models.CASCADE,
        related_name='metrics'
    )

    timestamp = models.DateTimeField()

    # Equity & Capital
    equity = models.DecimalField(max_digits=20, decimal_places=8)
    cash = models.DecimalField(max_digits=20, decimal_places=8)
    open_positions_value = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0.00'))

    # Performance
    total_pnl = models.DecimalField(max_digits=20, decimal_places=8)
    unrealized_pnl = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0.00'))
    realized_pnl = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0.00'))

    # Trade Counts
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    losing_trades = models.IntegerField(default=0)
    open_trades = models.IntegerField(default=0)

    # Drawdown
    peak_equity = models.DecimalField(max_digits=20, decimal_places=8)
    drawdown = models.DecimalField(max_digits=20, decimal_places=8)
    drawdown_percentage = models.DecimalField(max_digits=10, decimal_places=4)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['backtest_run', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.backtest_run.name} @ {self.timestamp}: ${self.equity}"
