from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0041_top_performing_symbol'),
    ]

    operations = [
        migrations.AddField(
            model_name='futurestradingsettings',
            name='macro_filter_enabled',
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Enable BTC macro filter at the Binance trade boundary. "
                    "When ON, futures orders are blocked if BTC's daily regime "
                    "contradicts the signal direction (LONG when BTC is below "
                    "EMA20/50 or 7d return < 0; SHORT when BTC is in uptrend or "
                    "3d return < -7%). "
                    "Signal-creation tagging (signal.meta.macro_at_signal) is "
                    "always on regardless of this flag — it powers the analytics "
                    "filter on Bot Performance and has near-zero cost."
                ),
            ),
        ),
    ]
