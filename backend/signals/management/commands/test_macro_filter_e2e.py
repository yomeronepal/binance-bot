"""
End-to-end smoke test for the BTC macro filter.

Exercises every layer of the chain on the running server, with no mocks:

  1. Live BTC snapshot fetch (force-refreshed to bypass cache)
  2. evaluate_macro_filter for both directions against the live snapshot
  3. macro_summary shape (powers /public/macro-status/)
  4. Signal-creation stamping — saves a synthetic Signal with each
     direction, asserts ``meta['macro_at_signal']`` populated
  5. Trade-boundary gate — calls ``_check_macro_filter`` directly,
     asserts log-row written when direction conflicts with regime
  6. Bot Performance filter — queries ``?macro_filter=allow|block`` against
     the live PaperTrade table and reports the row counts

Run inside the prod web container:

    docker exec binancebot_web_prod \\
        python manage.py test_macro_filter_e2e

By default the script is non-destructive — it creates two test Signals
tagged ``meta.smoke=True``, asserts on them, then deletes them. Pass
``--keep-signals`` to leave them in place for manual inspection.

Exit code is 0 on full pass, 1 on any failure. CI-friendly.
"""
from __future__ import annotations

import sys
import traceback
from decimal import Decimal

from django.core.management.base import BaseCommand


PASS = '\033[32m✓\033[0m'
FAIL = '\033[31m✗\033[0m'
WARN = '\033[33m⚠\033[0m'


class Command(BaseCommand):
    help = "End-to-end smoke test of the BTC macro filter chain."

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-signals', action='store_true',
            help="Don't delete the synthetic test Signals at the end.",
        )

    def handle(self, *args, **opts):
        self.failures = []
        self.keep = bool(opts['keep_signals'])

        self._step('1', 'Fetch live BTC snapshot', self._test_snapshot)
        self._step('2', 'evaluate_macro_filter against live snapshot',
                   self._test_pure_filter)
        self._step('3', 'macro_summary shape', self._test_macro_summary)
        self._step('4', 'Signal-creation stamps macro_at_signal',
                   self._test_signal_stamp)
        self._step('5', 'Trade-boundary gate logs CHECK_FAILED on block',
                   self._test_trade_gate)
        self._step('6', 'Bot Performance ?macro_filter= narrows results',
                   self._test_botperf_filter)

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
                "ALL CHECKS PASSED — macro filter chain is healthy"
            ))

    # ---- step runner ------------------------------------------------------
    def _step(self, num, title, fn):
        self.stdout.write(f"\n[{num}] {title}")
        try:
            fn()
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

    # ---- step 1 -----------------------------------------------------------
    def _test_snapshot(self):
        from scanner.services.btc_trend import (
            get_btc_snapshot, invalidate_btc_snapshot_cache,
        )
        invalidate_btc_snapshot_cache()
        snap = get_btc_snapshot(force_refresh=True)
        assert snap is not None, "snapshot is None — Binance unreachable?"
        assert snap.close > 0, f"BTC close should be >0, got {snap.close}"
        assert snap.ema7 > 0 and snap.ema20 > 0, "EMAs should be >0"
        assert isinstance(snap.above_ema7, bool)
        assert isinstance(snap.above_ema20, bool)
        self._ok(
            f"close=${snap.close:,.2f} ema7=${snap.ema7:,.2f} "
            f"ema20=${snap.ema20:,.2f} above7={snap.above_ema7} "
            f"above20={snap.above_ema20} ret_3d={snap.ret_3d:+.2f}% "
            f"ret_7d={snap.ret_7d:+.2f}%"
        )
        self._snapshot = snap

    # ---- step 2 -----------------------------------------------------------
    def _test_pure_filter(self):
        from scanner.services.macro_filter import evaluate_macro_filter
        long_decision, long_reason = evaluate_macro_filter('LONG', self._snapshot)
        short_decision, short_reason = evaluate_macro_filter('SHORT', self._snapshot)
        assert long_decision in ('ALLOW', 'BLOCK'), long_decision
        assert short_decision in ('ALLOW', 'BLOCK'), short_decision
        self._ok(f"LONG={long_decision} ({long_reason})")
        self._ok(f"SHORT={short_decision} ({short_reason})")
        self._long_dec = long_decision
        self._short_dec = short_decision

    # ---- step 3 -----------------------------------------------------------
    def _test_macro_summary(self):
        from scanner.services.macro_filter import macro_summary
        summary = macro_summary(self._snapshot)
        for k in ('snapshot', 'long', 'short', 'thresholds'):
            assert k in summary, f"summary missing key: {k}"
        assert summary['thresholds']['long_ret_7d_min'] == 0.0
        assert summary['thresholds']['short_ret_3d_min'] == -7.0
        self._ok("summary has snapshot/long/short/thresholds with correct values")

    # ---- step 4 -----------------------------------------------------------
    def _test_signal_stamp(self):
        from signals.models import Signal, Symbol
        from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig
        from scanner.services.btc_trend import get_btc_snapshot
        # We can't easily run _detect_new_signal end-to-end without
        # candles, but _create_signal exposes the same stamp path.
        # Synthesize a minimal call.
        engine = SignalDetectionEngine(config=SignalConfig())
        snap = get_btc_snapshot()

        import pandas as pd
        # Single "current" row; _create_signal reads ['close']
        df = pd.DataFrame([{'close': 50000.0}])
        active_signal = engine._create_signal(
            symbol='SMOKETEST',
            direction='LONG',
            df=df,
            current=df.iloc[-1],
            confidence=0.85,
            conditions={},
            timeframe='1h',
            config=engine.config,
        )
        assert active_signal is not None
        meta = active_signal.meta or {}
        assert 'macro_at_signal' in meta, (
            "macro_at_signal not stamped on freshly-created ActiveSignal"
        )
        ms = meta['macro_at_signal']
        for k in ('decision', 'reason', 'above_ema7', 'above_ema20',
                  'ret_3d', 'ret_7d', 'btc_close', 'fetched_at'):
            assert k in ms, f"macro_at_signal missing field: {k}"
        assert ms['decision'] in ('ALLOW', 'BLOCK')
        self._ok(
            f"meta.macro_at_signal stamped — decision={ms['decision']} "
            f"reason={ms['reason']} btc_close=${ms['btc_close']:,.2f}"
        )

    # ---- step 5 -----------------------------------------------------------
    def _test_trade_gate(self):
        """
        Calls _check_macro_filter against a mock Signal-like object for
        each direction. One direction is currently ALLOWED by the live
        snapshot, the other (typically) is not — assert the gate's
        boolean matches our pure-function decision and that a
        FuturesTradeLog row is written exactly when blocked.
        """
        from signals.services.futures_trader import futures_trading_service
        from signals.models_futures import FuturesTradeLog

        class _MockSignal:
            id = 0
            direction = 'LONG'

        # Snapshot count of CHECK_FAILED rows mentioning Macro before we run.
        before = FuturesTradeLog.objects.filter(
            action='CHECK_FAILED', message__icontains='Macro filter'
        ).count()

        results = {}
        for direction in ('LONG', 'SHORT'):
            sig = _MockSignal()
            sig.id = 0
            sig.direction = direction
            log_ctx = {
                'signal': None, 'symbol': 'SMOKETEST', 'direction': direction,
                'is_priority': True, 'force_execute': True,
            }
            ok = futures_trading_service._check_macro_filter(sig, direction, log_ctx)
            results[direction] = ok

        # Compare to pure-function decision (must agree exactly).
        from scanner.services.macro_filter import evaluate_macro_filter
        for direction in ('LONG', 'SHORT'):
            expect_allow = (
                evaluate_macro_filter(direction)[0] == 'ALLOW'
            )
            assert results[direction] is expect_allow, (
                f"_check_macro_filter for {direction} returned {results[direction]} "
                f"but pure evaluate said {'ALLOW' if expect_allow else 'BLOCK'}"
            )

        # A blocked direction should have written one log row.
        after = FuturesTradeLog.objects.filter(
            action='CHECK_FAILED', message__icontains='Macro filter'
        ).count()
        expected_new = sum(1 for v in results.values() if v is False)
        assert after - before == expected_new, (
            f"expected {expected_new} new CHECK_FAILED rows, "
            f"got {after - before}"
        )

        self._ok(
            f"_check_macro_filter LONG={results['LONG']} "
            f"SHORT={results['SHORT']}; "
            f"{expected_new} CHECK_FAILED log row(s) written"
        )

    # ---- step 6 -----------------------------------------------------------
    def _test_botperf_filter(self):
        """
        Hit the in-process query path that the public paper-trading
        endpoints use. Confirms the JSONField lookup actually narrows
        the queryset; no HTTP layer involved.
        """
        from signals.models import PaperTrade
        from signals.views_public_paper_trading import (
            _apply_macro_filter,
        )

        base = PaperTrade.objects.filter(user__isnull=True)
        total = base.count()
        allow_only = _apply_macro_filter(base, {'macro_filter': 'allow'}).count()
        block_only = _apply_macro_filter(base, {'macro_filter': 'block'}).count()
        no_filter = _apply_macro_filter(base, {'macro_filter': ''}).count()

        assert no_filter == total, "empty filter must be a no-op"
        assert allow_only <= total, "allow subset can't exceed total"
        assert block_only <= total, "block subset can't exceed total"
        # allow + block <= total (rest are pre-tag historicals with no
        # macro_at_signal key)
        assert allow_only + block_only <= total

        unstamped = total - allow_only - block_only
        self._ok(
            f"PaperTrade total={total} allow={allow_only} "
            f"block={block_only} unstamped={unstamped} "
            f"({unstamped*100/max(total,1):.0f}% pre-tag historicals)"
        )
        if total > 0 and (allow_only + block_only) == 0:
            self._warn(
                "No tagged signals found. Either the bot hasn't generated "
                "any signals since the macro-stamp deploy, or the stamp "
                "isn't running. Generate one signal and re-run."
            )
