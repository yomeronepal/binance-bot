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

from ..models.futures import FuturesTradingSettings, FuturesTrade
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


class OrphanedPositionError(Exception):
    """
    Raised when an entry filled on Binance but both SL placement and the
    subsequent auto-close retries failed.

    The position is still live on the exchange and will ride to TP, SL
    (if any), or liquidation unless an operator closes it manually.
    Carries the context needed to persist a ``status='FAILED'`` /
    ``error_message='ORPHANED: ...'`` :class:`FuturesTrade` and fire a
    push alert.

    Attributes:
        symbol: Trading pair (e.g. ``"BTCUSDT"``).
        direction: ``"LONG"`` or ``"SHORT"``.
        quantity: Position size, in base asset units.
        entry_price: Fill price of the entry leg.
        reason: Short human-readable explanation.
    """

    def __init__(self, symbol, direction, quantity, entry_price, reason):
        self.symbol = symbol
        self.direction = direction
        self.quantity = quantity
        self.entry_price = entry_price
        self.reason = reason
        super().__init__(
            f"ORPHANED POSITION on {symbol}: {direction} qty={quantity} @ {entry_price} — {reason}"
        )


class BinanceFuturesTrader:
    """Low-level async client for Binance Futures API."""

    BASE_URL = "https://fapi.binance.com"
    TESTNET_URL = "https://testnet.binancefuture.com"
    _server_time_offset = 0
    _last_time_sync = 0
    _hedge_mode: Optional[bool] = None
    _hedge_mode_checked_at = 0

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

    async def is_hedge_mode(self):
        """
        Detect whether the account uses Hedge (dualSidePosition) mode.

        Cached for 5 minutes. In Hedge Mode every order must carry
        positionSide and reduceOnly is rejected; in One-Way mode
        positionSide must be omitted (or "BOTH"). Detecting this once
        prevents silent SL/TP placement failures when the account is in
        Hedge Mode.
        """
        now = time.time()
        if (BinanceFuturesTrader._hedge_mode is not None
                and now - BinanceFuturesTrader._hedge_mode_checked_at < 300):
            return BinanceFuturesTrader._hedge_mode
        try:
            data = await self._request('GET', '/fapi/v1/positionSide/dual', signed=True)
            hedge = bool(data.get('dualSidePosition'))
            BinanceFuturesTrader._hedge_mode = hedge
            BinanceFuturesTrader._hedge_mode_checked_at = now
            logger.info(f"Position mode detected: {'HEDGE' if hedge else 'ONE_WAY'}")
            return hedge
        except Exception as e:
            logger.warning(f"Could not detect position mode, assuming ONE_WAY: {e}")
            BinanceFuturesTrader._hedge_mode = False
            BinanceFuturesTrader._hedge_mode_checked_at = now
            return False

    @staticmethod
    def _position_side_for(direction):
        """Return positionSide ('LONG' or 'SHORT') for the trade direction."""
        return 'LONG' if direction == 'LONG' else 'SHORT'

    async def _adapt_order_params(self, params, direction):
        """
        Inject positionSide for Hedge Mode and strip reduceOnly/closePosition
        flags that Binance rejects in Hedge Mode.

        In Hedge Mode the position is identified by positionSide alone;
        reduceOnly is rejected (-4046) and closePosition is rejected
        (-1106) when paired with reduceOnly. Leaving them in is the
        silent-failure that makes SL/TP never reach the exchange.
        """
        if not direction:
            return params
        if not await self.is_hedge_mode():
            return params
        params['positionSide'] = self._position_side_for(direction)
        params.pop('reduceOnly', None)
        return params

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
        steps = (Decimal(price) / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN)
        return (steps * tick_size).quantize(Decimal(10) ** -precision)

    @staticmethod
    def _fmt(value):
        """
        Format a Decimal/number as a fixed-point string for Binance API.

        ``str(Decimal('1E-7'))`` returns ``'1E-7'``, which Binance rejects.
        Sub-microcent tokens (1MBABYDOGE, SHIB, etc.) routinely produce
        tick-aligned trigger prices that normalise to that form, silently
        breaking SL/TP placement on those symbols. ``format(d, 'f')``
        always emits fixed-point, regardless of the Decimal's internal
        exponent.
        """
        return format(Decimal(value), 'f')

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

    async def _poll_order_until_settled(self, symbol, order_id,
                                          max_attempts=8, delay=0.3):
        """
        Poll GET /fapi/v1/order until the order reaches a settled state.

        Binance Futures' POST /fapi/v1/order can return status=NEW with
        executedQty=0 *even for MARKET orders* — the REST response is
        emitted before the matching engine settles the trade, especially
        under load. Trusting that initial response causes us to abandon
        a position that actually opens a moment later, leaving an orphan
        with no SL/TP. Polling the order endpoint reads the post-match
        state and avoids that whole class of bug.

        Args:
            symbol: Trading pair.
            order_id: orderId returned by the POST response.
            max_attempts: Total poll attempts (default 8 ≈ 2.4 s wall).
            delay: Seconds between polls.

        Returns:
            The latest order dict once status is FILLED / PARTIALLY_FILLED
            / CANCELED / EXPIRED / REJECTED, or the last response if
            polling timed out.
        """
        terminal = {'FILLED', 'PARTIALLY_FILLED', 'CANCELED', 'EXPIRED', 'REJECTED'}
        last = None
        for attempt in range(1, max_attempts + 1):
            try:
                order = await self._request(
                    'GET', '/fapi/v1/order',
                    {'symbol': symbol, 'orderId': order_id}, signed=True,
                )
                last = order
                status = order.get('status', '')
                executed_qty = float(order.get('executedQty', 0) or 0)
                if status in terminal or executed_qty > 0:
                    logger.info(
                        f"Order {order_id} settled on attempt {attempt}: "
                        f"status={status} executedQty={executed_qty}"
                    )
                    return order
                logger.info(
                    f"Order {order_id} not yet settled (attempt {attempt}/{max_attempts}): "
                    f"status={status} executedQty={executed_qty}"
                )
            except Exception as e:
                logger.warning(f"Poll order {order_id} attempt {attempt} failed: {e}")
            if attempt < max_attempts:
                await asyncio.sleep(delay)
        logger.error(
            f"Order {order_id} for {symbol} never settled after {max_attempts} polls"
        )
        return last

    async def place_entry_order(self, symbol, side, quantity, price=None, direction=None):
        """
        Place entry order as a MARKET order, then poll until Binance
        reports the actual fill state.

        Two production failures shaped this method:

        1. LIMIT IOC entries occasionally returned ``status=NEW`` (the
           timeInForce hint dropped or processed asynchronously); the
           order then matched a moment later and we'd never reach SL/TP.
           LIMIT IOC was removed.
        2. MARKET entries also occasionally return ``status=NEW`` with
           ``executedQty=0`` — Binance sends the response before the
           matching engine settles the trade. Under that race the order
           still fills, but our code abandons it. The fix is to poll
           ``GET /fapi/v1/order`` until a terminal state is observed.

        Args:
            symbol: Trading pair
            side: BUY or SELL
            quantity: Order quantity
            price: Ignored, retained for call-site compatibility
            direction: LONG/SHORT for Hedge Mode positionSide tagging
        """
        if price is not None:
            logger.debug(
                f"place_entry_order: ignoring signal price {price} for {symbol}, "
                "entering MARKET (LIMIT IOC removed to fix double-fill bug)"
            )
        logger.info(f"Placing MARKET entry: {side} {quantity} {symbol}")
        try:
            params = {
                'symbol': symbol, 'side': side, 'type': 'MARKET',
                'quantity': self._fmt(quantity),
            }
            params = await self._adapt_order_params(params, direction)
            result = await self._request('POST', '/fapi/v1/order', params, signed=True)
            logger.info(
                f"MARKET entry POST result: {side} {quantity} {symbol} | "
                f"status={result.get('status')} avgPrice={result.get('avgPrice')} "
                f"executedQty={result.get('executedQty')}"
            )
            if not self._order_filled(result):
                order_id = result.get('orderId')
                if order_id:
                    polled = await self._poll_order_until_settled(symbol, order_id)
                    if polled:
                        result = polled
                        logger.info(
                            f"MARKET entry settled state: {side} {quantity} {symbol} | "
                            f"status={result.get('status')} avgPrice={result.get('avgPrice')} "
                            f"executedQty={result.get('executedQty')}"
                        )
            return result
        except Exception as e:
            logger.error(f"MARKET entry FAILED: {side} {quantity} {symbol} | {e}")
            return None

    async def _place_limit_ioc(self, symbol, side, quantity, price, direction=None):
        """Place LIMIT IOC order — fills immediately at signal price or cancels."""
        params = {
            'symbol': symbol, 'side': side, 'type': 'LIMIT',
            'price': str(price), 'quantity': str(quantity), 'timeInForce': 'IOC',
        }
        params = await self._adapt_order_params(params, direction)
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

    async def place_market_order(self, symbol, side, quantity, reduce_only=False, direction=None):
        """
        Place a market order (used for closing positions).

        Args:
            symbol: Trading pair
            side: BUY or SELL
            quantity: Order quantity
            reduce_only: If True, only reduces existing position (ignored in Hedge Mode)
            direction: LONG/SHORT of the position being closed (for Hedge Mode positionSide)
        """
        params = {
            'symbol': symbol, 'side': side, 'type': 'MARKET',
            'quantity': self._fmt(quantity),
        }
        if reduce_only:
            params['reduceOnly'] = 'true'
        params = await self._adapt_order_params(params, direction)

        try:
            result = await self._request('POST', '/fapi/v1/order', params, signed=True)
            logger.info(f"Market order placed: {side} {quantity} {symbol}")
            return result
        except Exception as e:
            logger.error(f"Failed to place market order: {e}")
            return None

    async def _place_with_quantity(self, symbol, side, quantity, stop_price, order_type, label, direction=None):
        """
        Place conditional order with explicit quantity + reduceOnly (One-Way mode)
        or positionSide (Hedge Mode).

        Args:
            symbol: Trading pair
            side: BUY or SELL
            quantity: Position quantity
            stop_price: Trigger price
            order_type: STOP_MARKET or TAKE_PROFIT_MARKET
            label: SL or TP for logging
            direction: LONG/SHORT of the underlying position (for Hedge Mode)
        """
        params = {
            'symbol': symbol, 'side': side, 'type': order_type,
            'quantity': self._fmt(quantity), 'stopPrice': self._fmt(stop_price),
            'reduceOnly': 'true', 'workingType': 'MARK_PRICE', 'priceProtect': 'true',
        }
        params = await self._adapt_order_params(params, direction)
        try:
            result = await self._request('POST', '/fapi/v1/order', params, signed=True)
            order_id = result.get('orderId')
            logger.info(f"[QTY] {label} placed: {side} {quantity} {symbol} @ {stop_price} | OrderID: {order_id}")
            return {'orderId': str(order_id), 'method': 'quantity', **result}
        except Exception as e:
            logger.warning(f"[QTY] {label} failed for {symbol}: {e}")
            return None

    async def _place_with_close_position(self, symbol, side, stop_price, order_type, label, direction=None):
        """
        Place conditional order with closePosition=true (no quantity needed).

        Args:
            symbol: Trading pair
            side: BUY or SELL
            stop_price: Trigger price
            order_type: STOP_MARKET or TAKE_PROFIT_MARKET
            label: SL or TP for logging
            direction: LONG/SHORT of the position being protected (for Hedge Mode)
        """
        params = {
            'symbol': symbol, 'side': side, 'type': order_type,
            'closePosition': 'true', 'stopPrice': self._fmt(stop_price),
            'workingType': 'MARK_PRICE', 'priceProtect': 'true',
        }
        params = await self._adapt_order_params(params, direction)
        try:
            result = await self._request('POST', '/fapi/v1/order', params, signed=True)
            order_id = result.get('orderId')
            logger.info(f"[CLOSE_POS] {label} placed: {side} {symbol} @ {stop_price} | OrderID: {order_id}")
            return {'orderId': str(order_id), 'method': 'closePosition', **result}
        except Exception as e:
            logger.warning(f"[CLOSE_POS] {label} failed for {symbol}: {e}")
            return None

    async def _place_algo_conditional(self, symbol, side, trigger_price, order_type, label, direction=None):
        """
        Place SL/TP via Binance Algo API (the only endpoint that supports STOP_MARKET/TAKE_PROFIT_MARKET).

        Args:
            symbol: Trading pair
            side: BUY or SELL
            trigger_price: Trigger price for SL or TP
            order_type: STOP_MARKET or TAKE_PROFIT_MARKET
            label: SL or TP for logging
            direction: LONG/SHORT of the underlying position (for Hedge Mode)

        Returns:
            Dict with orderId or None
        """
        if trigger_price <= 0:
            logger.error(f"{label} price is {trigger_price}, cannot place order")
            return None

        params = {
            'symbol': symbol, 'side': side, 'algoType': 'CONDITIONAL',
            'type': order_type, 'closePosition': 'true', 'triggerPrice': self._fmt(trigger_price),
        }
        params = await self._adapt_order_params(params, direction)
        try:
            result = await self._request('POST', '/fapi/v1/algoOrder', params, signed=True)
            algo_id = result.get('algoId')
            logger.info(f"[ALGO] {label} placed: {side} {symbol} @ {trigger_price} | AlgoID: {algo_id}")
            return {'orderId': str(algo_id), 'algoId': algo_id, 'method': 'algo', **result}
        except Exception as e:
            logger.error(f"[ALGO] {label} failed for {symbol}: {e}")
            return None

    async def _place_with_algo(self, symbol, side, stop_price, order_type, label, direction=None):
        """Backward-compatible alias for _place_algo_conditional."""
        return await self._place_algo_conditional(symbol, side, stop_price, order_type, label, direction)

    async def _place_conditional_with_fallback(self, symbol, side, quantity, trigger_price,
                                                order_type, label, methods, direction=None):
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
            direction: LONG/SHORT of the underlying position (for Hedge Mode positionSide)

        Returns:
            Order result dict or None if all methods fail
        """
        if trigger_price <= 0:
            logger.error(f"{label} price is {trigger_price}, cannot place order")
            return None

        logger.info(f"Placing {label}: {symbol} {side} {order_type} @ {trigger_price}")

        dispatch = {
            'algo': lambda: self._place_with_algo(symbol, side, trigger_price, order_type, label, direction),
            'quantity': lambda: self._place_with_quantity(symbol, side, quantity, trigger_price, order_type, label, direction),
            'close_position': lambda: self._place_with_close_position(symbol, side, trigger_price, order_type, label, direction),
        }

        for method in methods:
            result = await dispatch[method]()
            if result:
                return result

        logger.error(f"ALL {label} methods FAILED for {symbol} {side} @ {trigger_price}")
        return None

    async def place_stop_loss_order(self, symbol, side, quantity, stop_price,
                                     current_price=None, symbol_info=None, direction=None):
        """
        Place a stop loss order with 3-level fallback: closePosition -> quantity -> algo.
        Uses /fapi/v1/order STOP_MARKET (closePosition=true is most reliable).
        Signal's SL value is used directly (no recalculation).

        Args:
            symbol: Trading pair
            side: BUY or SELL
            quantity: Position quantity
            stop_price: Stop loss trigger price from signal
            current_price: Unused, kept for backward compatibility
            symbol_info: Symbol info for price rounding (optional)
            direction: LONG/SHORT of the underlying position (for Hedge Mode)
        """
        if symbol_info:
            stop_price = self._round_price(stop_price, symbol_info)
        return await self._place_conditional_with_fallback(
            symbol, side, quantity, stop_price, 'STOP_MARKET', 'SL',
            ['close_position', 'quantity', 'algo'], direction=direction,
        )

    async def place_take_profit_order(self, symbol, side, quantity, take_profit_price,
                                       current_price=None, symbol_info=None, direction=None):
        """
        Place a take profit order with 3-level fallback: closePosition -> quantity -> algo.
        Uses /fapi/v1/order TAKE_PROFIT_MARKET (closePosition=true is most reliable).
        Signal's TP value is used directly (no recalculation).

        Args:
            symbol: Trading pair
            side: BUY or SELL
            quantity: Position quantity
            take_profit_price: Take profit trigger price from signal
            current_price: Unused, kept for backward compatibility
            symbol_info: Symbol info for price rounding (optional)
            direction: LONG/SHORT of the underlying position (for Hedge Mode)
        """
        if symbol_info:
            take_profit_price = self._round_price(take_profit_price, symbol_info)
        return await self._place_conditional_with_fallback(
            symbol, side, quantity, take_profit_price, 'TAKE_PROFIT_MARKET', 'TP',
            ['close_position', 'quantity', 'algo'], direction=direction,
        )

    async def place_trailing_stop_order(self, symbol, side, quantity, callback_rate,
                                         activation_price=None, direction=None):
        """
        Place a trailing stop market order.

        Args:
            symbol: Trading pair
            side: SELL for LONG positions, BUY for SHORT positions
            quantity: Position quantity
            callback_rate: Callback rate in percentage (0.1 to 5.0)
            activation_price: Price at which trailing stop activates (optional)
            direction: LONG/SHORT of the underlying position (for Hedge Mode)
        """
        params = {
            'symbol': symbol, 'side': side, 'type': 'TRAILING_STOP_MARKET',
            'quantity': self._fmt(quantity), 'callbackRate': self._fmt(callback_rate),
            'reduceOnly': 'true',
        }
        if activation_price:
            params['activationPrice'] = self._fmt(activation_price)
        params = await self._adapt_order_params(params, direction)

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
        return await self.place_market_order(
            symbol, side, quantity, reduce_only=True, direction=direction,
        )

    async def close_position_with_retry(self, symbol, direction, quantity, attempts=3):
        """
        Close a position with bounded retries and exponential backoff.

        Used on the SL-failure rescue path: a single close attempt is too
        fragile because the rescue only fires when something is already
        going wrong (API hiccup, position-mode mismatch, transient rate
        limit). Backoff pattern: 0.5s, 1s, 2s between attempts.

        Args:
            symbol: Trading pair.
            direction: ``"LONG"`` or ``"SHORT"``.
            quantity: Position size to close.
            attempts: Maximum close attempts (default 3).

        Returns:
            bool: True if at least one attempt returned a result object
            (treated as "order accepted"); False if every attempt failed.
        """
        delay = 0.5
        for attempt in range(1, attempts + 1):
            try:
                result = await self.close_position(symbol, direction, quantity)
            except Exception as exc:
                logger.warning(
                    f"close_position attempt {attempt}/{attempts} raised for {symbol}: {exc}"
                )
                result = None

            if result:
                logger.info(
                    f"close_position succeeded for {symbol} on attempt {attempt}/{attempts}"
                )
                return True

            if attempt < attempts:
                await asyncio.sleep(delay)
                delay *= 2

        logger.error(
            f"close_position FAILED all {attempts} attempts for {symbol} {direction} qty={quantity}"
        )
        return False

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
        hedge = await self.is_hedge_mode()
        position_side = self._position_side_for(direction) if hedge else None

        if entry_price:
            entry_order = {
                'symbol': symbol, 'side': entry_side, 'type': 'LIMIT',
                'price': self._fmt(entry_price), 'quantity': self._fmt(quantity),
                'timeInForce': 'GTC',
            }
        else:
            entry_order = {
                'symbol': symbol, 'side': entry_side, 'type': 'MARKET',
                'quantity': self._fmt(quantity),
            }
        if position_side:
            entry_order['positionSide'] = position_side

        logger.info(f"[BATCH] Entry: {entry_order['type']} {entry_side} {quantity} {symbol}"
                     + (f" @ {entry_price}" if entry_price else ""))

        sl_tp_base = {
            'symbol': symbol, 'side': close_side, 'quantity': self._fmt(quantity),
            'workingType': 'MARK_PRICE', 'priceProtect': 'true',
        }
        if position_side:
            sl_tp_base['positionSide'] = position_side
        else:
            sl_tp_base['reduceOnly'] = 'true'

        orders = [
            entry_order,
            {**sl_tp_base, 'type': 'STOP_MARKET', 'stopPrice': self._fmt(sl_price)},
            {**sl_tp_base, 'type': 'TAKE_PROFIT_MARKET', 'stopPrice': self._fmt(tp_price)},
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
                symbol, close_side, quantity, sl_rounded,
                symbol_info=symbol_info, direction=direction,
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
                symbol, close_side, quantity, tp_rounded,
                symbol_info=symbol_info, direction=direction,
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

    async def _rescue_or_orphan(self, symbol, direction, quantity, entry_price, reason):
        """
        Try to close a position that lost its SL; raise on total failure.

        Called when SL placement or post-placement verification cannot be
        repaired. A successful rescue raises a plain :class:`Exception`
        (entry reversed, matches the original behaviour so upstream keeps
        treating it as a normal failed trade). A failed rescue raises
        :class:`OrphanedPositionError` so ``execute_signal`` can persist a
        FAILED/ORPHANED ``FuturesTrade`` row and push-alert the operator.

        Args:
            symbol: Trading pair.
            direction: ``"LONG"`` or ``"SHORT"``.
            quantity: Position size to close.
            entry_price: Actual entry fill price (for the orphan record).
            reason: Short explanation of why the rescue was triggered.

        Raises:
            OrphanedPositionError: If every close attempt failed — live
                position remains on Binance and needs manual intervention.
            Exception: If the rescue succeeded — entry reversed, same
                semantics as the pre-retry behaviour.
        """
        logger.error(f"CRITICAL: {reason} for {symbol}! Attempting rescue close.")
        closed = await self.close_position_with_retry(symbol, direction, quantity)
        if closed:
            raise Exception(f"{reason} on {symbol}. Entry reversed by rescue close.")
        raise OrphanedPositionError(symbol, direction, quantity, entry_price, reason)

    async def _check_sl_tp_on_exchange(self, symbol):
        """
        Query Binance for both regular and algo orders and report which
        conditional types are present.

        Used as a post-placement safety net: even if ``place_stop_loss_order``
        returned a success dict, the order may have been rejected post-hoc
        (margin rules, price bands, position-mode mismatch). A direct query
        is the only source of truth.

        Algo orders (listed via ``/fapi/v1/allAlgoOrders``) live on a
        separate endpoint from ``/fapi/v1/openOrders``. Without checking
        both, a successful algo fallback would be falsely reported as
        missing — triggering a wasteful retry that collides with the
        already-placed algo order ("An open stop or take profit order
        with GTE and closePosition in the direction is existing") and
        cascades into the rescue close.

        Args:
            symbol: Trading pair to check.

        Returns:
            Tuple[bool, bool]: ``(sl_present, tp_present)``. On API error
            both are reported True (fail-open) so a transient query failure
            does not trigger a needless position-close.
        """
        sl_present = False
        tp_present = False
        regular_failed = False
        algo_failed = False

        try:
            orders = await self.get_all_open_orders(symbol)
            types_present = {o.get('type') for o in (orders or [])}
            sl_present = 'STOP_MARKET' in types_present
            tp_present = 'TAKE_PROFIT_MARKET' in types_present
        except Exception as exc:
            logger.warning(f"openOrders query failed for {symbol}: {exc}")
            regular_failed = True

        try:
            algo_resp = await self._request(
                'GET', '/fapi/v1/allAlgoOrders',
                {'symbol': symbol, 'algoStatus': 'NEW'}, signed=True,
            )
            algo_list = algo_resp if isinstance(algo_resp, list) else algo_resp.get('rows', [])
            for o in algo_list or []:
                otype = (
                    o.get('type')
                    or o.get('orderType')
                    or o.get('algoOrderType')
                    or ''
                ).upper()
                if otype == 'STOP_MARKET':
                    sl_present = True
                elif otype == 'TAKE_PROFIT_MARKET':
                    tp_present = True
        except Exception as exc:
            logger.warning(f"allAlgoOrders query failed for {symbol}: {exc}")
            algo_failed = True

        if regular_failed and algo_failed:
            logger.warning(
                f"Both order queries failed for {symbol} — treating SL/TP as present (fail-open)"
            )
            return True, True

        return sl_present, tp_present

    async def _place_tp_with_retry(self, symbol, close_side, quantity, tp_rounded, direction=None):
        """
        Place a TP order with a single automatic retry.

        TP failure used to be only a warning, which meant a silently naked
        upside on winning trades. Retry once before giving up.
        """
        result = await self.place_take_profit_order(
            symbol, close_side, quantity, tp_rounded, direction=direction,
        )
        if result:
            return result
        logger.warning(f"TP first attempt failed for {symbol}, retrying once")
        await asyncio.sleep(0.5)
        return await self.place_take_profit_order(
            symbol, close_side, quantity, tp_rounded, direction=direction,
        )

    async def place_trade_orders(self, symbol, direction, leverage, position_size,
                                  sl, tp, symbol_info, current_price, signal_entry=None):
        """
        Place entry + SL + TP on Binance using signal's exact prices.

        Flow:
            1. Entry: LIMIT IOC at signal price -> MARKET fallback (/fapi/v1/order).
            2. SL: conditional order with fallback chain
               (close_position -> quantity -> algo).
            3. TP: same conditional fallback chain, with one auto-retry.
            4. Verification: query /fapi/v1/openOrders and confirm both
               STOP_MARKET and TAKE_PROFIT_MARKET are actually present.
               If SL is missing, position is auto-closed; if TP is missing,
               a CRITICAL warning is appended but the trade continues.

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
        entry_side, close_side = self._sides(direction)

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

            entry_result = await self.place_entry_order(
                symbol, entry_side, quantity, entry_rounded, direction=direction,
            )
            if not entry_result:
                raise Exception("Entry order failed — Binance returned no result")

            if not self._order_filled(entry_result):
                status = entry_result.get('status', 'UNKNOWN')
                raise Exception(f"Entry not filled — status={status}")

            avg_price = await self._resolve_entry_price(entry_result, symbol, entry_price)
            logger.info(f"Entry filled: {direction} {quantity} {symbol} @ {avg_price}")

            warnings = []

            sl_result = await self.place_stop_loss_order(
                symbol, close_side, quantity, sl_rounded, direction=direction,
            )
            if not sl_result:
                await self._rescue_or_orphan(
                    symbol, direction, quantity, avg_price,
                    reason=f"SL placement failed at {sl_rounded}",
                )

            tp_result = await self._place_tp_with_retry(
                symbol, close_side, quantity, tp_rounded, direction=direction,
            )
            if not tp_result:
                warnings.append(f"TP failed after retry — only SL active at {sl_rounded}")

            sl_result, tp_result, verify_warnings = await self._verify_and_repair_sl_tp(
                symbol, direction, close_side, quantity, sl_rounded, tp_rounded,
                sl_result, tp_result, avg_price,
            )
            warnings.extend(verify_warnings)

            logger.info(
                f"Trade opened: {direction} {quantity} {symbol} @ {avg_price} "
                f"(SL: {sl_rounded}, TP: {tp_rounded})"
            )

            return self._build_trade_result(
                quantity, avg_price, entry_result.get('orderId', ''),
                str(sl_result.get('orderId', '')) if sl_result else None,
                str(tp_result.get('orderId', '')) if tp_result else None,
                sl_rounded, tp_rounded, warnings
            )

        except Exception as e:
            logger.error(f"Failed to place orders for {symbol}: {e}")
            raise

    async def _verify_and_repair_sl_tp(self, symbol, direction, close_side, quantity,
                                         sl_rounded, tp_rounded, sl_result, tp_result,
                                         avg_price):
        """
        Confirm SL and TP are live on Binance; repair or close on mismatch.

        Runs ~300ms after placement to let the exchange index the orders.
        If SL is missing: one retry; still missing => rescue-close the
        position (3-attempt backoff), raising :class:`OrphanedPositionError`
        if even that fails. If TP is missing: one retry; still missing =>
        append a critical warning and continue (SL still protects downside).

        Args:
            symbol: Trading pair.
            direction: LONG or SHORT (for close on SL failure).
            close_side: BUY or SELL side for the SL/TP closing orders.
            quantity: Position size.
            sl_rounded: Tick-size-rounded SL trigger price.
            tp_rounded: Tick-size-rounded TP trigger price.
            sl_result: Result dict from initial SL placement.
            tp_result: Result dict from initial TP placement (may be None).
            avg_price: Actual entry fill price, propagated for orphan alerts.

        Returns:
            Tuple[dict, Optional[dict], List[str]]:
            (final_sl_result, final_tp_result, warnings_to_append).

        Raises:
            OrphanedPositionError: If SL cannot be repaired AND the rescue
                close also fails across all retries.
            Exception: If SL cannot be repaired but the rescue close
                succeeded (entry-reversed path).
        """
        await asyncio.sleep(0.3)
        sl_on_exchange, tp_on_exchange = await self._check_sl_tp_on_exchange(symbol)
        extra_warnings = []

        if not sl_on_exchange:
            logger.error(
                f"CRITICAL: SL reported placed but missing on exchange for {symbol}, retrying"
            )
            sl_retry = await self.place_stop_loss_order(
                symbol, close_side, quantity, sl_rounded, direction=direction,
            )
            if not sl_retry:
                await self._rescue_or_orphan(
                    symbol, direction, quantity, avg_price,
                    reason=f"SL missing after placement + repair retry at {sl_rounded}",
                )
            sl_result = sl_retry
            extra_warnings.append("SL required retry after post-placement verification")

        if tp_result and not tp_on_exchange:
            logger.error(
                f"CRITICAL: TP reported placed but missing on exchange for {symbol}, retrying"
            )
            tp_retry = await self.place_take_profit_order(
                symbol, close_side, quantity, tp_rounded, direction=direction,
            )
            if tp_retry:
                tp_result = tp_retry
                extra_warnings.append("TP required retry after post-placement verification")
            else:
                extra_warnings.append(
                    f"TP verification failed even after retry — only SL active at {sl_rounded}"
                )
                tp_result = None

        return sl_result, tp_result, extra_warnings

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

        entry_result = await self.place_entry_order(
            symbol, entry_side, quantity, entry_price, direction=direction,
        )

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
            symbol, close_side, quantity, sl_rounded,
            symbol_info=symbol_info, direction=direction,
        )
        if not sl_result:
            logger.error(f"CRITICAL: SL failed for {symbol}! Closing position.")
            await self.close_position(symbol, direction, quantity)
            raise Exception(f"SL could not be placed on {symbol}. Entry reversed.")

        tp_result = await self.place_take_profit_order(
            symbol, close_side, quantity, tp_rounded,
            symbol_info=symbol_info, direction=direction,
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
            from ..models.futures import FuturesTradeLog
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

        # Macro filter — re-evaluate against a *fresh* BTC snapshot.
        # The signal's stored macro_at_signal stamp is for analytics
        # (what the regime looked like when we detected the setup);
        # this gate uses the regime *now* because BTC may have moved
        # in the seconds-to-minutes between detection and trade.
        if not self._check_macro_filter(signal, direction, log_ctx):
            return False

        if not self._check_duplicates(signal, symbol_name, direction, log_ctx):
            return False

        return True

    def _check_macro_filter(self, signal, direction, log_ctx):
        """
        Block trades that fight their asset class's daily regime.

        Routes to the right macro filter based on ``signal.asset_class``:
            CRYPTO     → BTC daily regime
            STOCK      → SPY daily regime
            COMMODITY  → XAU (gold) daily regime

        Pure check — no side effects beyond a ``CHECK_FAILED`` log row.
        Snapshot-fetch failures fail open (allow) so a transient
        network issue doesn't pause the bot; each per-class filter
        returns ``ALLOW`` + ``*_snapshot_unavailable_allow`` in that
        case.

        Honours the per-class admin toggles on
        ``FuturesTradingSettings``: ``crypto_macro_filter_enabled``,
        ``stock_macro_filter_enabled``,
        ``commodity_macro_filter_enabled``. When the relevant flag is
        OFF, the gate short-circuits to True (allow) without
        consulting any regime snapshot. Signal-creation tagging is
        unaffected by the flags.
        """
        asset_class = (getattr(signal, 'asset_class', None) or 'CRYPTO').upper()
        flag_attr = {
            'CRYPTO': 'crypto_macro_filter_enabled',
            'STOCK': 'stock_macro_filter_enabled',
            'COMMODITY': 'commodity_macro_filter_enabled',
        }.get(asset_class, 'crypto_macro_filter_enabled')

        try:
            settings_obj = FuturesTradingSettings.get_settings()
            if not getattr(settings_obj, flag_attr, True):
                return True
        except Exception as exc:
            logger.warning(
                "Macro filter setting lookup failed (allowing trade): %s", exc,
            )
            return True

        try:
            from scanner.services.macro_router import evaluate_for_symbol
            symbol_str = signal.symbol.symbol if hasattr(signal.symbol, 'symbol') else str(signal.symbol)
            decision, reason, _ = evaluate_for_symbol(
                symbol_str, direction, asset_class=asset_class,
            )
        except Exception as exc:
            logger.warning(
                "Macro filter raised (allowing trade): signal=%s err=%s",
                signal.id, exc,
            )
            return True

        if decision == 'BLOCK':
            self._log(
                'CHECK_FAILED', 'WARNING',
                f"Macro filter blocked: {reason}",
                details={
                    'macro_reason': reason,
                    'direction': direction,
                    'asset_class': asset_class,
                },
                **log_ctx,
            )
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

    def _handle_orphaned_position(self, signal, orphan, trade_settings, log_ctx):
        """
        Persist an orphan FuturesTrade row and fire a push alert.

        Called when ``place_trade_orders`` raised
        :class:`OrphanedPositionError` — entry filled but SL could not be
        attached and the rescue close also failed. The position is live on
        Binance and will run to liquidation without manual intervention.

        The FuturesTrade is written with ``status='FAILED'`` (no schema
        change required) and ``error_message`` prefixed ``ORPHANED:`` so
        operators can filter in the admin. ``sl_order_id`` / ``tp_order_id``
        are left blank — the alert is the source of truth, not the DB.

        Args:
            signal: Originating Signal instance.
            orphan: The :class:`OrphanedPositionError` carrying context.
            trade_settings: Snapshot of ``FuturesTradingSettings`` used for
                this trade (for leverage / position_size_usdt).
            log_ctx: Logging context dict for ``_log``.
        """
        logger.critical(
            f"ORPHANED POSITION: signal {signal.id} {orphan.symbol} {orphan.direction} "
            f"qty={orphan.quantity} @ {orphan.entry_price} — {orphan.reason} — "
            "MANUAL CLOSE REQUIRED"
        )

        trade = self._persist_orphan_trade(signal, orphan, trade_settings)
        self._broadcast_orphan_alert(signal, orphan, trade)

        self._log('TRADE_FAILED', 'CRITICAL',
                  f"ORPHANED position on {orphan.symbol}: {orphan.reason}",
                  signal=signal, trade=trade,
                  details={
                      'symbol': orphan.symbol,
                      'direction': orphan.direction,
                      'quantity': str(orphan.quantity),
                      'entry_price': str(orphan.entry_price),
                      'reason': orphan.reason,
                  },
                  **{k: v for k, v in log_ctx.items() if k not in ('signal',)})

    def _persist_orphan_trade(self, signal, orphan, trade_settings):
        """
        Write a FuturesTrade row marking the position as ORPHANED.

        Returns:
            FuturesTrade: The persisted row, or None if DB write also
            failed (logged but non-fatal — the push alert is the backup).
        """
        try:
            return FuturesTrade.objects.create(
                signal=signal,
                symbol=orphan.symbol,
                direction=orphan.direction,
                leverage=trade_settings.leverage,
                quantity=orphan.quantity,
                entry_price=orphan.entry_price,
                stop_loss=signal.sl,
                take_profit=signal.tp,
                position_size_usdt=trade_settings.trade_amount,
                binance_order_id='',
                sl_order_id=None,
                tp_order_id=None,
                entry_time=dj_timezone.now(),
                status='FAILED',
                error_message=f"ORPHANED: {orphan.reason}",
            )
        except Exception as exc:
            logger.error(
                f"Failed to persist ORPHANED FuturesTrade for signal {signal.id}: {exc}",
                exc_info=True,
            )
            return None

    def _broadcast_orphan_alert(self, signal, orphan, trade):
        """Send a CRITICAL push notification to every subscriber."""
        try:
            from .push_notification import broadcast
            broadcast(
                title=f"CRITICAL: Orphan {orphan.symbol}",
                body=(
                    f"{orphan.direction} {orphan.quantity} {orphan.symbol} "
                    f"@ {orphan.entry_price} lost its SL and auto-close failed. "
                    "Close MANUALLY on Binance NOW."
                ),
                data={
                    'type': 'orphaned_position',
                    'signal_id': str(signal.id),
                    'trade_id': str(trade.id) if trade else '',
                    'symbol': orphan.symbol,
                    'direction': orphan.direction,
                    'quantity': str(orphan.quantity),
                    'entry_price': str(orphan.entry_price),
                    'reason': orphan.reason,
                },
                signal_obj=signal,
            )
        except Exception as exc:
            logger.error(f"Failed to broadcast orphan alert for signal {signal.id}: {exc}")

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
        except OrphanedPositionError as orphan:
            self._handle_orphaned_position(signal, orphan, trade_settings, log_ctx)
            return None
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
