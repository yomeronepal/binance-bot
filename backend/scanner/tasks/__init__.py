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
    check_and_close_paper_trades,
)

from .backtest_tasks import (
    run_backtest_async,
)

from .multi_timeframe_scanner import (
    scan_multi_timeframe,
    scan_1d_timeframe,
    scan_4h_timeframe,
    scan_1h_timeframe,
    scan_15m_timeframe,
)

from .futures_multi_timeframe_scanner import (
    scan_futures_1d,
    scan_futures_4h,
    scan_futures_1h,
    scan_futures_15m,
    scan_futures_5m,
)

__all__ = [
    'scan_binance_market',
    'scan_futures_market',
    'full_data_refresh',
    'send_signal_notifications',
    'cleanup_expired_signals',
    'system_health_check',
    'test_celery_task',
    'check_and_close_paper_trades',
    'run_backtest_async',
    'scan_multi_timeframe',
    'scan_1d_timeframe',
    'scan_4h_timeframe',
    'scan_1h_timeframe',
    'scan_15m_timeframe',
    'scan_futures_1d',
    'scan_futures_4h',
    'scan_futures_1h',
    'scan_futures_15m',
    'scan_futures_5m',
]

