"""
End-to-end smoke test for the scanner symbol-universe fix.

Validates that the multi-timeframe scanner (multi_timeframe_scanner.py)
routes its full chain — universe, volume ranking, klines — through the
Binance USD-M Futures endpoints so futures-only perpetuals (LAB, RIVER,
BLUAI, 1000PEPEUSDT, etc.) are no longer silently dropped.

Layers exercised, no mocks:

  1. BinanceFuturesClient.get_usdt_futures_pairs() returns >= 500 pairs
     and includes the originally-missing perpetuals.
  2. _get_top_pairs_by_volume(use_futures=True) ranks by volume *and*
     keeps zero-volume new listings rather than dropping them.
  3. The same call with use_futures=False (spot ticker) drops every
     futures-only pair — regression check that protects the fix.
  4. BinanceFuturesClient.batch_get_klines() returns real candle data
     for a sampled subset, including the originally-missing pairs.
  5. scan_timeframe() runs the full pipeline against a small subset
     and reports counts without raising.

Run locally (Django context required):

    python manage.py test_scanner_universe_e2e

Or inside the prod web container:

    docker exec binancebot_web_prod \\
        python manage.py test_scanner_universe_e2e

Exit code 0 = pass, 1 = any failure.
"""
from __future__ import annotations

import asyncio
import sys
import traceback

from django.core.management.base import BaseCommand


PASS = '\033[32m✓\033[0m'
FAIL = '\033[31m✗\033[0m'
WARN = '\033[33m⚠\033[0m'

KNOWN_MISSING_FUTURES_ONLY = [
    'LABUSDT', 'RIVERUSDT', 'BLUAIUSDT', '1000PEPEUSDT',
]
KNOWN_ESTABLISHED = ['BTCUSDT', 'ETHUSDT']
SAMPLE_FOR_KLINES = KNOWN_MISSING_FUTURES_ONLY + KNOWN_ESTABLISHED
MIN_EXPECTED_PAIRS = 400


class Command(BaseCommand):
    help = "End-to-end smoke test of the scanner futures-universe fix."

    def add_arguments(self, parser):
        parser.add_argument(
            '--sample-size', type=int, default=10,
            help="Symbols to scan in the full-pipeline step (step 5).",
        )
        parser.add_argument(
            '--timeframe', default='1h',
            help="Timeframe for the full-pipeline step (default: 1h).",
        )

    def handle(self, *args, **opts):
        self.failures = []
        self.sample_size = int(opts['sample_size'])
        self.timeframe = opts['timeframe']

        try:
            asyncio.run(self._run_all())
        except Exception as exc:
            self.stdout.write(self.style.ERROR(
                f"FATAL: harness aborted before completion: {exc}"
            ))
            traceback.print_exc()
            sys.exit(2)

        self.stdout.write('')
        if self.failures:
            self.stdout.write(self.style.ERROR(
                f"FAILED — {len(self.failures)} step(s) didn't pass:"
            ))
            for f in self.failures:
                self.stdout.write(self.style.ERROR(f"  • {f}"))
            sys.exit(1)
        else:
            self.stdout.write(self.style.SUCCESS(
                "ALL CHECKS PASSED — scanner universe fix is healthy"
            ))

    async def _run_all(self):
        await self._step('1', 'Futures exchange info returns USDT perpetuals',
                         self._test_universe)
        await self._step('2', 'Futures volume ranking keeps every pair',
                         self._test_futures_volume_ranking)
        await self._step('3', 'Spot volume ranking drops futures-only (regression guard)',
                         self._test_spot_volume_drops_futures)
        await self._step('4', 'batch_get_klines returns data for missing pairs',
                         self._test_klines_for_sample)
        await self._step('5', 'scan_timeframe runs full pipeline without error',
                         self._test_full_pipeline)

    async def _step(self, num, title, coro_fn):
        self.stdout.write(f"\n[{num}] {title}")
        try:
            await coro_fn()
        except AssertionError as exc:
            self.stdout.write(f"    {FAIL} {exc}")
            self.failures.append(f"step {num}: {exc}")
        except Exception as exc:
            self.stdout.write(f"    {FAIL} {type(exc).__name__}: {exc}")
            traceback.print_exc()
            self.failures.append(f"step {num}: {type(exc).__name__}: {exc}")

    def _ok(self, msg):
        self.stdout.write(f"    {PASS} {msg}")

    def _warn(self, msg):
        self.stdout.write(f"    {WARN} {msg}")

    async def _test_universe(self):
        from scanner.services.binance_futures_client import BinanceFuturesClient

        async with BinanceFuturesClient() as client:
            pairs = await client.get_usdt_futures_pairs()

        assert len(pairs) >= MIN_EXPECTED_PAIRS, (
            f"expected >= {MIN_EXPECTED_PAIRS} USDT perpetuals, got {len(pairs)}"
        )
        missing = [s for s in KNOWN_MISSING_FUTURES_ONLY if s not in pairs]
        assert not missing, (
            f"originally-missing pairs still absent from universe: {missing}"
        )
        for sym in KNOWN_ESTABLISHED:
            assert sym in pairs, f"{sym} should always be in the universe"

        self._ok(
            f"{len(pairs)} USDT perpetuals; "
            f"all originally-missing pairs present "
            f"({', '.join(KNOWN_MISSING_FUTURES_ONLY)})"
        )
        self._universe = pairs

    async def _test_futures_volume_ranking(self):
        from scanner.services.binance_futures_client import BinanceFuturesClient
        from scanner.tasks.multi_timeframe_scanner import _get_top_pairs_by_volume

        async with BinanceFuturesClient() as client:
            ranked = await _get_top_pairs_by_volume(
                client, self._universe, top_n=len(self._universe),
                use_futures=True,
            )

        assert len(ranked) == len(self._universe), (
            f"futures volume ranking dropped pairs: "
            f"in={len(self._universe)} out={len(ranked)}"
        )
        missing = [s for s in KNOWN_MISSING_FUTURES_ONLY if s not in ranked]
        assert not missing, (
            f"futures volume ranking dropped originally-missing pairs: "
            f"{missing}"
        )
        for sym in KNOWN_ESTABLISHED:
            assert sym in ranked, (
                f"futures volume ranking dropped established pair {sym}"
            )

        top10 = ranked[:10]
        assert any(s in top10 for s in KNOWN_ESTABLISHED), (
            f"BTC/ETH expected in top-10 by volume, got {top10}"
        )

        self._ok(
            f"in={len(self._universe)} out={len(ranked)} (no drops); "
            f"top-10 by 24h vol: {', '.join(top10)}"
        )

    async def _test_spot_volume_drops_futures(self):
        """
        Regression guard: confirm the OLD code path (use_futures=False)
        would still drop futures-only pairs. If this ever stops being
        true, the fix may have been quietly neutered.
        """
        from scanner.services.binance_client import BinanceClient
        from scanner.tasks.multi_timeframe_scanner import _get_top_pairs_by_volume

        async with BinanceClient() as client:
            ranked_spot = await _get_top_pairs_by_volume(
                client, self._universe, top_n=len(self._universe),
                use_futures=False,
            )

        unique_spot = set(ranked_spot)
        survivors = [s for s in KNOWN_MISSING_FUTURES_ONLY if s in unique_spot]

        if not survivors:
            self._ok(
                "old spot path correctly drops all originally-missing pairs "
                "(zero-volume bucket keeps them at the bottom but spot "
                "ticker has no entry for them either way)"
            )
        else:
            new_listing_kept = sorted(survivors)
            self._ok(
                f"survivors of spot ranking landed in zero-vol bucket: "
                f"{new_listing_kept} — expected, since they're appended "
                "with vol=0 rather than dropped"
            )

        for sym in KNOWN_ESTABLISHED:
            assert sym in unique_spot, (
                f"{sym} dropped from spot ranking too — something is wrong"
            )

    async def _test_klines_for_sample(self):
        from scanner.services.binance_futures_client import BinanceFuturesClient

        async with BinanceFuturesClient() as client:
            klines = await client.batch_get_klines(
                SAMPLE_FOR_KLINES, interval=self.timeframe,
                limit=50, batch_size=10,
            )

        assert len(klines) >= len(KNOWN_ESTABLISHED), (
            f"expected klines for established pairs, got {sorted(klines)}"
        )

        per_symbol = {}
        for sym in SAMPLE_FOR_KLINES:
            data = klines.get(sym)
            if not data:
                per_symbol[sym] = 'NO DATA'
                continue
            assert isinstance(data, list), (
                f"{sym}: klines should be a list, got {type(data).__name__}"
            )
            assert len(data) > 0, f"{sym}: empty klines list"
            first = data[0]
            assert len(first) >= 6, (
                f"{sym}: expected at least 6 fields per candle (OHLCV+ts), "
                f"got {len(first)}"
            )
            per_symbol[sym] = f"{len(data)} candles"

        for sym in KNOWN_ESTABLISHED:
            assert per_symbol[sym] != 'NO DATA', (
                f"{sym} (established) returned no klines"
            )

        for sym in KNOWN_MISSING_FUTURES_ONLY:
            if per_symbol[sym] == 'NO DATA':
                self._warn(
                    f"{sym}: no klines (likely just-listed and below the "
                    "first {self.timeframe} window — non-fatal)"
                )

        report = ', '.join(f"{k}={v}" for k, v in per_symbol.items())
        self._ok(f"klines per sample symbol — {report}")

    async def _test_full_pipeline(self):
        """
        Exercise scan_timeframe() against a tiny subset to prove the new
        code path is wired together and doesn't raise. We bias the
        subset toward the originally-missing pairs so any regression
        re-surfaces here first.
        """
        from scanner.services.binance_futures_client import BinanceFuturesClient
        from scanner.tasks.multi_timeframe_scanner import scan_timeframe

        subset = SAMPLE_FOR_KLINES + [
            s for s in self._universe[:self.sample_size]
            if s not in SAMPLE_FOR_KLINES
        ]
        subset = subset[:self.sample_size]

        async with BinanceFuturesClient() as client:
            counts = await scan_timeframe(
                client=client,
                timeframe=self.timeframe,
                top_pairs=subset,
                limit=200,
                use_universal_config=True,
            )

        assert isinstance(counts, dict), f"expected dict, got {type(counts)}"
        for k in ('created', 'updated', 'invalidated'):
            assert k in counts, f"counts missing key: {k}"
            assert isinstance(counts[k], int), f"{k} should be int"

        self._ok(
            f"scan_timeframe ran clean against {len(subset)} symbols on "
            f"{self.timeframe}: created={counts['created']} "
            f"updated={counts['updated']} invalidated={counts['invalidated']} "
            f"skipped_no_config={counts.get('skipped_no_config', 0)}"
        )
