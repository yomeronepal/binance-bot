"""
Celery configuration for Binance Trading Bot project.
Handles periodic tasks, background jobs, and monitoring.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('binance_bot')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat Schedule (Periodic Tasks)
app.conf.beat_schedule = {
    # ============================================================================
    # SPOT SCANNING - MULTI-TIMEFRAME
    # ============================================================================

    'scan-1d-timeframe': {
        'task': 'scanner.tasks.multi_timeframe_scanner.scan_1d_timeframe',
        'schedule': crontab(minute=5, hour=0),
        'options': {'expires': 3600.0},
    },

    'scan-4h-timeframe': {
        'task': 'scanner.tasks.multi_timeframe_scanner.scan_4h_timeframe',
        'schedule': crontab(minute=5, hour='0,4,8,12,16,20'),
        'options': {'expires': 1800.0},
    },

    'scan-1h-timeframe': {
        'task': 'scanner.tasks.multi_timeframe_scanner.scan_1h_timeframe',
        'schedule': crontab(minute=5),
        'options': {'expires': 1800.0},
    },

    'scan-15m-timeframe': {
        'task': 'scanner.tasks.multi_timeframe_scanner.scan_15m_timeframe',
        'schedule': crontab(minute='*/15'),
        'options': {'expires': 900.0},
    },

    # ============================================================================
    # FUTURES SCANNING - MULTI-TIMEFRAME (ALL PAIRS)
    # ============================================================================

    'scan-futures-1d-timeframe': {
        'task': 'scanner.tasks.futures_multi_timeframe_scanner.scan_futures_1d',
        'schedule': crontab(minute=15, hour=0),
        'options': {'expires': 3600.0},
    },

    'scan-futures-4h-timeframe': {
        'task': 'scanner.tasks.futures_multi_timeframe_scanner.scan_futures_4h',
        'schedule': crontab(minute=15, hour='0,4,8,12,16,20'),
        'options': {'expires': 1800.0},
    },

    'scan-futures-1h-timeframe': {
        'task': 'scanner.tasks.futures_multi_timeframe_scanner.scan_futures_1h',
        'schedule': crontab(minute=15),
        'options': {'expires': 1800.0},
    },

    'scan-futures-15m-timeframe': {
        'task': 'scanner.tasks.futures_multi_timeframe_scanner.scan_futures_15m',
        'schedule': crontab(minute='*/15'),
        'options': {'expires': 900.0},
    },

    # ============================================================================
    # SYSTEM MAINTENANCE
    # ============================================================================

    # Full data refresh - REDUCED FREQUENCY
    'full-data-refresh': {
        'task': 'scanner.tasks.celery_tasks.full_data_refresh',
        'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours (was every hour)
        'options': {'expires': 3600.0},
    },

    # Cleanup expired signals - KEEP FREQUENT
    'cleanup-expired-signals': {
        'task': 'scanner.tasks.celery_tasks.cleanup_expired_signals',
        'schedule': 300.0,  # Every 5 minutes
    },

    # System health check - OPTIMIZED
    'system-health-check': {
        'task': 'scanner.tasks.celery_tasks.system_health_check',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes (was 10)
        'options': {'expires': 1200.0},
    },

    # Paper trading check - KEEP FREQUENT
    'check-paper-trades': {
        'task': 'scanner.tasks.celery_tasks.check_and_close_paper_trades',
        'schedule': 30.0,  # Every 30 seconds
        'options': {'expires': 25.0},
    },

    # Fibonacci pullback monitoring - FREQUENT
    'monitor-fibonacci-pullbacks': {
        'task': 'scanner.tasks.celery_tasks.monitor_fibonacci_pullbacks',
        'schedule': 30.0,  # Every 30 seconds
        'options': {'expires': 25.0},
    },

    # Cache maintenance - OPTIMIZED
    'check-stale-cache': {
        'task': 'signals.check_stale_cache',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },

    # Performance monitoring - OPTIMIZED
    'monitor-config-performance': {
        'task': 'signals.monitor_config_performance',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },

}

# Celery Configuration
app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Task execution settings
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,

    # Worker settings
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks

    # Task routing
    task_routes={
        'scanner.tasks.celery_tasks.scan_binance_market': {'queue': 'scanner'},
        'scanner.tasks.celery_tasks.scan_futures_market': {'queue': 'scanner'},
        'scanner.tasks.celery_tasks.full_data_refresh': {'queue': 'scanner'},
        'scanner.tasks.celery_tasks.send_signal_notifications': {'queue': 'notifications'},
        'scanner.tasks.celery_tasks.cleanup_expired_signals': {'queue': 'celery'},
        'scanner.tasks.celery_tasks.system_health_check': {'queue': 'celery'},
        'scanner.tasks.celery_tasks.check_and_close_paper_trades': {'queue': 'paper_trading'},
        # Backtesting tasks
        'scanner.tasks.backtest_tasks.run_backtest_async': {'queue': 'backtesting'},
        # Futures multi-timeframe scanning tasks
        'scanner.tasks.futures_multi_timeframe_scanner.scan_futures_1d': {'queue': 'scanner'},
        'scanner.tasks.futures_multi_timeframe_scanner.scan_futures_4h': {'queue': 'scanner'},
        'scanner.tasks.futures_multi_timeframe_scanner.scan_futures_1h': {'queue': 'scanner'},
        'scanner.tasks.futures_multi_timeframe_scanner.scan_futures_15m': {'queue': 'scanner'},
        'scanner.tasks.futures_multi_timeframe_scanner.scan_futures_5m': {'queue': 'scanner'},
    },
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f'Request: {self.request!r}')
    return 'Celery is working!'
