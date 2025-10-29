"""
Trading signal models following clean architecture principles.
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _


class Symbol(models.Model):
    """
    Trading symbol model representing tradable pairs.
    """
    MARKET_TYPE_CHOICES = [
        ('SPOT', _('Spot')),
        ('FUTURES', _('Futures')),
    ]

    symbol = models.CharField(
        max_length=20,
        unique=True,
        help_text=_("Trading pair symbol (e.g., BTCUSDT)")
    )
    exchange = models.CharField(
        max_length=50,
        default='BINANCE',
        help_text=_("Exchange name")
    )
    active = models.BooleanField(
        default=True,
        help_text=_("Whether symbol is actively traded")
    )
    market_type = models.CharField(
        max_length=10,
        choices=MARKET_TYPE_CHOICES,
        default='SPOT',
        help_text=_("Market type (SPOT/FUTURES)")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'symbols'
        ordering = ['symbol']
        verbose_name = _('Symbol')
        verbose_name_plural = _('Symbols')
        indexes = [
            models.Index(fields=['symbol', 'active']),
            models.Index(fields=['exchange', 'active']),
        ]

    def __str__(self):
        return f"{self.symbol} ({self.exchange})"

    def __repr__(self):
        return f"<Symbol: {self.symbol}>"


class Signal(models.Model):
    """
    Trading signal model with entry, stop-loss, and take-profit levels.
    """
    DIRECTION_CHOICES = [
        ('LONG', _('Long')),
        ('SHORT', _('Short')),
    ]

    TIMEFRAME_CHOICES = [
        ('1m', _('1 Minute')),
        ('5m', _('5 Minutes')),
        ('15m', _('15 Minutes')),
        ('30m', _('30 Minutes')),
        ('1h', _('1 Hour')),
        ('4h', _('4 Hours')),
        ('1d', _('1 Day')),
        ('1w', _('1 Week')),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', _('Active')),
        ('EXPIRED', _('Expired')),
        ('EXECUTED', _('Executed')),
        ('CANCELLED', _('Cancelled')),
    ]

    MARKET_TYPE_CHOICES = [
        ('SPOT', _('Spot')),
        ('FUTURES', _('Futures')),
    ]

    TRADING_TYPE_CHOICES = [
        ('SCALPING', _('Scalping')),
        ('DAY', _('Day Trading')),
        ('SWING', _('Swing Trading')),
    ]

    # Relationships
    symbol = models.ForeignKey(
        Symbol,
        on_delete=models.CASCADE,
        related_name='signals',
        help_text=_("Trading symbol")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='created_signals',
        null=True,
        blank=True,
        help_text=_("User who created this signal")
    )

    # Signal details
    direction = models.CharField(
        max_length=10,
        choices=DIRECTION_CHOICES,
        help_text=_("Trade direction (LONG/SHORT)")
    )
    timeframe = models.CharField(
        max_length=5,
        choices=TIMEFRAME_CHOICES,
        default='1h',
        help_text=_("Signal timeframe")
    )

    # Price levels
    entry = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(0)],
        help_text=_("Entry price")
    )
    sl = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(0)],
        help_text=_("Stop loss price"),
        verbose_name=_("Stop Loss")
    )
    tp = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(0)],
        help_text=_("Take profit price"),
        verbose_name=_("Take Profit")
    )

    # Signal metadata
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.5,
        help_text=_("Signal confidence (0.0 - 1.0)")
    )
    source = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Signal source (e.g., bot name, indicator)")
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        help_text=_("Signal status")
    )
    market_type = models.CharField(
        max_length=10,
        choices=MARKET_TYPE_CHOICES,
        default='SPOT',
        help_text=_("Market type (SPOT/FUTURES)")
    )
    leverage = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Leverage for futures (e.g., 10x)")
    )
    trading_type = models.CharField(
        max_length=10,
        choices=TRADING_TYPE_CHOICES,
        default='DAY',
        help_text=_("Trading type (SCALPING/DAY/SWING)")
    )
    estimated_duration_hours = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Estimated time to reach target in hours")
    )

    # Additional information
    meta = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Additional metadata (indicators, volume, etc.)")
    )
    description = models.TextField(
        blank=True,
        help_text=_("Signal description or notes")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Signal expiration time")
    )

    class Meta:
        db_table = 'signals'
        ordering = ['-created_at']
        verbose_name = _('Signal')
        verbose_name_plural = _('Signals')
        indexes = [
            models.Index(fields=['symbol', 'direction', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['timeframe', '-created_at']),
            models.Index(fields=['-confidence', '-created_at']),
        ]

    def __str__(self):
        return f"{self.direction} {self.symbol.symbol} @ {self.entry}"

    def __repr__(self):
        return f"<Signal: {self.direction} {self.symbol.symbol}>"

    @property
    def risk_reward_ratio(self):
        """Calculate risk/reward ratio."""
        if self.direction == 'LONG':
            risk = float(self.entry - self.sl)
            reward = float(self.tp - self.entry)
        else:  # SHORT
            risk = float(self.sl - self.entry)
            reward = float(self.entry - self.tp)

        if risk <= 0:
            return None
        return round(reward / risk, 2)

    @property
    def is_active(self):
        """Check if signal is currently active."""
        return self.status == 'ACTIVE'

    def calculate_position_size(self, account_balance, risk_percentage=0.01):
        """
        Calculate position size based on account balance and risk.

        Args:
            account_balance: Total account balance
            risk_percentage: Percentage of account to risk (default 1%)

        Returns:
            Position size in base currency
        """
        if self.direction == 'LONG':
            risk_per_unit = float(self.entry - self.sl)
        else:  # SHORT
            risk_per_unit = float(self.sl - self.entry)

        if risk_per_unit <= 0:
            return 0

        risk_amount = account_balance * risk_percentage
        position_size = risk_amount / risk_per_unit

        return round(position_size, 8)


class UserSubscription(models.Model):
    """
    User subscription model for managing billing and access tiers.
    """
    TIER_CHOICES = [
        ('free', _('Free')),
        ('pro', _('Pro')),
        ('premium', _('Premium')),
    ]

    STATUS_CHOICES = [
        ('active', _('Active')),
        ('inactive', _('Inactive')),
        ('cancelled', _('Cancelled')),
        ('expired', _('Expired')),
    ]

    # User relationship (OneToOne)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='signal_subscription',
        help_text=_("User associated with this subscription")
    )

    # Subscription details
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default='free',
        help_text=_("Subscription tier")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text=_("Subscription status")
    )

    # Stripe integration
    stripe_customer_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text=_("Stripe customer ID")
    )
    stripe_subscription_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text=_("Stripe subscription ID")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Subscription expiration date")
    )

    class Meta:
        db_table = 'user_subscriptions'
        ordering = ['-created_at']
        verbose_name = _('User Subscription')
        verbose_name_plural = _('User Subscriptions')
        indexes = [
            models.Index(fields=['tier', 'status']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['stripe_customer_id']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.tier.upper()}"

    def __repr__(self):
        return f"<UserSubscription: {self.user.username} ({self.tier})>"

    @property
    def is_premium(self):
        """Check if user has premium subscription."""
        return self.tier in ['pro', 'premium'] and self.status == 'active'

    @property
    def is_active(self):
        """Check if subscription is currently active."""
        return self.status == 'active'

    def get_signal_limit(self):
        """Get maximum signals per day based on tier."""
        limits = {
            'free': 5,
            'pro': 50,
            'premium': None,  # Unlimited
        }
        return limits.get(self.tier, 5)

    def can_access_advanced_features(self):
        """Check if user can access advanced features."""
        return self.tier in ['pro', 'premium'] and self.is_active


class PaperTrade(models.Model):
    """
    Paper trading model for simulated trades without real execution.
    Tracks virtual trades based on real signals and market prices.
    """
    TRADE_STATUS_CHOICES = [
        ('PENDING', _('Pending Entry')),
        ('OPEN', _('Open')),
        ('CLOSED_TP', _('Closed - Take Profit Hit')),
        ('CLOSED_SL', _('Closed - Stop Loss Hit')),
        ('CLOSED_MANUAL', _('Closed - Manually')),
        ('CANCELLED', _('Cancelled')),
    ]

    # Relationships
    signal = models.ForeignKey(
        'Signal',
        on_delete=models.CASCADE,
        related_name='paper_trades',
        help_text=_("Associated trading signal")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='paper_trades',
        null=True,
        blank=True,
        help_text=_("User who owns this trade (null for system-wide)")
    )

    # Trade Details
    symbol = models.CharField(
        max_length=20,
        help_text=_("Trading pair symbol")
    )
    direction = models.CharField(
        max_length=10,
        choices=[('LONG', 'Long'), ('SHORT', 'Short')],
        help_text=_("Trade direction")
    )
    market_type = models.CharField(
        max_length=10,
        choices=[('SPOT', 'Spot'), ('FUTURES', 'Futures')],
        default='SPOT',
        help_text=_("Market type")
    )

    # Entry Information
    entry_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("Entry price")
    )
    entry_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Time when position was entered")
    )
    position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=100.00,
        help_text=_("Position size in USDT")
    )
    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text=_("Quantity of asset")
    )

    # Exit Levels
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

    # Exit Information
    exit_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text=_("Exit price")
    )
    exit_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Time when position was closed")
    )

    # Performance Metrics
    profit_loss = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        help_text=_("Profit/Loss in USDT")
    )
    profit_loss_percentage = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        help_text=_("Profit/Loss in percentage")
    )

    # Futures Specific
    leverage = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(125)],
        help_text=_("Leverage for futures trading")
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=TRADE_STATUS_CHOICES,
        default='PENDING',
        help_text=_("Current trade status")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'paper_trades'
        ordering = ['-created_at']
        verbose_name = _('Paper Trade')
        verbose_name_plural = _('Paper Trades')
        indexes = [
            models.Index(fields=['signal', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['symbol', 'status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"Paper {self.direction} {self.symbol} @ {self.entry_price}"

    @property
    def is_open(self):
        """Check if trade is currently open."""
        return self.status in ['PENDING', 'OPEN']

    @property
    def is_closed(self):
        """Check if trade is closed."""
        return self.status.startswith('CLOSED')

    @property
    def is_profitable(self):
        """Check if trade was profitable."""
        return self.profit_loss > 0

    @property
    def duration_hours(self):
        """Calculate trade duration in hours."""
        if self.entry_time and self.exit_time:
            duration = self.exit_time - self.entry_time
            return duration.total_seconds() / 3600
        return None

    @property
    def risk_reward_ratio(self):
        """Calculate actual risk/reward ratio."""
        if self.direction == 'LONG':
            risk = float(self.entry_price - self.stop_loss)
            reward = float(self.take_profit - self.entry_price)
        else:  # SHORT
            risk = float(self.stop_loss - self.entry_price)
            reward = float(self.entry_price - self.take_profit)

        if risk > 0:
            return round(reward / risk, 2)
        return 0

    def calculate_profit_loss(self, current_price=None):
        """Calculate current or final P/L."""
        exit_price = current_price or self.exit_price
        if not exit_price:
            return 0, 0

        quantity = float(self.quantity)
        entry = float(self.entry_price)
        exit_p = float(exit_price)

        if self.direction == 'LONG':
            pnl = (exit_p - entry) * quantity
        else:  # SHORT
            pnl = (entry - exit_p) * quantity

        # Apply leverage for futures
        if self.market_type == 'FUTURES' and self.leverage:
            pnl *= self.leverage

        pnl_percentage = (pnl / float(self.position_size)) * 100

        return round(pnl, 8), round(pnl_percentage, 4)

    def check_stop_loss_hit(self, current_price):
        """Check if stop loss has been hit."""
        price = float(current_price)
        sl = float(self.stop_loss)

        if self.direction == 'LONG':
            return price <= sl
        else:  # SHORT
            return price >= sl

    def check_take_profit_hit(self, current_price):
        """Check if take profit has been hit."""
        price = float(current_price)
        tp = float(self.take_profit)

        if self.direction == 'LONG':
            return price >= tp
        else:  # SHORT
            return price <= tp

    def close_trade(self, exit_price, status='CLOSED_MANUAL'):
        """Close the trade and calculate final P/L."""
        from django.utils import timezone

        self.exit_price = exit_price
        self.exit_time = timezone.now()
        self.status = status

        # Calculate final P/L
        pnl, pnl_pct = self.calculate_profit_loss(exit_price)
        self.profit_loss = pnl
        self.profit_loss_percentage = pnl_pct

        self.save()
        return pnl, pnl_pct
