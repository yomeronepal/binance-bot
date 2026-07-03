"""Day-trading models for the 15m Market Structure Pullback strategy.

These tables are intentionally separate from the intraday Signal /
PaperTrade / PaperAccount models so the day-trade bot runs and is
monitored independently. The strategy is defined in
docs/15m_STRATEGY_V2.md and uses ATR-based scale-out exits
(TP1/TP2/runner) with a trailing stop.
"""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
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
    is_priority = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("Generated inside an active DayTradeSession window"),
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

    def save(self, *args, **kwargs):
        """Flag priority from the active session windows on first save."""
        if not self.pk:
            self.is_priority = DayTradeSession.is_priority_now()
        super().save(*args, **kwargs)

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
    is_priority = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("Copied from the signal: opened inside a session window"),
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


class DayTradeStrategyConfig(models.Model):
    """Admin-tunable parameters for the 15m Market Structure Pullback engine.

    The DayTradeSignalEngine and execution monitor load the active row, so
    every threshold, ATR multiplier, scale-out size and score weight can be
    changed from Django admin without a redeploy.
    """

    VWAP_ANCHOR_CHOICES = [
        ('daily_utc', _('Daily (00:00 UTC reset)')),
        ('rolling', _('Rolling N-period')),
    ]

    name = models.CharField(
        max_length=50,
        unique=True,
        default='default',
        help_text=_("Config name (one active config drives the engine)"),
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this config is the one the engine uses"),
    )
    symbols = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Symbols to scan, e.g. [\"BTCUSDT\", \"ETHUSDT\"]. Use [\"*\"] for all."),
    )
    universe_top_n = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(0), MaxValueValidator(1000)],
        help_text=_("When symbols is [\"*\"], scan only the top N pairs by 24h volume (0 = all)"),
    )
    signal_cooldown_minutes = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(0), MaxValueValidator(1440)],
        help_text=_("After a symbol's trade closes, suppress new signals for it for this many minutes (0 = disabled)"),
    )

    entry_timeframe = models.CharField(max_length=5, default='15m', help_text=_("Entry/execution timeframe"))
    trend_timeframe = models.CharField(max_length=5, default='1h', help_text=_("Higher-timeframe trend filter"))
    trend_ema_fast = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(2), MaxValueValidator(400)],
        help_text=_("Fast EMA for the trend filter"),
    )
    trend_ema_slow = models.PositiveIntegerField(
        default=200,
        validators=[MinValueValidator(5), MaxValueValidator(500)],
        help_text=_("Slow EMA for the trend filter"),
    )

    pivot_lookback = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(2), MaxValueValidator(20)],
        help_text=_("Candles each side that define a confirmed swing point"),
    )

    pullback_ema_fast = models.PositiveIntegerField(
        default=20,
        validators=[MinValueValidator(2), MaxValueValidator(200)],
        help_text=_("Fast EMA of the pullback zone"),
    )
    pullback_ema_slow = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(5), MaxValueValidator(400)],
        help_text=_("Slow EMA of the pullback zone"),
    )
    use_vwap = models.BooleanField(default=True, help_text=_("Include VWAP in the pullback zone"))
    vwap_anchor = models.CharField(
        max_length=12,
        choices=VWAP_ANCHOR_CHOICES,
        default='daily_utc',
        help_text=_("How VWAP is anchored"),
    )

    rsi_period = models.PositiveIntegerField(
        default=14,
        validators=[MinValueValidator(2), MaxValueValidator(100)],
        help_text=_("RSI period"),
    )
    rsi_threshold = models.FloatField(
        default=50.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(99.0)],
        help_text=_("RSI midline (LONG above, SHORT below)"),
    )
    macd_fast = models.PositiveIntegerField(default=12, validators=[MinValueValidator(2), MaxValueValidator(100)])
    macd_slow = models.PositiveIntegerField(default=26, validators=[MinValueValidator(3), MaxValueValidator(200)])
    macd_signal = models.PositiveIntegerField(default=9, validators=[MinValueValidator(2), MaxValueValidator(100)])

    volume_multiplier = models.FloatField(
        default=1.3,
        validators=[MinValueValidator(0.5), MaxValueValidator(5.0)],
        help_text=_("Volume must exceed this multiple of its average"),
    )
    volume_avg_period = models.PositiveIntegerField(
        default=20,
        validators=[MinValueValidator(2), MaxValueValidator(200)],
        help_text=_("Lookback for the average-volume baseline"),
    )

    adx_min = models.FloatField(
        default=20.0,
        validators=[MinValueValidator(5.0), MaxValueValidator(60.0)],
        help_text=_("Minimum ADX for a tradeable trend"),
    )
    adx_period = models.PositiveIntegerField(
        default=14,
        validators=[MinValueValidator(2), MaxValueValidator(100)],
        help_text=_("ADX period"),
    )

    sl_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('2.50'),
        validators=[MinValueValidator(Decimal('0.10')), MaxValueValidator(Decimal('20.00'))],
        help_text=_("Stop loss as percent from entry (v1-style single SL)"),
    )
    tp_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('6.00'),
        validators=[MinValueValidator(Decimal('0.10')), MaxValueValidator(Decimal('50.00'))],
        help_text=_("Take profit as percent from entry (v1-style single TP)"),
    )

    atr_period = models.PositiveIntegerField(
        default=14,
        validators=[MinValueValidator(2), MaxValueValidator(100)],
        help_text=_("ATR period (used for the ATR-regime score component)"),
    )
    sl_atr_mult = models.FloatField(
        default=1.8,
        validators=[MinValueValidator(0.2), MaxValueValidator(10.0)],
        help_text=_("Initial stop = entry -/+ this x ATR"),
    )
    tp1_atr_mult = models.FloatField(
        default=2.0,
        validators=[MinValueValidator(0.2), MaxValueValidator(20.0)],
        help_text=_("TP1 distance in ATR multiples"),
    )
    tp1_close_pct = models.FloatField(
        default=50.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text=_("Percent of position closed at TP1"),
    )
    tp2_atr_mult = models.FloatField(
        default=4.0,
        validators=[MinValueValidator(0.2), MaxValueValidator(40.0)],
        help_text=_("TP2 distance in ATR multiples"),
    )
    tp2_close_pct = models.FloatField(
        default=30.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text=_("Percent of position closed at TP2"),
    )
    runner_pct = models.FloatField(
        default=20.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text=_("Percent left as the trailing runner"),
    )
    trail_atr_mult = models.FloatField(
        default=2.0,
        validators=[MinValueValidator(0.2), MaxValueValidator(20.0)],
        help_text=_("Trailing-stop distance in ATR multiples"),
    )
    risk_per_trade_pct = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.10')), MaxValueValidator(Decimal('5.00'))],
        help_text=_("Account risk per trade (percent) — unused while fixed margin sizing is on"),
    )
    margin_per_trade = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('1.00'))],
        help_text=_("Fixed margin (USDT) committed per paper trade"),
    )
    leverage = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(125)],
        help_text=_("Leverage applied to each paper trade"),
    )

    enable_liquidity_sweep = models.BooleanField(
        default=True,
        help_text=_("Score the optional liquidity-sweep confirmation"),
    )

    weight_trend = models.FloatField(default=3.0, help_text=_("1H trend filter weight"))
    weight_structure = models.FloatField(default=3.0, help_text=_("Market-structure weight"))
    weight_volume = models.FloatField(default=2.0, help_text=_("Volume confirmation weight"))
    weight_pullback = models.FloatField(default=2.0, help_text=_("Pullback-zone weight"))
    weight_macd = models.FloatField(default=1.5, help_text=_("MACD momentum weight"))
    weight_rsi = models.FloatField(default=1.0, help_text=_("RSI momentum weight"))
    weight_atr = models.FloatField(default=1.0, help_text=_("ATR regime weight"))
    min_score = models.FloatField(
        default=8.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(13.5)],
        help_text=_("Minimum weighted score (of 13.5) to emit a signal"),
    )
    min_confidence = models.FloatField(
        default=0.70,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text=_("Minimum confidence (0-1) to emit a signal and paper trade it"),
    )

    structure_quality_enabled = models.BooleanField(
        default=False,
        help_text=_("V3: use significance-filtered swings + structure bonus (validated: off)"),
    )
    structure_min_swing_atr = models.FloatField(
        default=0.0,
        help_text=_("Ignore swing legs smaller than this x ATR (0 = off)"),
    )
    weight_structure_bonus = models.FloatField(
        default=0.0,
        help_text=_("Additive BOS/strong-leg confluence weight (validated: 0)"),
    )
    require_bos = models.BooleanField(
        default=False, help_text=_("Require a Break of Structure (validated: off)"))
    block_on_choch = models.BooleanField(
        default=False, help_text=_("Reject on Change of Character (validated: off)"))

    trend_filter_enabled = models.BooleanField(
        default=True,
        help_text=_("V3: 1H trend-strength gate beyond the EMA cross (validated: on)"),
    )
    trend_slope_lookback = models.PositiveIntegerField(
        default=3, help_text=_("Bars used to measure the 1H EMA50 slope"))
    trend_min_slope_pct = models.FloatField(
        default=0.0, help_text=_("Min EMA50 slope %% over the lookback (validated: 0/off)"))
    trend_min_ema_gap_pct = models.FloatField(
        default=0.5, help_text=_("Min EMA50-EMA200 gap as %% of price (validated: 0.5)"))
    trend_require_price_above_ema50 = models.BooleanField(
        default=True, help_text=_("Require price on the trend side of EMA50 (validated: on)"))
    trend_require_adx_rising = models.BooleanField(
        default=False, help_text=_("Require 1H ADX rising (validated: off)"))

    regime_filter_enabled = models.BooleanField(
        default=True,
        help_text=_("V3: market-regime gate before scanning (validated: on)"),
    )
    regime_min_adx = models.FloatField(
        default=0.0, help_text=_("Require 15m ADX >= this (validated: 0/off)"))
    regime_max_choppiness = models.FloatField(
        default=0.0, help_text=_("Reject if Choppiness Index > this (validated: 0/off)"))
    regime_choppiness_period = models.PositiveIntegerField(
        default=14, help_text=_("Choppiness Index lookback"))
    regime_min_bbw_pct = models.FloatField(
        default=0.0, help_text=_("Min Bollinger band width %% (validated: 0/off)"))
    regime_bb_period = models.PositiveIntegerField(
        default=20, help_text=_("Bollinger period for band width"))
    regime_bb_std = models.FloatField(
        default=2.0, help_text=_("Bollinger std-dev multiplier"))
    regime_atr_percentile_min = models.FloatField(
        default=30.0,
        help_text=_("Require ATR percentile (0-100) >= this (validated: 30)"),
    )
    regime_atr_percentile_period = models.PositiveIntegerField(
        default=100, help_text=_("Lookback bars for the ATR percentile"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'daytrade_strategy_configs'
        ordering = ['-is_active', 'name']
        verbose_name = _('Day-Trade Strategy Config')
        verbose_name_plural = _('Day-Trade Strategy Configs')

    def __str__(self):
        state = 'Active' if self.is_active else 'Inactive'
        return f"DayTrade config '{self.name}' ({state}, min_score={self.min_score})"

    @property
    def max_score(self):
        """Total of all component weights."""
        return (
            self.weight_trend + self.weight_structure + self.weight_volume
            + self.weight_pullback + self.weight_macd + self.weight_rsi
            + self.weight_atr
        )

    @classmethod
    def get_active(cls):
        """Return the active config, creating a default one if none exists."""
        config = cls.objects.filter(is_active=True).order_by('name').first()
        if config is None:
            config, _created = cls.objects.get_or_create(
                name='default',
                defaults={'symbols': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']},
            )
        return config


class DayTradeSession(models.Model):
    """Auto-discovered favourable trading window for the day-trade bot.

    Mirrors the v1 TradingSession golden-window concept but is isolated to the
    day-trade system. Windows are produced by the session optimizer from closed
    DayTradePaperTrade history (high win-rate NPT hour / hour-weekday blocks).
    Analytics only: these gate the Bot Performance filters, not signal generation.
    """
    SESSION_TYPE_CHOICES = [
        ('ALL_DAYS', _('All days window')),
        ('WEEKDAY', _('Weekday-specific window')),
    ]

    name = models.CharField(max_length=120, unique=True)
    session_type = models.CharField(
        max_length=20, choices=SESSION_TYPE_CHOICES, default='ALL_DAYS')
    description = models.CharField(max_length=255, blank=True, default='')

    start_hour = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text=_("Window start hour (Nepal time, inclusive)"))
    end_hour = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(24)],
        help_text=_("Window end hour (Nepal time, exclusive)"))
    active_days = models.JSONField(
        default=list, blank=True,
        help_text=_("Python weekdays (0=Mon..6=Sun) this window applies to; empty = all days"))

    win_rate = models.FloatField(null=True, blank=True)
    total_trades_analyzed = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    auto_generated = models.BooleanField(default=True)
    last_optimized_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'daytrade_sessions'
        ordering = ['start_hour', 'name']
        verbose_name = _('Day-Trade Session')
        verbose_name_plural = _('Day-Trade Sessions')

    def __str__(self):
        days = 'all days' if not self.active_days else f"days {self.active_days}"
        return f"{self.name} ({self.start_hour:02d}:00-{self.end_hour:02d}:00 NPT, {days})"

    def covers(self, npt_hour, npt_weekday):
        """True if a trade at this NPT hour/weekday falls inside the window."""
        if not (self.start_hour <= npt_hour < self.end_hour):
            return False
        return not self.active_days or npt_weekday in self.active_days

    @classmethod
    def is_priority_now(cls):
        """Whether the current NPT time falls inside any active session window.

        Nepal Time is UTC + 5h45m, matching ``covers`` semantics. Returns
        False on any error so signal creation is never blocked by this check.

        Returns:
            True if an active session covers the current NPT hour/weekday.
        """
        try:
            npt_now = timezone.now() + timedelta(hours=5, minutes=45)
            hour, weekday = npt_now.hour, npt_now.weekday()
            return any(
                session.covers(hour, weekday)
                for session in cls.objects.filter(is_active=True)
            )
        except Exception:
            return False
