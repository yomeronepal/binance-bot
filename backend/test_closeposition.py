#!/usr/bin/env python3
import asyncio
import aiohttp
import hashlib
import hmac
import time
import os
import sys
from decimal import Decimal, ROUND_DOWN

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()
from django.conf import settings

API_KEY = settings.BINANCE_API_KEY
API_SECRET = settings.BINANCE_API_SECRET
BASE_URL = 'https://fapi.binance.com'


async def get_signature(query_string):
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
        params['recvWindow'] = 60000
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        params['signature'] = await get_signature(query_string)

    async with session.request(method, url, params=params, headers=headers) as resp:
        data = await resp.json()
        if resp.status != 200:
            error_msg = data.get('msg', str(data))
            raise Exception(f"Binance API error: {error_msg}")
        return data


async def test_closeposition_orders():
    async with aiohttp.ClientSession() as session:
        symbol = 'BTCUSDT'

        print("=" * 60)
        print("TEST: SL/TP with closePosition=true")
        print("=" * 60)

        price_data = await request(session, 'GET', '/fapi/v1/ticker/price', {'symbol': symbol})
        current_price = Decimal(price_data['price'])
        print(f"Current {symbol} price: ${current_price}")

        exchange_info = await request(session, 'GET', '/fapi/v1/exchangeInfo', {'symbol': symbol})
        symbol_info = exchange_info['symbols'][0]

        tick_size = Decimal('0.1')
        for f in symbol_info.get('filters', []):
            if f['filterType'] == 'PRICE_FILTER':
                tick_size = Decimal(f['tickSize'])
                break

        try:
            await request(session, 'POST', '/fapi/v1/marginType',
                         {'symbol': symbol, 'marginType': 'ISOLATED'}, signed=True)
            print("Margin: ISOLATED")
        except Exception as e:
            if 'No need' in str(e):
                print("Margin: Already ISOLATED")
            else:
                print(f"Margin warning: {e}")

        await request(session, 'POST', '/fapi/v1/leverage',
                     {'symbol': symbol, 'leverage': 10}, signed=True)
        print("Leverage: 10x")

        quantity = Decimal('0.002')
        print(f"\n--- ENTRY ORDER (LONG {quantity} BTC) ---")

        entry_params = {
            'symbol': symbol,
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': str(quantity),
        }

        entry_result = await request(session, 'POST', '/fapi/v1/order', entry_params, signed=True)
        avg_price_str = entry_result.get('avgPrice', '0')
        avg_price = Decimal(avg_price_str) if avg_price_str and Decimal(avg_price_str) > 0 else current_price
        print(f"Entry filled @ ${avg_price}")

        sl_price = avg_price * Decimal('0.97')
        sl_price = (sl_price / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size

        tp_price = avg_price * Decimal('1.05')
        tp_price = (tp_price / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size

        print(f"\n--- SL ORDER (closePosition=true) ---")
        sl_params = {
            'symbol': symbol,
            'side': 'SELL',
            'algoType': 'CONDITIONAL',
            'type': 'STOP_MARKET',
            'closePosition': 'true',
            'triggerPrice': str(sl_price),
        }

        try:
            sl_result = await request(session, 'POST', '/fapi/v1/algoOrder', sl_params, signed=True)
            sl_algo_id = sl_result.get('algoId')
            print(f"SL placed @ ${sl_price} | AlgoID: {sl_algo_id}")
        except Exception as e:
            print(f"SL failed: {e}")
            sl_algo_id = None

        print(f"\n--- TP ORDER (closePosition=true) ---")
        tp_params = {
            'symbol': symbol,
            'side': 'SELL',
            'algoType': 'CONDITIONAL',
            'type': 'TAKE_PROFIT_MARKET',
            'closePosition': 'true',
            'triggerPrice': str(tp_price),
        }

        try:
            tp_result = await request(session, 'POST', '/fapi/v1/algoOrder', tp_params, signed=True)
            tp_algo_id = tp_result.get('algoId')
            print(f"TP placed @ ${tp_price} | AlgoID: {tp_algo_id}")
        except Exception as e:
            print(f"TP failed: {e}")
            tp_algo_id = None

        print(f"\n--- ACTIVE ALGO ORDERS ---")
        algo_orders = await request(session, 'GET', '/fapi/v1/allAlgoOrders',
                                   {'symbol': symbol, 'algoStatus': 'NEW'}, signed=True)
        orders_list = algo_orders if isinstance(algo_orders, list) else algo_orders.get('rows', [])
        print(f"Found {len(orders_list)} active algo orders:")
        for order in orders_list:
            print(f"  {order.get('type')} @ {order.get('triggerPrice')} (ID: {order.get('algoId')})")

        print("\n" + "=" * 60)
        print("TEST COMPLETE!")
        print("=" * 60)
        print(f"\nPosition: LONG {quantity} {symbol} @ ${avg_price}")
        print(f"SL: ${sl_price}")
        print(f"TP: ${tp_price}")
        print("\nNow go to Binance Futures and:")
        print("1. Check that SL/TP orders show 'Close Position'")
        print("2. Close the position manually")
        print("3. Verify that SL/TP orders are auto-cancelled")


if __name__ == '__main__':
    asyncio.run(test_closeposition_orders())
