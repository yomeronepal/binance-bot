from django.db import migrations, models


ASSET_CLASS_CHOICES = [
    ('CRYPTO', 'Crypto'),
    ('STOCK', 'Stock'),
    ('COMMODITY', 'Commodity'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0042_futurestradingsettings_macro_filter_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='symbol',
            name='asset_class',
            field=models.CharField(
                max_length=10,
                choices=ASSET_CLASS_CHOICES,
                default='CRYPTO',
                db_index=True,
                help_text='Asset class (CRYPTO/STOCK/COMMODITY)',
            ),
        ),
        migrations.AddField(
            model_name='signal',
            name='asset_class',
            field=models.CharField(
                max_length=10,
                choices=ASSET_CLASS_CHOICES,
                default='CRYPTO',
                db_index=True,
                help_text='Asset class (CRYPTO/STOCK/COMMODITY)',
            ),
        ),
        migrations.AddField(
            model_name='papertrade',
            name='asset_class',
            field=models.CharField(
                max_length=10,
                choices=ASSET_CLASS_CHOICES,
                default='CRYPTO',
                db_index=True,
                help_text='Asset class (CRYPTO/STOCK/COMMODITY)',
            ),
        ),
    ]
