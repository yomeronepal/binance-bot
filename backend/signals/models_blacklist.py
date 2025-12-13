"""
Blacklist models for excluding symbols from trading.
"""
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class BlacklistedSymbol(models.Model):
    """
    Model for tracking blacklisted trading symbols.
    Blacklisted symbols are excluded from:
    - Signal generation
    - Paper trading
    - Auto-trading
    """
    REASON_CHOICES = [
        ('HIGH_VOLATILITY', _('High Volatility - Too risky')),
        ('LOW_LIQUIDITY', _('Low Liquidity - Poor fills')),
        ('POOR_PERFORMANCE', _('Poor Performance - Consistent losses')),
        ('DELISTED', _('Delisted - No longer available')),
        ('TEMPORARY', _('Temporary - Short-term exclusion')),
        ('MANUAL', _('Manual - User preference')),
        ('OTHER', _('Other')),
    ]

    symbol = models.CharField(
        max_length=20,
        unique=True,
        help_text=_("Symbol to blacklist (e.g., BTCUSDT)")
    )
    reason = models.CharField(
        max_length=30,
        choices=REASON_CHOICES,
        default='MANUAL',
        help_text=_("Reason for blacklisting")
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text=_("Additional notes about why this symbol is blacklisted")
    )
    blacklisted_at = models.DateTimeField(
        default=timezone.now,
        help_text=_("When this symbol was blacklisted")
    )
    blacklisted_until = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("Auto-remove from blacklist after this date (optional)")
    )
    active = models.BooleanField(
        default=True,
        help_text=_("Whether this blacklist entry is currently active")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'signals_blacklisted_symbols'
        ordering = ['-blacklisted_at']
        verbose_name = _('Blacklisted Symbol')
        verbose_name_plural = _('Blacklisted Symbols')
        indexes = [
            models.Index(fields=['symbol', 'active']),
            models.Index(fields=['active', 'blacklisted_at']),
        ]

    def __str__(self):
        return f"{self.symbol} - {self.get_reason_display()}"

    def is_expired(self):
        """Check if blacklist entry has expired."""
        if not self.blacklisted_until:
            return False
        return timezone.now() > self.blacklisted_until

    @classmethod
    def is_blacklisted(cls, symbol):
        """
        Check if a symbol is currently blacklisted.

        Args:
            symbol (str): Symbol to check (e.g., 'BTCUSDT')

        Returns:
            bool: True if symbol is blacklisted, False otherwise
        """
        now = timezone.now()
        return cls.objects.filter(
            symbol=symbol,
            active=True
        ).filter(
            models.Q(blacklisted_until__isnull=True) |
            models.Q(blacklisted_until__gt=now)
        ).exists()

    @classmethod
    def get_blacklisted_symbols(cls):
        """
        Get all currently blacklisted symbols.

        Returns:
            list: List of blacklisted symbol strings
        """
        now = timezone.now()
        return list(
            cls.objects.filter(
                active=True
            ).filter(
                models.Q(blacklisted_until__isnull=True) |
                models.Q(blacklisted_until__gt=now)
            ).values_list('symbol', flat=True)
        )

    def save(self, *args, **kwargs):
        """Override save to auto-deactivate expired entries."""
        if self.is_expired() and self.active:
            self.active = False
        super().save(*args, **kwargs)
