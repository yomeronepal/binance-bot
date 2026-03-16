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


class TradingSession(models.Model):
    """
    Trading session model for managing trading time windows.
    Replaces hardcoded trading window logic with flexible database configuration.
    """
    SESSION_TYPE_CHOICES = [
        ('GOLDEN_WINDOW', _('Golden Window')),  # Premium window (time + specific days)
        ('ACTIVE_TRADING_WINDOW', _('Active Trading Window')),  # Active window (time only)
    ]

    # Basic information
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Session name (e.g., GW1, GW2)")
    )
    session_type = models.CharField(
        max_length=30,
        choices=SESSION_TYPE_CHOICES,
        help_text=_("Type of trading session")
    )
    description = models.TextField(
        blank=True,
        help_text=_("Session description")
    )

    # Time window (Nepal Time)
    start_hour = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text=_("Start hour in Nepal Time (0-23)")
    )
    start_minute = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(59)],
        default=0,
        help_text=_("Start minute (0-59)")
    )
    end_hour = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text=_("End hour in Nepal Time (0-23)")
    )
    end_minute = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(59)],
        default=0,
        help_text=_("End minute (0-59)")
    )

    # Active days (for GOLDEN_WINDOW type)
    # Python weekday: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    active_days = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Active days for GOLDEN_WINDOW type (0=Mon, 6=Sun). Empty = all days")
    )

    # Enable/disable
    active = models.BooleanField(
        default=True,
        help_text=_("Whether this session is active")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_sessions'
        ordering = ['start_hour', 'start_minute']
        verbose_name = _('Trading Session')
        verbose_name_plural = _('Trading Sessions')
        indexes = [
            models.Index(fields=['active', 'session_type']),
            models.Index(fields=['start_hour', 'end_hour']),
        ]

    def __str__(self):
        return f"{self.name} ({self.start_hour:02d}:{self.start_minute:02d}-{self.end_hour:02d}:{self.end_minute:02d} NPT)"

    def __repr__(self):
        return f"<TradingSession: {self.name}>"

    @property
    def time_window_minutes(self):
        """Get time window in minutes from midnight."""
        return (
            self.start_hour * 60 + self.start_minute,
            self.end_hour * 60 + self.end_minute
        )

    def is_time_in_window(self, npt_datetime):
        """
        Check if a given Nepal time is within this session's time window.
        
        Args:
            npt_datetime: datetime object in Nepal Time
            
        Returns:
            bool: True if time is within window
        """
        current_minutes = npt_datetime.hour * 60 + npt_datetime.minute
        start_minutes, end_minutes = self.time_window_minutes
        return start_minutes <= current_minutes < end_minutes

    def is_day_active(self, npt_datetime):
        """
        Check if a given Nepal time falls on an active day for this session.
        
        Args:
            npt_datetime: datetime object in Nepal Time
            
        Returns:
            bool: True if day is active (or no active_days restriction)
        """
        if not self.active_days:
            return True  # No day restriction
        return npt_datetime.weekday() in self.active_days

    def matches(self, npt_datetime):
        """
        Check if a datetime matches this trading session.
        
        For GOLDEN_WINDOW: Must match both time AND active days
        For ACTIVE_TRADING_WINDOW: Must match time only
        
        Args:
            npt_datetime: datetime object in Nepal Time
            
        Returns:
            bool: True if datetime matches session criteria
        """
        if not self.active:
            return False

        # Check time window
        if not self.is_time_in_window(npt_datetime):
            return False

        # For GOLDEN_WINDOW, also check day
        if self.session_type == 'GOLDEN_WINDOW':
            return self.is_day_active(npt_datetime)

        # ACTIVE_TRADING_WINDOW only needs time match
        return True

    @classmethod
    def get_active_sessions(cls):
        """Get all active trading sessions."""
        return cls.objects.filter(active=True)

    @classmethod
    def get_matching_session(cls, npt_datetime):
        """
        Get the first matching session for a given datetime.
        Prioritizes GOLDEN_WINDOW over ACTIVE_TRADING_WINDOW.
        
        Args:
            npt_datetime: datetime object in Nepal Time
            
        Returns:
            TradingSession or None
        """
        sessions = cls.get_active_sessions().order_by(
            models.Case(
                models.When(session_type='GOLDEN_WINDOW', then=0),
                models.When(session_type='ACTIVE_TRADING_WINDOW', then=1),
                default=2
            )
        )
        
        for session in sessions:
            if session.matches(npt_datetime):
                return session
        
        return None



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

    # Priority flag for high win-rate time windows
    is_priority = models.BooleanField(
        default=False,
        help_text=_("Signal generated during high win-rate hours (16:00-17:00 or 21:00-23:00 Nepal Time)")
    )

    # Golden Window 2 flag for premium windows on specific days
    is_golden_2 = models.BooleanField(
        default=False,
        help_text=_("Signal generated during premium windows (16:00-17:00 or 21:00-23:00 NPT) on Sun/Wed/Thu only")
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

    @staticmethod
    def is_high_winrate_hour():
        """
        Check if current Nepal Time is within high win-rate trading windows.
        Windows (Nepal Time UTC+5:45):
        - 21:00-23:00 NPT
        """
        from datetime import datetime, timezone as dt_timezone, timedelta

        NEPAL_TZ_OFFSET = timedelta(hours=5, minutes=45)
        TRADING_WINDOWS = [
            (21, 0, 23, 0),
        ]

        utc_now = datetime.now(dt_timezone.utc)
        nepal_now = utc_now + NEPAL_TZ_OFFSET
        current_time_minutes = nepal_now.hour * 60 + nepal_now.minute

        for start_hour, start_min, end_hour, end_min in TRADING_WINDOWS:
            window_start = start_hour * 60 + start_min
            window_end = end_hour * 60 + end_min

            if window_start <= current_time_minutes < window_end:
                return True

        return False

    @staticmethod
    def is_golden_window_2():
        """
        Check if current Nepal Time is within premium trading windows on specific days.
        Windows (Nepal Time UTC+5:45) on Sun/Tue/Wed/Thu only:
        - 21:00-23:00 NPT
        """
        from datetime import datetime, timezone as dt_timezone, timedelta

        NEPAL_TZ_OFFSET = timedelta(hours=5, minutes=45)
        TRADING_WINDOWS = [
            (21, 0, 23, 0),
        ]
        GOLDEN_DAYS = [6, 2, 3, 1]  # Sunday=6, Wednesday=2, Thursday=3, Tuesday=1

        utc_now = datetime.now(dt_timezone.utc)
        nepal_now = utc_now + NEPAL_TZ_OFFSET
        current_time_minutes = nepal_now.hour * 60 + nepal_now.minute
        weekday = nepal_now.weekday()  # 0=Mon, 6=Sun

        # Check if it's a golden day
        if weekday not in GOLDEN_DAYS:
            return False

        # Check if within trading window
        for start_hour, start_min, end_hour, end_min in TRADING_WINDOWS:
            window_start = start_hour * 60 + start_min
            window_end = end_hour * 60 + end_min

            if window_start <= current_time_minutes < window_end:
                return True

        return False

    def save(self, *args, **kwargs):
        """Auto-set is_priority and is_golden_2 based on creation time for new signals."""
        if not self.pk:
            self.is_priority = self.is_high_winrate_hour()
            self.is_golden_2 = self.is_golden_window_2()
        super().save(*args, **kwargs)


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
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paper_trades',
        help_text=_("Associated trading signal (nullable to preserve trades)")
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
    timeframe = models.CharField(
        max_length=5,
        null=True,
        blank=True,
        help_text=_("Signal timeframe (e.g., 1h, 4h)")
    )
    confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text=_("Signal confidence (0.0 - 1.0)")
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

    # Priority / Golden Window
    is_priority = models.BooleanField(
        default=False,
        help_text=_("Whether this is a Golden Window trade")
    )
    is_golden_2 = models.BooleanField(
        default=False,
        help_text=_("Whether this is a Golden Window 2.0 trade (Sun/Wed/Thu 21-23 NPT)")
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
            models.Index(fields=['status', '-created_at'], name='paper_trade_status_created_idx'),
            models.Index(fields=['user', '-created_at'], name='paper_trade_user_created_idx'),
            models.Index(fields=['market_type', 'status'], name='paper_trade_market_status_idx'),
            models.Index(fields=['timeframe', 'status'], name='paper_trade_timefra_idx'),
            models.Index(fields=['confidence', 'status'], name='paper_trade_confide_idx'),
            models.Index(fields=['is_priority', 'status'], name='paper_trade_gw1_status_idx'),
            models.Index(fields=['is_golden_2', 'status'], name='paper_trade_gw2_status_idx'),
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


class PaperAccount(models.Model):
    """
    Paper trading account for auto-trading simulation.
    Manages virtual balance and tracks all auto-executed trades.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='paper_account',
        help_text=_("User who owns this paper account")
    )

    # Account balances
    initial_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=1000.00,
        help_text=_("Starting balance in USDT")
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=1000.00,
        help_text=_("Available balance in USDT")
    )
    equity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=1000.00,
        help_text=_("Total equity (balance + unrealized P/L)")
    )

    # Performance metrics
    total_pnl = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_("Total profit/loss")
    )
    realized_pnl = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_("Realized profit/loss from closed trades")
    )
    unrealized_pnl = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_("Unrealized P/L from open positions")
    )

    # Trading statistics
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    losing_trades = models.IntegerField(default=0)
    win_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_("Win rate percentage")
    )

    # Risk management
    max_position_size = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text=_("Maximum position size as percentage of balance")
    )
    max_open_trades = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text=_("Maximum number of concurrent open trades")
    )

    # Auto-trading settings
    auto_trading_enabled = models.BooleanField(
        default=False,
        help_text=_("Enable automatic trade execution on new signals")
    )
    auto_trade_spot = models.BooleanField(
        default=True,
        help_text=_("Auto-trade SPOT signals")
    )
    auto_trade_futures = models.BooleanField(
        default=True,
        help_text=_("Auto-trade FUTURES signals")
    )
    min_signal_confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.70,
        validators=[MinValueValidator(0.50), MaxValueValidator(0.95)],
        help_text=_("Minimum signal confidence to auto-trade")
    )

    # Open positions tracking
    open_positions = models.JSONField(
        default=list,
        help_text=_("List of currently open positions")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_trade_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Paper Account")
        verbose_name_plural = _("Paper Accounts")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['auto_trading_enabled'], name='paper_acct_auto_trade_idx'),
            models.Index(fields=['-total_pnl'], name='paper_acct_pnl_idx'),
            models.Index(fields=['-updated_at'], name='paper_acct_updated_idx'),
            models.Index(fields=['-win_rate'], name='paper_acct_winrate_idx'),
        ]

    def __str__(self):
        return f"Paper Account - {self.user.username} (Balance: ${self.balance})"

    def update_metrics(self):
        """
        Update account metrics based on closed trades.
        """
        from django.db.models import Sum, Count, Q

        # Get all trades for this account
        trades = PaperTrade.objects.filter(user=self.user)
        closed_trades = trades.filter(status__startswith='CLOSED')

        # Update trade counts
        self.total_trades = closed_trades.count()
        self.winning_trades = closed_trades.filter(profit_loss__gt=0).count()
        self.losing_trades = closed_trades.filter(profit_loss__lt=0).count()

        # Calculate win rate
        if self.total_trades > 0:
            self.win_rate = (self.winning_trades / self.total_trades) * 100
        else:
            self.win_rate = 0

        # Calculate realized P/L
        aggregates = closed_trades.aggregate(
            total=Sum('profit_loss')
        )
        self.realized_pnl = aggregates['total'] or 0

        # Update balance (initial + realized P/L)
        self.balance = self.initial_balance + self.realized_pnl

        # Total P/L includes unrealized
        self.total_pnl = self.realized_pnl + self.unrealized_pnl

        # Equity = balance + unrealized P/L
        self.equity = self.balance + self.unrealized_pnl

        self.save()

    def can_open_trade(self, symbol, direction):
        """
        Check if a new trade can be opened.

        Args:
            symbol: Trading pair symbol
            direction: LONG or SHORT

        Returns:
            bool: True if trade can be opened
        """
        # Check if auto-trading is enabled
        if not self.auto_trading_enabled:
            return False

        # Check max open trades limit
        open_count = len(self.open_positions)
        if open_count >= self.max_open_trades:
            return False

        # Check for duplicate position (same symbol + direction)
        for pos in self.open_positions:
            if pos.get('symbol') == symbol and pos.get('direction') == direction:
                return False  # Duplicate trade not allowed

        # Check if sufficient balance
        position_size = (self.balance * self.max_position_size / 100)
        if position_size < 10:  # Minimum $10 position
            return False

        return True

    def add_position(self, trade):
        """
        Add a new position to open_positions.

        Args:
            trade: PaperTrade instance
        """
        position = {
            'trade_id': trade.id,
            'symbol': trade.symbol,
            'direction': trade.direction,
            'entry_price': str(trade.entry_price),
            'stop_loss': str(trade.stop_loss),
            'take_profit': str(trade.take_profit),
            'position_size': str(trade.position_size),
            'opened_at': trade.entry_time.isoformat() if trade.entry_time else None,
        }
        self.open_positions.append(position)
        self.last_trade_at = trade.entry_time
        self.save()

    def remove_position(self, trade_id):
        """
        Remove a position from open_positions.

        Args:
            trade_id: ID of the trade to remove
        """
        self.open_positions = [
            pos for pos in self.open_positions
            if pos.get('trade_id') != trade_id
        ]
        self.save()

    def reset_account(self):
        """
        Reset account to initial state.
        """
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.total_pnl = 0
        self.realized_pnl = 0
        self.unrealized_pnl = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.win_rate = 0
        self.open_positions = []
        self.last_trade_at = None
        self.save()

        # Close all open trades
        PaperTrade.objects.filter(
            user=self.user,
            status='OPEN'
        ).update(status='CANCELLED')

    def calculate_position_size(self, signal_confidence=None):
        """
        Calculate position size based on risk management rules.

        Args:
            signal_confidence: Optional confidence level (0-1)

        Returns:
            Decimal: Position size in USDT
        """
        from decimal import Decimal

        base_size = self.balance * self.max_position_size / 100

        # Adjust based on confidence (if provided)
        if signal_confidence:
            confidence_multiplier = Decimal(str(signal_confidence))
            base_size = base_size * confidence_multiplier

        # Ensure minimum position size
        min_size = Decimal('10.00')
        return max(base_size, min_size)


# Import backtesting models
from .models_backtest import (
    BacktestRun,
    BacktestTrade,
    StrategyOptimization,
    OptimizationRecommendation,
    BacktestMetric,
)

# Import walk-forward optimization models
from .models_walkforward import (
    WalkForwardOptimization,
    WalkForwardWindow,
    WalkForwardMetric,
)

# Import Monte Carlo simulation models
from .models_montecarlo import (
    MonteCarloSimulation,
    MonteCarloRun,
    MonteCarloDistribution,
)


# Import ML-based tuning models
from .models_mltuning import (
    MLTuningJob,
    MLTuningSample,
    MLPrediction,
    MLModel,
)

# Import futures trading models
from .models_futures import (
    FuturesTradingSettings,
    FuturesTrade,
)

# Import blacklist models
from .models_blacklist import (
    BlacklistedSymbol,
)
