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
    run_optimization_async,
    generate_recommendations_async,
)

from .walkforward_tasks import (
    run_walkforward_optimization_async,
)

from .montecarlo_tasks import (
    run_montecarlo_simulation_async,
)

from .mltuning_tasks import (
    run_ml_tuning_async,
)

from .multi_timeframe_scanner import (
    scan_multi_timeframe,
    scan_1d_timeframe,
    scan_4h_timeframe,
    scan_1h_timeframe,
    scan_15m_timeframe,
)

from .forex_scanner import (
    scan_forex_signals,
    scan_major_forex_pairs,
    scan_all_forex_pairs,
    scan_forex_scalping,
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
    'run_optimization_async',
    'generate_recommendations_async',
    'run_walkforward_optimization_async',
    'run_montecarlo_simulation_async',
    'run_ml_tuning_async',
    'scan_multi_timeframe',
    'scan_1d_timeframe',
    'scan_4h_timeframe',
    'scan_1h_timeframe',
    'scan_15m_timeframe',
    'scan_forex_signals',
    'scan_major_forex_pairs',
    'scan_all_forex_pairs',
    'scan_forex_scalping',
]
