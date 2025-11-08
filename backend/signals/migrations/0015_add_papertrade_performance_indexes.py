# Generated manually for optimization
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0014_fix_papertrade_cascade'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='papertrade',
            index=models.Index(fields=['status', '-created_at'], name='paper_trade_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='papertrade',
            index=models.Index(fields=['user', '-created_at'], name='paper_trade_user_created_idx'),
        ),
        migrations.AddIndex(
            model_name='papertrade',
            index=models.Index(fields=['market_type', 'status'], name='paper_trade_market_status_idx'),
        ),
    ]
