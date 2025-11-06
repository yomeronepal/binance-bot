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
    # Scan 1-day timeframe every 6 hours (best for swing trading)
    'scan-1d-timeframe': {
        'task': 'scanner.tasks.multi_timeframe_scanner.scan_1d_timeframe',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        'options': {
            'expires': 3000.0,
        }
    },

    # Scan 4-hour timeframe every 4 hours (day trading)
    'scan-4h-timeframe': {
        'task': 'scanner.tasks.multi_timeframe_scanner.scan_4h_timeframe',
        'schedule': crontab(minute=0, hour='*/2'),  # Every 4 hours
        'options': {
            'expires': 3000.0,
        }
    },

    # Scan 1-hour timeframe every hour (intraday trading)
    'scan-1h-timeframe': {
        'task': 'scanner.tasks.multi_timeframe_scanner.scan_1h_timeframe',
        'schedule': crontab(minute=0),  # Every hour at minute 0
        'options': {
            'expires': 3000.0,
        }
    },

    # Scan 15-minute timeframe every 15 minutes (scalping)
    'scan-15m-timeframe': {
        'task': 'scanner.tasks.multi_timeframe_scanner.scan_15m_timeframe',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {
             'expires': 900.0,  # 15 minutes
        }
    },

    # === FOREX SIGNAL SCANNING ===

    # Scan major forex pairs (4h and 1d) every 4 hours
    'scan-major-forex-pairs': {
        'task': 'scanner.tasks.scan_major_forex_pairs',
        'schedule': crontab(minute=15, hour='*/4'),  # Every 4 hours at :15
        'options': {
            'expires': 3000.0,
        }
    },

    # Scan forex for scalping (15m and 1h) every hour
    # 'scan-forex-scalping': {
    #     'task': 'scanner.tasks.scan_forex_scalping',
    #     'schedule': crontab(minute=30),  # Every hour at :30
    #     'options': {
    #         'expires': 3000.0,
    #     }
    # },

    # OLD CONFIGS (DISABLED - NOW USING MULTI-TIMEFRAME ABOVE)
    # # Scan Binance SPOT market every minute
    # 'scan-binance-market': {
    #     'task': 'scanner.tasks.celery_tasks.scan_binance_market',
    #     'schedule': 60.0,  # Every 60 seconds
    #     'options': {
    #         'expires': 50.0,  # Expire if not executed within 50 seconds
    #     }
    # },

    # # Scan Binance FUTURES market every minute
    # 'scan-futures-market': {
    #     'task': 'scanner.tasks.celery_tasks.scan_futures_market',
    #     'schedule': 60.0,  # Every 60 seconds
    #     'options': {
    #         'expires': 50.0,  # Expire if not executed within 50 seconds
    #     }
    # },

    # # Full data refresh every hour
    # 'full-data-refresh': {
    #     'task': 'scanner.tasks.celery_tasks.full_data_refresh',
    #     'schedule': crontab(minute=0),  # Every hour at minute 0
    #     'options': {
    #         'expires': 3000.0,
    #     }
    # },

    # # Send high-confidence signal notifications every 2 minutes
    # 'send-signal-notifications': {
    #     'task': 'scanner.tasks.celery_tasks.send_signal_notifications',
    #     'schedule': 120.0,  # Every 2 minutes
    #     'options': {
    #         'expires': 110.0,
    #     }
    # },

    # # Cleanup expired signals every 5 minutes
    # 'cleanup-expired-signals': {
    #     'task': 'scanner.tasks.celery_tasks.cleanup_expired_signals',
    #     'schedule': 300.0,  # Every 5 minutes
    # },

    # # System health check every 10 minutes
    # 'system-health-check': {
    #     'task': 'scanner.tasks.celery_tasks.system_health_check',
    #     'schedule': 600.0,  # Every 10 minutes
    # },

    # # Check and auto-close paper trades every 30 seconds
    # 'check-paper-trades': {
    #     'task': 'scanner.tasks.celery_tasks.check_and_close_paper_trades',
    #     'schedule': 30.0,  # Every 30 seconds
    #     'options': {
    #         'expires': 25.0,  # Expire if not executed within 25 seconds
    #     }
    # },

    # # Aggregate strategy performance data every hour
    # 'aggregate-strategy-performance': {
    #     'task': 'signals.aggregate_strategy_performance',
    #     'schedule': crontab(minute=5),  # Every hour at minute 5
    #     'options': {
    #         'expires': 3000.0,
    #     }
    # },

    # # Check for stale cache every 30 minutes
    # 'check-stale-cache': {
    #     'task': 'signals.check_stale_cache',
    #     'schedule': crontab(minute='*/30'),  # Every 30 minutes
    # },

    # # Check trade thresholds for auto-optimization every hour
    # 'check-trade-threshold': {
    #     'task': 'signals.check_trade_threshold',
    #     'schedule': crontab(minute=10),  # Every hour at minute 10
    # },

    # # Scheduled optimization - runs weekly on Sundays at 3 AM
    # 'scheduled-optimization': {
    #     'task': 'signals.scheduled_optimization',
    #     'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3 AM
    # },

    # # Monitor config performance every 6 hours
    # 'monitor-config-performance': {
    #     'task': 'signals.monitor_config_performance',
    #     'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    # },

    # # Cleanup old optimization runs monthly
    # 'cleanup-old-optimization-runs': {
    #     'task': 'signals.cleanup_old_optimization_runs',
    #     'schedule': crontab(hour=2, minute=0, day_of_month=1),  # 1st of month at 2 AM
    # },
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
        # Backtesting tasks
        'scanner.tasks.backtest_tasks.run_backtest_async': {'queue': 'backtesting'},
        'scanner.tasks.backtest_tasks.run_optimization_async': {'queue': 'backtesting'},
        'scanner.tasks.backtest_tasks.generate_recommendations_async': {'queue': 'backtesting'},
        # Walk-Forward Optimization tasks
        'scanner.tasks.walkforward_tasks.run_walkforward_optimization_async': {'queue': 'backtesting'},
        # Monte Carlo Simulation tasks
        'scanner.tasks.montecarlo_tasks.run_montecarlo_simulation_async': {'queue': 'backtesting'},
        # ML-Based Tuning tasks
        'scanner.tasks.mltuning_tasks.run_ml_tuning_async': {'queue': 'backtesting'},
    },
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f'Request: {self.request!r}')
    return 'Celery is working!'
