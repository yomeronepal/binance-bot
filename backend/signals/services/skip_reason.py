"""Reconstruct the live circuit-breaker decision for a paper trade.

The live trading gate halts after a run of consecutive losing trades within
the current Nepal-time (NPT = UTC + 5h45m) day. Paper trading still records
every trade; these helpers tag each one with what that gate *would* have done
so the Bot Performance page can show taken vs skipped trades side by side.
"""
from datetime import timedelta

from django.utils import timezone


NEPAL_OFFSET = timedelta(hours=5, minutes=45)


def npt_day_start_utc(now_utc):
    """Return the UTC instant of the current Nepal-time day's midnight.

    Args:
        now_utc: Timezone-aware UTC datetime for "now".

    Returns:
        A UTC datetime marking 00:00 NPT of the day ``now_utc`` falls in.
    """
    npt_now = now_utc + NEPAL_OFFSET
    npt_midnight = npt_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return npt_midnight - NEPAL_OFFSET


def consecutive_losses(pnls):
    """Count net-negative closes since the last net-positive close.

    Args:
        pnls: Iterable of profit_loss values in exit-time order.

    Returns:
        Length of the trailing run of non-positive closes.
    """
    streak = 0
    for pnl in pnls:
        streak = 0 if (pnl or 0) > 0 else streak + 1
    return streak


def breaker_skip_reason(model, base_filter, threshold=2):
    """Return 'breaker' if the loss-streak gate would skip a new trade now.

    Looks at the engine's closed system paper trades within the current NPT
    day and counts consecutive net-negative closes since the last net-positive
    one. Returns 'breaker' when that streak is at or above ``threshold``,
    otherwise '' (the trade would be taken).

    Args:
        model: PaperTrade or DayTradePaperTrade class.
        base_filter: Filter kwargs identifying the engine's system trades
            (e.g. ``{'user__isnull': True}``).
        threshold: Consecutive losses that trip the breaker.

    Returns:
        'breaker' or ''.
    """
    day_start = npt_day_start_utc(timezone.now())
    pnls = (
        model.objects
        .filter(exit_time__gte=day_start, status__startswith='CLOSED', **base_filter)
        .order_by('exit_time')
        .values_list('profit_loss', flat=True)
    )
    return 'breaker' if consecutive_losses(pnls) >= threshold else ''
