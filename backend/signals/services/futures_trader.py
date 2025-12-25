"""
Binance Futures Trading Service for real trade execution.
Handles placing, monitoring, and closing futures positions.
"""
import logging
import hashlib
import hmac
import time
import asyncio
from decimal import Decimal, ROUND_DOWN
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone, timedelta

import aiohttp
from django.conf import settings
from django.utils import timezone as dj_timezone
from django.db import transaction

from ..models_futures import FuturesTradingSettings, FuturesTrade
from ..models import Signal

logger = logging.getLogger(__name__)

NEPAL_TZ_OFFSET = timedelta(hours=5, minutes=45)
TRADING_WINDOWS = [
    (21, 0, 23, 0),
]


def is_within_trading_window():
    """Check if current Nepal time is within trading windows."""
    utc_now = datetime.now(timezone.utc)
    nepal_now = utc_now + NEPAL_TZ_OFFSET
    current_time_minutes = nepal_now.hour * 60 + nepal_now.minute

    for start_hour, start_min, end_hour, end_min in TRADING_WINDOWS:
        window_start = start_hour * 60 + start_min
        window_end = end_hour * 60 + end_min
        if window_start <= current_time_minutes < window_end:
            return True
    return False


class BinanceFuturesTrader:
    """
    Service for executing real futures trades on Binance.
    """
    BASE_URL = "https://fapi.binance.com"
    TESTNET_URL = "https://testnet.binancefuture.com"

    # Class-level cache for server time offset
    _server_time_offset = 0
    _last_time_sync = 0

    def __init__(self, use_testnet: bool = False):
        self.api_key = settings.BINANCE_API_KEY
        self.api_secret = settings.BINANCE_API_SECRET
        self.base_url = self.TESTNET_URL if use_testnet else self.BASE_URL
        self.session: Optional[aiohttp.ClientSession] = None

    def _generate_signature(self, query_string: str) -> str:
        """Generate HMAC SHA256 signature for signed endpoints."""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def _sync_server_time(self):
        """
        Sync local time with Binance server time to avoid timestamp errors.
        Caches the offset for 5 minutes.
        """
        current_time = time.time()
        # Re-sync every 5 minutes
        if current_time - BinanceFuturesTrader._last_time_sync > 300:
            try:
                session = await self._get_session()
                url = f"{self.base_url}/fapi/v1/time"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        server_time = data.get('serverTime', 0)
                        local_time = int(time.time() * 1000)
                        BinanceFuturesTrader._server_time_offset = server_time - local_time
                        BinanceFuturesTrader._last_time_sync = current_time
                        logger.info(f"Synced with Binance server. Time offset: {BinanceFuturesTrader._server_time_offset}ms")
            except Exception as e:
                logger.warning(f"Failed to sync server time: {e}")

    def _get_timestamp(self) -> int:
        """Get timestamp adjusted for server time offset."""
        return int(time.time() * 1000) + BinanceFuturesTrader._server_time_offset

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        signed: bool = False
    ) -> Dict:
        """Make API request to Binance Futures."""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"

        if params is None:
            params = {}

        headers = {'X-MBX-APIKEY': self.api_key}

        if signed:
            # Sync server time before making signed requests
            await self._sync_server_time()
            params['timestamp'] = self._get_timestamp()
            params['recvWindow'] = 60000  # 60 seconds tolerance for clock drift
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            params['signature'] = self._generate_signature(query_string)

        try:
            async with session.request(method, url, params=params, headers=headers) as response:
                data = await response.json()

                if response.status != 200:
                    error_msg = data.get('msg', str(data))
                    logger.error(f"Binance API error: {error_msg}")
                    raise Exception(f"Binance API error: {error_msg}")

                return data

        except aiohttp.ClientError as e:
            logger.error(f"Network error: {e}")
            raise

    async def get_account_balance(self) -> Dict:
        """Get futures account balance."""
        return await self._request('GET', '/fapi/v2/balance', signed=True)

    async def get_open_positions(self) -> list:
        """Get all open positions from Binance."""
        try:
            positions = await self._request('GET', '/fapi/v2/positionRisk', signed=True)
            # Filter only positions with non-zero quantity
            return [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        except Exception as e:
            logger.error(f"Failed to get open positions: {e}")
            return []

    async def get_position_for_symbol(self, symbol: str) -> Optional[Dict]:
        """Get position for a specific symbol."""
        try:
            positions = await self._request(
                'GET', '/fapi/v2/positionRisk',
                {'symbol': symbol},
                signed=True
            )
            for p in positions:
                if float(p.get('positionAmt', 0)) != 0:
                    return p
            return None
        except Exception as e:
            logger.error(f"Failed to get position for {symbol}: {e}")
            return None

    async def get_trade_history(self, symbol: str, limit: int = 50) -> list:
        """Get recent trade history for a symbol."""
        try:
            return await self._request(
                'GET', '/fapi/v1/userTrades',
                {'symbol': symbol, 'limit': limit},
                signed=True
            )
        except Exception as e:
            logger.error(f"Failed to get trade history for {symbol}: {e}")
            return []

    async def get_income_history(self, symbol: str = None, income_type: str = None, limit: int = 100) -> list:
        """
        Get income history (realized PnL, funding fees, etc).
        income_type can be: REALIZED_PNL, FUNDING_FEE, COMMISSION, etc.
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

    async def get_all_open_orders(self, symbol: str = None) -> list:
        """Get all open orders."""
        try:
            params = {}
            if symbol:
                params['symbol'] = symbol
            return await self._request('GET', '/fapi/v1/openOrders', params, signed=True)
        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return []

    async def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Get symbol trading rules (precision, min qty, etc)."""
        try:
            exchange_info = await self._request('GET', '/fapi/v1/exchangeInfo')
            for s in exchange_info.get('symbols', []):
                if s['symbol'] == symbol:
                    return s
            return None
        except Exception as e:
            logger.error(f"Failed to get symbol info for {symbol}: {e}")
            return None

    async def get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current market price for symbol."""
        try:
            data = await self._request('GET', '/fapi/v1/ticker/price', {'symbol': symbol})
            return Decimal(data['price'])
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol."""
        try:
            await self._request(
                'POST',
                '/fapi/v1/leverage',
                {'symbol': symbol, 'leverage': leverage},
                signed=True
            )
            logger.info(f"Set leverage for {symbol} to {leverage}x")
            return True
        except Exception as e:
            logger.error(f"Failed to set leverage for {symbol}: {e}")
            return False

    async def set_margin_type(self, symbol: str, margin_type: str = 'ISOLATED') -> bool:
        """Set margin type (ISOLATED or CROSSED)."""
        try:
            await self._request(
                'POST',
                '/fapi/v1/marginType',
                {'symbol': symbol, 'marginType': margin_type},
                signed=True
            )
            logger.info(f"Set margin type for {symbol} to {margin_type}")
            return True
        except Exception as e:
            if 'No need to change margin type' in str(e):
                return True
            logger.error(f"Failed to set margin type for {symbol}: {e}")
            return False

    def _get_price_precision(self, symbol_info: Dict) -> Tuple[Decimal, int]:
        """Get tick size and price precision from symbol info."""
        tick_size = Decimal('0.01')
        price_precision = 2

        for f in symbol_info.get('filters', []):
            if f['filterType'] == 'PRICE_FILTER':
                tick_size = Decimal(f['tickSize'])
                tick_str = f['tickSize'].rstrip('0').rstrip('.')
                if '.' in tick_str:
                    price_precision = len(tick_str.split('.')[1])
                else:
                    price_precision = 0
                break

        return tick_size, price_precision

    def _round_price(self, price: Decimal, symbol_info: Dict) -> Decimal:
        """Round price to symbol's tick size precision."""
        tick_size, price_precision = self._get_price_precision(symbol_info)
        steps = (price / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN)
        rounded_price = steps * tick_size
        return rounded_price.quantize(Decimal(10) ** -price_precision)

    def _calculate_quantity(
        self,
        symbol_info: Dict,
        price: Decimal,
        position_size_usdt: Decimal,
        leverage: int
    ) -> Decimal:
        """Calculate order quantity based on position size and precision rules."""
        quantity_precision = 3
        min_qty = Decimal('0.001')
        step_size = Decimal('0.001')

        for f in symbol_info.get('filters', []):
            if f['filterType'] == 'LOT_SIZE':
                min_qty = Decimal(f['minQty'])
                step_size = Decimal(f['stepSize'])
            if f['filterType'] == 'QUANTITY_PRECISION':
                quantity_precision = int(f.get('quantityPrecision', 3))

        notional_value = position_size_usdt * leverage
        raw_quantity = notional_value / price

        steps = (raw_quantity / step_size).quantize(Decimal('1'), rounding=ROUND_DOWN)
        quantity = steps * step_size

        if quantity < min_qty:
            quantity = min_qty

        return quantity.quantize(Decimal(10) ** -quantity_precision)

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        reduce_only: bool = False
    ) -> Optional[Dict]:
        """Place a market order."""
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
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

    async def place_stop_loss_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        stop_price: Decimal,
        current_price: Optional[Decimal] = None,
        symbol_info: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Place a stop loss order using Binance Algo Order API.
        Uses closePosition=true so the order auto-cancels when position is closed.
        As of Dec 2024, conditional orders must use /fapi/v1/algoOrder endpoint.
        """
        logger.info(f"Placing SL order: {symbol} {side} closePosition=true triggerPrice={stop_price}")

        if current_price:
            tolerance = current_price * Decimal('0.001')
            if side == 'SELL' and stop_price >= (current_price + tolerance):
                logger.error(f"SL price {stop_price} must be BELOW current price {current_price} for LONG position")
                return None
            if side == 'BUY' and stop_price <= (current_price - tolerance):
                logger.error(f"SL price {stop_price} must be ABOVE current price {current_price} for SHORT position")
                return None

        if symbol_info:
            stop_price = self._round_price(stop_price, symbol_info)

        params = {
            'symbol': symbol,
            'side': side,
            'algoType': 'CONDITIONAL',
            'type': 'STOP_MARKET',
            'closePosition': 'true',
            'triggerPrice': str(stop_price),
        }

        try:
            result = await self._request('POST', '/fapi/v1/algoOrder', params, signed=True)
            algo_id = result.get('algoId')
            logger.info(f"✅ Stop loss order placed: {side} {symbol} @ {stop_price} (closePosition) | AlgoID: {algo_id}")
            return {'orderId': str(algo_id), 'algoId': algo_id, **result}
        except Exception as e:
            logger.error(f"❌ Failed to place SL order for {symbol}: {e}")
            return None

    async def place_take_profit_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        take_profit_price: Decimal,
        current_price: Optional[Decimal] = None,
        symbol_info: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Place a take profit order using Binance Algo Order API.
        Uses closePosition=true so the order auto-cancels when position is closed.
        As of Dec 2024, conditional orders must use /fapi/v1/algoOrder endpoint.
        """
        logger.info(f"Placing TP order: {symbol} {side} closePosition=true triggerPrice={take_profit_price}")

        if current_price:
            tolerance = current_price * Decimal('0.001')
            if side == 'SELL' and take_profit_price <= (current_price - tolerance):
                logger.error(f"TP price {take_profit_price} must be ABOVE current price {current_price} for LONG position")
                return None
            if side == 'BUY' and take_profit_price >= (current_price + tolerance):
                logger.error(f"TP price {take_profit_price} must be BELOW current price {current_price} for SHORT position")
                return None

        if symbol_info:
            take_profit_price = self._round_price(take_profit_price, symbol_info)

        params = {
            'symbol': symbol,
            'side': side,
            'algoType': 'CONDITIONAL',
            'type': 'TAKE_PROFIT_MARKET',
            'closePosition': 'true',
            'triggerPrice': str(take_profit_price),
        }

        try:
            result = await self._request('POST', '/fapi/v1/algoOrder', params, signed=True)
            algo_id = result.get('algoId')
            logger.info(f"✅ Take profit order placed: {side} {symbol} @ {take_profit_price} (closePosition) | AlgoID: {algo_id}")
            return {'orderId': str(algo_id), 'algoId': algo_id, **result}
        except Exception as e:
            logger.error(f"❌ Failed to place TP order for {symbol}: {e}")
            return None

    async def place_trailing_stop_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        callback_rate: Decimal,
        activation_price: Optional[Decimal] = None
    ) -> Optional[Dict]:
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
            'symbol': symbol,
            'side': side,
            'type': 'TRAILING_STOP_MARKET',
            'quantity': str(quantity),
            'callbackRate': str(callback_rate),
            'reduceOnly': 'true',
        }

        if activation_price:
            params['activationPrice'] = str(activation_price)

        try:
            result = await self._request('POST', '/fapi/v1/order', params, signed=True)
            logger.info(
                f"Trailing stop order placed: {side} {quantity} {symbol} "
                f"(callback: {callback_rate}%, activation: {activation_price or 'immediate'})"
            )
            return result
        except Exception as e:
            logger.error(f"Failed to place trailing stop order: {e}")
            return None

    async def cancel_all_orders(self, symbol: str) -> bool:
        """Cancel all open orders for a symbol (both regular and algo orders)."""
        success = True

        try:
            await self._request(
                'DELETE',
                '/fapi/v1/allOpenOrders',
                {'symbol': symbol},
                signed=True
            )
            logger.info(f"Regular orders cancelled for {symbol}")
        except Exception as e:
            logger.warning(f"Failed to cancel regular orders for {symbol}: {e}")
            success = False

        try:
            algo_orders = await self._request(
                'GET',
                '/fapi/v1/allAlgoOrders',
                {'symbol': symbol, 'algoStatus': 'NEW'},
                signed=True
            )
            orders_list = algo_orders if isinstance(algo_orders, list) else algo_orders.get('rows', [])
            for order in orders_list:
                algo_id = order.get('algoId')
                if algo_id:
                    try:
                        await self._request(
                            'DELETE',
                            '/fapi/v1/algoOrder',
                            {'symbol': symbol, 'algoId': algo_id},
                            signed=True
                        )
                        logger.info(f"Cancelled algo order {algo_id} for {symbol}")
                    except Exception as e:
                        logger.warning(f"Failed to cancel algo order {algo_id}: {e}")
        except Exception as e:
            logger.warning(f"Failed to cancel algo orders for {symbol}: {e}")

        return success

    async def close_position(self, symbol: str, direction: str, quantity: Decimal) -> Optional[Dict]:
        """Close an open position."""
        side = 'SELL' if direction == 'LONG' else 'BUY'
        return await self.place_market_order(symbol, side, quantity, reduce_only=True)

    async def execute_trade_from_signal(
        self,
        signal_id: int,
        symbol_name: str,
        direction: str,
        sl: Decimal,
        tp: Decimal,
        confidence: Decimal
    ) -> Optional[Dict]:
        """
        Execute a futures trade based on signal data.
        This method only handles API calls, no DB operations.

        Args:
            signal_id: Signal ID for logging
            symbol_name: Symbol to trade (e.g., 'XRPUSDT')
            direction: 'LONG' or 'SHORT'
            sl: Stop loss price
            tp: Take profit price
            confidence: Signal confidence

        Returns:
            Dict with trade result if successful, None otherwise
        """
        try:
            symbol_info = await self.get_symbol_info(symbol_name)
            if not symbol_info:
                raise Exception(f"Could not get symbol info for {symbol_name}")

            current_price = await self.get_current_price(symbol_name)
            if not current_price:
                raise Exception(f"Could not get current price for {symbol_name}")

            return {
                'symbol_info': symbol_info,
                'current_price': current_price
            }

        except Exception as e:
            logger.error(f"❌ Failed to get market data for signal {signal_id}: {e}")
            return None

    async def place_trade_orders(
        self,
        symbol: str,
        direction: str,
        leverage: int,
        position_size: Decimal,
        sl: Decimal,
        tp: Decimal,
        symbol_info: Dict,
        current_price: Decimal
    ) -> Optional[Dict]:
        """
        Place market order with fixed SL/TP orders on Binance.
        Dynamic trailing stop will upgrade the SL later when profit tiers are reached.
        """
        logger.info(
            f"📊 TRADE EXECUTION START: {symbol} {direction} | "
            f"Margin: ${position_size} | Leverage: {leverage}x | "
            f"Notional: ${position_size * leverage} | Price: ${current_price} | "
            f"SL: ${sl} | TP: ${tp}"
        )
        errors = []

        try:
            margin_ok = await self.set_margin_type(symbol, 'ISOLATED')
            if not margin_ok:
                errors.append("Failed to set margin type")

            leverage_ok = await self.set_leverage(symbol, leverage)
            if not leverage_ok:
                errors.append(f"Failed to set leverage to {leverage}x")

            quantity = self._calculate_quantity(
                symbol_info,
                current_price,
                position_size,
                leverage
            )

            logger.info(
                f"📊 Quantity calculated: {quantity} {symbol} | "
                f"Expected Notional: ${float(quantity) * float(current_price):.2f}"
            )

            side = 'BUY' if direction == 'LONG' else 'SELL'
            entry_result = await self.place_market_order(symbol, side, quantity)

            if not entry_result:
                raise Exception("Failed to place entry order - insufficient balance or invalid parameters")

            avg_price = Decimal(entry_result.get('avgPrice', str(current_price)))

            logger.info(f"✅ Entry order filled: {direction} {quantity} {symbol} @ {avg_price}")

            sl_side = 'SELL' if direction == 'LONG' else 'BUY'
            tp_side = 'SELL' if direction == 'LONG' else 'BUY'

            sl_valid = sl
            tp_valid = tp

            if direction == 'LONG':
                if sl >= avg_price:
                    sl_valid = avg_price * Decimal('0.97')
                    logger.warning(f"SL {sl} >= entry {avg_price}, adjusted to {sl_valid}")
                if tp <= avg_price:
                    tp_valid = avg_price * Decimal('1.05')
                    logger.warning(f"TP {tp} <= entry {avg_price}, adjusted to {tp_valid}")
            else:
                if sl <= avg_price:
                    sl_valid = avg_price * Decimal('1.03')
                    logger.warning(f"SL {sl} <= entry {avg_price}, adjusted to {sl_valid}")
                if tp >= avg_price:
                    tp_valid = avg_price * Decimal('0.95')
                    logger.warning(f"TP {tp} >= entry {avg_price}, adjusted to {tp_valid}")

            sl_rounded = self._round_price(sl_valid, symbol_info)
            tp_rounded = self._round_price(tp_valid, symbol_info)

            logger.info(f"SL/TP after validation: SL={sl_rounded}, TP={tp_rounded}, Entry={avg_price}")

            sl_result = await self.place_stop_loss_order(
                symbol, sl_side, quantity, sl_rounded, avg_price, symbol_info
            )

            if not sl_result:
                logger.error(f"⚠️ CRITICAL: No stop loss protection for {symbol}! Position is unprotected!")

            tp_result = await self.place_take_profit_order(
                symbol, tp_side, quantity, tp_rounded, avg_price, symbol_info
            )

            if not tp_result:
                logger.warning(f"Failed to place TP order for {symbol}, but entry was successful")

            logger.info(
                f"✅ Futures trade opened: {direction} {quantity} {symbol} @ {avg_price} "
                f"(SL: {sl_rounded}, TP: {tp_rounded}, Leverage: {leverage}x)"
            )

            return {
                'quantity': quantity,
                'entry_price': avg_price,
                'order_id': str(entry_result.get('orderId', '')),
                'sl_order_id': str(sl_result.get('orderId', '')) if sl_result else None,
                'tp_order_id': str(tp_result.get('orderId', '')) if tp_result else None
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Failed to place orders for {symbol}: {error_msg}")
            raise Exception(f"{error_msg}. Previous errors: {'; '.join(errors)}" if errors else error_msg)

    async def close(self):
        """Close the session."""
        if self.session and not self.session.closed:
            await self.session.close()


class FuturesTradingService:
    """
    High-level service for futures trading operations.
    Handles DB operations synchronously and API calls asynchronously.
    """

    def __init__(self, use_testnet: bool = False):
        self.use_testnet = use_testnet

    def execute_signal(self, signal: Signal) -> Optional[FuturesTrade]:
        """
        Execute a futures trade from a signal.
        DB operations are sync, API calls run in a separate thread.

        Args:
            signal: Signal instance

        Returns:
            FuturesTrade if successful, None otherwise
        """
        trade_settings = FuturesTradingSettings.get_settings()

        if not trade_settings.is_enabled:
            logger.debug(f"Futures trading disabled, skipping signal {signal.id}")
            return None

        # Calculate if we are in Golden Window 2
        # GW2: 21:00-23:00 NPT (1260-1380 minutes) AND (Sun=6, Wed=2, Thu=3)
        utc_now = datetime.now(timezone.utc)
        nepal_now = utc_now + NEPAL_TZ_OFFSET
        day_minutes = nepal_now.hour * 60 + nepal_now.minute
        is_gw2 = False
        if (1260 <= day_minutes < 1380) and (nepal_now.weekday() in [6, 2, 3]):
            is_gw2 = True

        # Check trading window constraints
        # Logic: If use_trading_window is True, we must be in window OR be a valid GW2 trade if that's enabled
        if trade_settings.use_trading_window:
            in_window = is_within_trading_window()
            gw2_override = (trade_settings.trade_on_golden_window_2 and is_gw2)
            
            if not in_window and not gw2_override:
                logger.info(f"Signal {signal.id} outside trading window, skipping futures trade")
                return None
            
            if gw2_override and not in_window:
                logger.info(f"Signal {signal.id} is GW2 (Override), executing despite general window settings.")

        symbol_name = signal.symbol.symbol
        direction = signal.direction
        confidence = signal.confidence

        can_trade, reason = trade_settings.can_trade(symbol_name, direction, confidence)
        if not can_trade:
            logger.info(f"Cannot trade signal {signal.id}: {reason}")
            return None

        with transaction.atomic():
            existing_trade = FuturesTrade.objects.select_for_update().filter(
                symbol=symbol_name,
                direction=direction,
                status__in=['OPEN', 'PENDING']
            ).exists()

            if existing_trade:
                logger.info(f"Already have open/pending {direction} position on {symbol_name}")
                return None

            futures_trade = FuturesTrade.objects.create(
                signal=signal,
                symbol=symbol_name,
                direction=direction,
                leverage=trade_settings.leverage,
                quantity=Decimal('0'),
                stop_loss=signal.sl,
                take_profit=signal.tp,
                position_size_usdt=trade_settings.trade_amount,
                status='PENDING'
            )

        import threading

        api_result = [None]
        api_exception = [None]

        def run_api_calls():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    async def _execute():
                        trader = BinanceFuturesTrader(use_testnet=self.use_testnet)
                        try:
                            market_data = await trader.execute_trade_from_signal(
                                signal.id, symbol_name, direction,
                                signal.sl, signal.tp, confidence
                            )
                            if not market_data:
                                return None

                            result = await trader.place_trade_orders(
                                symbol_name, direction,
                                trade_settings.leverage,
                                trade_settings.trade_amount,
                                signal.sl, signal.tp,
                                market_data['symbol_info'],
                                market_data['current_price']
                            )
                            return result
                        finally:
                            await trader.close()
                    api_result[0] = loop.run_until_complete(_execute())
                finally:
                    loop.close()
            except Exception as e:
                api_exception[0] = e

        thread = threading.Thread(target=run_api_calls)
        thread.start()
        thread.join(timeout=60)

        if api_exception[0]:
            futures_trade.status = 'FAILED'
            futures_trade.error_message = str(api_exception[0])
            futures_trade.save()
            logger.error(f"❌ Futures trade failed for signal {signal.id}: {api_exception[0]}")
            return None

        if not api_result[0]:
            futures_trade.status = 'FAILED'
            futures_trade.error_message = "API call returned no result"
            futures_trade.save()
            return None

        result = api_result[0]
        futures_trade.quantity = result['quantity']
        futures_trade.entry_price = result['entry_price']
        futures_trade.binance_order_id = result['order_id']
        futures_trade.entry_time = dj_timezone.now()
        futures_trade.status = 'OPEN'

        # Save any warnings about SL/TP placement
        if result.get('warnings'):
            futures_trade.error_message = "Trade opened with warnings: " + "; ".join(result['warnings'])

        futures_trade.save()

        logger.info(
            f"💰 Futures trade opened: {direction} {result['quantity']} {symbol_name} "
            f"@ {result['entry_price']} (Trade ID: {futures_trade.id})"
        )

        if result.get('warnings'):
            logger.warning(f"⚠️ Trade {futures_trade.id} warnings: {result['warnings']}")

        return futures_trade

    def close_trade(self, trade: FuturesTrade) -> bool:
        """
        Close an open futures trade (sync wrapper).
        Handles both sync and async contexts properly.

        Args:
            trade: FuturesTrade instance to close

        Returns:
            True if successful, False otherwise
        """
        if not trade.is_open:
            logger.warning(f"Trade {trade.id} is not open")
            return False

        import threading

        result = [False]
        exception = [None]

        def run_in_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    async def _close():
                        trader = BinanceFuturesTrader(use_testnet=self.use_testnet)
                        try:
                            await trader.cancel_all_orders(trade.symbol)
                            close_result = await trader.close_position(
                                trade.symbol,
                                trade.direction,
                                trade.quantity
                            )
                            if close_result:
                                exit_price = Decimal(close_result.get('avgPrice', '0'))
                                trade.close_trade(exit_price, 'CLOSED_MANUAL')
                                logger.info(f"Futures trade {trade.id} closed @ {exit_price}")
                                return True
                            return False
                        finally:
                            await trader.close()
                    result[0] = loop.run_until_complete(_close())
                finally:
                    loop.close()
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join(timeout=60)

        if exception[0]:
            raise exception[0]
        return result[0]


futures_trading_service = FuturesTradingService(use_testnet=False)
