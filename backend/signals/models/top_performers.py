"""
Top performing symbols, ranked monthly from Bot Performance (PaperTrade).

Each calculation snapshot stores the top-N symbols for a single calendar
month, computed from closed PaperTrade rows whose ``exit_time`` falls
inside that month. Snapshots are immutable history — re-running the
monthly cron updates the metrics for the same ``(symbol, period_start)``
tuple via ``update_or_create`` rather than appending duplicates.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class TopPerformingSymbol(models.Model):
    """
    A single (symbol, month) snapshot — its rank in that month's top-N.

    Source: ``PaperTrade`` rows with ``status='CLOSED'`` and
    ``exit_time`` between ``period_start`` and ``period_end``. Ranking
    metric: aggregate PnL across all closed paper trades for that
    symbol in the period (sum of ``profit_loss``).
    """

    symbol = models.CharField(
        max_length=20,
        help_text=_("Trading pair symbol, e.g. BTCUSDT"),
    )
    period_start = models.DateField(
        help_text=_("First day of the calendar month covered (YYYY-MM-01)"),
    )
    period_end = models.DateField(
        help_text=_("Last day of the calendar month (inclusive)"),
    )

    rank = models.PositiveSmallIntegerField(
        help_text=_("1 = highest PnL in the period; 10 = lowest of the top 10"),
    )

    total_trades = models.PositiveIntegerField(default=0)
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    win_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text=_("Win percentage (0-100), 1 d.p."),
    )

    total_pnl = models.DecimalField(
        max_digits=14, decimal_places=4, default=0,
        help_text=_("Sum of profit_loss in USDT for all closed trades in the period"),
    )
    total_pnl_pct = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        help_text=_("Sum of profit_loss_percentage values"),
    )
    avg_pnl_pct = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        help_text=_("Average profit_loss_percentage per trade"),
    )
    best_trade_pct = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        help_text=_("Largest single-trade profit_loss_percentage in the period"),
    )
    worst_trade_pct = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        help_text=_("Largest single-trade loss percentage in the period (signed)"),
    )

    calculated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("When this row was last (re)calculated"),
    )

    class Meta:
        db_table = 'top_performing_symbols'
        ordering = ['-period_start', 'rank']
        unique_together = [('symbol', 'period_start')]
        verbose_name = _('Top Performing Symbol')
        verbose_name_plural = _('Top Performing Symbols')
        indexes = [
            models.Index(fields=['-period_start', 'rank'],
                          name='topperf_period_rank_idx'),
            models.Index(fields=['symbol', '-period_start'],
                          name='topperf_symbol_period_idx'),
        ]

    def __str__(self):
        return f"#{self.rank} {self.symbol} {self.period_start:%Y-%m} pnl={self.total_pnl}"

    @classmethod
    def latest_top_n(cls, n=10):
        """Return the most recent month's top-N rows (ordered by rank)."""
        latest_period = cls.objects.values_list('period_start', flat=True).first()
        if latest_period is None:
            return cls.objects.none()
        return cls.objects.filter(period_start=latest_period).order_by('rank')[:n]

    @classmethod
    def for_period(cls, period_start):
        """All rows for a specific month, ordered by rank."""
        return cls.objects.filter(period_start=period_start).order_by('rank')
