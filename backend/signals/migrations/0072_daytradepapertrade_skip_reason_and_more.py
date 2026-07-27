from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0071_remove_futurestradingsettings_daytrade_max_trades_per_session_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='daytradepapertrade',
            name='skip_reason',
            field=models.CharField(blank=True, db_index=True, default='', help_text="Live gate that would have skipped this trade: ''=taken, 'breaker'.", max_length=16),
        ),
        migrations.AddField(
            model_name='papertrade',
            name='skip_reason',
            field=models.CharField(blank=True, db_index=True, default='', help_text="Live gate that would have skipped this trade: ''=taken, 'breaker'.", max_length=16),
        ),
    ]
