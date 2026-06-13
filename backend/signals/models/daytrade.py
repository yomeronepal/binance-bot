"""Day-trading models for the 15m Market Structure Pullback strategy.

These tables are intentionally separate from the intraday Signal /
PaperTrade / PaperAccount models so the day-trade bot runs and is
monitored independently. The strategy is defined in
docs/15m_STRATEGY_V2.md and uses ATR-based scale-out exits
(TP1/TP2/runner) with a trailing stop.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


DIRECTION_CHOICES = [
    ('LONG', _('Long')),
    ('SHORT', _('Short')),
]

OPEN_TRADE_STATUSES = ['PENDING', 'OPEN', 'PARTIAL']


class DayTradeSignal(models.Model):
    """A day-trade signal emitted by the DayTradeSignalEngine.

    Carries the ATR-derived exit map (initial stop, TP1, TP2) and the
    15m candle bucket the signal belongs to. The unique constraint on
    (symbol, entry_timeframe, candle_open_time, direction) guarantees the
    same forming candle can never produce two rows, even when the 1-minute
    scanner re-evaluates it concurrently.
    """

    STATUS_CHOICES = [
        ('ACTIVE', _('Active')),
        ('EXPIRED', _('Expired')),
        ('EXECUTED', _('Executed')),
        ('CANCELLED', _('Cancelled')),
    ]

    symbol = models.CharField(
        max_length=20,
        db_index=True,
        help_text=_("Trading pair symbol"),
    )
    direction = models.CharField(
        max_length=10,
        choices=DIRECTION_CHOICES,
        help_text=_("Trade direction (LONG/SHORT)"),
    )
    entry_timeframe = models.CharField(
        max_length=5,
        default='15m',
        help_text=_("Entry/execution timeframe"),
    )
    trend_timeframe = models.CharField(
        max_length=5,
        default='1h',
        help_text=_("Higher timeframe used for the trend filter"),
    )
    candle_open_time = models.DateTimeField(
        help_text=_("Open time of the entry-timeframe candle this signal belongs to"),
    )

    entry = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(0)],
        help_text=_("Entry price"),
    )
    stop_loss = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(0)],
        help_text=_("Initial stop loss price (Entry -/+ 1.8 x ATR)"),
    )
    tp1 = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(0)],
        help_text=_("Take profit 1 price (2 x ATR)"),
    )
    tp2 = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(0)],
        help_text=_("Take profit 2 price (4 x ATR)"),
    )
    atr = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(0)],
        help_text=_("ATR value at signal time, used for trailing-stop sizing"),
    )

    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.0,
        help_text=_("Normalized confidence (0.0 - 1.0)"),
    )
    score = models.FloatField(
        default=0.0,
        help_text=_("Raw weighted score (max 13.5)"),
    )

    market_type = models.CharField(
        max_length=10,
        choices=[('SPOT', _('Spot')), ('FUTURES', _('Futures'))],
        default='FUTURES',
        help_text=_("Market type"),
    )
    leverage = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Leverage for futures"),
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        db_index=True,
        help_text=_("Signal status"),
    )
    source = models.CharField(
        max_length=100,
        default='daytrade_engine',
        help_text=_("Signal source"),
    )
    meta = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Structure, pullback zone, liquidity sweep and score breakdown"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Signal expiration time"),
    )

    class Meta:
        db_table = 'daytrade_signals'
        ordering = ['-created_at']
        verbose_name = _('Day-Trade Signal')
        verbose_name_plural = _('Day-Trade Signals')
        constraints = [
            models.UniqueConstraint(
                fields=['symbol', 'entry_timeframe', 'candle_open_time', 'direction'],
                name='daytrade_signal_dedup',
            ),
        ]
        indexes = [
            models.Index(fields=['symbol', 'direction', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['-confidence', '-created_at']),
        ]

    def __str__(self):
        return f"DayTrade {self.direction} {self.symbol} @ {self.entry}"

    @property
    def risk_reward_ratio(self):
        """Return the reward/risk ratio to TP2, or None if risk is non-positive."""
        if self.direction == 'LONG':
            risk = float(self.entry - self.stop_loss)
            reward = float(self.tp2 - self.entry)
        else:
            risk = float(self.stop_loss - self.entry)
            reward = float(self.entry - self.tp2)
        if risk <= 0:
            return None
        return round(reward / risk, 2)


class DayTradePaperTrade(models.Model):
    """A simulated day-trade with ATR scale-out exits and a trailing runner.

    Position is opened at full ``quantity`` and reduced as TP1 (50%) and
    TP2 (30%) fill; the remaining 20% runner is managed by ``trailing_stop``.
    ``remaining_quantity`` and the per-leg DayTradeTradeExit rows track the
    scale-out. A partial unique constraint allows only one live trade per
    symbol so the 1-minute scanner cannot open duplicates.
    """

    TRADE_STATUS_CHOICES = [
        ('PENDING', _('Pending Entry')),
        ('OPEN', _('Open')),
        ('PARTIAL', _('Partially Closed')),
        ('CLOSED_TP', _('Closed - Take Profit')),
        ('CLOSED_SL', _('Closed - Stop Loss')),
        ('CLOSED_TRAIL', _('Closed - Trailing Stop')),
        ('CLOSED_MANUAL', _('Closed - Manually')),
        ('CANCELLED', _('Cancelled')),
    ]

    signal = models.ForeignKey(
        'DayTradeSignal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paper_trades',
        help_text=_("Originating day-trade signal (nullable to preserve trades)"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daytrade_paper_trades',
        null=True,
        blank=True,
        help_text=_("Owner (null for the system-wide bot)"),
    )

    symbol = models.CharField(max_length=20, help_text=_("Trading pair symbol"))
    direction = models.CharField(
        max_length=10,
        choices=DIRECTION_CHOICES,
        help_text=_("Trade direction"),
    )
    market_type = models.CharField(
        max_length=10,
        choices=[('SPOT', _('Spot')), ('FUTURES', _('Futures'))],
        default='FUTURES',
        help_text=_("Market type"),
    )
    timeframe = models.CharField(
        max_length=5,
        default='15m',
        help_text=_("Entry timeframe"),
    )
    confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text=_("Signal confidence at entry"),
    )

    entry_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("Average entry price"),
    )
    entry_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Time the position was entered"),
    )
    position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('100.00'),
        help_text=_("Position notional in USDT (from risk-based sizing)"),
    )
    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("Total opened quantity of the asset"),
    )
    remaining_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("Quantity still open after partial exits"),
    )

    initial_stop_loss = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("Original 1.8 x ATR stop at entry"),
    )
    stop_loss = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("Current effective stop loss"),
    )
    trailing_stop = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text=_("Trailing stop for the runner (Highest -/+ 2 x ATR)"),
    )
    tp1_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("TP1 target (2 x ATR)"),
    )
    tp2_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("TP2 target (4 x ATR)"),
    )
    atr_at_entry = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("ATR at entry, used for trailing-stop distance"),
    )
    tp1_filled = models.BooleanField(default=False, help_text=_("TP1 leg closed"))
    tp2_filled = models.BooleanField(default=False, help_text=_("TP2 leg closed"))

    account_risk_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        help_text=_("Account risk percent used for position sizing"),
    )
    stop_distance = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text=_("Entry-to-stop distance used for position sizing"),
    )

    exit_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text=_("Final/average exit price once fully closed"),
    )
    exit_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Time the position was fully closed"),
    )

    realized_pnl = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        help_text=_("Realized P/L accumulated across partial exits (USDT)"),
    )
    profit_loss = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        help_text=_("Total realized P/L for the trade (USDT)"),
    )
    profit_loss_percentage = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        help_text=_("Total P/L as percent of notional"),
    )

    leverage = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(125)],
        help_text=_("Leverage for futures"),
    )

    status = models.CharField(
        max_length=20,
        choices=TRADE_STATUS_CHOICES,
        default='PENDING',
        help_text=_("Current trade status"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'daytrade_paper_trades'
        ordering = ['-created_at']
        verbose_name = _('Day-Trade Paper Trade')
        verbose_name_plural = _('Day-Trade Paper Trades')
        constraints = [
            models.UniqueConstraint(
                fields=['symbol'],
                condition=Q(status__in=OPEN_TRADE_STATUSES),
                name='daytrade_one_open_per_symbol',
            ),
        ]
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['symbol', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['-entry_time']),
        ]

    def __str__(self):
        return f"DayTrade {self.direction} {self.symbol} @ {self.entry_price} ({self.status})"

    @property
    def is_open(self):
        """True while the trade can still be managed."""
        return self.status in OPEN_TRADE_STATUSES

    @property
    def is_closed(self):
        """True once the trade is fully closed."""
        return self.status.startswith('CLOSED')

    @property
    def duration_hours(self):
        """Hours between entry and full exit, or None if still open."""
        if self.entry_time and self.exit_time:
            return (self.exit_time - self.entry_time).total_seconds() / 3600
        return None

    def stop_hit(self, current_price):
        """Return True if ``current_price`` has reached the current stop."""
        price = float(current_price)
        stop = float(self.trailing_stop if self.trailing_stop is not None else self.stop_loss)
        if self.direction == 'LONG':
            return price <= stop
        return price >= stop


class DayTradeTradeExit(models.Model):
    """One scale-out leg of a DayTradePaperTrade.

    Records each partial close (TP1, TP2, trailing stop, stop loss, or
    manual) so the multi-stage exit is fully auditable and metrics can be
    rebuilt from the legs.
    """

    EXIT_TYPE_CHOICES = [
        ('TP1', _('Take Profit 1')),
        ('TP2', _('Take Profit 2')),
        ('TRAIL', _('Trailing Stop')),
        ('SL', _('Stop Loss')),
        ('MANUAL', _('Manual')),
    ]

    trade = models.ForeignKey(
        'DayTradePaperTrade',
        on_delete=models.CASCADE,
        related_name='exits',
        help_text=_("Parent day-trade"),
    )
    exit_type = models.CharField(
        max_length=10,
        choices=EXIT_TYPE_CHOICES,
        help_text=_("Which leg of the exit plan this fill represents"),
    )
    price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("Fill price for this leg"),
    )
    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("Quantity closed in this leg"),
    )
    pnl = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        help_text=_("Realized P/L for this leg (USDT)"),
    )
    exit_time = models.DateTimeField(
        help_text=_("Time this leg was closed"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'daytrade_trade_exits'
        ordering = ['exit_time']
        verbose_name = _('Day-Trade Trade Exit')
        verbose_name_plural = _('Day-Trade Trade Exits')
        indexes = [
            models.Index(fields=['trade', 'exit_time']),
        ]

    def __str__(self):
        return f"{self.exit_type} {self.quantity} @ {self.price}"


class DayTradePaperAccount(models.Model):
    """Virtual account for the day-trade bot.

    Mirrors PaperAccount but aggregates over DayTradePaperTrade. Metrics
    are rebuilt from fully-closed trades in a single aggregate query.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daytrade_paper_account',
        null=True,
        blank=True,
        help_text=_("Owner (null for the system-wide bot account)"),
    )

    initial_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('10000.00'),
        help_text=_("Starting balance in USDT"),
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('10000.00'),
        help_text=_("Available balance in USDT"),
    )
    equity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('10000.00'),
        help_text=_("Balance plus unrealized P/L"),
    )

    total_pnl = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    realized_pnl = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    unrealized_pnl = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    losing_trades = models.IntegerField(default=0)
    win_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_("Win rate percentage"),
    )

    risk_per_trade_pct = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.10')), MaxValueValidator(Decimal('5.00'))],
        help_text=_("Default account risk per trade (percent)"),
    )
    max_open_trades = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text=_("Maximum concurrent open day-trades"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_trade_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'daytrade_paper_accounts'
        ordering = ['-created_at']
        verbose_name = _('Day-Trade Paper Account')
        verbose_name_plural = _('Day-Trade Paper Accounts')
        indexes = [
            models.Index(fields=['-total_pnl'], name='daytrade_acct_pnl_idx'),
            models.Index(fields=['-updated_at'], name='daytrade_acct_updated_idx'),
        ]

    def __str__(self):
        owner = self.user.username if self.user else 'bot'
        return f"DayTrade Account - {owner} (Balance: ${self.balance})"

    def update_metrics(self):
        """Rebuild counts, win rate, realized P/L and balances from closed trades."""
        from django.db.models import Sum, Count, Q as _Q

        trades = DayTradePaperTrade.objects.all()
        if self.user_id is not None:
            trades = trades.filter(user=self.user)
        closed = trades.filter(status__startswith='CLOSED')

        stats = closed.aggregate(
            total=Count('id'),
            winning=Count('id', filter=_Q(profit_loss__gt=0)),
            losing=Count('id', filter=_Q(profit_loss__lt=0)),
            realized=Sum('profit_loss'),
        )

        self.total_trades = stats['total'] or 0
        self.winning_trades = stats['winning'] or 0
        self.losing_trades = stats['losing'] or 0
        self.win_rate = (
            (self.winning_trades / self.total_trades) * 100
            if self.total_trades > 0 else Decimal('0.00')
        )
        self.realized_pnl = stats['realized'] or Decimal('0.00')
        self.balance = self.initial_balance + self.realized_pnl
        self.total_pnl = self.realized_pnl + self.unrealized_pnl
        self.equity = self.balance + self.unrealized_pnl
        self.save()
