"""Models for the 4h order-block (ICT) engine — paper-first validation harness.

Isolated from the swing, day-trade and futures models so the order-block
strategy runs and is measured independently. Strategy: 4h break of structure
from the last opposing candle (order block), fixed 2R ATR target, both
directions, no signal filters (validated as the robust edge). Risk is managed
by fixed-fractional sizing plus a concurrent-position cap to bound drawdown.
Paper only; cost-aware (fee + slippage netted into P/L).
"""
from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

DEFAULT_OB_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT',
    'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'LTCUSDT', 'DOTUSDT', 'ATOMUSDT',
]


class OrderBlockStrategyConfig(models.Model):
    """Singleton config for the 4h order-block engine (admin-tunable)."""

    name = models.CharField(max_length=50, default='default', unique=True)
    enabled = models.BooleanField(
        default=False,
        help_text=_("Master switch for the 4h order-block paper harness"),
    )
    symbols = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Symbols to scan (default: 12 majors)"),
    )
    entry_timeframe = models.CharField(max_length=5, default='4h')
    rr = models.FloatField(default=2.0, help_text=_("Reward:risk multiple for the fixed target"))
    swing_k = models.PositiveIntegerField(default=2, help_text=_("Swing confirmation lag (bars)"))
    lookback = models.PositiveIntegerField(default=10, help_text=_("Bars to search for the order block"))
    sl_buffer_atr = models.FloatField(default=0.25, help_text=_("ATR buffer beyond the order block"))
    atr_period = models.PositiveIntegerField(default=14)
    account_equity = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('10000'),
        help_text=_("Starting equity base for fixed-fractional sizing (USDT)"),
    )
    risk_per_trade_pct = models.FloatField(
        default=1.0, help_text=_("Percent of current equity risked per trade"),
    )
    max_concurrent_positions = models.PositiveIntegerField(
        default=3, help_text=_("Cap on simultaneous open positions (correlated-exposure limit)"),
    )
    leverage = models.IntegerField(default=10)
    fee_rate = models.DecimalField(max_digits=8, decimal_places=6, default=Decimal('0.0004'))
    slippage_rate = models.DecimalField(max_digits=8, decimal_places=6, default=Decimal('0.0002'))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'order_block_strategy_config'
        verbose_name = _('Order Block Strategy Config')
        verbose_name_plural = _('Order Block Strategy Config')

    def __str__(self):
        return f"OrderBlockConfig({self.name}, enabled={self.enabled})"

    @classmethod
    def get_active(cls):
        """Return the config row, creating it with defaults if missing."""
        config, _created = cls.objects.get_or_create(
            name='default',
            defaults={'symbols': list(DEFAULT_OB_SYMBOLS)},
        )
        return config

    def scan_symbols(self):
        """Configured symbols, or the default majors when unset."""
        return self.symbols or list(DEFAULT_OB_SYMBOLS)


class OrderBlockPaperTrade(models.Model):
    """A simulated 4h order-block trade, sized fixed-fractional, closed net of cost."""

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
    risk_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, help_text=_("USDT risked to the stop"),
    )
    confidence = models.PositiveIntegerField(default=0)
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
        db_table = 'order_block_paper_trades'
        ordering = ['-created_at']
        verbose_name = _('Order Block Paper Trade')
        verbose_name_plural = _('Order Block Paper Trades')
        indexes = [
            models.Index(fields=['symbol', 'status']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"OB {self.direction} {self.symbol} [{self.status}]"


class OrderBlockSignal(models.Model):
    """A 4h order-block signal detected by the scanner (feed/analytics).

    Recorded whenever the entry rule fires, whether or not a paper trade was
    opened (a trade is skipped if one is already open for the symbol or the
    concurrency cap is reached), so the feed shows everything detected each 4h.
    """

    STATUS_CHOICES = [
        ('ACTIVE', _('Active')),
        ('EXECUTED', _('Executed')),
        ('SKIPPED', _('Skipped')),
        ('EXPIRED', _('Expired')),
    ]

    symbol = models.CharField(max_length=20, db_index=True)
    direction = models.CharField(max_length=10, choices=OrderBlockPaperTrade.DIRECTION_CHOICES)
    entry_timeframe = models.CharField(max_length=5, default='4h')
    candle_open_time = models.DateTimeField(help_text=_("Open time of the 4h candle this signal belongs to"))
    entry = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8)
    atr = models.DecimalField(max_digits=20, decimal_places=8)
    confidence = models.PositiveIntegerField(default=0)
    structure = models.CharField(max_length=10, blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE', db_index=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_block_signals'
        ordering = ['-created_at']
        verbose_name = _('Order Block Signal')
        verbose_name_plural = _('Order Block Signals')
        constraints = [
            models.UniqueConstraint(
                fields=['symbol', 'entry_timeframe', 'candle_open_time', 'direction'],
                name='order_block_signal_dedup',
            ),
        ]
        indexes = [
            models.Index(fields=['symbol', 'direction', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"OB {self.direction} {self.symbol} @ {self.entry}"

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
