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
        help_text=_("Only trade during trading windows (NPT 17:00-18:00 & 21:00-23:00)")
    )

    trade_on_golden_window_2 = models.BooleanField(
        default=False,
        help_text=_("Specifically enable trading during Golden Window 2 (Sun/Wed/Thu 21:00-23:00 NPT)")
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

    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        settings_obj, created = cls.objects.get_or_create(pk=1)
        if created:
            settings_obj.allowed_symbols = ['BTCUSDT', 'ETHUSDT']
            settings_obj.save()
        return settings_obj

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
