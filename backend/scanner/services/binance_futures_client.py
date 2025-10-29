"""
Binance Futures REST API client with async support.
"""
import aiohttp
import asyncio
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class BinanceFuturesClient:
    """Async Binance Futures REST API client."""

    BASE_URL = "https://fapi.binance.com"  # Futures API endpoint

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=10)
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=30,
            ttl_dns_cache=300,
            ssl=True
        )
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make an API request with retry logic."""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=10)
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30, ssl=True)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)

        url = f"{self.BASE_URL}{endpoint}"
        headers = {}

        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key

        retries = 3
        backoff = 1

        for attempt in range(retries):
            try:
                async with self.session.request(method, url, params=params, headers=headers) as response:
                    if response.status == 429:
                        retry_after = int(response.headers.get('Retry-After', backoff))
                        logger.warning(f"Rate limited. Retrying after {retry_after} seconds.")
                        await asyncio.sleep(retry_after)
                        backoff *= 2
                        continue

                    if response.status == 418:
                        logger.error("IP has been banned by Binance.")
                        raise Exception("IP banned by Binance API")

                    response.raise_for_status()
                    return await response.json()

            except aiohttp.ClientError as e:
                logger.error(f"Request failed (attempt {attempt + 1}/{retries}): {e}")
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2

        raise Exception(f"Failed to complete request after {retries} attempts")

    async def get_exchange_info(self) -> Dict:
        """Get futures exchange information."""
        return await self._request('GET', '/fapi/v1/exchangeInfo')

    async def get_usdt_futures_pairs(self) -> List[str]:
        """Get all USDT perpetual futures pairs."""
        exchange_info = await self.get_exchange_info()
        futures_pairs = [
            symbol['symbol']
            for symbol in exchange_info['symbols']
            if symbol['symbol'].endswith('USDT')
            and symbol['status'] == 'TRADING'
            and symbol['contractType'] == 'PERPETUAL'
        ]
        logger.info(f"Found {len(futures_pairs)} USDT perpetual futures pairs")
        return futures_pairs

    async def get_klines(
        self,
        symbol: str,
        interval: str = '5m',
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[List]:
        """Get futures candlestick data."""
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }

        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time

        return await self._request('GET', '/fapi/v1/klines', params)

    async def get_24h_ticker(self, symbol: str) -> Dict:
        """Get 24-hour futures price change statistics."""
        params = {'symbol': symbol}
        return await self._request('GET', '/fapi/v1/ticker/24hr', params)

    async def get_price(self, symbol: str) -> Dict:
        """Get latest futures price."""
        params = {'symbol': symbol}
        return await self._request('GET', '/fapi/v1/ticker/price', params)

    async def batch_get_klines(
        self,
        symbols: List[str],
        interval: str = '5m',
        limit: int = 100,
        batch_size: int = 20
    ) -> Dict[str, List[List]]:
        """Get klines for multiple futures symbols in batches."""
        results = {}

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            logger.info(f"Fetching futures klines for batch {i//batch_size + 1} ({len(batch)} symbols)")

            tasks = [
                self.get_klines(symbol, interval, limit)
                for symbol in batch
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for symbol, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to fetch klines for {symbol}: {result}")
                else:
                    results[symbol] = result

            if i + batch_size < len(symbols):
                await asyncio.sleep(0.5)

        return results

    async def close(self):
        """Close the client session."""
        if self.session:
            await self.session.close()
            self.session = None
