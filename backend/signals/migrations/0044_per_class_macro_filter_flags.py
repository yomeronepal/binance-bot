from django.db import migrations, models


def copy_legacy_flag_to_per_class(apps, schema_editor):
    """
    Preserve current behavior on existing rows: copy the legacy
    ``macro_filter_enabled`` value into all three new per-class flags
    so first deploy doesn't silently flip anything.
    """
    FuturesTradingSettings = apps.get_model('signals', 'FuturesTradingSettings')
    for row in FuturesTradingSettings.objects.all():
        row.crypto_macro_filter_enabled = row.macro_filter_enabled
        row.stock_macro_filter_enabled = row.macro_filter_enabled
        row.commodity_macro_filter_enabled = row.macro_filter_enabled
        row.save(update_fields=[
            'crypto_macro_filter_enabled',
            'stock_macro_filter_enabled',
            'commodity_macro_filter_enabled',
        ])


def noop_reverse(apps, schema_editor):
    """Schema removal handles the field drop; nothing to undo data-wise."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0043_asset_class'),
    ]

    operations = [
        migrations.AddField(
            model_name='futurestradingsettings',
            name='crypto_macro_filter_enabled',
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Enable BTC macro filter for CRYPTO signals at the "
                    "Binance trade boundary."
                ),
            ),
        ),
        migrations.AddField(
            model_name='futurestradingsettings',
            name='stock_macro_filter_enabled',
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Enable SPY macro filter for STOCK signals."
                ),
            ),
        ),
        migrations.AddField(
            model_name='futurestradingsettings',
            name='commodity_macro_filter_enabled',
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Enable XAU (gold) macro filter for COMMODITY signals."
                ),
            ),
        ),
        migrations.RunPython(copy_legacy_flag_to_per_class, noop_reverse),
    ]
