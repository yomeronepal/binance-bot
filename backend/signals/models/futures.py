"""
Futures trading models for real Binance futures trading.
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


class FuturesTradingSettings(models.Model):
    """
    Global settings for futures trading.
    Singleton model - only one instance should exist.
    """
    is_enabled = models.BooleanField(
        default=False,
        help_text=_("Enable/disable futures trading")
    )

    trade_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('5.00'),
        validators=[MinValueValidator(Decimal('1.00'))],
        help_text=_("Base trade amount in USDT (before leverage)")
    )

    total_trading_capital = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('10.00'))],
        help_text=_(
            "Last known Binance futures USDT wallet balance. Written by "
            "the monthly rebalance task (signals.monthly_balance_rebalance) "
            "and read by the frontend balance display. Also used by the "
            "Golden Window auto-trader as the per-trade sizing pool "
            "(per_trade = total_trading_capital / max_active_gw_trades)."
        ),
    )

    last_balance_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_(
            "When total_trading_capital was last refreshed from the "
            "live Binance futures balance."
        ),
    )

    # New: Max trades during golden window session
    max_active_gw_trades = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text=_("Per-trade sizing divisor: per_trade = total_trading_capital / this. "
                    "Set by the rebalancer to (max_concurrent_trades + 1) so one slot's "
                    "worth is held back as the reserve. NOT the concurrency cap.")
    )

    leverage = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(125)],
        help_text=_("Leverage multiplier (1-125x)")
    )

    max_concurrent_trades = models.IntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text=_("Maximum simultaneous open trades (the actual slot cap used by the "
                    "auto-traders). Deployable capital = this x per_trade.")
    )

    min_signal_confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.70'),
        validators=[MinValueValidator(Decimal('0.50')), MaxValueValidator(Decimal('0.99'))],
        help_text=_("Minimum signal confidence to take trade")
    )

    allowed_symbols = models.JSONField(
        default=list,
        blank=True,
        help_text=_("List of allowed symbols for trading (empty = all)")
    )

    trade_long = models.BooleanField(
        default=True,
        help_text=_("Allow LONG trades")
    )

    trade_short = models.BooleanField(
        default=True,
        help_text=_("Allow SHORT trades")
    )

    use_trading_window = models.BooleanField(
        default=True,
        help_text=_("Only trade during trading windows (NPT 16:00-17:00 & 21:00-23:00)")
    )

    trade_on_golden_window_2 = models.BooleanField(
        default=False,
        help_text=_("Specifically enable trading during Golden Window 2 (Sun/Wed/Thu 21:00-23:00 NPT)")
    )

    gw_auto_trader_enabled = models.BooleanField(
        default=False,
        help_text=_("Enable automatic trading during golden windows (GW1/GW2)")
    )

    daytrade_live_enabled = models.BooleanField(
        default=True,
        help_text=_(
            "Execute REAL Binance futures orders for day-trade signals that fire "
            "inside an active optimized Day-Trade Session. Still requires the "
            "global 'is_enabled' master switch to be ON; sized from the shared "
            "futures pool (total_trading_capital / max_active_gw_trades)."
        )
    )

    consecutive_sl_halt_threshold = models.PositiveIntegerField(
        default=2,
        help_text=_(
            "Circuit breaker (per engine): after this many consecutive stop-losses "
            "since the last take-profit within the engine's active trading-session "
            "window, block that engine's new live futures entries until a take-profit "
            "resets it. Validated optimum is 2 (forward-tested). 0 = disabled."
        )
    )

    cut_loser_enabled = models.BooleanField(
        default=False,
        help_text=_("Enable 'cut loser first' - close losing trades when they recover near breakeven")
    )

    cut_loser_trigger_loss_pct = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('2.0'),
        validators=[MinValueValidator(Decimal('0.5')), MaxValueValidator(Decimal('10.0'))],
        help_text=_("Trigger cut-loser when unrealized loss exceeds this % (0.5% - 10%)")
    )

    cut_loser_close_at_pct = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('0.3'),
        validators=[MinValueValidator(Decimal('-1.0')), MaxValueValidator(Decimal('1.0'))],
        help_text=_("Close trade when it recovers to this % from entry (-1% to +1%, negative = small loss, positive = small profit)")
    )

    futures_universe_screen_enabled = models.BooleanField(
        default=False,
        help_text=_("Screen futures signals by liquidity + volatility before executing (drops illiquid/parabolic symbols)")
    )

    opposite_exit_enabled = models.BooleanField(
        default=False,
        help_text=_("Arm a trade in drawdown when an opposite day-trade signal appears, then close it once it recovers to profit")
    )

    opposite_exit_shadow_mode = models.BooleanField(
        default=True,
        help_text=_("Log opposite-exit arm/close decisions without executing them (validation mode)")
    )

    opposite_exit_min_confidence = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('0.70'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        help_text=_("Minimum confidence of the opposite day-trade signal that arms an exit")
    )

    opposite_exit_min_profit_pct = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('0.20'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('10'))],
        help_text=_("Only close an armed trade once unrealized PnL reaches this % of margin (covers round-trip fees)")
    )

    fear_greed_enabled = models.BooleanField(
        default=False,
        help_text=_("Enable Fear & Greed Index filter for trade direction")
    )

    macro_filter_enabled = models.BooleanField(
        default=True,
        help_text=_(
            "Legacy global toggle. Kept for backwards compatibility — "
            "the per-class flags (crypto/stock/commodity_macro_filter_"
            "enabled) are the source of truth used at the trade "
            "boundary. New deployments should ignore this field."
        ),
    )

    crypto_macro_filter_enabled = models.BooleanField(
        default=True,
        help_text=_(
            "Enable BTC macro filter for CRYPTO signals at the Binance "
            "trade boundary. When ON, futures orders on crypto perps "
            "are blocked if BTC's daily regime contradicts the signal "
            "direction."
        ),
    )

    stock_macro_filter_enabled = models.BooleanField(
        default=True,
        help_text=_(
            "Enable SPY macro filter for STOCK signals (NVDA, MSTR, "
            "TSLA, ...). When ON, orders on tokenized-equity perps "
            "are blocked if SPY's daily regime contradicts the signal "
            "direction."
        ),
    )

    commodity_macro_filter_enabled = models.BooleanField(
        default=True,
        help_text=_(
            "Enable XAU (gold) macro filter for COMMODITY signals "
            "(XAU, XAG, CL, ...). When ON, orders on tokenized-"
            "commodity perps are blocked if gold's daily regime "
            "contradicts the signal direction."
        ),
    )

    fear_greed_short_threshold = models.IntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(50)],
        help_text=_("F&G <= this: only SHORT allowed (Extreme Fear). Range: 5-50")
    )

    fear_greed_long_threshold = models.IntegerField(
        default=60,
        validators=[MinValueValidator(50), MaxValueValidator(95)],
        help_text=_("F&G >= this: only LONG allowed (Greed). Range: 50-95")
    )

    neutral_reversal_enabled = models.BooleanField(
        default=False,
        help_text=_("In neutral F&G zone, reverse signal direction and use tight SL/TP")
    )

    neutral_reversal_sl_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.5'),
        validators=[MinValueValidator(Decimal('0.5')), MaxValueValidator(Decimal('5.0'))],
        help_text=_("Stop loss % for neutral market reversed trades (default 1.5%)")
    )

    neutral_reversal_tp_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('2.5'),
        validators=[MinValueValidator(Decimal('0.5')), MaxValueValidator(Decimal('10.0'))],
        help_text=_("Take profit % for neutral market reversed trades (default 2.5%)")
    )

    dynamic_trailing_enabled = models.BooleanField(
        default=False,
        help_text=_("Enable dynamic trailing stop that tightens as profit grows")
    )

    dynamic_trailing_tiers = models.JSONField(
        default=list,
        blank=True,
        help_text=_("List of profit tiers: [{profit_pct: 2, trailing_pct: 1}, {profit_pct: 3, trailing_pct: 2}]")
    )

    initial_trailing_callback = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('1.5'),
        validators=[MinValueValidator(Decimal('0.1')), MaxValueValidator(Decimal('5.0'))],
        help_text=_("Initial trailing stop callback % before any tier is reached (0.1% - 5.0%)")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'futures_trading_settings'
        verbose_name = _('Futures Trading Settings')
        verbose_name_plural = _('Futures Trading Settings')

    def __str__(self):
        status = "Enabled" if self.is_enabled else "Disabled"
        return f"Futures Trading: {status} | ${self.trade_amount} x {self.leverage}x"

    @property
    def effective_position_size(self):
        """Calculate effective position size with leverage."""
        return self.trade_amount * self.leverage

    @property
    def per_trade_amount(self):
        """Calculate per-trade amount when dividing total capital equally."""
        return self.total_trading_capital / self.max_active_gw_trades

    def get_available_gw_trade_slots(self):
        """
        Get number of available trade slots.

        Concurrency is capped by ``max_concurrent_trades`` (the slot count),
        which is distinct from ``max_active_gw_trades`` (the per-trade sizing
        divisor). With divisor=5 and slots=4, one unit (balance / 5) is never
        deployed and stays as the reserve.
        """
        current_open = FuturesTrade.objects.filter(status='OPEN').count()
        return max(0, self.max_concurrent_trades - current_open)

    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        settings_obj, created = cls.objects.get_or_create(pk=1)
        if created:
            settings_obj.allowed_symbols = []
            settings_obj.dynamic_trailing_tiers = [
                {'profit_pct': 2, 'trailing_pct': 1},
                {'profit_pct': 3, 'trailing_pct': 2},
                {'profit_pct': 5, 'trailing_pct': 3},
                {'profit_pct': 8, 'trailing_pct': 5},
            ]
            settings_obj.save()
        return settings_obj

    def get_trailing_tier_for_profit(self, profit_pct: Decimal):
        """
        Get the appropriate trailing stop % for a given profit level.

        Args:
            profit_pct: Current profit percentage

        Returns:
            Tuple of (tier_index, trailing_pct) or (0, None) if no tier reached
        """
        if not self.dynamic_trailing_tiers:
            return 0, None

        tiers = sorted(self.dynamic_trailing_tiers, key=lambda x: float(x.get('profit_pct', 0)))
        tier_index = 0
        trailing_pct = None

        for i, tier in enumerate(tiers):
            tier_profit = Decimal(str(tier.get('profit_pct', 0)))
            if profit_pct >= tier_profit:
                tier_index = i + 1
                trailing_pct = Decimal(str(tier.get('trailing_pct', 1)))

        return tier_index, trailing_pct

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def can_trade(self, symbol, direction, confidence):
        """
        Check if a trade is allowed based on settings.

        Args:
            symbol: Trading symbol (e.g., BTCUSDT)
            direction: LONG or SHORT
            confidence: Signal confidence (0-1)

        Returns:
            tuple: (can_trade: bool, reason: str)
        """
        if not self.is_enabled:
            return False, "Futures trading is disabled"

        if direction == 'LONG' and not self.trade_long:
            return False, "LONG trades are disabled"

        if direction == 'SHORT' and not self.trade_short:
            return False, "SHORT trades are disabled"

        if confidence < float(self.min_signal_confidence):
            return False, f"Confidence {confidence:.2%} below minimum {self.min_signal_confidence:.2%}"

        if self.allowed_symbols and symbol not in self.allowed_symbols:
            return False, f"Symbol {symbol} not in allowed list"

        open_trades = FuturesTrade.objects.filter(status='OPEN').count()
        if open_trades >= self.max_concurrent_trades:
            return False, f"Max concurrent trades reached ({self.max_concurrent_trades})"

        return True, "Trade allowed"


class FuturesTrade(models.Model):
    """
    Record of actual futures trades executed on Binance.
    """
    TRADE_STATUS_CHOICES = [
        ('PENDING', _('Pending')),
        ('OPEN', _('Open')),
        ('CLOSED_TP', _('Closed - Take Profit')),
        ('CLOSED_SL', _('Closed - Stop Loss')),
        ('CLOSED_MANUAL', _('Closed - Manual')),
        ('CLOSED_REVERSAL', _('Closed - Opposite Signal')),
        ('FAILED', _('Failed')),
        ('CANCELLED', _('Cancelled')),
    ]

    DIRECTION_CHOICES = [
        ('LONG', _('Long')),
        ('SHORT', _('Short')),
    ]

    signal = models.ForeignKey(
        'Signal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='futures_trades',
        help_text=_("Associated trading signal")
    )

    symbol = models.CharField(
        max_length=20,
        help_text=_("Trading pair symbol")
    )

    direction = models.CharField(
        max_length=10,
        choices=DIRECTION_CHOICES,
        help_text=_("Trade direction")
    )

    leverage = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(125)],
        help_text=_("Leverage used for this trade")
    )

    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("Position quantity")
    )

    entry_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text=_("Entry price")
    )

    stop_loss = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("Stop loss price")
    )

    take_profit = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("Take profit price")
    )

    exit_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text=_("Exit price")
    )

    position_size_usdt = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("Position size in USDT (margin)")
    )

    profit_loss = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('0'),
        help_text=_("Realized P/L in USDT")
    )

    profit_loss_percentage = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal('0'),
        help_text=_("P/L percentage")
    )

    # Live data fields (updated by sync task)
    mark_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text=_("Current mark price from Binance")
    )

    unrealized_pnl = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('0'),
        help_text=_("Unrealized P/L in USDT (live)")
    )

    unrealized_pnl_percentage = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal('0'),
        help_text=_("Unrealized P/L percentage (live)")
    )

    liquidation_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text=_("Liquidation price from Binance")
    )

    margin_type = models.CharField(
        max_length=20,
        default='ISOLATED',
        help_text=_("Margin type (ISOLATED/CROSS)")
    )

    last_sync_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Last time this trade was synced with Binance")
    )

    status = models.CharField(
        max_length=20,
        choices=TRADE_STATUS_CHOICES,
        default='PENDING',
        help_text=_("Trade status")
    )

    binance_order_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_("Binance order ID for entry")
    )

    binance_exit_order_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_("Binance order ID for exit")
    )

    error_message = models.TextField(
        blank=True,
        help_text=_("Error message if trade failed")
    )

    entry_attempts = models.IntegerField(
        default=0,
        help_text=_("Number of order-placement attempts made for this trade")
    )

    next_entry_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Earliest time to retry a failed entry (exponential backoff)")
    )

    cut_loser_triggered = models.BooleanField(
        default=False,
        help_text=_("Whether cut-loser mode has been triggered for this trade")
    )

    opposite_exit_armed = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("Armed to close on recovery after an opposite signal appeared while in drawdown")
    )

    opposite_exit_armed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the opposite-exit arm was triggered")
    )

    max_loss_pct_reached = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal('0'),
        help_text=_("Maximum loss percentage reached during trade")
    )

    max_profit_pct_reached = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal('0'),
        help_text=_("Maximum profit percentage reached during trade")
    )

    current_trailing_tier = models.IntegerField(
        default=0,
        help_text=_("Current dynamic trailing tier level (0 = base tier)")
    )

    sl_order_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_("Binance order/algo ID for stop loss")
    )

    tp_order_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_("Binance order/algo ID for take profit")
    )

    trailing_order_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_("Current trailing stop order ID on Binance")
    )

    entry_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Time when position was opened")
    )

    exit_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Time when position was closed")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'futures_trades'
        ordering = ['-created_at']
        verbose_name = _('Futures Trade')
        verbose_name_plural = _('Futures Trades')
        indexes = [
            models.Index(fields=['symbol', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['signal', 'status']),
        ]

    def __str__(self):
        return f"{self.direction} {self.symbol} x{self.leverage} @ {self.entry_price or 'pending'}"

    @property
    def is_open(self):
        return self.status == 'OPEN'

    @property
    def is_closed(self):
        return self.status.startswith('CLOSED')

    @property
    def is_profitable(self):
        return self.profit_loss > 0

    def calculate_pnl(self, exit_price):
        """Calculate profit/loss for given exit price."""
        if not self.entry_price:
            return Decimal('0'), Decimal('0')

        entry = float(self.entry_price)
        exit_p = float(exit_price)
        qty = float(self.quantity)

        if self.direction == 'LONG':
            pnl = (exit_p - entry) * qty
        else:
            pnl = (entry - exit_p) * qty

        pnl_pct = (pnl / float(self.position_size_usdt)) * 100

        return Decimal(str(round(pnl, 4))), Decimal(str(round(pnl_pct, 4)))

    def close_trade(self, exit_price, status='CLOSED_MANUAL'):
        """Close the trade with given exit price and status."""
        from django.utils import timezone

        self.exit_price = exit_price
        self.exit_time = timezone.now()
        self.status = status

        pnl, pnl_pct = self.calculate_pnl(exit_price)
        self.profit_loss = pnl
        self.profit_loss_percentage = pnl_pct

        self.save()


class FuturesTradeLog(models.Model):
    """
    Audit log for every futures trade request.
    Tracks the full decision pipeline: signal -> checks -> execution -> result.
    """
    LOG_LEVEL_CHOICES = [
        ('INFO', _('Info')),
        ('WARNING', _('Warning')),
        ('ERROR', _('Error')),
        ('SUCCESS', _('Success')),
    ]

    ACTION_CHOICES = [
        ('SIGNAL_RECEIVED', _('Signal Received')),
        ('CHECK_PASSED', _('Check Passed')),
        ('CHECK_FAILED', _('Check Failed')),
        ('TRADE_SUBMITTED', _('Trade Submitted')),
        ('TRADE_EXECUTED', _('Trade Executed')),
        ('TRADE_FAILED', _('Trade Failed')),
        ('TRADE_CLOSED', _('Trade Closed')),
        ('ORDER_PLACED', _('Order Placed')),
        ('ORDER_FAILED', _('Order Failed')),
    ]

    signal = models.ForeignKey(
        'Signal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='futures_logs',
    )

    trade = models.ForeignKey(
        FuturesTrade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
    )

    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
    )

    level = models.CharField(
        max_length=10,
        choices=LOG_LEVEL_CHOICES,
        default='INFO',
    )

    symbol = models.CharField(max_length=20, blank=True)
    direction = models.CharField(max_length=10, blank=True)
    is_priority = models.BooleanField(default=False)
    force_execute = models.BooleanField(default=False)

    message = models.TextField(
        help_text=_("Human-readable log message"),
    )

    details = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Extra details (settings, prices, errors, order IDs)"),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'futures_trade_logs'
        ordering = ['-created_at']
        verbose_name = _('Futures Trade Log')
        verbose_name_plural = _('Futures Trade Logs')
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['signal', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['level', '-created_at']),
            models.Index(fields=['symbol', '-created_at']),
        ]

    def __str__(self):
        return f"[{self.level}] {self.action} {self.symbol} - {self.message[:60]}"


class BalanceRebalanceLog(models.Model):
    """
    One row per ``rebalance_from_futures_balance`` invocation —
    monthly Celery beat or manual ``manage.py rebalance_now``.

    Captures the live Binance USDT balance at run time, the values
    that were computed and written, and what the previous values were.
    ``applied=False`` rows are kept too (dry runs, failures) so the
    history reflects every attempt, not just successful writes.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    balance = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=_("Futures USDT wallet balance at rebalance time"),
    )

    per_trade_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Computed per-trade size (balance / 3)"),
    )

    max_concurrent_trades = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Max concurrent trades set on this run"),
    )

    backup_reserve = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=_("balance - max_concurrent * per_trade"),
    )

    previous_trade_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("trade_amount on FuturesTradingSettings before this run"),
    )

    previous_max_concurrent_trades = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("max_concurrent_trades on FuturesTradingSettings before this run"),
    )

    applied = models.BooleanField(
        default=False,
        help_text=_("True if FuturesTradingSettings was written; False for dry-runs / failures"),
    )

    reason = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Short outcome reason (e.g. 'rebalanced', 'dry-run; no write', 'balance fetch failed: ...')"),
    )

    class Meta:
        db_table = 'balance_rebalance_logs'
        ordering = ['-created_at']
        verbose_name = _('Balance Rebalance Log')
        verbose_name_plural = _('Balance Rebalance Logs')
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['applied', '-created_at']),
        ]

    def __str__(self):
        bal = f"${self.balance}" if self.balance is not None else "?"
        flag = 'APPLIED' if self.applied else 'SKIPPED'
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {flag} balance={bal} reason={self.reason}"
