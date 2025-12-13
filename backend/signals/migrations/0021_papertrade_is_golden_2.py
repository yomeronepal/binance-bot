# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0020_papertrade_is_priority'),
    ]

    operations = [
        migrations.AddField(
            model_name='papertrade',
            name='is_golden_2',
            field=models.BooleanField(default=False, help_text='Whether this is a Golden Window 2.0 trade (Sun/Wed/Thu 21-23 NPT)'),
        ),
    ]
