"""Backfill trading costs onto historical day-trade paper trades.

Existing closed trades were recorded gross (no fees/slippage). This command
estimates the same round-trip cost the executor now applies, stores it in
``fees_paid`` and re-nets ``profit_loss`` so the dashboard reflects reality.
Idempotent: only touches closed trades whose ``fees_paid`` is still zero.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from scanner.tasks.daytrade_executor import _trade_cost
from signals.models.daytrade import DayTradePaperTrade, DayTradePaperAccount


class Command(BaseCommand):
    help = "Backfill fees_paid + net profit_loss on historical day-trade paper trades"

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help="Persist changes. Without it, runs as a dry-run.",
        )

    def handle(self, *args, **options):
        apply = options['apply']
        qs = DayTradePaperTrade.objects.filter(
            exit_time__isnull=False, fees_paid=0,
        )
        total = qs.count()
        gross_sum = Decimal('0')
        cost_sum = Decimal('0')
        changed = 0

        for trade in qs.iterator():
            if not (trade.exit_price and trade.quantity and trade.entry_price):
                continue
            cost = _trade_cost(trade, trade.exit_price, trade.exit_time)
            gross_sum += trade.realized_pnl or Decimal('0')
            cost_sum += cost
            changed += 1
            if apply:
                trade.fees_paid = cost
                trade.profit_loss = (trade.realized_pnl or Decimal('0')) - cost
                if trade.position_size:
                    trade.profit_loss_percentage = (trade.profit_loss / trade.position_size) * Decimal('100')
                trade.save(update_fields=['fees_paid', 'profit_loss', 'profit_loss_percentage'])

        net_sum = gross_sum - cost_sum
        mode = "APPLIED" if apply else "DRY-RUN"
        self.stdout.write(
            f"[{mode}] candidates={total} adjusted={changed} "
            f"gross={gross_sum:.2f} costs={cost_sum:.2f} net={net_sum:.2f}"
        )

        if apply:
            for account in DayTradePaperAccount.objects.all():
                account.update_metrics()
            self.stdout.write("Recomputed day-trade account metrics.")
