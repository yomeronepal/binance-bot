import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0056_daytradestrategyconfig_block_on_choch_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DayTradeSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('session_type', models.CharField(
                    choices=[('ALL_DAYS', 'All days window'), ('WEEKDAY', 'Weekday-specific window')],
                    default='ALL_DAYS', max_length=20)),
                ('description', models.CharField(blank=True, default='', max_length=255)),
                ('start_hour', models.PositiveIntegerField(
                    validators=[django.core.validators.MinValueValidator(0),
                                django.core.validators.MaxValueValidator(23)])),
                ('end_hour', models.PositiveIntegerField(
                    validators=[django.core.validators.MinValueValidator(1),
                                django.core.validators.MaxValueValidator(24)])),
                ('active_days', models.JSONField(blank=True, default=list)),
                ('win_rate', models.FloatField(blank=True, null=True)),
                ('total_trades_analyzed', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('auto_generated', models.BooleanField(default=True)),
                ('last_optimized_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Day-Trade Session',
                'verbose_name_plural': 'Day-Trade Sessions',
                'db_table': 'daytrade_sessions',
                'ordering': ['start_hour', 'name'],
            },
        ),
    ]
