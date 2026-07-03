from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0061_daytradestrategyconfig_signal_cooldown_minutes'),
    ]

    operations = [
        migrations.AddField(
            model_name='daytradesignal',
            name='is_priority',
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text='Generated inside an active DayTradeSession window',
            ),
        ),
        migrations.AddField(
            model_name='daytradepapertrade',
            name='is_priority',
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text='Copied from the signal: opened inside a session window',
            ),
        ),
    ]
