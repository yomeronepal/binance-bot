from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0044_per_class_macro_filter_flags'),
    ]

    operations = [
        migrations.CreateModel(
            name='BalanceRebalanceLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('balance', models.DecimalField(blank=True, decimal_places=4, help_text='Futures USDT wallet balance at rebalance time', max_digits=14, null=True)),
                ('per_trade_amount', models.DecimalField(blank=True, decimal_places=2, help_text='Computed per-trade size (balance / 3)', max_digits=12, null=True)),
                ('max_concurrent_trades', models.IntegerField(blank=True, help_text='Max concurrent trades set on this run', null=True)),
                ('backup_reserve', models.DecimalField(blank=True, decimal_places=4, help_text='balance - max_concurrent * per_trade', max_digits=14, null=True)),
                ('previous_trade_amount', models.DecimalField(blank=True, decimal_places=2, help_text='trade_amount on FuturesTradingSettings before this run', max_digits=12, null=True)),
                ('previous_max_concurrent_trades', models.IntegerField(blank=True, help_text='max_concurrent_trades on FuturesTradingSettings before this run', null=True)),
                ('applied', models.BooleanField(default=False, help_text='True if FuturesTradingSettings was written; False for dry-runs / failures')),
                ('reason', models.CharField(blank=True, help_text="Short outcome reason (e.g. 'rebalanced', 'dry-run; no write', 'balance fetch failed: ...')", max_length=255)),
            ],
            options={
                'verbose_name': 'Balance Rebalance Log',
                'verbose_name_plural': 'Balance Rebalance Logs',
                'db_table': 'balance_rebalance_logs',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['-created_at'], name='balance_reb_created_8d2e3f_idx'),
                    models.Index(fields=['applied', '-created_at'], name='balance_reb_applied_5d4a1c_idx'),
                ],
            },
        ),
    ]
