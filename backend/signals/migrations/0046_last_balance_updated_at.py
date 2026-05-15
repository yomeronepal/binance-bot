from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0045_balance_rebalance_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='futurestradingsettings',
            name='last_balance_updated_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text=(
                    "When total_trading_capital was last refreshed from "
                    "the live Binance futures balance."
                ),
            ),
        ),
        migrations.AlterField(
            model_name='futurestradingsettings',
            name='total_trading_capital',
            field=models.DecimalField(
                max_digits=12,
                decimal_places=2,
                default='100.00',
                help_text=(
                    "Last known Binance futures USDT wallet balance. "
                    "Written by the monthly rebalance task and read by "
                    "the frontend balance display."
                ),
            ),
        ),
    ]
