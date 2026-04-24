"""
Binance Futures Trading Service for real trade execution.
Handles placing, monitoring, and closing futures positions.
"""
import json
import logging
import hashlib
import hmac
import time
import asyncio
import threading
from decimal import Decimal, ROUND_DOWN
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

import aiohttp
from django.conf import settings
from django.utils import timezone as dj_timezone

from ..models_futures import FuturesTradingSettings, FuturesTrade
from ..models import Signal

logger = logging.getLogger(__name__)

NEPAL_TZ_OFFSET = timedelta(hours=5, minutes=45)


def is_within_trading_window():
    """Check if current Nepal Time is within any active TradingSession."""
    from ..models import TradingSession
    nepal_now = datetime.now(timezone.utc) + NEPAL_TZ_OFFSET
    return TradingSession.get_matching_session(nepal_now) is not None


def _run_in_thread(async_fn, timeout=60):
    """
    Run an async function in a dedicated thread with its own event loop.

    Args:
        async_fn: Async callable (no arguments) to execute
        timeout: Max seconds to wait for completion

    Returns:
        Result from the async function, or None on timeout

    Raises:
        Exception from async_fn if it raised one
    """
    container = {'result': None, 'error': None}

    def target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            container['result'] = loop.run_until_complete(async_fn())
        except Exception as e:
            container['error'] = e
        finally:
            loop.close()

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=timeout)

    if container['error']:
        raise container['error']
    return container['result']


class BinanceFuturesTrader:
    """Low-level async client for Binance Futures API."""

    BASE_URL = "https://fapi.binance.com"
    TESTNET_URL = "https://testnet.binancefuture.com"
    _server_time_offset = 0
    _last_time_sync = 0

    def __init__(self, use_testnet=False):
        self.api_key = settings.BINANCE_API_KEY
        self.api_secret = settings.BINANCE_API_SECRET
        self.base_url = self.TESTNET_URL if use_testnet else self.BASE_URL
        self.session: Optional[aiohttp.ClientSession] = None

    @staticmethod
    def _sides(direction):
        """
        Return (entry_side, close_side) for a given trade direction.

        Args:
            direction: 'LONG' or 'SHORT'

        Returns:
            Tuple of (entry_side, close_side) e.g. ('BUY', 'SELL')
        """
        return ('BUY', 'SELL') if direction == 'LONG' else ('SELL', 'BUY')

    def _generate_signature(self, query_string):
        """Generate HMAC SHA256 signature for signed endpoints."""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _get_session(self):
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session

    async def _sync_server_time(self):
        """Sync local time with Binance server. Caches offset for 5 minutes."""
        now = time.time()
        if now - BinanceFuturesTrader._last_time_sync <= 300:
            return
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/fapi/v1/time") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    server_time = data.get('serverTime', 0)
                    local_time = int(time.time() * 1000)
                    BinanceFuturesTrader._server_time_offset = server_time - local_time
                    BinanceFuturesTrader._last_time_sync = now
                    logger.info(f"Synced with Binance server. Offset: {BinanceFuturesTrader._server_time_offset}ms")
        except Exception as e:
            logger.warning(f"Failed to sync server time: {e}")

    def _get_timestamp(self):
        """Get timestamp adjusted for server time offset."""
        return int(time.time() * 1000) + BinanceFuturesTrader._server_time_offset

    async def _request(self, method, endpoint, params=None, signed=False):
        """
        Make API request to Binance Futures.

        Signed POST requests send params as form-encoded body (not URL query string)
        to avoid aiohttp's yarl re-encoding the JSON in batchOrders.
        This matches how python-binance and the requests library handle Binance signing.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            signed: Whether to sign the request

        Returns:
            Parsed JSON response

        Raises:
            Exception on API error or network failure
        """
        session = await self._get_session()
        headers = {'X-MBX-APIKEY': self.api_key}
        params = params or {}

        try:
            if not signed:
                url = f"{self.base_url}{endpoint}"
                async with session.request(method, url, params=params, headers=headers) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        raise Exception(f"Binance API error: {data.get('msg', str(data))}")
                    return data

            await self._sync_server_time()
            params['timestamp'] = self._get_timestamp()
            params['recvWindow'] = 60000
            query_string = urlencode(params)
            signature = self._generate_signature(query_string)
            signed_payload = f"{query_string}&signature={signature}"
            url = f"{self.base_url}{endpoint}"

            if method == 'POST':
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                async with session.post(url, data=signed_payload, headers=headers) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        raise Exception(f"Binance API error: {data.get('msg', str(data))}")
                    return data
            else:
                full_url = f"{url}?{signed_payload}"
                async with session.request(method, full_url, headers=headers) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        raise Exception(f"Binance API error: {data.get('msg', str(data))}")
                    return data

        except aiohttp.ClientError as e:
            logger.error(f"Network error: {e}")
            raise

    async def get_account_balance(self):
        """Get futures account balance."""
        return await self._request('GET', '/fapi/v2/balance', signed=True)

    async def get_open_positions(self):
        """Get all open positions with non-zero quantity from Binance."""
        try:
            positions = await self._request('GET', '/fapi/v2/positionRisk', signed=True)
            return [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        except Exception as e:
            logger.error(f"Failed to get open positions: {e}")
            return []

    async def get_position_for_symbol(self, symbol):
        """Get open position for a specific symbol, or None."""
        try:
            positions = await self._request(
                'GET', '/fapi/v2/positionRisk', {'symbol': symbol}, signed=True
            )
            for p in positions:
                if float(p.get('positionAmt', 0)) != 0:
                    return p
            return None
        except Exception as e:
            logger.error(f"Failed to get position for {symbol}: {e}")
            return None

    async def get_trade_history(self, symbol, limit=50):
        """Get recent trade history for a symbol."""
        try:
            return await self._request(
                'GET', '/fapi/v1/userTrades',
                {'symbol': symbol, 'limit': limit}, signed=True
            )
        except Exception as e:
            logger.error(f"Failed to get trade history for {symbol}: {e}")
            return []

    async def get_income_history(self, symbol=None, income_type=None, limit=100):
        """
        Get income history (realized PnL, funding fees, etc).

        Args:
            symbol: Filter by symbol (optional)
            income_type: REALIZED_PNL, FUNDING_FEE, COMMISSION, etc. (optional)
            limit: Max records to return
        """
        try:
            params = {'limit': limit}
            if symbol:
                params['symbol'] = symbol
            if income_type:
                params['incomeType'] = income_type
            return await self._request('GET', '/fapi/v1/income', params, signed=True)
        except Exception as e:
            logger.error(f"Failed to get income history: {e}")
            return []

    async def get_all_open_orders(self, symbol=None):
        """Get all open orders, optionally filtered by symbol."""
        try:
            params = {'symbol': symbol} if symbol else {}
            return await self._request('GET', '/fapi/v1/openOrders', params, signed=True)
        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return []

    async def get_symbol_info(self, symbol):
        """Get symbol trading rules (precision, min qty, tick size, etc)."""
        try:
            exchange_info = await self._request('GET', '/fapi/v1/exchangeInfo')
            for s in exchange_info.get('symbols', []):
                if s['symbol'] == symbol:
                    return s
            return None
        except Exception as e:
            logger.error(f"Failed to get symbol info for {symbol}: {e}")
            return None

    async def get_current_price(self, symbol):
        """Get current market price for symbol."""
        try:
            data = await self._request('GET', '/fapi/v1/ticker/price', {'symbol': symbol})
            return Decimal(data['price'])
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None

    async def set_leverage(self, symbol, leverage):
        """Set leverage for a symbol."""
        try:
            await self._request(
                'POST', '/fapi/v1/leverage',
                {'symbol': symbol, 'leverage': leverage}, signed=True
            )
            logger.info(f"Set leverage for {symbol} to {leverage}x")
            return True
        except Exception as e:
            logger.error(f"Failed to set leverage for {symbol}: {e}")
            return False

    async def set_margin_type(self, symbol, margin_type='ISOLATED'):
        """Set margin type (ISOLATED or CROSSED)."""
        try:
            await self._request(
                'POST', '/fapi/v1/marginType',
                {'symbol': symbol, 'marginType': margin_type}, signed=True
            )
            logger.info(f"Set margin type for {symbol} to {margin_type}")
            return True
        except Exception as e:
            if 'No need to change margin type' in str(e):
                return True
            logger.error(f"Failed to set margin type for {symbol}: {e}")
            return False

    def _get_price_precision(self, symbol_info):
        """
        Get tick size and price precision from symbol info.

        Returns:
            Tuple of (tick_size, precision_digits)
        """
        for f in symbol_info.get('filters', []):
            if f['filterType'] == 'PRICE_FILTER':
                tick_size = Decimal(f['tickSize'])
                tick_str = f['tickSize'].rstrip('0').rstrip('.')
                precision = len(tick_str.split('.')[1]) if '.' in tick_str else 0
                return tick_size, precision
        return Decimal('0.01'), 2

    def _round_price(self, price, symbol_info):
        """Round price down to symbol's tick size precision."""
        tick_size, precision = self._get_price_precision(symbol_info)
        steps = (price / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN)
        return (steps * tick_size).quantize(Decimal(10) ** -precision)

    def _round_sl_tp(self, sl, tp, symbol_info):
        """
        Round SL and TP to symbol tick size. No recalculation — signal values preserved.

        Args:
            sl: Stop loss price from signal
            tp: Take profit price from signal
            symbol_info: Binance symbol info for tick size

        Returns:
            Tuple of (sl_rounded, tp_rounded)
        """
        return self._round_price(sl, symbol_info), self._round_price(tp, symbol_info)

    def _log_sl_tp_warnings(self, direction, sl, tp, reference_price):
        """Log warnings if SL/TP appear on the wrong side of reference price."""
        if direction == 'LONG':
            if sl >= reference_price:
                logger.warning(f"SL ({sl}) >= entry ({reference_price}) for LONG — using signal value as-is")
            if tp <= reference_price:
                logger.warning(f"TP ({tp}) <= entry ({reference_price}) for LONG — using signal value as-is")
        else:
            if sl <= reference_price:
                logger.warning(f"SL ({sl}) <= entry ({reference_price}) for SHORT — using signal value as-is")
            if tp >= reference_price:
                logger.warning(f"TP ({tp}) >= entry ({reference_price}) for SHORT — using signal value as-is")

    def _calculate_quantity(self, symbol_info, price, position_size_usdt, leverage):
        """
        Calculate order quantity based on position size and symbol precision rules.

        Args:
            symbol_info: Binance symbol info dict
            price: Entry price for calculation
            position_size_usdt: Margin amount in USDT
            leverage: Leverage multiplier

        Returns:
            Properly rounded quantity Decimal
        """
        min_qty = Decimal('0.001')
        step_size = Decimal('0.001')
        quantity_precision = int(symbol_info.get('quantityPrecision', 3))

        for f in symbol_info.get('filters', []):
            if f['filterType'] == 'LOT_SIZE':
                min_qty = Decimal(f['minQty'])
                step_size = Decimal(f['stepSize'])
                break

        raw_quantity = (position_size_usdt * leverage) / price
        steps = (raw_quantity / step_size).quantize(Decimal('1'), rounding=ROUND_DOWN)
        quantity = max(steps * step_size, min_qty)
        return quantity.quantize(Decimal(10) ** -quantity_precision)

    async def place_entry_order(self, symbol, side, quantity, price=None):
        """
        Place entry order using signal's price.

        Strategy: LIMIT IOC at signal price (fills immediately or cancels),
        falls back to MARKET if IOC doesn't fill.

        Args:
            symbol: Trading pair
            side: BUY or SELL
            quantity: Order quantity
            price: Signal entry price for LIMIT order, None for MARKET
        """
        if price:
            result = await self._place_limit_ioc(symbol, side, quantity, price)
            if result and self._order_filled(result):
                logger.info(f"Entry filled via LIMIT IOC: {side} {quantity} {symbol} @ {price}")
                return result
            logger.warning(
                f"LIMIT IOC {'not filled' if result else 'failed'} at {price}, "
                f"falling back to MARKET (status={result.get('status', 'N/A') if result else 'None'})"
            )

        logger.info(f"Placing MARKET entry: {side} {quantity} {symbol}")
        try:
            params = {
                'symbol': symbol, 'side': side, 'type': 'MARKET',
                'quantity': str(quantity),
            }
            result = await self._request('POST', '/fapi/v1/order', params, signed=True)
            logger.info(
                f"MARKET entry result: {side} {quantity} {symbol} | "
                f"status={result.get('status')} avgPrice={result.get('avgPrice')} "
                f"executedQty={result.get('executedQty')}"
            )
            return result
        except Exception as e:
            logger.error(f"MARKET entry FAILED: {side} {quantity} {symbol} | {e}")
            return None

    async def _place_limit_ioc(self, symbol, side, quantity, price):
        """Place LIMIT IOC order — fills immediately at signal price or cancels."""
        params = {
            'symbol': symbol, 'side': side, 'type': 'LIMIT',
            'price': str(price), 'quantity': str(quantity), 'timeInForce': 'IOC',
        }
        try:
            result = await self._request('POST', '/fapi/v1/order', params, signed=True)
            logger.info(
                f"LIMIT IOC response: {side} {symbol} @ {price} | "
                f"status={result.get('status')} executedQty={result.get('executedQty')}"
            )
            return result
        except Exception as e:
            logger.warning(f"LIMIT IOC failed: {e}")
            return None

    def _order_filled(self, result):
        """Check if an order result indicates a fill (full or partial)."""
        if not result:
            return False
        status = result.get('status', '')
        executed_qty = float(result.get('executedQty', 0))
        return status == 'FILLED' or executed_qty > 0

    async def place_market_order(self, symbol, side, quantity, reduce_only=False):
        """
        Place a market order (used for closing positions).

        Args:
            symbol: Trading pair
            side: BUY or SELL
            quantity: Order quantity
            reduce_only: If True, only reduces existing position
        """
        params = {
            'symbol': symbol, 'side': side, 'type': 'MARKET',
            'quantity': str(quantity),
        }
        if reduce_only:
            params['reduceOnly'] = 'true'

        try:
            result = await self._request('POST', '/fapi/v1/order', params, signed=True)
            logger.info(f"Market order placed: {side} {quantity} {symbol}")
            return result
        except Exception as e:
            logger.error(f"Failed to place market order: {e}")
            return None

    async def _place_with_quantity(self, symbol, side, quantity, stop_price, order_type, label):
        """
        Place conditional order with explicit quantity + reduceOnly.

        Args:
            symbol: Trading pair
            side: BUY or SELL
            quantity: Position quantity
            stop_price: Trigger price
            order_type: STOP_MARKET or TAKE_PROFIT_MARKET
            label: SL or TP for logging
        """
        params = {
            'symbol': symbol, 'side': side, 'type': order_type,
            'quantity': str(quantity), 'stopPrice': str(stop_price),
            'reduceOnly': 'true', 'workingType': 'MARK_PRICE', 'priceProtect': 'true',
        }
        try:
            result = await self._request('POST', '/fapi/v1/order', params, signed=True)
            order_id = result.get('orderId')
            logger.info(f"[QTY] {label} placed: {side} {quantity} {symbol} @ {stop_price} | OrderID: {order_id}")
            return {'orderId': str(order_id), 'method': 'quantity', **result}
        except Exception as e:
            logger.warning(f"[QTY] {label} failed for {symbol}: {e}")
            return None

    async def _place_with_close_position(self, symbol, side, stop_price, order_type, label):
        """
        Place conditional order with closePosition=true (no quantity needed).

        Args:
            symbol: Trading pair
            side: BUY or SELL
            stop_price: Trigger price
            order_type: STOP_MARKET or TAKE_PROFIT_MARKET
            label: SL or TP for logging
        """
        params = {
            'symbol': symbol, 'side': side, 'type': order_type,
            'closePosition': 'true', 'stopPrice': str(stop_price),
            'workingType': 'MARK_PRICE', 'priceProtect': 'true',
        }
        try:
            result = await self._request('POST', '/fapi/v1/order', params, signed=True)
            order_id = result.get('orderId')
            logger.info(f"[CLOSE_POS] {label} placed: {side} {symbol} @ {stop_price} | OrderID: {order_id}")
            return {'orderId': str(order_id), 'method': 'closePosition', **result}
        except Exception as e:
            logger.warning(f"[CLOSE_POS] {label} failed for {symbol}: {e}")
            return None

    async def _place_with_algo(self, symbol, side, stop_price, order_type, label):
        """
        Place conditional order via algo endpoint (last resort).

        Args:
            symbol: Trading pair
            side: BUY or SELL
            stop_price: Trigger price
            order_type: STOP_MARKET or TAKE_PROFIT_MARKET
            label: SL or TP for logging
        """
        params = {
            'symbol': symbol, 'side': side, 'algoType': 'CONDITIONAL',
            'type': order_type, 'closePosition': 'true', 'triggerPrice': str(stop_price),
        }
        try:
            result = await self._request('POST', '/fapi/v1/algoOrder', params, signed=True)
            algo_id = result.get('algoId')
            logger.info(f"[ALGO] {label} placed: {side} {symbol} @ {stop_price} | AlgoID: {algo_id}")
            return {'orderId': str(algo_id), 'algoId': algo_id, 'method': 'algo', **result}
        except Exception as e:
            logger.error(f"[ALGO] {label} ALSO failed for {symbol}: {e}")
            return None

    async def _place_conditional_with_fallback(self, symbol, side, quantity, trigger_price,
                                                order_type, label, methods):
        """
        Place a conditional order (SL/TP) trying multiple methods in order.

        Args:
            symbol: Trading pair
            side: BUY or SELL
            quantity: Position quantity
            trigger_price: Trigger price for the order
            order_type: STOP_MARKET or TAKE_PROFIT_MARKET
            label: SL or TP for logging
            methods: Ordered list of methods to try ('algo', 'quantity', 'close_position')

        Returns:
            Order result dict or None if all methods fail
        """
        if trigger_price <= 0:
            logger.error(f"{label} price is {trigger_price}, cannot place order")
            return None

        logger.info(f"Placing {label}: {symbol} {side} {order_type} @ {trigger_price}")

        dispatch = {
            'algo': lambda: self._place_with_algo(symbol, side, trigger_price, order_type, label),
            'quantity': lambda: self._place_with_quantity(symbol, side, quantity, trigger_price, order_type, label),
            'close_position': lambda: self._place_with_close_position(symbol, side, trigger_price, order_type, label),
        }

        for method in methods:
            result = await dispatch[method]()
            if result:
                return result

        logger.error(f"ALL {label} methods FAILED for {symbol} {side} @ {trigger_price}")
        return None

    async def place_stop_loss_order(self, symbol, side, quantity, stop_price,
                                     current_price=None, symbol_info=None):
        """
        Place a stop loss order with 3-level fallback: algo -> quantity -> closePosition.
        Signal's SL value is used directly (no recalculation).

        Args:
            symbol: Trading pair
            side: BUY or SELL
            quantity: Position quantity
            stop_price: Stop loss trigger price from signal
            current_price: Unused, kept for backward compatibility
            symbol_info: Symbol info for price rounding (optional)
        """
        if symbol_info:
            stop_price = self._round_price(stop_price, symbol_info)
        return await self._place_conditional_with_fallback(
            symbol, side, quantity, stop_price, 'STOP_MARKET', 'SL',
            ['algo', 'quantity', 'close_position']
        )

    async def place_take_profit_order(self, symbol, side, quantity, take_profit_price,
                                       current_price=None, symbol_info=None):
        """
        Place a take profit order with 3-level fallback: quantity -> closePosition -> algo.
        Signal's TP value is used directly (no recalculation).

        Args:
            symbol: Trading pair
            side: BUY or SELL
            quantity: Position quantity
            take_profit_price: Take profit trigger price from signal
            current_price: Unused, kept for backward compatibility
            symbol_info: Symbol info for price rounding (optional)
        """
        if symbol_info:
            take_profit_price = self._round_price(take_profit_price, symbol_info)
        return await self._place_conditional_with_fallback(
            symbol, side, quantity, take_profit_price, 'TAKE_PROFIT_MARKET', 'TP',
            ['quantity', 'close_position', 'algo']
        )

    async def place_trailing_stop_order(self, symbol, side, quantity, callback_rate,
                                         activation_price=None):
        """
        Place a trailing stop market order.

        Args:
            symbol: Trading pair
            side: SELL for LONG positions, BUY for SHORT positions
            quantity: Position quantity
            callback_rate: Callback rate in percentage (0.1 to 5.0)
            activation_price: Price at which trailing stop activates (optional)
        """
        params = {
            'symbol': symbol, 'side': side, 'type': 'TRAILING_STOP_MARKET',
            'quantity': str(quantity), 'callbackRate': str(callback_rate),
            'reduceOnly': 'true',
        }
        if activation_price:
            params['activationPrice'] = str(activation_price)

        try:
            result = await self._request('POST', '/fapi/v1/order', params, signed=True)
            logger.info(
                f"Trailing stop placed: {side} {quantity} {symbol} "
                f"(callback: {callback_rate}%, activation: {activation_price or 'immediate'})"
            )
            return result
        except Exception as e:
            logger.error(f"Failed to place trailing stop order: {e}")
            return None

    async def cancel_all_orders(self, symbol):
        """Cancel all open orders for a symbol (both regular and algo)."""
        success = True

        try:
            await self._request('DELETE', '/fapi/v1/allOpenOrders', {'symbol': symbol}, signed=True)
            logger.info(f"Regular orders cancelled for {symbol}")
        except Exception as e:
            logger.warning(f"Failed to cancel regular orders for {symbol}: {e}")
            success = False

        try:
            algo_orders = await self._request(
                'GET', '/fapi/v1/allAlgoOrders',
                {'symbol': symbol, 'algoStatus': 'NEW'}, signed=True
            )
            orders_list = algo_orders if isinstance(algo_orders, list) else algo_orders.get('rows', [])
            for order in orders_list:
                algo_id = order.get('algoId')
                if not algo_id:
                    continue
                try:
                    await self._request(
                        'DELETE', '/fapi/v1/algoOrder',
                        {'symbol': symbol, 'algoId': algo_id}, signed=True
                    )
                    logger.info(f"Cancelled algo order {algo_id} for {symbol}")
                except Exception as e:
                    logger.warning(f"Failed to cancel algo order {algo_id}: {e}")
        except Exception as e:
            logger.warning(f"Failed to cancel algo orders for {symbol}: {e}")

        return success

    async def close_position(self, symbol, direction, quantity):
        """Close an open position with a reduce-only market order."""
        side = 'SELL' if direction == 'LONG' else 'BUY'
        return await self.place_market_order(symbol, side, quantity, reduce_only=True)

    async def _fetch_market_data(self, signal_id, symbol_name):
        """
        Fetch symbol info and current price from Binance.

        Args:
            signal_id: Signal ID for error logging
            symbol_name: Trading pair

        Returns:
            Dict with 'symbol_info' and 'current_price', or None on failure
        """
        try:
            symbol_info = await self.get_symbol_info(symbol_name)
            if not symbol_info:
                raise Exception(f"Could not get symbol info for {symbol_name}")

            current_price = await self.get_current_price(symbol_name)
            if not current_price:
                raise Exception(f"Could not get current price for {symbol_name}")

            return {'symbol_info': symbol_info, 'current_price': current_price}
        except Exception as e:
            logger.error(f"Failed to get market data for signal {signal_id}: {e}")
            return None

    async def place_batch_orders(self, symbol, direction, quantity, sl_price, tp_price,
                                  entry_price=None):
        """
        Place entry + SL + TP in a single batch API call.
        Uses LIMIT at signal entry when provided, else MARKET.

        Args:
            symbol: Trading pair
            direction: LONG or SHORT
            quantity: Position quantity
            sl_price: Stop loss trigger price
            tp_price: Take profit trigger price
            entry_price: Signal entry price for LIMIT order (None = MARKET)

        Returns:
            Dict with entry/sl/tp order results or None
        """
        entry_side, close_side = self._sides(direction)

        if entry_price:
            entry_order = {
                'symbol': symbol, 'side': entry_side, 'type': 'LIMIT',
                'price': str(entry_price), 'quantity': str(quantity), 'timeInForce': 'GTC',
            }
        else:
            entry_order = {
                'symbol': symbol, 'side': entry_side, 'type': 'MARKET',
                'quantity': str(quantity),
            }

        logger.info(f"[BATCH] Entry: {entry_order['type']} {entry_side} {quantity} {symbol}"
                     + (f" @ {entry_price}" if entry_price else ""))

        sl_tp_base = {
            'symbol': symbol, 'side': close_side, 'quantity': str(quantity),
            'reduceOnly': 'true', 'workingType': 'MARK_PRICE', 'priceProtect': 'true',
        }

        orders = [
            entry_order,
            {**sl_tp_base, 'type': 'STOP_MARKET', 'stopPrice': str(sl_price)},
            {**sl_tp_base, 'type': 'TAKE_PROFIT_MARKET', 'stopPrice': str(tp_price)},
        ]

        batch_json = json.dumps(orders, separators=(',', ':'))
        logger.info(f"[BATCH] Payload: {batch_json[:200]}...")

        try:
            results = await self._request(
                'POST', '/fapi/v1/batchOrders',
                {'batchOrders': batch_json}, signed=True
            )
            return self._parse_batch_response(results, direction, quantity, symbol)
        except Exception as e:
            logger.warning(f"[BATCH] Batch order failed: {e}")
            return None

    def _parse_batch_response(self, results, direction, quantity, symbol):
        """
        Parse raw Binance batch order response into structured result.

        Args:
            results: List of order results from batch API
            direction: LONG or SHORT
            quantity: Position quantity
            symbol: Trading pair

        Returns:
            Dict with entry/sl/tp results, or None if entry failed
        """
        entry_res = results[0] if len(results) > 0 else None
        sl_res = results[1] if len(results) > 1 else None
        tp_res = results[2] if len(results) > 2 else None

        def is_ok(res):
            return res and 'orderId' in res and 'code' not in res

        entry_ok, sl_ok, tp_ok = is_ok(entry_res), is_ok(sl_res), is_ok(tp_res)

        if entry_ok:
            logger.info(
                f"[BATCH] Entry filled: {direction} {quantity} {symbol} "
                f"@ {entry_res.get('avgPrice', 'market')} | "
                f"SL: {'OK' if sl_ok else 'FAILED'} | TP: {'OK' if tp_ok else 'FAILED'}"
            )

        if not sl_ok and sl_res:
            logger.error(f"[BATCH] SL error: code={sl_res.get('code')} msg={sl_res.get('msg')}")
        if not tp_ok and tp_res:
            logger.error(f"[BATCH] TP error: code={tp_res.get('code')} msg={tp_res.get('msg')}")

        if not entry_ok:
            error_msg = entry_res.get('msg', str(entry_res)) if entry_res else 'No response'
            logger.error(f"[BATCH] Entry failed: {error_msg}")
            return None

        return {
            'entry': entry_res,
            'sl': sl_res if sl_ok else None,
            'tp': tp_res if tp_ok else None,
            'method': 'batch',
        }

    async def _resolve_entry_price(self, entry_result, symbol, fallback_price):
        """
        Extract actual fill price from an entry order result.
        Falls back to fetching order details, then to the provided fallback.

        Args:
            entry_result: Order result dict from Binance
            symbol: Trading pair (for order detail fetch)
            fallback_price: Price to use if avgPrice unavailable

        Returns:
            Actual fill price as Decimal
        """
        raw_avg = entry_result.get('avgPrice', '0')
        avg_price = Decimal(raw_avg) if raw_avg and Decimal(raw_avg) > 0 else Decimal('0')

        if avg_price <= 0:
            order_id = entry_result.get('orderId')
            if order_id:
                try:
                    detail = await self._request(
                        'GET', '/fapi/v1/order',
                        {'symbol': symbol, 'orderId': order_id}, signed=True
                    )
                    fetched = detail.get('avgPrice', '0')
                    if fetched and Decimal(fetched) > 0:
                        avg_price = Decimal(fetched)
                        logger.info(f"Fetched avgPrice from order {order_id}: {avg_price}")
                except Exception as e:
                    logger.warning(f"Failed to fetch order details: {e}")

        if avg_price <= 0:
            avg_price = fallback_price
            logger.warning(f"Using fallback price {fallback_price} (avgPrice was {raw_avg})")

        return avg_price

    async def _retry_failed_sl_tp(self, batch_result, symbol, direction, quantity,
                                    sl_rounded, tp_rounded, symbol_info):
        """
        Retry SL/TP orders that failed in batch placement.

        Args:
            batch_result: Result from place_batch_orders
            symbol: Trading pair
            direction: LONG or SHORT
            quantity: Position quantity
            sl_rounded: Rounded SL price
            tp_rounded: Rounded TP price
            symbol_info: Symbol info for rounding

        Returns:
            Tuple of (sl_order_id, tp_order_id, warnings_list)
        """
        _, close_side = self._sides(direction)
        warnings = []
        sl_order_id = None
        tp_order_id = None

        if batch_result.get('sl'):
            sl_order_id = str(batch_result['sl'].get('orderId', ''))
        else:
            logger.warning(f"SL failed in batch for {symbol}, retrying separately...")
            sl_result = await self.place_stop_loss_order(
                symbol, close_side, quantity, sl_rounded, symbol_info=symbol_info
            )
            if sl_result:
                sl_order_id = str(sl_result.get('orderId', ''))
            else:
                warnings.append("SL failed in batch and separate retry")

        if batch_result.get('tp'):
            tp_order_id = str(batch_result['tp'].get('orderId', ''))
        else:
            logger.warning(f"TP failed in batch for {symbol}, retrying separately...")
            tp_result = await self.place_take_profit_order(
                symbol, close_side, quantity, tp_rounded, symbol_info=symbol_info
            )
            if tp_result:
                tp_order_id = str(tp_result.get('orderId', ''))
            else:
                warnings.append("TP failed in batch and all 3 separate retries")

        return sl_order_id, tp_order_id, warnings

    def _build_trade_result(self, quantity, entry_price, order_id,
                             sl_order_id, tp_order_id, sl_price, tp_price, warnings):
        """
        Build standardized trade result dict.

        Returns:
            Dict with all trade execution details
        """
        return {
            'quantity': quantity,
            'entry_price': entry_price,
            'order_id': str(order_id),
            'sl_order_id': sl_order_id,
            'tp_order_id': tp_order_id,
            'sl_price': str(sl_price),
            'tp_price': str(tp_price),
            'warnings': warnings,
        }

    async def place_trade_orders(self, symbol, direction, leverage, position_size,
                                  sl, tp, symbol_info, current_price, signal_entry=None):
        """
        Place entry + SL + TP on Binance using signal's exact prices.

        Uses LIMIT at signal entry when provided, else MARKET.
        SL/TP from signal are only rounded to tick size, never recalculated.

        Args:
            symbol: Trading pair
            direction: LONG or SHORT
            leverage: Leverage multiplier
            position_size: Margin amount in USDT
            sl: Stop loss from signal
            tp: Take profit from signal
            symbol_info: Binance symbol info
            current_price: Current market price (fallback)
            signal_entry: Signal's entry price for LIMIT order (optional)
        """
        entry_price = signal_entry or current_price
        logger.info(
            f"TRADE START: {symbol} {direction} | Margin: ${position_size} | Leverage: {leverage}x | "
            f"Signal Entry: ${entry_price} | Market: ${current_price} | SL: ${sl} | TP: ${tp}"
        )

        try:
            await self.set_margin_type(symbol, 'ISOLATED')
            await self.set_leverage(symbol, leverage)

            quantity = self._calculate_quantity(symbol_info, entry_price, position_size, leverage)
            logger.info(f"Quantity: {quantity} {symbol} (Notional: ${float(quantity) * float(entry_price):.2f})")

            self._log_sl_tp_warnings(direction, sl, tp, entry_price)
            sl_rounded, tp_rounded = self._round_sl_tp(sl, tp, symbol_info)
            entry_rounded = self._round_price(entry_price, symbol_info) if signal_entry else None
            logger.info(f"Rounded — Entry={entry_rounded}, SL={sl_rounded}, TP={tp_rounded}")

            batch_result = await self.place_batch_orders(
                symbol, direction, quantity, sl_rounded, tp_rounded, entry_price=entry_rounded
            )

            if batch_result and batch_result.get('entry'):
                return await self._handle_batch_result(
                    batch_result, quantity, entry_price, sl_rounded, tp_rounded,
                    symbol, direction, symbol_info
                )

            logger.warning(f"Batch failed for {symbol}, falling back to separate orders...")
            return await self._place_separate_orders(
                symbol, direction, quantity, sl_rounded, tp_rounded,
                entry_price, symbol_info, entry_rounded
            )

        except Exception as e:
            logger.error(f"Failed to place orders for {symbol}: {e}")
            raise

    async def _handle_batch_result(self, batch_result, quantity, fallback_price,
                                     sl_rounded, tp_rounded, symbol, direction, symbol_info):
        """
        Process successful batch order: resolve fill price and retry any failed SL/TP.

        Args:
            batch_result: Result from place_batch_orders
            quantity: Position quantity
            fallback_price: Price fallback if avgPrice unavailable
            sl_rounded: Rounded SL price
            tp_rounded: Rounded TP price
            symbol: Trading pair
            direction: LONG or SHORT
            symbol_info: Symbol info for SL/TP retry rounding
        """
        entry = batch_result['entry']
        avg_price = await self._resolve_entry_price(entry, symbol, fallback_price)

        sl_order_id, tp_order_id, warnings = await self._retry_failed_sl_tp(
            batch_result, symbol, direction, quantity, sl_rounded, tp_rounded, symbol_info
        )

        logger.info(
            f"Trade opened [BATCH]: {direction} {quantity} {symbol} @ {avg_price} "
            f"(SL: {sl_rounded}, TP: {tp_rounded})"
        )

        return self._build_trade_result(
            quantity, avg_price, entry.get('orderId', ''),
            sl_order_id, tp_order_id, sl_rounded, tp_rounded, warnings
        )

    async def _place_separate_orders(self, symbol, direction, quantity, sl_rounded, tp_rounded,
                                      fallback_price, symbol_info, entry_price=None):
        """
        Fallback: Place entry first (IOC LIMIT -> MARKET), then SL/TP after confirmed fill.

        Args:
            symbol: Trading pair
            direction: LONG or SHORT
            quantity: Order quantity
            sl_rounded: Signal SL price (rounded to tick size)
            tp_rounded: Signal TP price (rounded to tick size)
            fallback_price: Fallback if fill price unavailable
            symbol_info: Symbol info for SL/TP rounding
            entry_price: Signal entry price for LIMIT order (None = MARKET)
        """
        entry_side, close_side = self._sides(direction)

        entry_result = await self.place_entry_order(symbol, entry_side, quantity, entry_price)

        if not entry_result:
            raise Exception("Entry order failed — Binance returned no result")

        status = entry_result.get('status', 'UNKNOWN')
        exec_qty = entry_result.get('executedQty', '0')
        logger.info(f"Entry response [SEPARATE]: status={status} executedQty={exec_qty} orderId={entry_result.get('orderId')}")

        if not self._order_filled(entry_result):
            raise Exception(f"Entry not filled — status={status}, executedQty={exec_qty}")

        avg_price = Decimal(
            entry_result.get('avgPrice') or entry_result.get('price') or str(fallback_price)
        )
        if avg_price <= 0:
            avg_price = fallback_price

        logger.info(f"Entry filled [SEPARATE]: {direction} {exec_qty} {symbol} @ {avg_price}")

        warnings = []

        sl_result = await self.place_stop_loss_order(
            symbol, close_side, quantity, sl_rounded, symbol_info=symbol_info
        )
        if not sl_result:
            logger.error(f"CRITICAL: SL failed for {symbol}! Closing position.")
            await self.close_position(symbol, direction, quantity)
            raise Exception(f"SL could not be placed on {symbol}. Entry reversed.")

        tp_result = await self.place_take_profit_order(
            symbol, close_side, quantity, tp_rounded, symbol_info=symbol_info
        )
        if not tp_result:
            warnings.append(f"TP failed - only SL active at {sl_rounded}")

        logger.info(
            f"Trade opened [SEPARATE]: {direction} {quantity} {symbol} @ {avg_price} "
            f"(SL: {sl_rounded}, TP: {tp_rounded})"
        )

        return self._build_trade_result(
            quantity, avg_price, entry_result.get('orderId', ''),
            str(sl_result.get('orderId', '')) if sl_result else None,
            str(tp_result.get('orderId', '')) if tp_result else None,
            sl_rounded, tp_rounded, warnings
        )

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()


class FuturesTradingService:
    """High-level service bridging sync Django code with async Binance API calls."""

    def __init__(self, use_testnet=False):
        self.use_testnet = use_testnet

    def _log(self, action, level, message, signal=None, trade=None,
             symbol='', direction='', is_priority=False, force_execute=False, details=None):
        """Write a FuturesTradeLog entry."""
        try:
            from ..models_futures import FuturesTradeLog
            FuturesTradeLog.objects.create(
                signal=signal, trade=trade, action=action, level=level,
                symbol=symbol, direction=direction, is_priority=is_priority,
                force_execute=force_execute, message=message, details=details or {},
            )
        except Exception as e:
            logger.error(f"Failed to write trade log: {e}")

    def _check_trading_window(self, signal, trade_settings, log_ctx, force_execute):
        """
        Check if signal is within trading window or has override.

        Returns:
            True if trading is allowed, False if blocked
        """
        if force_execute:
            logger.info(f"Signal {signal.id} force_execute=True, bypassing trading window check")
            self._log('CHECK_PASSED', 'INFO', "force_execute=True, bypassing trading window", **log_ctx)
            return True

        if not trade_settings.use_trading_window:
            return True

        nepal_now = datetime.now(timezone.utc) + NEPAL_TZ_OFFSET
        day_minutes = nepal_now.hour * 60 + nepal_now.minute
        is_gw2 = (1260 <= day_minutes < 1380) and (nepal_now.weekday() in [6, 2, 3])

        in_window = is_within_trading_window()
        gw2_override = trade_settings.trade_on_golden_window_2 and is_gw2

        if not in_window and not gw2_override:
            msg = f"Outside trading window (in_window={in_window}, gw2={is_gw2})"
            logger.info(f"Signal {signal.id} {msg}")
            self._log('CHECK_FAILED', 'WARNING', msg, **log_ctx)
            return False

        if gw2_override and not in_window:
            logger.info(f"Signal {signal.id} is GW2 (Override)")

        return True

    def _check_fear_greed(self, signal, trade_settings, direction, is_neutral_reversal, log_ctx):
        """
        Check Fear & Greed filter.

        Returns:
            True if trading is allowed, False if blocked by F&G
        """
        if not trade_settings.fear_greed_enabled:
            return True

        from .fear_greed import get_fear_greed_value, check_direction_allowed

        fg_value = get_fear_greed_value()
        if fg_value is None:
            logger.warning(f"Signal {signal.id}: F&G unavailable, proceeding without filter")
            return True

        if is_neutral_reversal:
            self._log('CHECK_PASSED', 'INFO',
                      f"F&G={fg_value}: Signal already reversed at creation, proceeding",
                      details={'fg_value': fg_value}, **log_ctx)
            return True

        fg_allowed, fg_reason = check_direction_allowed(
            direction, fg_value,
            trade_settings.fear_greed_short_threshold,
            trade_settings.fear_greed_long_threshold
        )

        if not fg_allowed:
            logger.info(f"Signal {signal.id} blocked by F&G filter: {fg_reason}")
            self._log('CHECK_FAILED', 'WARNING', f"F&G blocked: {fg_reason}",
                      details={'fg_value': fg_value}, **log_ctx)
            return False

        self._log('CHECK_PASSED', 'INFO', f"F&G passed: {fg_reason}",
                  details={'fg_value': fg_value}, **log_ctx)
        return True

    def _check_duplicates(self, signal, symbol_name, direction, log_ctx):
        """
        Check for duplicate trades or existing open positions.

        Returns:
            True if no duplicates, False if blocked
        """
        if FuturesTrade.objects.filter(signal=signal).exists():
            msg = "Duplicate: FuturesTrade already exists for this signal"
            logger.info(f"Signal {signal.id} {msg}")
            self._log('CHECK_FAILED', 'WARNING', msg, **log_ctx)
            return False

        if FuturesTrade.objects.filter(symbol=symbol_name, direction=direction, status='OPEN').exists():
            msg = f"Already have open {direction} position on {symbol_name}"
            logger.info(msg)
            self._log('CHECK_FAILED', 'WARNING', msg, **log_ctx)
            return False

        return True

    def _run_pre_trade_checks(self, signal, trade_settings, log_ctx, force_execute):
        """
        Run all pre-trade validation checks.

        Args:
            signal: Signal instance
            trade_settings: FuturesTradingSettings instance
            log_ctx: Logging context dict
            force_execute: Whether to bypass window checks

        Returns:
            True if all checks pass, False otherwise
        """
        symbol_name = signal.symbol.symbol
        direction = signal.direction
        confidence = signal.confidence

        if not trade_settings.is_enabled:
            logger.warning(f"Futures trading is DISABLED, skipping signal {signal.id}")
            self._log('CHECK_FAILED', 'WARNING', "Futures trading is DISABLED in settings", **log_ctx)
            return False

        if not self._check_trading_window(signal, trade_settings, log_ctx, force_execute):
            return False

        can_trade, reason = trade_settings.can_trade(symbol_name, direction, confidence)
        if not can_trade:
            logger.warning(f"Cannot trade signal {signal.id}: {reason}")
            self._log('CHECK_FAILED', 'WARNING', f"can_trade failed: {reason}", **log_ctx)
            return False

        is_neutral_reversal = bool(
            isinstance(getattr(signal, 'meta', None), dict) and
            signal.meta.get('neutral_reversal')
        )

        if not self._check_fear_greed(signal, trade_settings, direction, is_neutral_reversal, log_ctx):
            return False

        if not self._check_duplicates(signal, symbol_name, direction, log_ctx):
            return False

        return True

    def _create_futures_trade(self, signal, result, trade_settings, trade_sl, trade_tp):
        """
        Create FuturesTrade record from API result.

        Args:
            signal: Signal instance
            result: Dict from place_trade_orders
            trade_settings: FuturesTradingSettings instance
            trade_sl: Signal SL (fallback)
            trade_tp: Signal TP (fallback)

        Returns:
            FuturesTrade instance
        """
        warnings_text = "; ".join(result.get('warnings', []))
        return FuturesTrade.objects.create(
            signal=signal,
            symbol=signal.symbol.symbol,
            direction=signal.direction,
            leverage=trade_settings.leverage,
            quantity=result['quantity'],
            entry_price=result['entry_price'],
            stop_loss=Decimal(result['sl_price']) if result.get('sl_price') else trade_sl,
            take_profit=Decimal(result['tp_price']) if result.get('tp_price') else trade_tp,
            position_size_usdt=trade_settings.trade_amount,
            binance_order_id=result.get('order_id', ''),
            sl_order_id=result.get('sl_order_id'),
            tp_order_id=result.get('tp_order_id'),
            entry_time=dj_timezone.now(),
            status='OPEN',
            error_message=f"Warnings: {warnings_text}" if warnings_text else '',
        )

    def execute_signal(self, signal, force_execute=False):
        """
        Execute a futures trade from a signal.
        Runs all pre-trade checks (sync), then API calls in a separate thread.

        Args:
            signal: Signal instance
            force_execute: If True, bypass trading window checks

        Returns:
            FuturesTrade if successful, None otherwise
        """
        symbol_name = signal.symbol.symbol
        direction = signal.direction
        is_priority = getattr(signal, 'is_priority', False)

        log_ctx = dict(signal=signal, symbol=symbol_name, direction=direction,
                       is_priority=is_priority, force_execute=force_execute)

        self._log('SIGNAL_RECEIVED', 'INFO',
                  f"Futures trade request: {direction} {symbol_name} conf={signal.confidence}",
                  details={'confidence': str(signal.confidence), 'sl': str(signal.sl), 'tp': str(signal.tp)},
                  **log_ctx)

        trade_settings = FuturesTradingSettings.get_settings()

        if not self._run_pre_trade_checks(signal, trade_settings, log_ctx, force_execute):
            return None

        trade_sl = signal.sl
        trade_tp = signal.tp

        self._log('TRADE_SUBMITTED', 'INFO',
                  f"All checks passed. Submitting to Binance API",
                  details={'leverage': trade_settings.leverage, 'trade_amount': str(trade_settings.trade_amount)},
                  **log_ctx)

        logger.info(
            f"Signal {signal.id}: All checks passed. Executing Binance API call for "
            f"{direction} {symbol_name} (leverage={trade_settings.leverage}x, amount=${trade_settings.trade_amount})"
        )

        use_testnet = self.use_testnet
        leverage = trade_settings.leverage
        trade_amount = trade_settings.trade_amount
        signal_entry = Decimal(str(signal.entry))

        async def _execute():
            trader = BinanceFuturesTrader(use_testnet=use_testnet)
            try:
                market_data = await trader._fetch_market_data(signal.id, symbol_name)
                if not market_data:
                    return None
                return await trader.place_trade_orders(
                    symbol_name, direction, leverage, trade_amount,
                    trade_sl, trade_tp,
                    market_data['symbol_info'], market_data['current_price'],
                    signal_entry=signal_entry
                )
            finally:
                await trader.close()

        try:
            result = _run_in_thread(_execute)
        except Exception as e:
            logger.error(f"Futures API failed for signal {signal.id}: {e}")
            self._log('TRADE_FAILED', 'ERROR', f"Binance API error: {e}",
                      details={'error': str(e)}, **log_ctx)
            return None

        if not result:
            logger.error(f"Futures API returned no result for signal {signal.id}")
            self._log('TRADE_FAILED', 'ERROR',
                      "Binance API returned no result (market data or order failed)", **log_ctx)
            return None

        futures_trade = self._create_futures_trade(signal, result, trade_settings, trade_sl, trade_tp)

        is_neutral_reversal = bool(
            isinstance(getattr(signal, 'meta', None), dict) and
            signal.meta.get('neutral_reversal')
        )

        logger.info(
            f"Futures trade created: {direction} {result['quantity']} {symbol_name} "
            f"@ {result['entry_price']} | SL: {futures_trade.stop_loss} | TP: {futures_trade.take_profit} "
            f"(Trade ID: {futures_trade.id}, Signal ID: {signal.id})"
        )

        self._log('TRADE_EXECUTED', 'SUCCESS',
                  f"Trade opened: {direction} {result['quantity']} {symbol_name} @ {result['entry_price']}",
                  signal=signal, trade=futures_trade, symbol=symbol_name, direction=direction,
                  is_priority=is_priority, force_execute=force_execute,
                  details={
                      'entry_price': str(result['entry_price']),
                      'quantity': str(result['quantity']),
                      'sl': str(futures_trade.stop_loss),
                      'tp': str(futures_trade.take_profit),
                      'leverage': leverage,
                      'order_id': result.get('order_id', ''),
                      'sl_order_id': result.get('sl_order_id', ''),
                      'tp_order_id': result.get('tp_order_id', ''),
                      'warnings': result.get('warnings', []),
                      'is_neutral_reversal': is_neutral_reversal,
                  })

        return futures_trade

    def close_trade(self, trade):
        """
        Close an open futures trade (sync wrapper).
        Cancels all orders, closes position, updates trade record.

        Args:
            trade: FuturesTrade instance to close

        Returns:
            True if successful, False otherwise
        """
        if not trade.is_open:
            logger.warning(f"Trade {trade.id} is not open")
            return False

        use_testnet = self.use_testnet

        async def _close():
            trader = BinanceFuturesTrader(use_testnet=use_testnet)
            try:
                await trader.cancel_all_orders(trade.symbol)
                close_result = await trader.close_position(
                    trade.symbol, trade.direction, trade.quantity
                )
                if close_result:
                    exit_price = Decimal(close_result.get('avgPrice', '0'))
                    trade.close_trade(exit_price, 'CLOSED_MANUAL')
                    logger.info(f"Futures trade {trade.id} closed @ {exit_price}")
                    return True
                return False
            finally:
                await trader.close()

        return _run_in_thread(_close)


futures_trading_service = FuturesTradingService(use_testnet=False)
