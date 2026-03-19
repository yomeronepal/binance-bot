"""
Test the full futures trade pipeline with step-by-step verification.

Usage:
    python manage.py test_futures_trade                                # Dry run
    python manage.py test_futures_trade --symbol ETHUSDT               # Different symbol
    python manage.py test_futures_trade --direction SHORT              # SHORT trade
    python manage.py test_futures_trade --execute                      # REAL trade via signal handler
    python manage.py test_futures_trade --execute --force              # REAL trade bypassing ALL checks
"""
import asyncio
import inspect
import logging
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from django.core.management.base import BaseCommand

from signals.models import Signal, Symbol, TradingSession
from signals.models_futures import FuturesTradingSettings, FuturesTrade
from signals.models_blacklist import BlacklistedSymbol
from signals.services.futures_trader import BinanceFuturesTrader, FuturesTradingService

logger = logging.getLogger(__name__)

NEPAL_TZ_OFFSET = timedelta(hours=5, minutes=45)


def get_nepal_now():
    return datetime.now(timezone.utc) + NEPAL_TZ_OFFSET


class Command(BaseCommand):
    help = 'Test full futures trade pipeline with step-by-step verification'

    def add_arguments(self, parser):
        parser.add_argument('--symbol', default='BTCUSDT', help='Trading pair (default: BTCUSDT)')
        parser.add_argument('--direction', default='LONG', choices=['LONG', 'SHORT'])
        parser.add_argument('--execute', action='store_true', help='Place REAL order (costs money!)')
        parser.add_argument('--force', action='store_true', help='Force execute, bypass all checks')

    def handle(self, *args, **options):
        symbol_name = options['symbol'].upper()
        direction = options['direction'].upper()
        execute = options['execute']
        force = options['force']

        self._header("FUTURES TRADE PIPELINE TEST")
        nepal_now = get_nepal_now()
        self._info(f"Nepal Time: {nepal_now.strftime('%Y-%m-%d %H:%M:%S %A')} NPT")
        self._info(f"Symbol: {symbol_name} | Direction: {direction}")
        self._info(f"Mode: {'FORCE EXECUTE' if force else 'LIVE' if execute else 'DRY RUN'}")

        all_ok = True

        all_ok = self._step_code_version() and all_ok
        in_session = self._step_trading_sessions(nepal_now)
        all_ok = self._step_settings(symbol_name, direction) and all_ok
        all_ok = self._step_blacklist(symbol_name) and all_ok
        all_ok = self._step_existing_positions(symbol_name, direction) and all_ok
        fg_ok = self._step_fear_greed(direction)
        all_ok = fg_ok and all_ok
        price = self._step_binance_connectivity(symbol_name)
        all_ok = (price is not None) and all_ok

        if not in_session:
            self._info("Signal would have is_priority=False (outside trading session)")
            if force:
                self._ok("--force flag: will bypass this")
            else:
                self._fail("Trade WILL BE BLOCKED unless --force is used")
                all_ok = False

        if not execute:
            self._header("DRY RUN SUMMARY")
            if all_ok:
                self._ok("All checks PASSED. Use --execute to place a real trade.")
            else:
                self._fail("Some checks FAILED. Fix issues above or use --execute --force")
            return

        if not price:
            self._fail("Cannot execute: Binance API unreachable")
            return

        self.stdout.write(self.style.WARNING(
            f"\n  *** REAL MONEY - PLACING FUTURES ORDER ***\n"
            f"  {direction} {symbol_name} @ ~${price}\n"
        ))
        confirm = input("  Type 'YES' to confirm: ")
        if confirm != 'YES':
            self.stdout.write("  Cancelled.")
            return

        if force:
            self._execute_force(symbol_name, direction, price)
        else:
            self._execute_via_signal(symbol_name, direction, price, in_session)

    def _step_code_version(self):
        self._header("STEP 1: CODE VERSION")
        sig = inspect.signature(FuturesTradingService.execute_signal)
        params = list(sig.parameters.keys())

        if 'force_execute' in params:
            self._ok("execute_signal has 'force_execute' param (latest code)")
            return True
        self._fail("OLD CODE: execute_signal missing 'force_execute'. Redeploy and restart celery!")
        return False

    def _step_trading_sessions(self, nepal_now):
        self._header("STEP 2: TRADING SESSIONS")

        sessions = TradingSession.objects.filter(active=True)
        matching = TradingSession.get_matching_session(nepal_now)

        if not sessions.exists():
            self._fail("No active trading sessions in DB!")
            return False

        for s in sessions:
            is_match = matching and matching.id == s.id
            marker = " ** ACTIVE **" if is_match else ""
            self._info(
                f"  {s.name} ({s.session_type}): "
                f"{s.start_hour:02d}:{s.start_minute:02d}-{s.end_hour:02d}:{s.end_minute:02d} NPT{marker}"
            )

        if matching:
            self._ok(f"In session: {matching.name} -> is_priority=True")
            return True

        self._fail("NOT in any session -> is_priority=False")
        return False

    def _step_settings(self, symbol_name, direction):
        self._header("STEP 3: FUTURES SETTINGS")

        s = FuturesTradingSettings.get_settings()
        ok = True

        if not s.is_enabled:
            self._fail(f"is_enabled = False  <-- BLOCKS ALL TRADES")
            ok = False
        else:
            self._ok(f"is_enabled = True")

        if direction == 'LONG' and not s.trade_long:
            self._fail("trade_long = False  <-- BLOCKS LONG")
            ok = False
        elif direction == 'SHORT' and not s.trade_short:
            self._fail("trade_short = False  <-- BLOCKS SHORT")
            ok = False
        else:
            self._ok(f"trade_{direction.lower()} = True")

        self._info(f"leverage = {s.leverage}x | trade_amount = ${s.trade_amount}")
        self._info(f"min_signal_confidence = {s.min_signal_confidence}")

        open_count = FuturesTrade.objects.filter(status='OPEN').count()
        if open_count >= s.max_concurrent_trades:
            self._fail(f"Open trades: {open_count}/{s.max_concurrent_trades} MAX REACHED")
            ok = False
        else:
            self._ok(f"Open trades: {open_count}/{s.max_concurrent_trades}")

        if s.allowed_symbols and symbol_name not in s.allowed_symbols:
            self._fail(f"{symbol_name} not in allowed_symbols: {s.allowed_symbols}")
            ok = False
        elif s.allowed_symbols:
            self._ok(f"{symbol_name} in allowed_symbols")
        else:
            self._ok(f"allowed_symbols = ALL (no filter)")

        can, reason = s.can_trade(symbol_name, direction, Decimal('0.80'))
        if not can:
            self._fail(f"can_trade: BLOCKED - {reason}")
            ok = False
        else:
            self._ok(f"can_trade: ALLOWED")

        return ok

    def _step_blacklist(self, symbol_name):
        self._header("STEP 4: BLACKLIST")
        if BlacklistedSymbol.is_blacklisted(symbol_name):
            self._fail(f"{symbol_name} is BLACKLISTED")
            return False
        self._ok(f"{symbol_name} not blacklisted")
        return True

    def _step_existing_positions(self, symbol_name, direction):
        self._header("STEP 5: EXISTING POSITIONS")
        has_open = FuturesTrade.objects.filter(
            symbol=symbol_name, direction=direction, status='OPEN'
        ).exists()
        if has_open:
            self._fail(f"Already have open {direction} on {symbol_name}")
            return False
        self._ok(f"No open {direction} on {symbol_name}")
        return True

    def _step_fear_greed(self, direction):
        self._header("STEP 6: FEAR & GREED INDEX")

        s = FuturesTradingSettings.get_settings()
        if not s.fear_greed_enabled:
            self._info("F&G filter DISABLED in settings (skipped)")
            return True

        try:
            from signals.services.fear_greed import get_fear_greed_value, check_direction_allowed
            fg = get_fear_greed_value()
            if fg is None:
                self._fail("F&G index unavailable (API error). Trade will proceed without F&G check.")
                return True

            allowed, reason = check_direction_allowed(
                direction, fg, s.fear_greed_short_threshold, s.fear_greed_long_threshold
            )
            if allowed:
                self._ok(f"F&G={fg}: {reason}")
                return True
            self._fail(f"F&G={fg}: {reason}")
            return False
        except Exception as e:
            self._fail(f"F&G error: {e}")
            return True

    def _step_binance_connectivity(self, symbol_name):
        self._header("STEP 7: BINANCE CONNECTIVITY")

        async def _test():
            trader = BinanceFuturesTrader(use_testnet=False)
            try:
                price = await trader.get_current_price(symbol_name)
                info = await trader.get_symbol_info(symbol_name)
                balance = await trader._request('GET', '/fapi/v2/balance', signed=True)
                usdt = next((b for b in balance if b['asset'] == 'USDT'), None)
                return price, info, usdt
            finally:
                await trader.close()

        try:
            price, info, usdt = asyncio.run(_test())

            if price:
                self._ok(f"Current price: ${price}")
            else:
                self._fail(f"Could not get price for {symbol_name}")
                return None

            if info:
                self._ok(f"Symbol info: found ({info['symbol']})")
            else:
                self._fail(f"Could not get symbol info for {symbol_name}")
                return None

            if usdt:
                avail = usdt.get('availableBalance', '0')
                self._ok(f"USDT balance: ${usdt.get('balance', '0')} (available: ${avail})")
            else:
                self._fail("No USDT balance found")

            return price

        except Exception as e:
            self._fail(f"Binance API error: {e}")
            return None

    def _execute_via_signal(self, symbol_name, direction, price, in_session):
        self._header("EXECUTING: SIGNAL -> HANDLER -> SERVICE -> BINANCE")

        symbol_obj, _ = Symbol.objects.get_or_create(
            symbol=symbol_name,
            defaults={'market_type': 'FUTURES'}
        )

        sl, tp = self._calculate_sl_tp(direction, price)
        self._info(f"Entry: ~${price} | SL: ${sl} | TP: ${tp}")

        self._info("Creating ACTIVE FUTURES signal...")
        signal = Signal.objects.create(
            symbol=symbol_obj,
            timeframe='1h',
            direction=direction,
            confidence=Decimal('0.80'),
            entry_price=price,
            sl=sl,
            tp=tp,
            status='ACTIVE',
            market_type='FUTURES',
            indicators={'rsi': 30 if direction == 'LONG' else 70, 'adx': 25, 'test_trade': True}
        )

        self._ok(f"Signal #{signal.id} created | is_priority={signal.is_priority}")

        if not signal.is_priority:
            self._fail(
                "Signal is NOT priority (outside trading session). "
                "Handler will skip it. Use --force to bypass."
            )
            signal.delete()
            return

        trade = FuturesTrade.objects.filter(signal=signal).first()
        self._report_trade_result(trade, signal)

    def _execute_force(self, symbol_name, direction, price):
        self._header("EXECUTING: FORCE MODE (bypass all checks)")

        from signals.services.futures_trader import futures_trading_service

        symbol_obj, _ = Symbol.objects.get_or_create(
            symbol=symbol_name,
            defaults={'market_type': 'FUTURES'}
        )

        sl, tp = self._calculate_sl_tp(direction, price)
        self._info(f"Entry: ~${price} | SL: ${sl} | TP: ${tp}")

        from django.db import connection
        signal_handlers_active = True
        try:
            from django.db.models.signals import post_save
            from signals.signals_handlers import execute_futures_trade_on_signal
            post_save.disconnect(execute_futures_trade_on_signal, sender=Signal)
            signal_handlers_active = False
            self._info("Disconnected signal handler to prevent double execution")
        except Exception:
            self._info("Could not disconnect handler, proceeding anyway")

        try:
            signal = Signal(
                symbol=symbol_obj,
                timeframe='1h',
                direction=direction,
                confidence=Decimal('0.80'),
                entry_price=price,
                sl=sl,
                tp=tp,
                status='ACTIVE',
                market_type='FUTURES',
                indicators={'test_trade': True, 'force': True}
            )
            signal.is_priority = True
            signal.save()
            self._ok(f"Signal #{signal.id} created (is_priority forced to True)")

            self._info("Calling execute_signal(force_execute=True)...")
            trade = futures_trading_service.execute_signal(signal, force_execute=True)
            self._report_trade_result(trade, signal)

        finally:
            if not signal_handlers_active:
                try:
                    from django.db.models.signals import post_save
                    from signals.signals_handlers import execute_futures_trade_on_signal
                    post_save.connect(execute_futures_trade_on_signal, sender=Signal)
                except Exception:
                    pass

    def _report_trade_result(self, trade, signal):
        if trade:
            self._header("TRADE PLACED SUCCESSFULLY")
            self._ok(f"Trade ID: {trade.id}")
            self._ok(f"{trade.direction} {trade.symbol} @ ${trade.entry_price}")
            self._ok(f"Quantity: {trade.quantity}")
            self._ok(f"SL: ${trade.stop_loss} | TP: ${trade.take_profit}")
            self._ok(f"Leverage: {trade.leverage}x")
            self._ok(f"Binance Order ID: {trade.binance_order_id}")
            self._ok(f"SL Order: {trade.sl_order_id}")
            self._ok(f"TP Order: {trade.tp_order_id}")
            if trade.error_message:
                self._fail(f"Warnings: {trade.error_message}")
        else:
            self._header("TRADE FAILED")
            self._fail("No FuturesTrade created. Possible reasons:")
            self._info("  1. is_enabled=False in FuturesTradingSettings")
            self._info("  2. can_trade() blocked (confidence/direction/max trades/allowed symbols)")
            self._info("  3. Fear & Greed filter blocked the direction")
            self._info("  4. Duplicate signal or open position exists")
            self._info("  5. Binance API error (check logs)")
            self._info(f"  Signal ID: {signal.id} | Check logs with: grep 'signal {signal.id}' in celery logs")

    def _calculate_sl_tp(self, direction, price):
        risk = Decimal('0.025')
        profit = Decimal('0.06')

        if direction == 'LONG':
            return (
                (price * (1 - risk)).quantize(Decimal('0.01')),
                (price * (1 + profit)).quantize(Decimal('0.01'))
            )
        return (
            (price * (1 + risk)).quantize(Decimal('0.01')),
            (price * (1 - profit)).quantize(Decimal('0.01'))
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
