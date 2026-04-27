from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0041_user_binance_connection'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='futurestrade',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='futures_trades',
                to=settings.AUTH_USER_MODEL,
                help_text=(
                    "User account this trade belongs to. NULL means the central bot "
                    "account (env BINANCE_API_KEY); a user FK means the trade was "
                    "executed on that user's connected Binance account."
                ),
            ),
        ),
    ]
