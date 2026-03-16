"""
Celery tasks for Golden Window optimization.
Analyzes paper trade performance and auto-updates trading sessions.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='signals.optimize_golden_windows', bind=True, max_retries=1)
def optimize_golden_windows(self, min_trades=5, min_win_rate=60.0, min_trades_weekday=3):
    """
    Periodic task: Analyze paper trades and update golden windows.
    Runs daily at 3:00 AM UTC (8:45 AM NPT).

    Args:
        min_trades: Minimum trades per hour for GW1
        min_win_rate: Minimum win rate % threshold
        min_trades_weekday: Minimum trades per hour+day for GW2

    Returns:
        Dict with optimization results
    """
    try:
        from signals.services.golden_window_analyzer import run_optimization

        logger.info("Starting Golden Window optimization...")
        result = run_optimization(
            min_trades=min_trades,
            min_win_rate=min_win_rate,
            min_trades_weekday=min_trades_weekday,
        )
        logger.info(f"Golden Window optimization completed: {result['status']}")
        return result

    except Exception as e:
        logger.error(f"Golden Window optimization failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=300)
