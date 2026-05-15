"""
Backfill ``asset_class`` on existing Symbol, Signal, and PaperTrade rows.

Fetches a fresh ``/fapi/v1/exchangeInfo`` snapshot to learn each
symbol's ``contractType`` (most reliable signal for the CRYPTO vs
TRADIFI lane). Anything not on Binance Futures is classified from the
symbol string alone — the classifier's curated ticker set still
catches commodities like ``XAU``/``XAG``/``GLD``/``SLV`` and falls
back to CRYPTO for everything else.

Idempotent: safe to re-run after every new TRADIFI listing.

Usage:
    python manage.py backfill_asset_class
    python manage.py backfill_asset_class --dry-run
"""
import asyncio
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from signals.models import Symbol, Signal, PaperTrade
from scanner.services.asset_classifier import classify_symbol


async def _fetch_contract_types() -> dict[str, str]:
    """
    Return {symbol_str: contract_type} from Binance Futures exchangeInfo.

    Returns an empty dict if the call fails so the rest of the backfill
    still runs from the curated ticker set.
    """
    try:
        from scanner.services.binance_futures_client import BinanceFuturesClient
        async with BinanceFuturesClient() as client:
            info = await client.get_exchange_info()
            return {
                row['symbol']: row.get('contractType')
                for row in info.get('symbols', [])
            }
    except Exception as exc:
        return {'__error__': str(exc)}


def _reclassify_symbols(contract_map: dict[str, str], dry_run: bool) -> Counter:
    """
    Walk every Symbol row, recompute asset_class, update if changed.
    """
    counter = Counter()
    qs = Symbol.objects.all().only('id', 'symbol', 'asset_class')
    to_update = []

    for sym in qs:
        new_class = classify_symbol(sym.symbol, contract_map.get(sym.symbol))
        counter[new_class] += 1
        if sym.asset_class != new_class:
            sym.asset_class = new_class
            to_update.append(sym)

    if to_update and not dry_run:
        Symbol.objects.bulk_update(to_update, ['asset_class'], batch_size=500)

    counter['_updated'] = len(to_update)
    return counter


def _propagate_to_signals(dry_run: bool) -> int:
    """
    Sync every Signal's asset_class to its parent Symbol's value.
    Single UPDATE per class — three queries total.
    """
    total = 0
    for cls in ('CRYPTO', 'STOCK', 'COMMODITY'):
        qs = Signal.objects.filter(symbol__asset_class=cls).exclude(asset_class=cls)
        count = qs.count()
        total += count
        if count and not dry_run:
            qs.update(asset_class=cls)
    return total


def _propagate_to_paper_trades(dry_run: bool) -> tuple[int, int]:
    """
    Set PaperTrade.asset_class.

    Two passes:
    1. Trades with a linked Signal — inherit from Signal.asset_class.
    2. Trades without a Signal (manual / replay) — classify from the
       symbol string. No contract_type available here.
    """
    inherited = 0
    for cls in ('CRYPTO', 'STOCK', 'COMMODITY'):
        qs = (
            PaperTrade.objects.filter(signal__asset_class=cls)
            .exclude(asset_class=cls)
        )
        count = qs.count()
        inherited += count
        if count and not dry_run:
            qs.update(asset_class=cls)

    classified = 0
    orphan_qs = PaperTrade.objects.filter(signal__isnull=True).only(
        'id', 'symbol', 'asset_class'
    )
    to_update = []
    for trade in orphan_qs:
        new_class = classify_symbol(trade.symbol)
        if trade.asset_class != new_class:
            trade.asset_class = new_class
            to_update.append(trade)

    classified = len(to_update)
    if to_update and not dry_run:
        PaperTrade.objects.bulk_update(to_update, ['asset_class'], batch_size=500)

    return inherited, classified


class Command(BaseCommand):
    help = 'Backfill asset_class on Symbol, Signal, and PaperTrade rows.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Compute counts but do not write any rows.',
        )

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no writes will happen.'))

        self.stdout.write('Fetching Binance Futures exchangeInfo for contract types…')
        contract_map = asyncio.run(_fetch_contract_types())
        if '__error__' in contract_map:
            self.stdout.write(
                self.style.WARNING(
                    f'  exchangeInfo unavailable ({contract_map["__error__"]}); '
                    'falling back to ticker-set classification only.'
                )
            )
            contract_map = {}
        else:
            self.stdout.write(
                f'  Got contract types for {len(contract_map)} symbols.'
            )

        with transaction.atomic():
            sym_counter = _reclassify_symbols(contract_map, dry_run)
            sig_updated = _propagate_to_signals(dry_run)
            trade_inherited, trade_classified = _propagate_to_paper_trades(dry_run)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS('Done.'))
        self.stdout.write(
            f'  Symbols: CRYPTO={sym_counter["CRYPTO"]} '
            f'STOCK={sym_counter["STOCK"]} '
            f'COMMODITY={sym_counter["COMMODITY"]} '
            f'(updated {sym_counter["_updated"]})'
        )
        self.stdout.write(f'  Signals updated: {sig_updated}')
        self.stdout.write(
            f'  PaperTrades: {trade_inherited} inherited from signal, '
            f'{trade_classified} classified from symbol string'
        )
