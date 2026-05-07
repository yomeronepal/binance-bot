"""
Sync the ``Symbol`` table with the live Binance USD-M Futures universe.

Idempotent. Safe to run on every deploy and on a daily Celery schedule.

Source of truth: ``GET /fapi/v1/exchangeInfo`` filtered to USDT +
TRADING + PERPETUAL. Mirrors what
``scanner.tasks.multi_timeframe_scanner`` actually scans, so the
``Symbol`` table can never silently lag behind the scanner.

The previous implementation used ``BinanceClient`` (spot
``/api/v3/exchangeInfo``) which silently dropped every futures-only
perpetual (LAB, RIVER, BLUAI, 1000PEPEUSDT, …). Those pairs would get
scanned by the scanner but never get a ``Symbol`` row until they
fired a signal.

Usage:

    python manage.py fetch_all_symbols
    python manage.py fetch_all_symbols --deactivate-stale
    python manage.py fetch_all_symbols --dry-run
"""
from __future__ import annotations

import asyncio

from django.core.management.base import BaseCommand
from django.db import transaction

from scanner.services.binance_futures_client import BinanceFuturesClient
from signals.models import Symbol


class Command(BaseCommand):
    help = (
        "Upsert every Binance USD-M USDT perpetual into the Symbol table. "
        "Idempotent; safe to run on deploy."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--deactivate-stale', action='store_true',
            help=(
                "Mark Symbol rows as active=False when they're no longer in "
                "the live Binance futures universe (delisted, halted, or "
                "switched to delivery). Default: leave stale rows alone."
            ),
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Print what would change without writing to the DB.",
        )

    def handle(self, *args, **opts):
        deactivate_stale = bool(opts['deactivate_stale'])
        dry_run = bool(opts['dry_run'])

        self.stdout.write("Fetching live Binance USD-M futures universe...")
        live_universe = self._fetch_live_universe()
        self.stdout.write(self.style.SUCCESS(
            f"  fetched {len(live_universe)} USDT perpetuals"
        ))

        existing = self._load_existing_rows()
        plan = self._build_sync_plan(live_universe, existing, deactivate_stale)

        self._print_plan_summary(plan, dry_run)

        if dry_run:
            return

        self._apply_plan(plan)

        total = Symbol.objects.count()
        active = Symbol.objects.filter(active=True).count()
        self.stdout.write(self.style.SUCCESS(
            f"\nSymbol table now: {total} total, {active} active"
        ))

    def _fetch_live_universe(self) -> set[str]:
        """Hit Binance for the canonical USDT perpetual list."""
        async def _go():
            async with BinanceFuturesClient() as client:
                return await client.get_usdt_futures_pairs()

        return set(asyncio.run(_go()))

    def _load_existing_rows(self) -> dict[str, bool]:
        """Map ``symbol -> active`` for every existing Symbol row."""
        return dict(
            Symbol.objects.values_list('symbol', 'active')
        )

    def _build_sync_plan(
        self,
        live: set[str],
        existing: dict[str, bool],
        deactivate_stale: bool,
    ) -> dict:
        """Diff the live universe against the DB. Returns a dict of work."""
        existing_symbols = set(existing.keys())

        to_create = sorted(live - existing_symbols)
        to_reactivate = sorted(
            s for s in live & existing_symbols if existing[s] is False
        )
        stale = sorted(existing_symbols - live)
        to_deactivate = (
            sorted(s for s in stale if existing[s] is True)
            if deactivate_stale else []
        )

        return {
            'to_create': to_create,
            'to_reactivate': to_reactivate,
            'to_deactivate': to_deactivate,
            'unchanged': sorted(
                s for s in live & existing_symbols if existing[s] is True
            ),
            'stale_ignored': sorted(stale) if not deactivate_stale else [],
        }

    def _print_plan_summary(self, plan: dict, dry_run: bool) -> None:
        prefix = "[dry-run] would " if dry_run else ""
        self.stdout.write(
            f"\n{prefix}create:      {len(plan['to_create'])}"
        )
        self.stdout.write(
            f"{prefix}reactivate:  {len(plan['to_reactivate'])}"
        )
        self.stdout.write(
            f"{prefix}deactivate:  {len(plan['to_deactivate'])}"
        )
        self.stdout.write(
            f"unchanged:    {len(plan['unchanged'])}"
        )
        if plan['stale_ignored']:
            self.stdout.write(
                f"stale (kept active, pass --deactivate-stale to flip): "
                f"{len(plan['stale_ignored'])}"
            )

        if plan['to_create'][:10]:
            preview = ', '.join(plan['to_create'][:10])
            more = '' if len(plan['to_create']) <= 10 else (
                f" (+ {len(plan['to_create']) - 10} more)"
            )
            self.stdout.write(f"  new sample: {preview}{more}")

    @transaction.atomic
    def _apply_plan(self, plan: dict) -> None:
        if plan['to_create']:
            Symbol.objects.bulk_create(
                [
                    Symbol(symbol=s, exchange='BINANCE', active=True)
                    for s in plan['to_create']
                ],
                ignore_conflicts=True,
                batch_size=500,
            )

        if plan['to_reactivate']:
            Symbol.objects.filter(symbol__in=plan['to_reactivate']).update(
                active=True,
            )

        if plan['to_deactivate']:
            Symbol.objects.filter(symbol__in=plan['to_deactivate']).update(
                active=False,
            )
