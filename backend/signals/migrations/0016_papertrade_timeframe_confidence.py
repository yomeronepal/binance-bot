from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0015_add_papertrade_performance_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='papertrade',
            name='timeframe',
            field=models.CharField(blank=True, help_text='Signal timeframe (e.g., 1h, 4h)', max_length=5, null=True),
        ),
        migrations.AddField(
            model_name='papertrade',
            name='confidence',
            field=models.FloatField(blank=True, help_text='Signal confidence (0.0 - 1.0)', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)]),
        ),
        migrations.AddIndex(
            model_name='papertrade',
            index=models.Index(fields=['timeframe', 'status'], name='paper_trade_timefra_idx'),
        ),
        migrations.AddIndex(
            model_name='papertrade',
            index=models.Index(fields=['confidence', 'status'], name='paper_trade_confide_idx'),
        ),
    ]
