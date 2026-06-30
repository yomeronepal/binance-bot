"""Signals Celery tasks package.

Importing the submodules here registers their @shared_task functions so
Celery's autodiscover_tasks() picks them up via the default ``tasks``
related name.
"""
from . import (
    balance_rebalance,
    daytrade_session,
    golden_window,
    optimization,
    strategy_performance,
    top_performers,
)
