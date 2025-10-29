"""
Scanner Celery tasks module.
Imports all tasks to make them discoverable by Celery.
"""
from .celery_tasks import (
    scan_binance_market,
    scan_futures_market,
    full_data_refresh,
    send_signal_notifications,
    cleanup_expired_signals,
    system_health_check,
    test_celery_task,
)

__all__ = [
    'scan_binance_market',
    'scan_futures_market',
    'full_data_refresh',
    'send_signal_notifications',
    'cleanup_expired_signals',
    'system_health_check',
    'test_celery_task',
]
