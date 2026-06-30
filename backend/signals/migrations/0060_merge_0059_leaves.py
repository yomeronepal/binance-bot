from django.db import migrations


class Migration(migrations.Migration):
    """Merge the two 0059 leaf migrations (daytrade_live_enabled + the
    max_active_gw_trades/max_concurrent_trades alters) into a single graph
    head. No schema operations — both 0059s touch independent fields."""

    dependencies = [
        ('signals', '0059_alter_futurestradingsettings_max_active_gw_trades_and_more'),
        ('signals', '0059_futurestradingsettings_daytrade_live_enabled'),
    ]

    operations = []
