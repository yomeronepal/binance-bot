"""
Test the full futures trade pipeline: Signal creation -> Handler -> Service -> Binance.

This simulates exactly what happens when a priority signal is generated,
going through all the checks (is_enabled, can_trade, blacklist, F&G, etc).

Usage:
    python manage.py test_futures_trade                              # Dry run - show what would happen
    python manage.py test_futures_trade --symbol BTCUSDT             # Different symbol
    python manage.py test_futures_trade --direction SHORT            # SHORT trade
    python manage.py test_futures_trade --execute                    # REAL trade via full pipeline
    python manage.py test_futures_trade --execute --skip-signal      # REAL trade via service only (no signal)
"""
import logging
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from django.core.management.base import BaseCommand

from signals.models import Signal, Symbol, TradingSession
from signals.models_futures import FuturesTradingSettings, FuturesTrade
from signals.models_blacklist import BlacklistedSymbol

logger = logging.getLogger(__name__)

NEPAL_TZ_OFFSET = timedelta(hours=5, minutes=45)


def get_nepal_now():
    return datetime.now(timezone.utc) + NEPAL_TZ_OFFSET


class Command(BaseCommand):
    help = 'Test full futures trade pipeline (signal -> handler -> service -> Binance)'

    def add_arguments(self, parser):
        parser.add_argument('--symbol', default='BTCUSDT', help='Trading pair (default: BTCUSDT)')
        parser.add_argument('--direction', default='LONG', choices=['LONG', 'SHORT'], help='Trade direction')
        parser.add_argument('--execute', action='store_true', help='Actually execute (REAL MONEY)')
        parser.add_argument('--skip-signal', action='store_true', help='Skip signal creation, test service directly')

    def handle(self, *args, **options):
        symbol_name = options['symbol'].upper()
        direction = options['direction'].upper()
        execute = options['execute']
        skip_signal = options['skip_signal']

        self._header("FUTURES TRADE PIPELINE TEST")
        self._info(f"Symbol: {symbol_name} | Direction: {direction}")
        self._info(f"Mode: {'LIVE EXECUTION' if execute else 'DRY RUN (checks only)'}")

        nepal_now = get_nepal_now()
        self._info(f"Nepal Time: {nepal_now.strftime('%Y-%m-%d %H:%M:%S')} NPT")

        self._check_trading_sessions(nepal_now)
        settings_ok = self._check_settings(symbol_name, direction)
        self._check_blacklist(symbol_name)
        self._check_existing_positions(symbol_name, direction)

        if not execute:
            self._header("DRY RUN COMPLETE")
            if settings_ok:
                self._ok("All checks passed. Use --execute to place a real trade.")
            else:
                self._fail("Some checks failed. Fix issues above before executing.")
            return

        self.stdout.write(self.style.WARNING(
            f"\n  *** LIVE MODE - WILL PLACE REAL FUTURES TRADE ***\n"
            f"  Symbol: {symbol_name} | Direction: {direction}\n"
        ))
        confirm = input("  Type 'YES' to confirm: ")
        if confirm != 'YES':
            self.stdout.write("  Cancelled.")
            return

        if skip_signal:
            self._execute_via_service(symbol_name, direction)
        else:
            self._execute_via_signal(symbol_name, direction)

    def _check_trading_sessions(self, nepal_now):
        self._header("TRADING SESSIONS (from DB)")

        sessions = TradingSession.objects.filter(active=True)
        if not sessions.exists():
            self._fail("No active trading sessions in DB")
            return

        matching = TradingSession.get_matching_session(nepal_now)

        for session in sessions:
            is_match = matching and matching.id == session.id
            marker = " <-- CURRENT" if is_match else ""
            status = self.style.SUCCESS("MATCH") if is_match else "no match"
            self._info(
                f"{session.name} ({session.session_type}): "
                f"{session.start_hour:02d}:{session.start_minute:02d}-"
                f"{session.end_hour:02d}:{session.end_minute:02d} NPT "
                f"[{status}]{marker}"
            )

        if matching:
            self._ok(f"Currently in session: {matching.name} ({matching.session_type})")
            self._ok("Signal created now would have is_priority=True")
        else:
            self._fail("NOT in any trading session. Signal would have is_priority=False")
            self._info("Priority signals bypass window checks, non-priority signals will be blocked")

    def _check_settings(self, symbol_name, direction):
        self._header("FUTURES TRADING SETTINGS")

        settings = FuturesTradingSettings.get_settings()
        all_ok = True

        checks = [
            ("is_enabled", settings.is_enabled, True),
            ("trade_long", settings.trade_long, direction == 'LONG'),
            ("trade_short", settings.trade_short, direction == 'SHORT'),
            ("use_trading_window", settings.use_trading_window, None),
        ]

        for name, value, required in checks:
            if required is None:
                self._info(f"{name}: {value}")
            elif required and not value:
                self._fail(f"{name}: {value} (needs to be True)")
                all_ok = False
            elif not required:
                self._ok(f"{name}: {value}")
            else:
                self._ok(f"{name}: {value}")

        self._info(f"leverage: {settings.leverage}x")
        self._info(f"trade_amount: ${settings.trade_amount}")
        self._info(f"min_signal_confidence: {settings.min_signal_confidence}")
        self._info(f"max_concurrent_trades: {settings.max_concurrent_trades}")
        self._info(f"fear_greed_enabled: {settings.fear_greed_enabled}")

        open_trades = FuturesTrade.objects.filter(status='OPEN').count()
        if open_trades >= settings.max_concurrent_trades:
            self._fail(f"Open trades: {open_trades}/{settings.max_concurrent_trades} (MAX REACHED)")
            all_ok = False
        else:
            self._ok(f"Open trades: {open_trades}/{settings.max_concurrent_trades}")

        can_trade, reason = settings.can_trade(symbol_name, direction, Decimal('0.75'))
        if can_trade:
            self._ok(f"can_trade({symbol_name}, {direction}): ALLOWED")
        else:
            self._fail(f"can_trade({symbol_name}, {direction}): BLOCKED - {reason}")
            all_ok = False

        return all_ok

    def _check_blacklist(self, symbol_name):
        self._header("BLACKLIST CHECK")
        if BlacklistedSymbol.is_blacklisted(symbol_name):
            self._fail(f"{symbol_name} is BLACKLISTED")
        else:
            self._ok(f"{symbol_name} is not blacklisted")

    def _check_existing_positions(self, symbol_name, direction):
        self._header("EXISTING POSITIONS CHECK")

        open_positions = FuturesTrade.objects.filter(
            symbol=symbol_name, direction=direction, status='OPEN'
        )
        if open_positions.exists():
            for t in open_positions:
                self._fail(
                    f"Open {t.direction} {t.symbol} @ {t.entry_price} "
                    f"(Trade ID: {t.id}, Signal ID: {t.signal_id})"
                )
        else:
            self._ok(f"No open {direction} position on {symbol_name}")

    def _execute_via_signal(self, symbol_name, direction):
        self._header("CREATING TEST SIGNAL (full pipeline)")

        symbol_obj, _ = Symbol.objects.get_or_create(
            symbol=symbol_name,
            defaults={'market_type': 'FUTURES'}
        )

        current_price = self._get_current_price(symbol_name)
        if not current_price:
            self._fail("Could not get current price from Binance")
            return

        sl, tp = self._calculate_sl_tp(direction, current_price)

        self._info(f"Price: {current_price} | SL: {sl} | TP: {tp}")
        self._info("Creating signal (this triggers the post_save handler)...")

        signal = Signal.objects.create(
            symbol=symbol_obj,
            timeframe='1h',
            direction=direction,
            confidence=Decimal('0.80'),
            entry_price=current_price,
            sl=sl,
            tp=tp,
            status='ACTIVE',
            market_type='FUTURES',
            indicators={
                'rsi': 30 if direction == 'LONG' else 70,
                'adx': 25,
                'test': True
            }
        )

        self._ok(f"Signal created: ID={signal.id}, is_priority={signal.is_priority}")

        trade = FuturesTrade.objects.filter(signal=signal).first()
        if trade:
            self._header("TRADE EXECUTED SUCCESSFULLY")
            self._ok(f"Trade ID: {trade.id}")
            self._ok(f"Direction: {trade.direction}")
            self._ok(f"Symbol: {trade.symbol}")
            self._ok(f"Entry: {trade.entry_price}")
            self._ok(f"Quantity: {trade.quantity}")
            self._ok(f"SL: {trade.stop_loss}")
            self._ok(f"TP: {trade.take_profit}")
            self._ok(f"Leverage: {trade.leverage}x")
            self._ok(f"Order ID: {trade.binance_order_id}")
            if trade.error_message:
                self._info(f"Warnings: {trade.error_message}")
        else:
            self._header("TRADE NOT CREATED")
            self._fail(
                "Signal handler did not create a FuturesTrade. "
                "Check celery worker logs for the exact reason."
            )
            self._info("Common causes:")
            self._info("  - FuturesTradingSettings.is_enabled = False")
            self._info("  - can_trade() check failed (confidence, direction, max trades)")
            self._info("  - Symbol is blacklisted")
            self._info("  - Already have open position on this symbol")
            self._info("  - Fear & Greed filter blocked the direction")
            self._info("  - Binance API connection error")

    def _execute_via_service(self, symbol_name, direction):
        self._header("EXECUTING VIA SERVICE DIRECTLY (skip signal)")

        from signals.services.futures_trader import futures_trading_service

        symbol_obj, _ = Symbol.objects.get_or_create(
            symbol=symbol_name,
            defaults={'market_type': 'FUTURES'}
        )

        current_price = self._get_current_price(symbol_name)
        if not current_price:
            self._fail("Could not get current price from Binance")
            return

        sl, tp = self._calculate_sl_tp(direction, current_price)

        signal = Signal.objects.create(
            symbol=symbol_obj,
            timeframe='1h',
            direction=direction,
            confidence=Decimal('0.80'),
            entry_price=current_price,
            sl=sl,
            tp=tp,
            status='ACTIVE',
            market_type='FUTURES',
            indicators={'test': True, 'skip_signal_handler': True}
        )

        self._info(f"Signal created: ID={signal.id}")
        self._info("Calling futures_trading_service.execute_signal(force_execute=True)...")

        trade = futures_trading_service.execute_signal(signal, force_execute=True)

        if trade:
            self._header("TRADE EXECUTED SUCCESSFULLY")
            self._ok(f"Trade ID: {trade.id} | {trade.direction} {trade.symbol} @ {trade.entry_price}")
            self._ok(f"SL: {trade.stop_loss} | TP: {trade.take_profit} | Lev: {trade.leverage}x")
        else:
            self._fail("execute_signal returned None. Check logs above for reason.")

    def _get_current_price(self, symbol_name):
        import asyncio
        from signals.services.futures_trader import BinanceFuturesTrader

        async def _fetch():
            trader = BinanceFuturesTrader(use_testnet=False)
            try:
                return await trader.get_current_price(symbol_name)
            finally:
                await trader.close()

        try:
            return asyncio.run(_fetch())
        except Exception as e:
            self._fail(f"Binance API error: {e}")
            return None

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
