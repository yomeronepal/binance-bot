"""
Add live PnL fields to FuturesTrade model for real-time tracking.
"""
from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0025_add_gw_trading_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='futurestrade',
            name='mark_price',
            field=models.DecimalField(
                blank=True,
                decimal_places=8,
                help_text='Current mark price from Binance',
                max_digits=20,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='futurestrade',
            name='unrealized_pnl',
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal('0'),
                help_text='Unrealized P/L in USDT (live)',
                max_digits=12
            ),
        ),
        migrations.AddField(
            model_name='futurestrade',
            name='unrealized_pnl_percentage',
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal('0'),
                help_text='Unrealized P/L percentage (live)',
                max_digits=8
            ),
        ),
        migrations.AddField(
            model_name='futurestrade',
            name='liquidation_price',
            field=models.DecimalField(
                blank=True,
                decimal_places=8,
                help_text='Liquidation price from Binance',
                max_digits=20,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='futurestrade',
            name='margin_type',
            field=models.CharField(
                default='ISOLATED',
                help_text='Margin type (ISOLATED/CROSS)',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='futurestrade',
            name='last_sync_time',
            field=models.DateTimeField(
                blank=True,
                help_text='Last time this trade was synced with Binance',
                null=True
            ),
        ),
    ]
