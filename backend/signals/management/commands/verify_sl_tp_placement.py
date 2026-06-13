"""
End-to-end verification: Signal -> Binance futures order -> SL/TP on exchange.

Places a real (or forced) signal through the production flow, then queries
Binance /fapi/v1/openOrders to prove that STOP_MARKET and TAKE_PROFIT_MARKET
orders actually exist on the exchange. Closes out the position afterwards
so the account is left flat.

Usage:
    python manage.py verify_sl_tp_placement --symbol BTCUSDT --direction LONG
    python manage.py verify_sl_tp_placement --symbol ETHUSDT --direction SHORT --sl-pct 1.0 --tp-pct 2.0
    python manage.py verify_sl_tp_placement --symbol BTCUSDT --direction LONG --keep-open
    python manage.py verify_sl_tp_placement --symbol BTCUSDT --direction LONG --yes
"""
import asyncio
import time
from decimal import Decimal
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError
from django.db.models.signals import post_save

from signals.models import Signal, Symbol
from signals.models.futures import FuturesTradingSettings, FuturesTrade
from signals.signals_handlers import execute_futures_trade_on_signal
from signals.services.futures_trader import (
    BinanceFuturesTrader,
    futures_trading_service,
    _run_in_thread,
)


EXPECTED_TYPES = {'STOP_MARKET', 'TAKE_PROFIT_MARKET'}
PRICE_TOLERANCE_PCT = Decimal('0.5')


class Command(BaseCommand):
    help = (
        'End-to-end test: generate signal, place futures order, '
        'verify SL and TP orders exist on Binance.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--symbol', default='BTCUSDT',
                            help='Trading pair (default: BTCUSDT)')
        parser.add_argument('--direction', choices=['LONG', 'SHORT'], default='LONG',
                            help='Trade direction (default: LONG)')
        parser.add_argument('--sl-pct', type=float, default=1.0,
                            help='Stop-loss distance from entry, percent (default: 1.0)')
        parser.add_argument('--tp-pct', type=float, default=2.0,
                            help='Take-profit distance from entry, percent (default: 2.0)')
        parser.add_argument('--confidence', type=float, default=0.85,
                            help='Signal confidence to store (default: 0.85)')
        parser.add_argument('--timeframe', default='1h',
                            help='Signal timeframe label (default: 1h)')
        parser.add_argument('--testnet', action='store_true',
                            help='Use Binance Futures testnet instead of mainnet')
        parser.add_argument('--keep-open', action='store_true',
                            help='Do NOT cancel orders / close position after verification')
        parser.add_argument('--yes', action='store_true',
                            help='Skip interactive confirmation prompt')
        parser.add_argument('--wait-seconds', type=float, default=2.0,
                            help='Seconds to wait after placement before querying openOrders (default: 2)')

    def handle(self, *args, **options):
        self.options = options
        self.use_testnet = options['testnet']
        self.symbol = options['symbol'].upper()
        self.direction = options['direction']

        self._print_header('VERIFY SL/TP PLACEMENT ON BINANCE')
        self._print_banner()
        self._preflight_checks()

        live_price = self._fetch_live_price()
        sl, tp = self._compute_sl_tp(live_price)
        self._print_plan(live_price, sl, tp)

        if not options['yes']:
            self._interactive_confirm()

        signal = self._create_signal(live_price, sl, tp)
        trade = self._execute_signal(signal)

        time.sleep(options['wait_seconds'])

        open_orders = self._fetch_open_orders(self.symbol)
        self._print_open_orders(open_orders)
        result = self._verify_sl_tp(open_orders, sl, tp)

        if not options['keep_open']:
            self._cleanup(trade)

        self._print_summary(result, trade)

        if not result['ok']:
            raise CommandError('SL/TP verification FAILED — see details above')

    def _preflight_checks(self):
        """Sanity-check settings before touching the exchange."""
        settings_obj = FuturesTradingSettings.get_settings()
        if not settings_obj.is_enabled:
            raise CommandError(
                'FuturesTradingSettings.is_enabled is False — enable it first or set --testnet'
            )
        self._info(f'Futures enabled: {settings_obj.is_enabled}')
        self._info(f'Leverage: {settings_obj.leverage}x | Trade amount: ${settings_obj.trade_amount}')
        self._info(f'Network: {"TESTNET" if self.use_testnet else "MAINNET (REAL MONEY)"}')

    def _fetch_live_price(self):
        """Pull current mark price from Binance for the target symbol."""
        async def _fetch():
            trader = BinanceFuturesTrader(use_testnet=self.use_testnet)
            try:
                return await trader.get_current_price(self.symbol)
            finally:
                await trader.close()

        price = _run_in_thread(_fetch)
        if not price or Decimal(str(price)) <= 0:
            raise CommandError(f'Could not fetch live price for {self.symbol}')
        return Decimal(str(price))

    def _compute_sl_tp(self, entry):
        """Derive SL/TP prices from entry and percentage offsets."""
        sl_pct = Decimal(str(self.options['sl_pct'])) / Decimal('100')
        tp_pct = Decimal(str(self.options['tp_pct'])) / Decimal('100')

        if self.direction == 'LONG':
            return entry * (1 - sl_pct), entry * (1 + tp_pct)
        return entry * (1 + sl_pct), entry * (1 - tp_pct)

    def _create_signal(self, entry, sl, tp):
        """Persist a Signal row (with handler disconnected) for the trader to consume."""
        symbol_obj, _ = Symbol.objects.get_or_create(
            symbol=self.symbol, defaults={'market_type': 'FUTURES'}
        )

        post_save.disconnect(execute_futures_trade_on_signal, sender=Signal)
        try:
            signal = Signal(
                symbol=symbol_obj,
                timeframe=self.options['timeframe'],
                direction=self.direction,
                confidence=self.options['confidence'],
                entry=entry,
                sl=sl,
                tp=tp,
                status='ACTIVE',
                market_type='FUTURES',
                leverage=10,
                meta={'verify_sl_tp_placement': True, 'created_at': datetime.now(timezone.utc).isoformat()},
            )
            signal.is_priority = True
            signal.save()
            self._ok(f'Signal #{signal.id} saved (direction={signal.direction}, entry=${signal.entry})')
            return signal
        finally:
            post_save.connect(execute_futures_trade_on_signal, sender=Signal)

    def _execute_signal(self, signal):
        """Run the same code path production uses to place an order."""
        self._print_header('PLACING ORDER VIA futures_trading_service.execute_signal')
        trade = futures_trading_service.execute_signal(signal, force_execute=True)
        if not trade:
            raise CommandError(
                f'futures_trading_service.execute_signal returned None for signal {signal.id} — '
                'check server logs for the reason.'
            )
        self._ok(f'FuturesTrade #{trade.id} created')
        self._info(f'  Entry order ID: {trade.binance_order_id}')
        self._info(f'  SL order ID:    {trade.sl_order_id or "(none)"}')
        self._info(f'  TP order ID:    {trade.tp_order_id or "(none)"}')
        return trade

    def _fetch_open_orders(self, symbol):
        """Ask Binance for all open orders on this symbol."""
        async def _fetch():
            trader = BinanceFuturesTrader(use_testnet=self.use_testnet)
            try:
                return await trader.get_all_open_orders(symbol)
            finally:
                await trader.close()

        return _run_in_thread(_fetch) or []

    def _print_open_orders(self, open_orders):
        """Pretty-print the list of open orders for the human."""
        self._print_header(f'BINANCE OPEN ORDERS ({self.symbol})')
        if not open_orders:
            self._fail('No open orders returned by Binance')
            return

        for order in open_orders:
            order_type = order.get('type', '?')
            side = order.get('side', '?')
            stop_price = order.get('stopPrice') or order.get('triggerPrice') or '-'
            price = order.get('price', '-')
            close_pos = order.get('closePosition', False)
            reduce_only = order.get('reduceOnly', False)
            order_id = order.get('orderId', '?')
            self._info(
                f'  [{order_type}] id={order_id} side={side} '
                f'stopPrice={stop_price} price={price} '
                f'closePosition={close_pos} reduceOnly={reduce_only}'
            )

    def _verify_sl_tp(self, open_orders, expected_sl, expected_tp):
        """Confirm a STOP_MARKET and TAKE_PROFIT_MARKET order exist with correct trigger prices."""
        self._print_header('VERIFICATION')

        by_type = {o.get('type'): o for o in open_orders if o.get('type') in EXPECTED_TYPES}

        sl_order = by_type.get('STOP_MARKET')
        tp_order = by_type.get('TAKE_PROFIT_MARKET')

        sl_on_exchange = sl_order is not None
        tp_on_exchange = tp_order is not None
        self._check('STOP_MARKET present on Binance', sl_on_exchange)
        self._check('TAKE_PROFIT_MARKET present on Binance', tp_on_exchange)

        sl_price_ok = self._verify_price(sl_order, expected_sl, 'SL')
        tp_price_ok = self._verify_price(tp_order, expected_tp, 'TP')

        ok = sl_on_exchange and tp_on_exchange and sl_price_ok and tp_price_ok
        return {
            'ok': ok,
            'sl_on_exchange': sl_on_exchange,
            'tp_on_exchange': tp_on_exchange,
            'sl_price_ok': sl_price_ok,
            'tp_price_ok': tp_price_ok,
        }

    def _verify_price(self, order, expected, label):
        """Check an order's stopPrice matches the expected value within tolerance."""
        if not order:
            return False
        actual_raw = order.get('stopPrice') or order.get('triggerPrice') or '0'
        actual = Decimal(str(actual_raw))
        expected_dec = Decimal(str(expected))
        if expected_dec == 0:
            passed = actual == 0
        else:
            diff_pct = abs(actual - expected_dec) / expected_dec * 100
            passed = diff_pct <= PRICE_TOLERANCE_PCT
        self._check(
            f'{label} stopPrice ≈ signal value '
            f'(expected={expected_dec}, actual={actual}, tol={PRICE_TOLERANCE_PCT}%)',
            passed,
        )
        return passed

    def _cleanup(self, trade):
        """Cancel all open orders and close position so the account is flat."""
        self._print_header('CLEANUP: CANCEL ORDERS + CLOSE POSITION')
        try:
            futures_trading_service.close_trade(trade)
            self._ok(f'Trade #{trade.id} closed')
        except Exception as e:
            self._fail(f'close_trade failed: {e}')
            self._info('Attempting direct cancel + market-close as fallback...')
            self._force_cleanup()

    def _force_cleanup(self):
        """Last-resort cleanup path if close_trade raises."""
        async def _run():
            trader = BinanceFuturesTrader(use_testnet=self.use_testnet)
            try:
                await trader.cancel_all_orders(self.symbol)
                position = await trader.get_position_for_symbol(self.symbol)
                if position:
                    qty = abs(Decimal(str(position.get('positionAmt', '0'))))
                    if qty > 0:
                        await trader.close_position(self.symbol, self.direction, qty)
            finally:
                await trader.close()

        try:
            _run_in_thread(_run)
            self._ok('Force cleanup completed')
        except Exception as e:
            self._fail(f'Force cleanup also failed: {e} — clean up manually!')

    def _print_summary(self, result, trade):
        """Final pass/fail summary."""
        self._print_header('SUMMARY')
        if result['ok']:
            self._ok('END-TO-END VERIFICATION PASSED')
            self._info('Signal → FuturesTrade → Binance openOrders all agree.')
        else:
            self._fail('END-TO-END VERIFICATION FAILED')
            if not result['sl_on_exchange']:
                self._fail('  SL order was not placed on Binance')
            if not result['tp_on_exchange']:
                self._fail('  TP order was not placed on Binance')
            if result['sl_on_exchange'] and not result['sl_price_ok']:
                self._fail('  SL stopPrice does not match signal')
            if result['tp_on_exchange'] and not result['tp_price_ok']:
                self._fail('  TP stopPrice does not match signal')
        if trade:
            self._info(f'FuturesTrade id: {trade.id} | status: {trade.status}')

    def _print_plan(self, price, sl, tp):
        """Show the user exactly what is about to happen."""
        self._print_header('TRADE PLAN')
        self._info(f'Symbol:    {self.symbol}')
        self._info(f'Direction: {self.direction}')
        self._info(f'Entry:     ${price}')
        self._info(f'SL:        ${sl} ({self.options["sl_pct"]}%)')
        self._info(f'TP:        ${tp} ({self.options["tp_pct"]}%)')
        self._info(f'Timeframe: {self.options["timeframe"]}')
        self._info(f'Cleanup:   {"NO (--keep-open)" if self.options["keep_open"] else "YES"}')

    def _interactive_confirm(self):
        """Block real-money trades behind a typed confirmation."""
        if self.use_testnet:
            return
        self.stdout.write(self.style.WARNING(
            '\n  *** REAL MONEY ON MAINNET — type YES to proceed ***'
        ))
        if input('  Confirm: ').strip() != 'YES':
            raise CommandError('Aborted by user')

    def _print_banner(self):
        net = 'TESTNET' if self.use_testnet else 'MAINNET'
        self._info(f'Run started at {datetime.now(timezone.utc).isoformat()} on {net}')

    def _print_header(self, text):
        self.stdout.write(f'\n{"=" * 64}')
        self.stdout.write(f'  {text}')
        self.stdout.write(f'{"=" * 64}')

    def _ok(self, text):
        self.stdout.write(self.style.SUCCESS(f'  [OK] {text}'))

    def _fail(self, text):
        self.stdout.write(self.style.ERROR(f'  [FAIL] {text}'))

    def _info(self, text):
        self.stdout.write(f'  [..] {text}')

    def _check(self, label, passed):
        if passed:
            self._ok(label)
        else:
            self._fail(label)
