from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0016_papertrade_timeframe_confidence'),
    ]

    operations = [
        migrations.AddField(
            model_name='signal',
            name='is_priority',
            field=models.BooleanField(
                default=False,
                help_text='Signal generated during high win-rate hours (17:00-18:00 or 21:00-23:00 UTC)'
            ),
        ),
    ]
