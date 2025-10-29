from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='signal',
            name='market_type',
            field=models.CharField(
                choices=[('SPOT', 'Spot'), ('FUTURES', 'Futures')],
                default='SPOT',
                help_text='Market type (SPOT/FUTURES)',
                max_length=10
            ),
        ),
        migrations.AddField(
            model_name='signal',
            name='leverage',
            field=models.IntegerField(
                blank=True,
                help_text='Leverage for futures (e.g., 10x)',
                null=True
            ),
        ),
        migrations.AddField(
            model_name='symbol',
            name='market_type',
            field=models.CharField(
                choices=[('SPOT', 'Spot'), ('FUTURES', 'Futures')],
                default='SPOT',
                help_text='Market type (SPOT/FUTURES)',
                max_length=10
            ),
        ),
    ]
