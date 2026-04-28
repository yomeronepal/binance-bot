from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0040_paper_trade_fear_greed'),
    ]

    operations = [
        migrations.CreateModel(
            name='TopPerformingSymbol',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('symbol', models.CharField(max_length=20)),
                ('period_start', models.DateField()),
                ('period_end', models.DateField()),
                ('rank', models.PositiveSmallIntegerField()),
                ('total_trades', models.PositiveIntegerField(default=0)),
                ('wins', models.PositiveIntegerField(default=0)),
                ('losses', models.PositiveIntegerField(default=0)),
                ('win_rate', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('total_pnl', models.DecimalField(decimal_places=4, default=0, max_digits=14)),
                ('total_pnl_pct', models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ('avg_pnl_pct', models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ('best_trade_pct', models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ('worst_trade_pct', models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ('calculated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Top Performing Symbol',
                'verbose_name_plural': 'Top Performing Symbols',
                'db_table': 'top_performing_symbols',
                'ordering': ['-period_start', 'rank'],
                'unique_together': {('symbol', 'period_start')},
                'indexes': [
                    models.Index(fields=['-period_start', 'rank'],
                                 name='topperf_period_rank_idx'),
                    models.Index(fields=['symbol', '-period_start'],
                                 name='topperf_symbol_period_idx'),
                ],
            },
        ),
    ]
