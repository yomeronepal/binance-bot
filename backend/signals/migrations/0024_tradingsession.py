# Generated manually 2025-12-19

from django.db import migrations, models
import django.core.validators


def seed_trading_sessions(apps, schema_editor):
    """Seed initial trading sessions from hardcoded values."""
    TradingSession = apps.get_model('signals', 'TradingSession')
    
    # GW1: 17:00-18:00 NPT, Active Trading Window (all days)
    TradingSession.objects.create(
        name='GW1',
        session_type='ACTIVE_TRADING_WINDOW',
        description='Golden Window 1: High win-rate period 17:00-18:00 NPT',
        start_hour=17,
        start_minute=0,
        end_hour=18,
        end_minute=0,
        active_days=[],  # All days
        active=True
    )
    
    # GW2: 21:00-23:00 NPT, Golden Window (Sun, Wed, Thu only)
    # Python weekday: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    TradingSession.objects.create(
        name='GW2',
        session_type='GOLDEN_WINDOW',
        description='Golden Window 2: Premium window 21:00-23:00 NPT on Sunday, Wednesday, Thursday',
        start_hour=21,
        start_minute=0,
        end_hour=23,
        end_minute=0,
        active_days=[6, 2, 3],  # Sunday=6, Wednesday=2, Thursday=3
        active=True
    )
    
    # Window 2: 21:00-23:00 NPT, Active Trading Window (all days)
    TradingSession.objects.create(
        name='Window 2',
        session_type='ACTIVE_TRADING_WINDOW',
        description='Active Trading Window 2: 21:00-23:00 NPT on all days',
        start_hour=21,
        start_minute=0,
        end_hour=23,
        end_minute=0,
        active_days=[],  # All days
        active=True
    )


def reverse_seed_trading_sessions(apps, schema_editor):
    """Remove seeded trading sessions."""
    TradingSession = apps.get_model('signals', 'TradingSession')
    TradingSession.objects.filter(name__in=['GW1', 'GW2', 'Window 2']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0023_add_blacklist_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='TradingSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Session name (e.g., GW1, GW2)', max_length=100, unique=True)),
                ('session_type', models.CharField(choices=[('GOLDEN_WINDOW', 'Golden Window'), ('ACTIVE_TRADING_WINDOW', 'Active Trading Window')], help_text='Type of trading session', max_length=30)),
                ('description', models.TextField(blank=True, help_text='Session description')),
                ('start_hour', models.IntegerField(help_text='Start hour in Nepal Time (0-23)', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(23)])),
                ('start_minute', models.IntegerField(default=0, help_text='Start minute (0-59)', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(59)])),
                ('end_hour', models.IntegerField(help_text='End hour in Nepal Time (0-23)', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(23)])),
                ('end_minute', models.IntegerField(default=0, help_text='End minute (0-59)', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(59)])),
                ('active_days', models.JSONField(blank=True, default=list, help_text='Active days for GOLDEN_WINDOW type (0=Mon, 6=Sun). Empty = all days')),
                ('active', models.BooleanField(default=True, help_text='Whether this session is active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Trading Session',
                'verbose_name_plural': 'Trading Sessions',
                'db_table': 'trading_sessions',
                'ordering': ['start_hour', 'start_minute'],
                'indexes': [
                    models.Index(fields=['active', 'session_type'], name='trading_ses_active_c7c2e5_idx'),
                    models.Index(fields=['start_hour', 'end_hour'], name='trading_ses_start_h_e36f43_idx'),
                ],
            },
        ),
        migrations.RunPython(seed_trading_sessions, reverse_seed_trading_sessions),
    ]
