"""
Models for chart annotations (Fib levels, support/resistance, notes)
"""
from django.db import models
from django.conf import settings


class ChartAnnotation(models.Model):
    """
    Stores user-defined chart annotations like Fib levels, support/resistance lines.
    """
    ANNOTATION_TYPES = [
        ('FIB', 'Fibonacci Level'),
        ('SUPPORT', 'Support Line'),
        ('RESISTANCE', 'Resistance Line'),
        ('TRENDLINE', 'Trendline'),
        ('NOTE', 'Note'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='chart_annotations',
    )
    symbol = models.CharField(max_length=20, db_index=True)
    annotation_type = models.CharField(max_length=20, choices=ANNOTATION_TYPES, default='FIB')
    price_level = models.DecimalField(max_digits=20, decimal_places=8)
    label = models.CharField(max_length=50, blank=True)  # e.g., "0.618", "Support 1"
    color = models.CharField(max_length=7, default='#3b82f6')  # Hex color
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['symbol', 'price_level']
        indexes = [
            models.Index(fields=['user', 'symbol', 'is_active']),
        ]

    def __str__(self):
        return f"{self.symbol} - {self.label} @ {self.price_level}"


class FibonacciSetup(models.Model):
    """
    Stores Fibonacci retracement setups (high/low) for auto-calculating levels.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='fibonacci_setups',
    )
    symbol = models.CharField(max_length=20, db_index=True)
    swing_high = models.DecimalField(max_digits=20, decimal_places=8)
    swing_low = models.DecimalField(max_digits=20, decimal_places=8)
    direction = models.CharField(max_length=10, choices=[('UP', 'Uptrend'), ('DOWN', 'Downtrend')], default='UP')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'symbol')

    def get_fib_levels(self):
        """Calculate Fibonacci retracement levels."""
        high = float(self.swing_high)
        low = float(self.swing_low)
        diff = high - low

        if self.direction == 'UP':
            # Uptrend: levels from high going down
            return {
                '0.0': high,
                '0.236': high - (diff * 0.236),
                '0.382': high - (diff * 0.382),
                '0.5': high - (diff * 0.5),
                '0.618': high - (diff * 0.618),
                '0.786': high - (diff * 0.786),
                '1.0': low,
            }
        else:
            # Downtrend: levels from low going up
            return {
                '0.0': low,
                '0.236': low + (diff * 0.236),
                '0.382': low + (diff * 0.382),
                '0.5': low + (diff * 0.5),
                '0.618': low + (diff * 0.618),
                '0.786': low + (diff * 0.786),
                '1.0': high,
            }

    def __str__(self):
        return f"{self.symbol} Fib: {self.swing_low} - {self.swing_high}"
