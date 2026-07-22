from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0063_futures_signal_quality_gate'),
    ]

    operations = [
        migrations.AddField(
            model_name='daytradepapertrade',
            name='fees_paid',
            field=models.DecimalField(
                decimal_places=8,
                default=0,
                max_digits=20,
                help_text='Estimated round-trip trading costs deducted (fees + slippage + funding, USDT)',
            ),
        ),
        migrations.AlterField(
            model_name='daytradepapertrade',
            name='profit_loss',
            field=models.DecimalField(
                decimal_places=8,
                default=0,
                max_digits=20,
                help_text='Total realized P/L for the trade, net of fees (USDT)',
            ),
        ),
    ]
