from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0053_daytradestrategyconfig_universe_top_n_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='daytradestrategyconfig',
            name='sl_percentage',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('2.50'),
                help_text='Stop loss as percent from entry (v1-style single SL)',
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(Decimal('0.10')),
                    django.core.validators.MaxValueValidator(Decimal('20.00')),
                ],
            ),
        ),
        migrations.AddField(
            model_name='daytradestrategyconfig',
            name='tp_percentage',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('6.00'),
                help_text='Take profit as percent from entry (v1-style single TP)',
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(Decimal('0.10')),
                    django.core.validators.MaxValueValidator(Decimal('50.00')),
                ],
            ),
        ),
        migrations.AlterField(
            model_name='daytradestrategyconfig',
            name='atr_period',
            field=models.PositiveIntegerField(
                default=14,
                help_text='ATR period (used for the ATR-regime score component)',
                validators=[
                    django.core.validators.MinValueValidator(2),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
    ]
