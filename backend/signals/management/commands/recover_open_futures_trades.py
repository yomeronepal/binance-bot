"""
Recover futures trades that were wrongly marked CLOSED_MANUAL but are still
open on Binance.

A transient Binance API failure could make the 30s sync see an empty position
list and close every open trade as CLOSED_MANUAL with $0 PnL. This command
re-checks each such trade against the live account and reverts the ones whose
position is still open, so the bot resumes managing them.

Usage:
    python manage.py recover_open_futures_trades              # dry-run (report only)
    python manage.py recover_open_futures_trades --apply      # actually revert
    python manage.py recover_open_futures_trades --symbol NEOUSDT --apply
"""
import asyncio
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from signals.services.futures_trader import BinanceFuturesTrader
from signals.models.futures import FuturesTrade


def _fetch_live_positions():
    """Return a dict of symbol -> live Binance position fields."""
    async def _run():
        trader = BinanceFuturesTrader(use_testnet=False)
        try:
            return await trader.get_open_positions(raise_on_error=True)
        finally:
            await trader.close()

    positions = asyncio.run(_run())
    live = {}
    for pos in positions:
        amount = float(pos.get('positionAmt', 0))
        if amount == 0:
            continue
        symbol = pos.get('symbol')
        live[symbol] = {
            'direction': 'LONG' if amount > 0 else 'SHORT',
            'quantity': abs(amount),
            'entry_price': Decimal(pos.get('entryPrice', '0')),
            'mark_price': Decimal(pos.get('markPrice', '0')),
            'unrealized_pnl': Decimal(pos.get('unRealizedProfit', '0')),
            'liquidation_price': Decimal(pos.get('liquidationPrice', '0')),
            'margin_type': pos.get('marginType', 'isolated'),
        }
    return live


def _candidate_trades(symbol):
    """Bot-opened trades wrongly closed as manual, newest first."""
    queryset = FuturesTrade.objects.filter(
        status='CLOSED_MANUAL', signal__isnull=False
    )
    if symbol:
        queryset = queryset.filter(symbol=symbol.upper())
    return queryset.order_by('-exit_time')


def _revert_trade(trade, live):
    """Restore a trade to OPEN using live Binance position data."""
    margin = trade.position_size_usdt or Decimal('0')
    unrealized = live['unrealized_pnl']
    trade.status = 'OPEN'
    trade.exit_price = None
    trade.exit_time = None
    trade.profit_loss = Decimal('0')
    trade.profit_loss_percentage = Decimal('0')
    trade.mark_price = live['mark_price']
    trade.unrealized_pnl = unrealized
    trade.unrealized_pnl_percentage = (unrealized / margin * 100) if margin else Decimal('0')
    trade.liquidation_price = live['liquidation_price'] if live['liquidation_price'] > 0 else None
    trade.margin_type = live['margin_type'].upper()
    trade.last_sync_time = timezone.now()
    trade.error_message = 'Recovered: was mis-marked CLOSED_MANUAL while still open on Binance'
    trade.save()


class Command(BaseCommand):
    help = 'Revert futures trades wrongly closed as CLOSED_MANUAL that are still open on Binance'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Persist the reversions (default: dry-run)')
        parser.add_argument('--symbol', default=None, help='Limit to a single symbol')

    def handle(self, *args, **options):
        apply_changes = options['apply']
        symbol = options['symbol']

        live = _fetch_live_positions()
        self.stdout.write(f"Live Binance positions: {len(live)} ({', '.join(sorted(live)) or 'none'})")

        candidates = _candidate_trades(symbol)
        self.stdout.write(f"CLOSED_MANUAL bot trades to inspect: {candidates.count()}")

        recovered = self._process_candidates(candidates, live, apply_changes)

        verb = 'Reverted' if apply_changes else 'Would revert'
        self.stdout.write(self.style.SUCCESS(f"{verb} {recovered} trade(s) to OPEN."))
        if not apply_changes and recovered:
            self.stdout.write("Re-run with --apply to persist these changes.")

    def _process_candidates(self, candidates, live, apply_changes):
        """Revert each candidate still open on Binance; return the count."""
        seen = set()
        recovered = 0
        for trade in candidates:
            match = live.get(trade.symbol)
            if not match or match['direction'] != trade.direction:
                continue
            key = (trade.symbol, trade.direction)
            if key in seen:
                self.stdout.write(
                    f"  SKIP trade {trade.id} {trade.symbol} {trade.direction}: "
                    f"another trade already recovered for this live position"
                )
                continue
            seen.add(key)
            self.stdout.write(
                f"  {trade.symbol} {trade.direction} (trade {trade.id}) is still open on Binance "
                f"@ entry {trade.entry_price}"
            )
            if apply_changes:
                _revert_trade(trade, match)
            recovered += 1
        return recovered
