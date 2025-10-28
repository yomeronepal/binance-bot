"""
Trading signal models
"""
from django.db import models
from django.conf import settings


class Signal(models.Model):
    """
    Trading signal model
    """
    SIGNAL_TYPES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('HOLD', 'Hold'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('EXECUTED', 'Executed'),
    ]

    symbol = models.CharField(max_length=20)  # e.g., BTCUSDT
    signal_type = models.CharField(max_length=10, choices=SIGNAL_TYPES)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    target_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    confidence = models.IntegerField(default=50)  # 0-100
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='signals',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'signals'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.signal_type} {self.symbol} @ {self.entry_price}"
