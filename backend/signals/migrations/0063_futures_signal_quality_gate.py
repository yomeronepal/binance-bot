from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0062_daytrade_is_priority'),
    ]

    operations = [
        migrations.AddField(
            model_name='futurestradingsettings',
            name='futures_universe_screen_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Screen futures signals by liquidity + volatility before executing (drops illiquid/parabolic symbols)',
            ),
        ),
        migrations.AddField(
            model_name='futurestradingsettings',
            name='opposite_exit_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Arm a trade in drawdown when an opposite day-trade signal appears, then close it once it recovers to profit',
            ),
        ),
        migrations.AddField(
            model_name='futurestradingsettings',
            name='opposite_exit_shadow_mode',
            field=models.BooleanField(
                default=True,
                help_text='Log opposite-exit arm/close decisions without executing them (validation mode)',
            ),
        ),
        migrations.AddField(
            model_name='futurestradingsettings',
            name='opposite_exit_min_confidence',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.70'),
                max_digits=4,
                help_text='Minimum confidence of the opposite day-trade signal that arms an exit',
                validators=[
                    django.core.validators.MinValueValidator(Decimal('0')),
                    django.core.validators.MaxValueValidator(Decimal('1')),
                ],
            ),
        ),
        migrations.AddField(
            model_name='futurestradingsettings',
            name='opposite_exit_min_profit_pct',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.20'),
                max_digits=4,
                help_text='Only close an armed trade once unrealized PnL reaches this % of margin (covers round-trip fees)',
                validators=[
                    django.core.validators.MinValueValidator(Decimal('0')),
                    django.core.validators.MaxValueValidator(Decimal('10')),
                ],
            ),
        ),
        migrations.AddField(
            model_name='futurestrade',
            name='opposite_exit_armed',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='Armed to close on recovery after an opposite signal appeared while in drawdown',
            ),
        ),
        migrations.AddField(
            model_name='futurestrade',
            name='opposite_exit_armed_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='When the opposite-exit arm was triggered',
            ),
        ),
        migrations.AlterField(
            model_name='futurestrade',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pending'),
                    ('OPEN', 'Open'),
                    ('CLOSED_TP', 'Closed - Take Profit'),
                    ('CLOSED_SL', 'Closed - Stop Loss'),
                    ('CLOSED_MANUAL', 'Closed - Manual'),
                    ('CLOSED_REVERSAL', 'Closed - Opposite Signal'),
                    ('FAILED', 'Failed'),
                    ('CANCELLED', 'Cancelled'),
                ],
                default='PENDING',
                help_text='Trade status',
                max_length=20,
            ),
        ),
    ]
