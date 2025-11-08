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
    # TIMEFRAME SCANNING - OPTIMIZED FOR SIGNAL QUALITY
    # ============================================================================

    # Scan 1-day timeframe - ONCE DAILY (swing trading)
    'scan-1d-timeframe': {
        'task': 'scanner.tasks.multi_timeframe_scanner.scan_1d_timeframe',
        'schedule': crontab(minute=5, hour=0),  # 00:05 UTC daily
        'options': {'expires': 3600.0},  # 1 hour expiry
    },

    # Scan 4-hour timeframe - AT 4H CANDLE CLOSES (your profit center)
    'scan-4h-timeframe': {
        'task': 'scanner.tasks.multi_timeframe_scanner.scan_4h_timeframe',
        'schedule': crontab(minute=5, hour='0,4,8,12,16,20'),  # 5 mins after 4h closes
        'options': {'expires': 1800.0},  # 30 minutes expiry
    },

    # Scan 1-hour timeframe - REDUCED FREQUENCY (intraday)
    'scan-1h-timeframe': {
        'task': 'scanner.tasks.multi_timeframe_scanner.scan_1h_timeframe',
        'schedule': crontab(minute=5),  # Only during active hours: 08:05-20:05 UTC
        'options': {'expires': 1800.0},
    },

    # Scan 15-minute timeframe - REDUCED FREQUENCY (scalping)
    'scan-15m-timeframe': {
        'task': 'scanner.tasks.multi_timeframe_scanner.scan_15m_timeframe',
        'schedule': crontab(minute='*/15'),  # Every 15min during active hours only
        'options': {'expires': 900.0},
    },
    # Scan Binance FUTURES market every minute
    'scan-futures-market': {
        'task': 'scanner.tasks.celery_tasks.scan_futures_market',
        'schedule': crontab(minute='*/5'),  # Every 60 seconds
        'options': {
            'expires': 50.0,  # Expire if not executed within 50 seconds
        }
    },

    # ============================================================================
    # SYSTEM MAINTENANCE - OPTIMIZED
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
        'schedule': 300.0,  # Every 30 seconds
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

    # ============================================================================
    # FOREX SCANNING - MULTI-TIMEFRAME
    # ============================================================================

    # Scan Forex + Commodities 1-day timeframe - ONCE DAILY
    'scan-forex-1d-timeframe': {
        'task': 'scanner.tasks.forex_scanner.scan_forex_signals',
        'schedule': crontab(minute=10, hour=0),  # 00:10 UTC daily
        'kwargs': {'timeframes': ['1d'], 'pair_types': ['major', 'commodities']},  # Added commodities
        'options': {'expires': 3600.0},  # 1 hour expiry
    },

    # Scan Forex + Commodities 4-hour timeframe - AT 4H CANDLE CLOSES
    'scan-forex-4h-timeframe': {
        'task': 'scanner.tasks.forex_scanner.scan_forex_signals',
        'schedule': crontab(minute=10, hour='0,4,8,12,16,20'),  # 10 mins after 4h closes
        'kwargs': {'timeframes': ['4h'], 'pair_types': ['major', 'commodities']},  # Added commodities
        'options': {'expires': 1800.0},  # 30 minutes expiry
    },

    # Scan Forex + Commodities 1-hour timeframe - EVERY HOUR
    'scan-forex-1h-timeframe': {
        'task': 'scanner.tasks.forex_scanner.scan_forex_signals',
        'schedule': crontab(minute=10),  # Every hour at :10
        'kwargs': {'timeframes': ['1h'], 'pair_types': ['major', 'commodities']},  # Added commodities
        'options': {'expires': 1800.0},
    },

    # Scan Forex 15-minute timeframe - EVERY 15 MINUTES (Forex only, commodities less liquid on 15m)
    'scan-forex-15m-timeframe': {
        'task': 'scanner.tasks.forex_scanner.scan_forex_signals',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'kwargs': {'timeframes': ['15m'], 'pair_types': ['major']},  # Forex only for scalping
        'options': {'expires': 900.0},
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
        # Forex and Commodity scanning tasks
        'scanner.tasks.forex_scanner.scan_forex_signals': {'queue': 'scanner'},
        'scanner.tasks.forex_scanner.scan_major_forex_pairs': {'queue': 'scanner'},
        'scanner.tasks.forex_scanner.scan_all_forex_pairs': {'queue': 'scanner'},
        'scanner.tasks.forex_scanner.scan_forex_scalping': {'queue': 'scanner'},
        'scanner.tasks.forex_scanner.scan_commodities': {'queue': 'scanner'},
        'scanner.tasks.forex_scanner.scan_forex_and_commodities': {'queue': 'scanner'},
        'scanner.tasks.forex_scanner.scan_all_markets': {'queue': 'scanner'},
    },
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f'Request: {self.request!r}')
    return 'Celery is working!'
