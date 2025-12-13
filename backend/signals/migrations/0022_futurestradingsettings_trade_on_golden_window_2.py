# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0021_papertrade_is_golden_2'),
    ]

    operations = [
        migrations.AddField(
            model_name='futurestradingsettings',
            name='trade_on_golden_window_2',
            field=models.BooleanField(default=False, help_text='Specifically enable trading during Golden Window 2 (Sun/Wed/Thu 21:00-23:00 NPT)'),
        ),
    ]
