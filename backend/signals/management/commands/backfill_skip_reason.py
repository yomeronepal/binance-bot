"""Reconstruct ``skip_reason`` on historical system paper trades.

For each engine (V1 PaperTrade and day-trade DayTradePaperTrade), closed
system trades are grouped by Nepal-time (NPT = UTC + 5h45m) day and walked in
exit-time order. The same 2-consecutive-loss circuit breaker used live is
replayed: a trade is tagged 'breaker' when the running streak of net-negative
closes before it has reached the threshold, otherwise ''. Reports taken vs
skipped counts per engine.
"""
from django.core.management.base import BaseCommand

from signals.models import PaperTrade
from signals.models.daytrade import DayTradePaperTrade
from signals.services.skip_reason import NEPAL_OFFSET


def _npt_day_key(exit_time):
    """NPT calendar date a UTC exit_time falls in."""
    return (exit_time + NEPAL_OFFSET).date()


def _reconstruct(trades, threshold):
    """Assign skip_reason to each trade in exit-time order within its NPT day.

    Args:
        trades: Closed trades ordered by exit_time.
        threshold: Consecutive losses that trip the breaker.

    Returns:
        (changed, taken, skipped) tuple; ``changed`` trades have their
        ``skip_reason`` set in memory (not saved).
    """
    streaks = {}
    changed = []
    taken = skipped = 0
    for trade in trades:
        if trade.exit_time is None:
            continue
        day = _npt_day_key(trade.exit_time)
        streak = streaks.get(day, 0)
        reason = 'breaker' if streak >= threshold else ''
        if trade.skip_reason != reason:
            trade.skip_reason = reason
            changed.append(trade)
        if reason:
            skipped += 1
        else:
            taken += 1
        streaks[day] = 0 if (trade.profit_loss or 0) > 0 else streak + 1
    return changed, taken, skipped


class Command(BaseCommand):
    help = "Reconstruct skip_reason on historical system paper trades"

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold', type=int, default=2,
            help="Consecutive losses that trip the breaker (default 2).",
        )

    def handle(self, *args, **options):
        threshold = options['threshold']
        for label, model in (('V1', PaperTrade), ('DayTrade', DayTradePaperTrade)):
            self._backfill_engine(label, model, threshold)

    def _backfill_engine(self, label, model, threshold):
        """Backfill one engine's closed system trades and print the tally."""
        trades = list(
            model.objects
            .filter(user__isnull=True, status__startswith='CLOSED', exit_time__isnull=False)
            .order_by('exit_time')
        )
        changed, taken, skipped = _reconstruct(trades, threshold)
        model.objects.bulk_update(changed, ['skip_reason'], batch_size=500)
        self.stdout.write(
            f"[{label}] closed={len(trades)} taken={taken} skipped={skipped} "
            f"updated={len(changed)}"
        )
