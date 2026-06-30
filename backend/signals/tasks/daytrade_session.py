"""Celery task for the day-trade trading-session optimizer.

Analyzes closed day-trade paper trades and refreshes the DayTradeSession
windows used by the Bot Performance filters. Analytics only.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='signals.optimize_daytrade_sessions', bind=True, max_retries=1)
def optimize_daytrade_sessions(self, min_trades=5, min_win_rate=55.0, min_trades_weekday=3):
    """Analyze day-trade paper trades and refresh the optimized session windows."""
    try:
        from signals.services.daytrade_session_analyzer import run_optimization

        logger.info("Starting day-trade session optimization...")
        result = run_optimization(
            min_trades=min_trades,
            min_win_rate=min_win_rate,
            min_trades_weekday=min_trades_weekday,
        )
        logger.info("Day-trade session optimization: %s", result['status'])
        return result
    except Exception as exc:
        logger.error("Day-trade session optimization failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=300)
