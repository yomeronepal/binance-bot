"""
Diagnose why futures trades are not executing for priority signals.

Usage:
    python manage.py diagnose_futures
    python manage.py diagnose_futures --symbol ETHUSDT
    python manage.py diagnose_futures --signal-id 123
"""
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from django.core.management.base import BaseCommand

from signals.models import Signal, TradingSession
from signals.models_futures import FuturesTradingSettings, FuturesTrade
from signals.models_blacklist import BlacklistedSymbol

NEPAL_TZ_OFFSET = timedelta(hours=5, minutes=45)


class Command(BaseCommand):
    help = 'Diagnose why futures trades are not executing'

    def add_arguments(self, parser):
        parser.add_argument('--symbol', default=None, help='Check specific symbol')
        parser.add_argument('--signal-id', type=int, default=None, help='Diagnose specific signal')

    def handle(self, *args, **options):
        nepal_now = datetime.now(timezone.utc) + NEPAL_TZ_OFFSET

        self._header("1. TIME & TRADING SESSIONS")
        self._info(f"Nepal Time: {nepal_now.strftime('%Y-%m-%d %H:%M:%S')} NPT")
        self._info(f"Day: {nepal_now.strftime('%A')} (weekday={nepal_now.weekday()})")

        self._check_sessions(nepal_now)
        self._check_settings(options.get('symbol'))
        self._check_recent_signals(options.get('signal_id'))
        self._check_open_positions()
        self._check_fear_greed()
        self._check_code_version()

    def _check_sessions(self, nepal_now):
        sessions = TradingSession.objects.filter(active=True)
        matching = TradingSession.get_matching_session(nepal_now)

        if not sessions.exists():
            self._fail("No active trading sessions in DB!")
            return

        for s in sessions:
            is_match = matching and matching.id == s.id
            days = []
            for attr, name in [('monday', 'Mon'), ('tuesday', 'Tue'), ('wednesday', 'Wed'),
                               ('thursday', 'Thu'), ('friday', 'Fri'), ('saturday', 'Sat'), ('sunday', 'Sun')]:
                if getattr(s, attr, True):
                    days.append(name)

            marker = " ** ACTIVE NOW **" if is_match else ""
            self._info(
                f"  {s.name} ({s.session_type}): "
                f"{s.start_hour:02d}:{s.start_minute:02d}-{s.end_hour:02d}:{s.end_minute:02d} "
                f"[{','.join(days)}]{marker}"
            )

        if matching:
            self._ok(f"Currently in: {matching.name} -> signals get is_priority=True")
        else:
            self._fail("NOT in any session -> signals get is_priority=False -> futures trade BLOCKED")

    def _check_settings(self, symbol=None):
        self._header("2. FUTURES TRADING SETTINGS")

        s = FuturesTradingSettings.get_settings()

        checks = {
            'is_enabled': (s.is_enabled, 'MUST be True'),
            'trade_long': (s.trade_long, 'needed for LONG trades'),
            'trade_short': (s.trade_short, 'needed for SHORT trades'),
            'use_trading_window': (s.use_trading_window, 'if True, window check applies'),
            'fear_greed_enabled': (s.fear_greed_enabled, 'if True, F&G filter applies'),
        }

        for name, (value, note) in checks.items():
            if name == 'is_enabled' and not value:
                self._fail(f"{name} = {value}  <-- THIS BLOCKS ALL TRADES ({note})")
            elif name in ('use_trading_window', 'fear_greed_enabled'):
                self._info(f"{name} = {value}  ({note})")
            else:
                self._ok(f"{name} = {value}")

        self._info(f"leverage = {s.leverage}x")
        self._info(f"trade_amount = ${s.trade_amount}")
        self._info(f"min_signal_confidence = {s.min_signal_confidence}")
        self._info(f"max_concurrent_trades = {s.max_concurrent_trades}")
        self._info(f"allowed_symbols = {s.allowed_symbols or 'ALL (no filter)'}")
        self._info(f"trade_on_golden_window_2 = {s.trade_on_golden_window_2}")

        if s.fear_greed_enabled:
            self._info(f"fear_greed_short_threshold = {s.fear_greed_short_threshold}")
            self._info(f"fear_greed_long_threshold = {s.fear_greed_long_threshold}")

        open_count = FuturesTrade.objects.filter(status='OPEN').count()
        if open_count >= s.max_concurrent_trades:
            self._fail(f"Open trades: {open_count}/{s.max_concurrent_trades} -- MAX REACHED, blocks new trades")
        else:
            self._ok(f"Open trades: {open_count}/{s.max_concurrent_trades}")

        if symbol:
            can, reason = s.can_trade(symbol, 'LONG', Decimal('0.75'))
            if can:
                self._ok(f"can_trade({symbol}, LONG, 0.75) = ALLOWED")
            else:
                self._fail(f"can_trade({symbol}, LONG, 0.75) = BLOCKED: {reason}")

    def _check_recent_signals(self, signal_id=None):
        self._header("3. RECENT PRIORITY SIGNALS")

        if signal_id:
            signals = Signal.objects.filter(id=signal_id)
            if not signals.exists():
                self._fail(f"Signal {signal_id} not found")
                return
        else:
            signals = Signal.objects.filter(
                market_type='FUTURES',
                status='ACTIVE',
            ).order_by('-created_at')[:10]

        if not signals.exists():
            self._info("No recent FUTURES ACTIVE signals found")
            return

        for sig in signals:
            has_trade = FuturesTrade.objects.filter(signal=sig).exists()
            trade_status = "HAS TRADE" if has_trade else "NO TRADE"

            priority_marker = "PRIORITY" if sig.is_priority else "not-priority"
            trade_marker = self.style.SUCCESS(trade_status) if has_trade else self.style.ERROR(trade_status)

            self._info(
                f"  Signal #{sig.id}: {sig.symbol.symbol} {sig.direction} "
                f"conf={sig.confidence} [{priority_marker}] [{trade_marker}] "
                f"created={sig.created_at.strftime('%Y-%m-%d %H:%M')}"
            )

            if sig.is_priority and not has_trade:
                self._diagnose_signal(sig)

    def _diagnose_signal(self, sig):
        s = FuturesTradingSettings.get_settings()
        symbol_name = sig.symbol.symbol

        if not s.is_enabled:
            self._fail(f"    -> BLOCKED: is_enabled=False")
            return

        can, reason = s.can_trade(symbol_name, sig.direction, sig.confidence)
        if not can:
            self._fail(f"    -> BLOCKED by can_trade: {reason}")
            return

        if BlacklistedSymbol.is_blacklisted(symbol_name):
            self._fail(f"    -> BLOCKED: {symbol_name} is blacklisted")
            return

        has_open = FuturesTrade.objects.filter(
            symbol=symbol_name, direction=sig.direction, status='OPEN'
        ).exists()
        if has_open:
            self._fail(f"    -> BLOCKED: already open {sig.direction} on {symbol_name}")
            return

        if s.fear_greed_enabled:
            from signals.services.fear_greed import get_fear_greed_value, check_direction_allowed
            fg = get_fear_greed_value()
            if fg is not None:
                allowed, fg_reason = check_direction_allowed(
                    sig.direction, fg, s.fear_greed_short_threshold, s.fear_greed_long_threshold
                )
                if not allowed:
                    self._fail(f"    -> BLOCKED by F&G: {fg_reason}")
                    return

        self._fail(f"    -> All DB checks passed. Likely Binance API error or code not deployed")

    def _check_open_positions(self):
        self._header("4. OPEN FUTURES TRADES")

        open_trades = FuturesTrade.objects.filter(status='OPEN')
        if not open_trades.exists():
            self._info("No open futures trades")
            return

        for t in open_trades:
            self._info(
                f"  Trade #{t.id}: {t.direction} {t.symbol} @ {t.entry_price} "
                f"(SL: {t.stop_loss}, TP: {t.take_profit}, Lev: {t.leverage}x)"
            )

    def _check_fear_greed(self):
        self._header("5. FEAR & GREED INDEX")

        try:
            from signals.services.fear_greed import get_fear_greed_value, fetch_fear_greed_index
            data = fetch_fear_greed_index()
            if data:
                self._ok(f"F&G Value: {data['value']} ({data['classification']})")
                self._info(f"Source: {data['source']}")

                s = FuturesTradingSettings.get_settings()
                if s.fear_greed_enabled:
                    self._info(f"SHORT threshold: <={s.fear_greed_short_threshold} (blocks LONG)")
                    self._info(f"LONG threshold: >={s.fear_greed_long_threshold} (blocks SHORT)")

                    v = data['value']
                    if v <= s.fear_greed_short_threshold:
                        self._fail(f"F&G={v}: LONG trades BLOCKED (fear zone)")
                    elif v >= s.fear_greed_long_threshold:
                        self._fail(f"F&G={v}: SHORT trades BLOCKED (greed zone)")
                    else:
                        self._ok(f"F&G={v}: Both directions allowed (neutral zone)")
                else:
                    self._info("F&G filter is DISABLED in settings")
            else:
                self._fail("Could not fetch F&G index (API unavailable)")
        except Exception as e:
            self._fail(f"F&G check error: {e}")

    def _check_code_version(self):
        self._header("6. CODE VERSION CHECK")

        from signals.services.futures_trader import FuturesTradingService
        import inspect
        sig = inspect.signature(FuturesTradingService.execute_signal)
        params = list(sig.parameters.keys())

        if 'force_execute' in params:
            self._ok("execute_signal has 'force_execute' param (latest code deployed)")
        else:
            self._fail(
                "execute_signal MISSING 'force_execute' param! "
                "Old code is running. Deploy latest changes and restart celery."
            )

    def _header(self, text):
        self.stdout.write(f"\n{'=' * 60}")
        self.stdout.write(f"  {text}")
        self.stdout.write(f"{'=' * 60}")

    def _ok(self, text):
        self.stdout.write(self.style.SUCCESS(f"  [OK] {text}"))

    def _fail(self, text):
        self.stdout.write(self.style.ERROR(f"  [FAIL] {text}"))

    def _info(self, text):
        self.stdout.write(f"  [..] {text}")
