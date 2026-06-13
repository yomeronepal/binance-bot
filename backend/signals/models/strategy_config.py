"""
Strategy configuration model for managing indicator parameters and SL/TP values
from Django admin instead of hardcoded values.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


class StrategyConfig(models.Model):
    """
    Per-timeframe strategy configuration.
    Replaces hardcoded SignalConfig and SL/TP percentages.
    One row per timeframe — editable from Django admin.
    """
    TIMEFRAME_CHOICES = [
        ('5m', '5 Minutes'),
        ('15m', '15 Minutes'),
        ('30m', '30 Minutes'),
        ('1h', '1 Hour'),
        ('4h', '4 Hours'),
        ('1d', '1 Day'),
    ]

    timeframe = models.CharField(
        max_length=5,
        choices=TIMEFRAME_CHOICES,
        unique=True,
        help_text=_("Timeframe this config applies to"),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this timeframe is actively scanned"),
    )

    min_confidence = models.FloatField(
        default=0.70,
        validators=[MinValueValidator(0.5), MaxValueValidator(1.0)],
        help_text=_("Minimum confidence score to generate signal (0.5-1.0)"),
    )

    long_rsi_min = models.FloatField(
        default=23.0,
        validators=[MinValueValidator(5.0), MaxValueValidator(50.0)],
        help_text=_("RSI minimum for LONG entry (oversold zone)"),
    )
    long_rsi_max = models.FloatField(
        default=33.0,
        validators=[MinValueValidator(10.0), MaxValueValidator(60.0)],
        help_text=_("RSI maximum for LONG entry"),
    )
    short_rsi_min = models.FloatField(
        default=67.0,
        validators=[MinValueValidator(40.0), MaxValueValidator(90.0)],
        help_text=_("RSI minimum for SHORT entry"),
    )
    short_rsi_max = models.FloatField(
        default=77.0,
        validators=[MinValueValidator(50.0), MaxValueValidator(95.0)],
        help_text=_("RSI maximum for SHORT entry (overbought zone)"),
    )

    long_adx_min = models.FloatField(
        default=26.0,
        validators=[MinValueValidator(10.0), MaxValueValidator(50.0)],
        help_text=_("Minimum ADX for LONG trend strength"),
    )
    short_adx_min = models.FloatField(
        default=26.0,
        validators=[MinValueValidator(10.0), MaxValueValidator(50.0)],
        help_text=_("Minimum ADX for SHORT trend strength"),
    )

    long_volume_multiplier = models.FloatField(
        default=1.2,
        validators=[MinValueValidator(0.5), MaxValueValidator(5.0)],
        help_text=_("Volume must be this multiple of average for LONG"),
    )
    short_volume_multiplier = models.FloatField(
        default=1.2,
        validators=[MinValueValidator(0.5), MaxValueValidator(5.0)],
        help_text=_("Volume must be this multiple of average for SHORT"),
    )

    sl_atr_multiplier = models.FloatField(
        default=3.0,
        validators=[MinValueValidator(0.5), MaxValueValidator(10.0)],
        help_text=_("Stop loss as ATR multiplier (for backtest engine)"),
    )
    tp_atr_multiplier = models.FloatField(
        default=9.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(20.0)],
        help_text=_("Take profit as ATR multiplier (for backtest engine)"),
    )

    sl_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('2.50'),
        validators=[MinValueValidator(Decimal('0.10')), MaxValueValidator(Decimal('10.00'))],
        help_text=_("Stop loss as percentage from entry price (for live signals)"),
    )
    tp_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('6.00'),
        validators=[MinValueValidator(Decimal('0.10')), MaxValueValidator(Decimal('20.00'))],
        help_text=_("Take profit as percentage from entry price (for live signals)"),
    )

    risk_reward_ratio = models.FloatField(
        default=3.0,
        validators=[MinValueValidator(0.5), MaxValueValidator(10.0)],
        help_text=_("Target risk/reward ratio"),
    )

    macd_weight = models.FloatField(default=2.0, help_text=_("MACD signal weight"))
    rsi_weight = models.FloatField(default=1.5, help_text=_("RSI signal weight"))
    price_ema_weight = models.FloatField(default=1.8, help_text=_("Price vs EMA weight"))
    adx_weight = models.FloatField(default=1.7, help_text=_("ADX trend strength weight"))
    ha_weight = models.FloatField(default=1.6, help_text=_("Heikin-Ashi trend weight"))
    volume_weight = models.FloatField(default=1.4, help_text=_("Volume confirmation weight"))
    ema_alignment_weight = models.FloatField(default=1.2, help_text=_("EMA alignment weight"))
    di_weight = models.FloatField(default=1.0, help_text=_("Directional indicator weight"))
    bb_weight = models.FloatField(default=0.8, help_text=_("Bollinger Bands weight"))
    volatility_weight = models.FloatField(default=0.5, help_text=_("Volatility adjustment weight"))
    supertrend_weight = models.FloatField(default=1.9, help_text=_("SuperTrend weight"))
    mfi_weight = models.FloatField(default=1.3, help_text=_("Money Flow Index weight"))
    psar_weight = models.FloatField(default=1.1, help_text=_("Parabolic SAR weight"))
    fibonacci_weight = models.FloatField(default=2.5, help_text=_("Fibonacci pullback weight"))

    fib_lookback_candles = models.IntegerField(
        default=50,
        validators=[MinValueValidator(10), MaxValueValidator(200)],
        help_text=_("Candles to search for Fibonacci swing points"),
    )
    fib_entry_zone_min = models.FloatField(
        default=0.5,
        help_text=_("Fibonacci entry zone minimum (0.5 = 50% retracement)"),
    )
    fib_entry_zone_max = models.FloatField(
        default=0.618,
        help_text=_("Fibonacci entry zone maximum (0.618 = golden ratio)"),
    )
    fib_enable_pullback = models.BooleanField(
        default=True,
        help_text=_("Enable Fibonacci pullback detection"),
    )

    rsi_period = models.IntegerField(default=14, validators=[MinValueValidator(5), MaxValueValidator(50)], help_text=_("RSI calculation period"))
    macd_fast = models.IntegerField(default=12, validators=[MinValueValidator(5), MaxValueValidator(50)], help_text=_("MACD fast EMA period"))
    macd_slow = models.IntegerField(default=26, validators=[MinValueValidator(10), MaxValueValidator(100)], help_text=_("MACD slow EMA period"))
    macd_signal = models.IntegerField(default=9, validators=[MinValueValidator(3), MaxValueValidator(30)], help_text=_("MACD signal line period"))
    ema_fast = models.IntegerField(default=9, validators=[MinValueValidator(3), MaxValueValidator(50)], help_text=_("Fast EMA period"))
    ema_medium = models.IntegerField(default=21, validators=[MinValueValidator(10), MaxValueValidator(100)], help_text=_("Medium EMA period"))
    ema_slow = models.IntegerField(default=50, validators=[MinValueValidator(20), MaxValueValidator(200)], help_text=_("Slow EMA period"))
    ema_trend = models.IntegerField(default=200, validators=[MinValueValidator(50), MaxValueValidator(500)], help_text=_("Trend EMA period (long-term)"))
    atr_period = models.IntegerField(default=14, validators=[MinValueValidator(5), MaxValueValidator(50)], help_text=_("ATR calculation period"))
    adx_period = models.IntegerField(default=14, validators=[MinValueValidator(5), MaxValueValidator(50)], help_text=_("ADX calculation period"))
    bb_period = models.IntegerField(default=20, validators=[MinValueValidator(10), MaxValueValidator(50)], help_text=_("Bollinger Bands period"))
    bb_std_dev = models.FloatField(default=2.0, validators=[MinValueValidator(0.5), MaxValueValidator(4.0)], help_text=_("Bollinger Bands standard deviation"))
    volume_ma_period = models.IntegerField(default=20, validators=[MinValueValidator(5), MaxValueValidator(50)], help_text=_("Volume moving average period"))
    supertrend_period = models.IntegerField(default=10, validators=[MinValueValidator(5), MaxValueValidator(50)], help_text=_("SuperTrend ATR period"))
    supertrend_multiplier = models.FloatField(default=3.0, validators=[MinValueValidator(1.0), MaxValueValidator(10.0)], help_text=_("SuperTrend ATR multiplier"))
    mfi_period = models.IntegerField(default=14, validators=[MinValueValidator(5), MaxValueValidator(50)], help_text=_("Money Flow Index period"))
    psar_acceleration = models.FloatField(default=0.02, validators=[MinValueValidator(0.005), MaxValueValidator(0.1)], help_text=_("Parabolic SAR acceleration factor"))
    psar_maximum = models.FloatField(default=0.2, validators=[MinValueValidator(0.1), MaxValueValidator(0.5)], help_text=_("Parabolic SAR maximum acceleration"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'strategy_configs'
        ordering = ['timeframe']
        verbose_name = _('Strategy Config')
        verbose_name_plural = _('Strategy Configs')

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.get_timeframe_display()} - {status} (Conf: {self.min_confidence}, SL: {self.sl_percentage}%, TP: {self.tp_percentage}%)"

    def to_signal_config(self):
        """Convert DB config to SignalConfig dataclass for the signal engine."""
        from scanner.strategies.signal_engine import SignalConfig
        return SignalConfig(
            min_confidence=self.min_confidence,
            long_rsi_min=self.long_rsi_min,
            long_rsi_max=self.long_rsi_max,
            short_rsi_min=self.short_rsi_min,
            short_rsi_max=self.short_rsi_max,
            long_adx_min=self.long_adx_min,
            short_adx_min=self.short_adx_min,
            long_volume_multiplier=self.long_volume_multiplier,
            short_volume_multiplier=self.short_volume_multiplier,
            sl_atr_multiplier=self.sl_atr_multiplier,
            tp_atr_multiplier=self.tp_atr_multiplier,
            sl_percentage=float(self.sl_percentage),
            tp_percentage=float(self.tp_percentage),
            risk_reward_ratio=self.risk_reward_ratio,
            macd_weight=self.macd_weight,
            rsi_weight=self.rsi_weight,
            price_ema_weight=self.price_ema_weight,
            adx_weight=self.adx_weight,
            ha_weight=self.ha_weight,
            volume_weight=self.volume_weight,
            ema_alignment_weight=self.ema_alignment_weight,
            di_weight=self.di_weight,
            bb_weight=self.bb_weight,
            volatility_weight=self.volatility_weight,
            supertrend_weight=self.supertrend_weight,
            mfi_weight=self.mfi_weight,
            psar_weight=self.psar_weight,
            fibonacci_weight=self.fibonacci_weight,
            fib_lookback_candles=self.fib_lookback_candles,
            fib_entry_zone_min=self.fib_entry_zone_min,
            fib_entry_zone_max=self.fib_entry_zone_max,
            fib_enable_pullback=self.fib_enable_pullback,
        )

    @classmethod
    def get_config(cls, timeframe):
        """
        Get strategy config for a timeframe.
        Returns DB config if exists, otherwise creates default from hardcoded values.
        """
        config, created = cls.objects.get_or_create(
            timeframe=timeframe,
            defaults=cls._get_defaults(timeframe)
        )
        if created:
            from django.utils import timezone as tz
            import logging
            logging.getLogger(__name__).info(f"Created default StrategyConfig for {timeframe}")
        return config

    @classmethod
    def _get_defaults(cls, timeframe):
        """Get default values per timeframe matching the hardcoded FUTURES_TIMEFRAME_CONFIGS."""
        defaults = {
            '5m': dict(
                min_confidence=0.78, long_adx_min=25.0, short_adx_min=25.0,
                long_rsi_min=25.0, long_rsi_max=35.0, short_rsi_min=65.0, short_rsi_max=75.0,
                sl_atr_multiplier=1.8, tp_atr_multiplier=4.5,
                sl_percentage=Decimal('2.50'), tp_percentage=Decimal('6.00'),
            ),
            '15m': dict(
                min_confidence=0.75, long_adx_min=25.0, short_adx_min=25.0,
                long_rsi_min=25.0, long_rsi_max=35.0, short_rsi_min=65.0, short_rsi_max=75.0,
                sl_atr_multiplier=2.5, tp_atr_multiplier=7.0,
                sl_percentage=Decimal('2.50'), tp_percentage=Decimal('6.00'),
            ),
            '30m': dict(
                min_confidence=0.73, long_adx_min=25.0, short_adx_min=25.0,
                long_rsi_min=25.0, long_rsi_max=35.0, short_rsi_min=65.0, short_rsi_max=75.0,
                sl_atr_multiplier=2.5, tp_atr_multiplier=7.0,
                sl_percentage=Decimal('2.50'), tp_percentage=Decimal('6.00'),
            ),
            '1h': dict(
                min_confidence=0.73, long_adx_min=26.0, short_adx_min=26.0,
                long_rsi_min=23.0, long_rsi_max=33.0, short_rsi_min=67.0, short_rsi_max=77.0,
                sl_atr_multiplier=3.0, tp_atr_multiplier=9.0,
                sl_percentage=Decimal('2.50'), tp_percentage=Decimal('6.00'),
            ),
            '4h': dict(
                min_confidence=0.70, long_adx_min=28.0, short_adx_min=28.0,
                long_rsi_min=23.0, long_rsi_max=33.0, short_rsi_min=67.0, short_rsi_max=77.0,
                sl_atr_multiplier=3.0, tp_atr_multiplier=9.0,
                sl_percentage=Decimal('2.50'), tp_percentage=Decimal('6.00'),
            ),
            '1d': dict(
                min_confidence=0.72, long_adx_min=30.0, short_adx_min=30.0,
                long_rsi_min=23.0, long_rsi_max=33.0, short_rsi_min=67.0, short_rsi_max=77.0,
                sl_atr_multiplier=3.5, tp_atr_multiplier=9.0,
                sl_percentage=Decimal('2.50'), tp_percentage=Decimal('6.00'),
            ),
        }
        return defaults.get(timeframe, {})
