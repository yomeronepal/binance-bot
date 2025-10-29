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
    # Scan Binance SPOT market every minute
    'scan-binance-market': {
        'task': 'scanner.tasks.celery_tasks.scan_binance_market',
        'schedule': 60.0,  # Every 60 seconds
        'options': {
            'expires': 50.0,  # Expire if not executed within 50 seconds
        }
    },

    # Scan Binance FUTURES market every minute
    'scan-futures-market': {
        'task': 'scanner.tasks.celery_tasks.scan_futures_market',
        'schedule': 60.0,  # Every 60 seconds
        'options': {
            'expires': 50.0,  # Expire if not executed within 50 seconds
        }
    },

    # Full data refresh every hour
    'full-data-refresh': {
        'task': 'scanner.tasks.celery_tasks.full_data_refresh',
        'schedule': crontab(minute=0),  # Every hour at minute 0
        'options': {
            'expires': 3000.0,
        }
    },

    # Send high-confidence signal notifications every 2 minutes
    'send-signal-notifications': {
        'task': 'scanner.tasks.celery_tasks.send_signal_notifications',
        'schedule': 120.0,  # Every 2 minutes
        'options': {
            'expires': 110.0,
        }
    },

    # Cleanup expired signals every 5 minutes
    'cleanup-expired-signals': {
        'task': 'scanner.tasks.celery_tasks.cleanup_expired_signals',
        'schedule': 300.0,  # Every 5 minutes
    },

    # System health check every 10 minutes
    'system-health-check': {
        'task': 'scanner.tasks.celery_tasks.system_health_check',
        'schedule': 600.0,  # Every 10 minutes
    },

    # Check and auto-close paper trades every 30 seconds
    'check-paper-trades': {
        'task': 'scanner.tasks.celery_tasks.check_and_close_paper_trades',
        'schedule': 30.0,  # Every 30 seconds
        'options': {
            'expires': 25.0,  # Expire if not executed within 25 seconds
        }
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
        'scanner.tasks.celery_tasks.cleanup_expired_signals': {'queue': 'maintenance'},
        'scanner.tasks.celery_tasks.system_health_check': {'queue': 'maintenance'},
        'scanner.tasks.celery_tasks.check_and_close_paper_trades': {'queue': 'paper_trading'},
    },
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f'Request: {self.request!r}')
    return 'Celery is working!'
