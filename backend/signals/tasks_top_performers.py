"""
Celery task: snapshot top-N performing symbols for the previous calendar
month. Scheduled monthly via Celery Beat (1st of each month at 03:00 UTC).

Idempotent — safe to re-run for the same period; rows are ``update_or_create``
keyed on (symbol, period_start) so the snapshot reflects the current
PaperTrade data each time.
"""
import logging

from celery import shared_task

from .services.top_performers_calculator import (
    compute_and_snapshot,
    previous_month_bounds,
)

logger = logging.getLogger(__name__)


@shared_task(name='signals.compute_monthly_top_performers',
             bind=True, max_retries=0)
def compute_monthly_top_performers(self):
    """
    Snapshot the top 10 performers for the calendar month that just ended.

    Runs on the 1st of each month at 03:00 UTC. Reading from PaperTrade
    closed rows whose ``exit_time`` falls in the previous month.
    """
    period_start, period_end = previous_month_bounds()
    summary = compute_and_snapshot(period_start, period_end, n=10)
    logger.info("monthly top-performers snapshot done: %s", summary)
    return summary
