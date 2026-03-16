"""
Test futures order placement on Binance.

Usage:
    python manage.py test_futures_order                          # Dry run CTSIUSDT LONG
    python manage.py test_futures_order --symbol USUALUSDT       # Different symbol
    python manage.py test_futures_order --direction SHORT        # SHORT trade
    python manage.py test_futures_order --amount 5               # $5 margin
    python manage.py test_futures_order --execute                # REAL order (spends money!)
    python manage.py test_futures_order --execute --batch-only   # Only test batch method
    python manage.py test_futures_order --execute --separate-only # Only test separate method
"""
import asyncio
import json
from decimal import Decimal

from django.core.management.base import BaseCommand

from signals.services.futures_trader import BinanceFuturesTrader
from signals.models_futures import FuturesTradingSettings


class Command(BaseCommand):
    help = 'Test futures order placement (dry-run by default, --execute for real)'

    def add_arguments(self, parser):
        parser.add_argument('--symbol', default='CTSIUSDT', help='Trading pair (default: CTSIUSDT)')
        parser.add_argument('--direction', default='LONG', choices=['LONG', 'SHORT'], help='Trade direction')
        parser.add_argument('--amount', type=float, default=5.0, help='Margin in USDT (default: 5)')
        parser.add_argument('--leverage', type=int, default=10, help='Leverage (default: 10)')
        parser.add_argument('--execute', action='store_true', help='Actually place the order (REAL MONEY)')
        parser.add_argument('--batch-only', action='store_true', help='Only test batch order method')
        parser.add_argument('--separate-only', action='store_true', help='Only test separate order method')

    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        direction = options['direction'].upper()
        amount = Decimal(str(options['amount']))
        leverage = options['leverage']
        execute = options['execute']
        batch_only = options['batch_only']
        separate_only = options['separate_only']

        if execute:
            self.stdout.write(self.style.WARNING(
                f"\n  *** LIVE MODE - WILL PLACE REAL ORDER ***\n"
                f"  Symbol: {symbol} | Direction: {direction}\n"
                f"  Margin: ${amount} | Leverage: {leverage}x\n"
            ))
            confirm = input("  Type 'YES' to confirm: ")
            if confirm != 'YES':
                self.stdout.write("Cancelled.")
                return

        asyncio.run(self._run_test(symbol, direction, amount, leverage, execute, batch_only, separate_only))

    async def _run_test(self, symbol, direction, amount, leverage, execute, batch_only, separate_only):
        trader = BinanceFuturesTrader(use_testnet=False)

        try:
            self._header("STEP 1: FETCH MARKET DATA")

            symbol_info = await trader.get_symbol_info(symbol)
            if not symbol_info:
                self._fail("Could not get symbol info")
                return

            tick_size, price_precision = trader._get_price_precision(symbol_info)
            self._info(f"Tick size: {tick_size} | Price precision: {price_precision}")

            self._print_filters(symbol_info)

            current_price = await trader.get_current_price(symbol)
            if not current_price:
                self._fail("Could not get current price")
                return
            self._ok(f"Current price: {current_price}")

            self._header("STEP 2: CALCULATE ORDER PARAMS")

            quantity = trader._calculate_quantity(symbol_info, current_price, amount, leverage)
            notional = float(quantity) * float(current_price)
            self._info(f"Margin: ${amount} x {leverage}x = ${float(amount) * leverage} notional")
            self._info(f"Quantity: {quantity}")
            self._info(f"Actual notional: ${notional:.4f}")

            if notional < 5:
                self._fail(f"Notional ${notional:.2f} below Binance minimum $5")
                return

            sl, tp = self._calculate_sl_tp(direction, current_price)
            sl_rounded = trader._round_price(sl, symbol_info)
            tp_rounded = trader._round_price(tp, symbol_info)
            self._ok(f"SL: {sl_rounded} (2.5% risk)")
            self._ok(f"TP: {tp_rounded} (6% target)")

            self._validate_sl_tp(direction, sl_rounded, tp_rounded, current_price)

            self._header("STEP 3: CHECK ACCOUNT")

            await self._check_account(trader, amount)
            await self._check_positions(trader, symbol)
            await self._check_open_orders(trader, symbol)

            self._header("STEP 4: ORDER PAYLOAD")

            entry_side = 'BUY' if direction == 'LONG' else 'SELL'
            close_side = 'SELL' if direction == 'LONG' else 'BUY'

            batch_payload = self._build_batch_payload(symbol, entry_side, close_side, quantity, sl_rounded, tp_rounded)
            self._info("Batch payload (POST /fapi/v1/batchOrders):")
            self.stdout.write(json.dumps(batch_payload, indent=2))

            if not execute:
                self._header("DRY RUN COMPLETE")
                self._ok("Order format valid. Use --execute to place real order.")
                return

            self._header("STEP 5: EXECUTING REAL ORDER")

            await trader.set_margin_type(symbol, 'ISOLATED')
            self._ok("Margin type: ISOLATED")

            await trader.set_leverage(symbol, leverage)
            self._ok(f"Leverage: {leverage}x")

            if not separate_only:
                self._info("Attempting BATCH order (entry + SL + TP in 1 call)...")
                batch_result = await trader.place_batch_orders(symbol, direction, quantity, sl_rounded, tp_rounded)

                if batch_result and batch_result.get('entry'):
                    self._report_batch_result(batch_result, direction, quantity, symbol, current_price, sl_rounded, tp_rounded)

                    if batch_result.get('sl') and batch_result.get('tp'):
                        self._header("SUCCESS - ALL 3 ORDERS PLACED VIA BATCH")
                        return

                    self._info("Some orders failed in batch, retrying individually...")
                    await self._retry_failed_orders(
                        trader, batch_result, symbol, close_side, quantity,
                        sl_rounded, tp_rounded, current_price, symbol_info
                    )
                    return
                else:
                    self._fail("Batch order failed")

            if not batch_only:
                self._info("Attempting SEPARATE orders (entry first, then SL + TP)...")
                await self._place_separate(
                    trader, symbol, direction, entry_side, close_side,
                    quantity, sl_rounded, tp_rounded, current_price, symbol_info
                )

        except Exception as e:
            self._fail(f"Error: {e}")
        finally:
            await trader.close()

    def _calculate_sl_tp(self, direction, price):
        risk = Decimal('0.025')
        profit = Decimal('0.06')

        if direction == 'LONG':
            return price * (1 - risk), price * (1 + profit)
        return price * (1 + risk), price * (1 - profit)

    def _validate_sl_tp(self, direction, sl, tp, price):
        if direction == 'LONG':
            if sl >= price:
                self._fail(f"SL {sl} must be BELOW entry {price} for LONG")
            if tp <= price:
                self._fail(f"TP {tp} must be ABOVE entry {price} for LONG")
        else:
            if sl <= price:
                self._fail(f"SL {sl} must be ABOVE entry {price} for SHORT")
            if tp >= price:
                self._fail(f"TP {tp} must be BELOW entry {price} for SHORT")

        self._ok("SL/TP validation passed")

    def _build_batch_payload(self, symbol, entry_side, close_side, qty, sl, tp):
        return [
            {'symbol': symbol, 'side': entry_side, 'type': 'MARKET', 'quantity': str(qty)},
            {
                'symbol': symbol, 'side': close_side, 'type': 'STOP_MARKET',
                'stopPrice': str(sl), 'quantity': str(qty),
                'reduceOnly': 'true', 'workingType': 'MARK_PRICE', 'priceProtect': 'true',
            },
            {
                'symbol': symbol, 'side': close_side, 'type': 'TAKE_PROFIT_MARKET',
                'stopPrice': str(tp), 'quantity': str(qty),
                'reduceOnly': 'true', 'workingType': 'MARK_PRICE', 'priceProtect': 'true',
            },
        ]

    def _print_filters(self, symbol_info):
        for f in symbol_info.get('filters', []):
            if f['filterType'] == 'LOT_SIZE':
                self._info(f"LOT_SIZE: min={f['minQty']} step={f['stepSize']}")
            if f['filterType'] == 'MIN_NOTIONAL':
                self._info(f"MIN_NOTIONAL: {f.get('notional', f.get('minNotional', 'N/A'))}")

    async def _check_account(self, trader, needed):
        try:
            balances = await trader._request('GET', '/fapi/v2/balance', signed=True)
            for b in balances:
                if b['asset'] == 'USDT' and float(b['balance']) > 0:
                    avail = float(b['availableBalance'])
                    self._info(f"USDT Balance: {b['balance']} | Available: {b['availableBalance']}")
                    if avail >= float(needed):
                        self._ok(f"Sufficient for ${needed} margin")
                    else:
                        self._fail(f"INSUFFICIENT: Need ${needed}, have ${avail:.2f}")
                    return
            self._info("No USDT balance found")
        except Exception as e:
            self._fail(f"Balance check failed: {e}")

    async def _check_positions(self, trader, symbol):
        try:
            positions = await trader.get_open_positions()
            symbol_positions = [p for p in positions if p['symbol'] == symbol]
            if symbol_positions:
                for p in symbol_positions:
                    self._info(f"EXISTING POSITION: {symbol} qty={p['positionAmt']} pnl={p.get('unRealizedProfit', '0')}")
            else:
                self._ok(f"No open position on {symbol}")
        except Exception as e:
            self._fail(f"Position check failed: {e}")

    async def _check_open_orders(self, trader, symbol):
        try:
            orders = await trader.get_all_open_orders(symbol)
            if orders:
                for o in orders:
                    self._info(f"EXISTING ORDER: {o['type']} {o['side']} stop={o.get('stopPrice', '-')}")
            else:
                self._ok(f"No open orders on {symbol}")
        except Exception as e:
            self._fail(f"Order check failed: {e}")

    def _report_batch_result(self, result, direction, qty, symbol, price, sl, tp):
        entry = result['entry']
        avg = entry.get('avgPrice', str(price))

        entry_id = entry.get('orderId', '-')
        self._ok(f"ENTRY: {direction} {qty} {symbol} @ {avg} (ID: {entry_id})")

        if result.get('sl'):
            sl_id = result['sl'].get('orderId', '-')
            self._ok(f"SL: STOP_MARKET @ {sl} (ID: {sl_id})")
        else:
            self._fail(f"SL: FAILED in batch")

        if result.get('tp'):
            tp_id = result['tp'].get('orderId', '-')
            self._ok(f"TP: TAKE_PROFIT_MARKET @ {tp} (ID: {tp_id})")
        else:
            self._fail(f"TP: FAILED in batch")

    async def _retry_failed_orders(self, trader, batch_result, symbol, close_side, qty, sl, tp, price, symbol_info):
        if not batch_result.get('sl'):
            self._info("Retrying SL with 3-level fallback...")
            sl_result = await trader.place_stop_loss_order(symbol, close_side, qty, sl, price, symbol_info)
            if sl_result:
                self._ok(f"SL placed via {sl_result.get('method', 'fallback')} (ID: {sl_result.get('orderId')})")
            else:
                self._fail("SL FAILED all methods - POSITION UNPROTECTED!")

        if not batch_result.get('tp'):
            self._info("Retrying TP with 3-level fallback...")
            tp_result = await trader.place_take_profit_order(symbol, close_side, qty, tp, price, symbol_info)
            if tp_result:
                self._ok(f"TP placed via {tp_result.get('method', 'fallback')} (ID: {tp_result.get('orderId')})")
            else:
                self._fail("TP FAILED all methods")

    async def _place_separate(self, trader, symbol, direction, entry_side, close_side, qty, sl, tp, price, symbol_info):
        self._info(f"Placing MARKET {entry_side} {qty} {symbol}...")
        entry_result = await trader.place_market_order(symbol, entry_side, qty)
        if not entry_result:
            self._fail("Entry order FAILED")
            return

        avg = Decimal(entry_result.get('avgPrice', str(price)))
        self._ok(f"ENTRY filled: {direction} {qty} {symbol} @ {avg} (ID: {entry_result.get('orderId')})")

        self._info(f"Placing SL @ {sl}...")
        sl_result = await trader.place_stop_loss_order(symbol, close_side, qty, sl, avg, symbol_info)
        if sl_result:
            self._ok(f"SL placed via [{sl_result.get('method')}] (ID: {sl_result.get('orderId')})")
        else:
            self._fail("SL FAILED all 3 methods!")
            self._info("Closing position for safety...")
            await trader.close_position(symbol, direction, qty)
            self._ok("Position closed")
            return

        self._info(f"Placing TP @ {tp}...")
        tp_result = await trader.place_take_profit_order(symbol, close_side, qty, tp, avg, symbol_info)
        if tp_result:
            self._ok(f"TP placed via [{tp_result.get('method')}] (ID: {tp_result.get('orderId')})")
        else:
            self._fail("TP FAILED (trade has SL only)")

        self._header("TRADE COMPLETE")

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
