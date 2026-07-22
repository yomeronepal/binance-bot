"""Summarize forward paper performance of the 4h swing engine (net of fees)."""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum, Count

from signals.models.swing import SwingPaperTrade


def _summarize(qs):
    """Return net metrics for a closed-trade queryset."""
    closed = qs.exclude(status='OPEN')
    n = closed.count()
    if not n:
        return None
    wins = closed.filter(profit_loss__gt=0).count()
    net = float(closed.aggregate(s=Sum('profit_loss'))['s'] or 0)
    fees = float(closed.aggregate(s=Sum('fees_paid'))['s'] or 0)
    gp = float(closed.filter(profit_loss__gt=0).aggregate(s=Sum('profit_loss'))['s'] or 0)
    gl = abs(float(closed.filter(profit_loss__lt=0).aggregate(s=Sum('profit_loss'))['s'] or 0))
    return {
        'closed': n,
        'win_rate': round(wins / n * 100, 1),
        'net_pnl': round(net, 2),
        'fees_paid': round(fees, 2),
        'profit_factor': round(gp / gl, 3) if gl else None,
        'expectancy': round(net / n, 3),
    }


class Command(BaseCommand):
    help = "Summarize 4h swing paper performance (net of fees)"

    def handle(self, *args, **options):
        overall = _summarize(SwingPaperTrade.objects.all())
        if overall is None:
            self.stdout.write("No closed swing trades yet.")
        else:
            self.stdout.write("=== OVERALL (net of fees) ===")
            for k, v in overall.items():
                self.stdout.write(f"  {k}: {v}")

        self.stdout.write("=== BY SYMBOL ===")
        rows = (SwingPaperTrade.objects.exclude(status='OPEN')
                .values('symbol')
                .annotate(net=Sum('profit_loss'), n=Count('id'))
                .order_by('net'))
        for r in rows:
            self.stdout.write(f"  {r['symbol']}: {r['n']} trades | net ${round(float(r['net'] or 0), 2)}")

        open_trades = SwingPaperTrade.objects.filter(status='OPEN')
        self.stdout.write(f"=== OPEN POSITIONS: {open_trades.count()} ===")
        for t in open_trades:
            self.stdout.write(f"  {t.direction} {t.symbol} @ {t.entry_price} (SL {t.stop_loss} / TP {t.take_profit})")
