from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0054_daytradestrategyconfig_sl_tp_percentage'),
    ]

    operations = [
        migrations.AddField(
            model_name='futurestrade',
            name='entry_attempts',
            field=models.IntegerField(
                default=0,
                help_text='Number of order-placement attempts made for this trade',
            ),
        ),
        migrations.AddField(
            model_name='futurestrade',
            name='next_entry_retry_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Earliest time to retry a failed entry (exponential backoff)',
            ),
        ),
    ]
