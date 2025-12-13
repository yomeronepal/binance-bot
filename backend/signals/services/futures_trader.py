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

from ..models_futures import FuturesTradingSettings, FuturesTrade
from ..models import Signal

logger = logging.getLogger(__name__)

NEPAL_TZ_OFFSET = timedelta(hours=5, minutes=45)
TRADING_WINDOWS = [
    (17, 0, 18, 0),
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
            params['timestamp'] = int(time.time() * 1000)
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
        stop_price: Decimal
    ) -> Optional[Dict]:
        """Place a stop-market order for stop loss."""
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'STOP_MARKET',
            'quantity': str(quantity),
            'stopPrice': str(stop_price),
            'reduceOnly': 'true',
        }

        try:
            result = await self._request('POST', '/fapi/v1/order', params, signed=True)
            logger.info(f"Stop loss order placed: {side} {quantity} {symbol} @ {stop_price}")
            return result
        except Exception as e:
            logger.error(f"Failed to place stop loss order: {e}")
            return None

    async def place_take_profit_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        take_profit_price: Decimal
    ) -> Optional[Dict]:
        """Place a take-profit-market order."""
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'TAKE_PROFIT_MARKET',
            'quantity': str(quantity),
            'stopPrice': str(take_profit_price),
            'reduceOnly': 'true',
        }

        try:
            result = await self._request('POST', '/fapi/v1/order', params, signed=True)
            logger.info(f"Take profit order placed: {side} {quantity} {symbol} @ {take_profit_price}")
            return result
        except Exception as e:
            logger.error(f"Failed to place take profit order: {e}")
            return None

    async def cancel_all_orders(self, symbol: str) -> bool:
        """Cancel all open orders for a symbol."""
        try:
            await self._request(
                'DELETE',
                '/fapi/v1/allOpenOrders',
                {'symbol': symbol},
                signed=True
            )
            logger.info(f"All orders cancelled for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel orders for {symbol}: {e}")
            return False

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
        Place market order with SL/TP orders on Binance.
        This method only handles API calls, no DB operations.
        """
        try:
            await self.set_margin_type(symbol, 'ISOLATED')
            await self.set_leverage(symbol, leverage)

            quantity = self._calculate_quantity(
                symbol_info,
                current_price,
                position_size,
                leverage
            )

            side = 'BUY' if direction == 'LONG' else 'SELL'
            entry_result = await self.place_market_order(symbol, side, quantity)

            if not entry_result:
                raise Exception("Failed to place entry order")

            avg_price = Decimal(entry_result.get('avgPrice', str(current_price)))

            sl_side = 'SELL' if direction == 'LONG' else 'BUY'
            tp_side = 'SELL' if direction == 'LONG' else 'BUY'

            await self.place_stop_loss_order(symbol, sl_side, quantity, sl)
            await self.place_take_profit_order(symbol, tp_side, quantity, tp)

            logger.info(
                f"✅ Futures trade opened: {direction} {quantity} {symbol} @ {avg_price} "
                f"(SL: {sl}, TP: {tp}, Leverage: {leverage}x)"
            )

            return {
                'quantity': quantity,
                'entry_price': avg_price,
                'order_id': str(entry_result.get('orderId', ''))
            }

        except Exception as e:
            logger.error(f"❌ Failed to place orders for {symbol}: {e}")
            raise

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

        existing_trade = FuturesTrade.objects.filter(
            symbol=symbol_name,
            direction=direction,
            status='OPEN'
        ).exists()

        if existing_trade:
            logger.info(f"Already have open {direction} position on {symbol_name}")
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
        futures_trade.save()

        logger.info(
            f"💰 Futures trade opened: {direction} {result['quantity']} {symbol_name} "
            f"@ {result['entry_price']} (Trade ID: {futures_trade.id})"
        )

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
