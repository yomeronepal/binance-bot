#!/usr/bin/env python3
"""
Test script to verify SL/TP order placement on Binance Futures.
Run this locally (not in Docker) to test the order flow.

Usage:
    python test_sl_tp.py

This will:
1. Open a small LONG position on BTCUSDT (0.001 BTC = ~$100)
2. Place a STOP (SL) order at 3% below entry
3. Place a TAKE_PROFIT (TP) order at 5% above entry

Check Binance Futures -> Open Orders to verify.
"""

import asyncio
import aiohttp
import hashlib
import hmac
import time
import os
from decimal import Decimal, ROUND_DOWN
from urllib.parse import urlencode

API_KEY = os.environ.get('BINANCE_API_KEY', '')
API_SECRET = os.environ.get('BINANCE_SECRET_KEY', '')

BASE_URL = 'https://fapi.binance.com'


async def get_signature(query_string: str) -> str:
    return hmac.new(
        API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


async def request(session, method, endpoint, params=None, signed=False):
    url = f"{BASE_URL}{endpoint}"
    headers = {'X-MBX-APIKEY': API_KEY}

    if params is None:
        params = {}

    if signed:
        params['timestamp'] = int(time.time() * 1000)
        params['recvWindow'] = 10000
        query_string = urlencode(params)
        params['signature'] = await get_signature(query_string)

    async with session.request(method, url, params=params, headers=headers) as resp:
        data = await resp.json()
        if resp.status != 200:
            raise Exception(f"Binance API error: {data.get('msg', data)}")
        return data


async def test_sl_tp():
    if not API_KEY or not API_SECRET:
        print("ERROR: Set BINANCE_API_KEY and BINANCE_SECRET_KEY environment variables")
        print("\nExample:")
        print("  export BINANCE_API_KEY='your_api_key'")
        print("  export BINANCE_SECRET_KEY='your_secret_key'")
        print("  python test_sl_tp.py")
        return

    async with aiohttp.ClientSession() as session:
        symbol = 'BTCUSDT'

        print("=" * 60)
        print("BINANCE SL/TP ORDER TEST")
        print("=" * 60)

        price_data = await request(session, 'GET', '/fapi/v1/ticker/price', {'symbol': symbol})
        current_price = Decimal(price_data['price'])
        print(f"\nCurrent {symbol} price: ${current_price}")

        exchange_info = await request(session, 'GET', '/fapi/v1/exchangeInfo', {'symbol': symbol})
        symbol_info = exchange_info['symbols'][0]

        tick_size = Decimal('0.01')
        for f in symbol_info.get('filters', []):
            if f['filterType'] == 'PRICE_FILTER':
                tick_size = Decimal(f['tickSize'])
                break

        print(f"Tick size: {tick_size}")

        try:
            await request(session, 'POST', '/fapi/v1/marginType',
                         {'symbol': symbol, 'marginType': 'ISOLATED'}, signed=True)
            print("Margin type set to ISOLATED")
        except Exception as e:
            if 'No need to change' in str(e):
                print("Margin type already ISOLATED")
            else:
                print(f"Margin type warning: {e}")

        await request(session, 'POST', '/fapi/v1/leverage',
                     {'symbol': symbol, 'leverage': 10}, signed=True)
        print("Leverage set to 10x")

        quantity = Decimal('0.001')
        print(f"\n--- PLACING ENTRY ORDER ---")
        print(f"Quantity: {quantity} BTC (~${float(quantity * current_price):.2f} notional)")

        entry_params = {
            'symbol': symbol,
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': str(quantity),
        }

        entry_result = await request(session, 'POST', '/fapi/v1/order', entry_params, signed=True)
        avg_price = Decimal(entry_result.get('avgPrice', str(current_price)))
        entry_order_id = entry_result.get('orderId')

        print(f"Entry FILLED at: ${avg_price}")
        print(f"Entry Order ID: {entry_order_id}")

        sl_stop_price = (avg_price * Decimal('0.97') / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size
        sl_limit_price = (sl_stop_price * Decimal('0.995') / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size

        tp_stop_price = (avg_price * Decimal('1.05') / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size
        tp_limit_price = (tp_stop_price * Decimal('0.995') / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size

        print(f"\n--- PLACING STOP LOSS ORDER ---")
        print(f"SL Stop Price: ${sl_stop_price} (triggers when price drops here)")
        print(f"SL Limit Price: ${sl_limit_price} (sells at this price or better)")

        sl_params = {
            'symbol': symbol,
            'side': 'SELL',
            'type': 'STOP',
            'quantity': str(quantity),
            'price': str(sl_limit_price),
            'stopPrice': str(sl_stop_price),
            'reduceOnly': 'true',
            'timeInForce': 'GTC',
        }

        try:
            sl_result = await request(session, 'POST', '/fapi/v1/order', sl_params, signed=True)
            print(f"SL Order ID: {sl_result.get('orderId')}")
            print(f"SL Status: {sl_result.get('status')}")
        except Exception as e:
            print(f"SL STOP order failed: {e}")
            print("Trying STOP_MARKET...")

            sl_params_market = {
                'symbol': symbol,
                'side': 'SELL',
                'type': 'STOP_MARKET',
                'quantity': str(quantity),
                'stopPrice': str(sl_stop_price),
                'reduceOnly': 'true',
                'workingType': 'MARK_PRICE',
            }
            try:
                sl_result = await request(session, 'POST', '/fapi/v1/order', sl_params_market, signed=True)
                print(f"SL (STOP_MARKET) Order ID: {sl_result.get('orderId')}")
            except Exception as e2:
                print(f"SL STOP_MARKET also failed: {e2}")

        print(f"\n--- PLACING TAKE PROFIT ORDER ---")
        print(f"TP Stop Price: ${tp_stop_price} (triggers when price rises here)")
        print(f"TP Limit Price: ${tp_limit_price} (sells at this price or better)")

        tp_params = {
            'symbol': symbol,
            'side': 'SELL',
            'type': 'TAKE_PROFIT',
            'quantity': str(quantity),
            'price': str(tp_limit_price),
            'stopPrice': str(tp_stop_price),
            'reduceOnly': 'true',
            'timeInForce': 'GTC',
        }

        try:
            tp_result = await request(session, 'POST', '/fapi/v1/order', tp_params, signed=True)
            print(f"TP Order ID: {tp_result.get('orderId')}")
            print(f"TP Status: {tp_result.get('status')}")
        except Exception as e:
            print(f"TP TAKE_PROFIT order failed: {e}")
            print("Trying TAKE_PROFIT_MARKET...")

            tp_params_market = {
                'symbol': symbol,
                'side': 'SELL',
                'type': 'TAKE_PROFIT_MARKET',
                'quantity': str(quantity),
                'stopPrice': str(tp_stop_price),
                'reduceOnly': 'true',
                'workingType': 'MARK_PRICE',
            }
            try:
                tp_result = await request(session, 'POST', '/fapi/v1/order', tp_params_market, signed=True)
                print(f"TP (TAKE_PROFIT_MARKET) Order ID: {tp_result.get('orderId')}")
            except Exception as e2:
                print(f"TP TAKE_PROFIT_MARKET also failed: {e2}")

        print("\n" + "=" * 60)
        print("TEST COMPLETE!")
        print("=" * 60)
        print("\nCheck Binance Futures -> BTCUSDT -> Open Orders")
        print("You should see:")
        print("  1. STOP order (SL) - pending")
        print("  2. TAKE_PROFIT order (TP) - pending")
        print("\nTo clean up (close position & cancel orders), run:")
        print("  python test_sl_tp.py --cleanup")


async def cleanup():
    if not API_KEY or not API_SECRET:
        print("ERROR: Set BINANCE_API_KEY and BINANCE_SECRET_KEY")
        return

    async with aiohttp.ClientSession() as session:
        symbol = 'BTCUSDT'

        print("Cancelling all orders...")
        try:
            await request(session, 'DELETE', '/fapi/v1/allOpenOrders', {'symbol': symbol}, signed=True)
            print("All orders cancelled")
        except Exception as e:
            print(f"Cancel orders error: {e}")

        print("Checking position...")
        positions = await request(session, 'GET', '/fapi/v2/positionRisk', {'symbol': symbol}, signed=True)

        for pos in positions:
            qty = Decimal(pos.get('positionAmt', '0'))
            if qty != 0:
                side = 'SELL' if qty > 0 else 'BUY'
                close_qty = abs(qty)

                print(f"Closing position: {side} {close_qty}")
                close_params = {
                    'symbol': symbol,
                    'side': side,
                    'type': 'MARKET',
                    'quantity': str(close_qty),
                    'reduceOnly': 'true',
                }
                await request(session, 'POST', '/fapi/v1/order', close_params, signed=True)
                print("Position closed")
            else:
                print("No open position")

        print("\nCleanup complete!")


if __name__ == '__main__':
    import sys

    if '--cleanup' in sys.argv:
        asyncio.run(cleanup())
    else:
        asyncio.run(test_sl_tp())
