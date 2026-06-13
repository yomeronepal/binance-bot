"""
Celery task: monthly rebalance of per-trade size from live Binance
futures balance.

Scheduled on the 1st of each month at 02:30 UTC (ahead of the other
monthly tasks at 03:00 / 03:30).
"""
import logging

from celery import shared_task

from ..services.balance_rebalancer import rebalance_from_futures_balance

logger = logging.getLogger(__name__)


@shared_task(
    name='signals.monthly_balance_rebalance',
    bind=True,
    max_retries=0,
)
def monthly_balance_rebalance(self):
    """
    Pull the current futures USDT balance and reset
    FuturesTradingSettings.trade_amount = balance / 3 and
    max_concurrent_trades = 2.

    Logs the summary; returns it for inspection via Celery result
    backend.
    """
    summary = rebalance_from_futures_balance()
    if summary['applied']:
        logger.info("monthly balance rebalance applied: %s", summary)
    else:
        logger.warning("monthly balance rebalance did not apply: %s", summary)
    return summary
