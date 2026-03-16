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

    # New: Total capital to divide among trades
    total_trading_capital = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('10.00'))],
        help_text=_("Total capital to divide equally among max_active_gw_trades")
    )

    # New: Max trades during golden window session
    max_active_gw_trades = models.IntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text=_("Maximum trades to execute during a golden window session (capital divided equally)")
    )

    leverage = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(125)],
        help_text=_("Leverage multiplier (1-125x)")
    )

    max_concurrent_trades = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text=_("Maximum number of concurrent open trades")
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
        Get number of available trade slots during golden window.
        Returns how many more trades can be opened.
        """
        current_open = FuturesTrade.objects.filter(status='OPEN').count()
        return max(0, self.max_active_gw_trades - current_open)

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

    cut_loser_triggered = models.BooleanField(
        default=False,
        help_text=_("Whether cut-loser mode has been triggered for this trade")
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
