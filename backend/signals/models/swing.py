"""Models for the 4h swing engine (paper-first validation harness).

Isolated from the day-trade and futures models so the swing strategy runs and
is measured independently. Strategy: 4h breakout gated by the 1D trend + ADX,
ATR-based ~2:1 exits. Paper only; cost-aware (fee + slippage netted into P/L).
"""
from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

DEFAULT_SWING_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT',
    'LTCUSDT', 'ADAUSDT', 'DOGEUSDT', 'SOLUSDT',
]


class SwingStrategyConfig(models.Model):
    """Singleton config for the 4h swing engine (admin-tunable)."""

    name = models.CharField(max_length=50, default='default', unique=True)
    enabled = models.BooleanField(
        default=False,
        help_text=_("Master switch for the 4h swing paper harness"),
    )
    symbols = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Symbols to scan (default: 8 majors)"),
    )
    entry_timeframe = models.CharField(max_length=5, default='4h')
    trend_timeframe = models.CharField(max_length=5, default='1d')
    adx_min = models.FloatField(default=20.0, help_text=_("1D ADX floor for a confirmed trend"))
    breakout_lookback = models.PositiveIntegerField(default=20, help_text=_("Prior 4h bars for the breakout"))
    sl_atr_mult = models.FloatField(default=1.5)
    tp_atr_mult = models.FloatField(default=3.0)
    margin_per_trade = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('100'))
    leverage = models.IntegerField(default=10)
    fee_rate = models.DecimalField(max_digits=8, decimal_places=6, default=Decimal('0.0004'))
    slippage_rate = models.DecimalField(max_digits=8, decimal_places=6, default=Decimal('0.0002'))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'swing_strategy_config'
        verbose_name = _('Swing Strategy Config')
        verbose_name_plural = _('Swing Strategy Config')

    def __str__(self):
        return f"SwingConfig({self.name}, enabled={self.enabled})"

    @classmethod
    def get_active(cls):
        """Return the config row, creating it with defaults if missing."""
        config, _created = cls.objects.get_or_create(
            name='default',
            defaults={'symbols': list(DEFAULT_SWING_SYMBOLS)},
        )
        return config

    def scan_symbols(self):
        """Configured symbols, or the default majors when unset."""
        return self.symbols or list(DEFAULT_SWING_SYMBOLS)


class SwingPaperTrade(models.Model):
    """A simulated 4h swing trade with ATR SL/TP, closed net of trading costs."""

    STATUS_CHOICES = [
        ('OPEN', _('Open')),
        ('CLOSED_TP', _('Closed - Take Profit')),
        ('CLOSED_SL', _('Closed - Stop Loss')),
    ]
    DIRECTION_CHOICES = [('LONG', _('Long')), ('SHORT', _('Short'))]

    symbol = models.CharField(max_length=20, db_index=True)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8)
    atr_at_entry = models.DecimalField(max_digits=20, decimal_places=8)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    position_size = models.DecimalField(max_digits=12, decimal_places=2, help_text=_("Margin (USDT)"))
    leverage = models.IntegerField(default=10)
    entry_time = models.DateTimeField()
    exit_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='OPEN', db_index=True)
    profit_loss = models.DecimalField(max_digits=20, decimal_places=8, default=0, help_text=_("Net of fees (USDT)"))
    fees_paid = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    profit_loss_percentage = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'swing_paper_trades'
        ordering = ['-created_at']
        verbose_name = _('Swing Paper Trade')
        verbose_name_plural = _('Swing Paper Trades')
        indexes = [
            models.Index(fields=['symbol', 'status']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Swing {self.direction} {self.symbol} [{self.status}]"


class SwingSignal(models.Model):
    """A 4h breakout signal detected by the swing scanner (feed/analytics).

    Recorded whenever the entry rule fires, whether or not a paper trade was
    opened (a trade is skipped if one is already open for the symbol), so the
    feed shows everything the engine detected each 4h.
    """

    STATUS_CHOICES = [
        ('ACTIVE', _('Active')),
        ('EXECUTED', _('Executed')),
        ('EXPIRED', _('Expired')),
    ]

    symbol = models.CharField(max_length=20, db_index=True)
    direction = models.CharField(max_length=10, choices=SwingPaperTrade.DIRECTION_CHOICES)
    entry_timeframe = models.CharField(max_length=5, default='4h')
    trend_timeframe = models.CharField(max_length=5, default='1d')
    candle_open_time = models.DateTimeField(help_text=_("Open time of the 4h candle this signal belongs to"))
    entry = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8)
    atr = models.DecimalField(max_digits=20, decimal_places=8)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE', db_index=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'swing_signals'
        ordering = ['-created_at']
        verbose_name = _('Swing Signal')
        verbose_name_plural = _('Swing Signals')
        constraints = [
            models.UniqueConstraint(
                fields=['symbol', 'entry_timeframe', 'candle_open_time', 'direction'],
                name='swing_signal_dedup',
            ),
        ]
        indexes = [
            models.Index(fields=['symbol', 'direction', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Swing {self.direction} {self.symbol} @ {self.entry}"

    @property
    def risk_reward_ratio(self):
        """Reward/risk to the take-profit, or None if risk is non-positive."""
        if self.direction == 'LONG':
            risk = float(self.entry - self.stop_loss)
            reward = float(self.take_profit - self.entry)
        else:
            risk = float(self.stop_loss - self.entry)
            reward = float(self.entry - self.take_profit)
        return round(reward / risk, 2) if risk > 0 else None
