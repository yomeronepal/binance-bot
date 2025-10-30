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
]
