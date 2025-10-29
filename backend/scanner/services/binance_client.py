"""
Binance REST API client with async support and rate limiting.
"""
import aiohttp
import asyncio
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimiter:
    """Rate limiter for Binance API calls."""
    max_requests_per_minute: int = 1200
    requests: List[float] = None
    
    def __post_init__(self):
        if self.requests is None:
            self.requests = []
    
    async def wait_if_needed(self):
        """Wait if rate limit is about to be exceeded."""
        now = time.time()
        # Remove requests older than 1 minute
        self.requests = [req_time for req_time in self.requests if now - req_time < 60]
        
        if len(self.requests) >= self.max_requests_per_minute:
            # Wait until the oldest request is more than 1 minute old
            wait_time = 60 - (now - self.requests[0]) + 0.1
            logger.warning(f"Rate limit reached. Waiting {wait_time:.2f} seconds.")
            await asyncio.sleep(wait_time)
            self.requests = []
        
        self.requests.append(now)


class BinanceClient:
    """Async Binance REST API client."""
    
    BASE_URL = "https://api.binance.com"
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limiter = RateLimiter()
    
    async def __aenter__(self):
        """Async context manager entry."""
        # Create timeout and connector with better settings
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=10)
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=30,
            ttl_dns_cache=300,
            ssl=True  # Enable SSL verification
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
        """Make an API request with rate limiting and retry logic."""
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
                await self.rate_limiter.wait_if_needed()
                
                async with self.session.request(method, url, params=params, headers=headers) as response:
                    if response.status == 429:  # Too many requests
                        retry_after = int(response.headers.get('Retry-After', backoff))
                        logger.warning(f"Rate limited. Retrying after {retry_after} seconds.")
                        await asyncio.sleep(retry_after)
                        backoff *= 2
                        continue
                    
                    if response.status == 418:  # IP banned
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
        """Get exchange information including all trading pairs."""
        return await self._request('GET', '/api/v3/exchangeInfo')
    
    async def get_usdt_pairs(self) -> List[str]:
        """Get all USDT trading pairs."""
        exchange_info = await self.get_exchange_info()
        usdt_pairs = [
            symbol['symbol']
            for symbol in exchange_info['symbols']
            if symbol['symbol'].endswith('USDT') and symbol['status'] == 'TRADING'
        ]
        logger.info(f"Found {len(usdt_pairs)} USDT pairs")
        return usdt_pairs
    
    async def get_klines(
        self,
        symbol: str,
        interval: str = '5m',
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[List]:
        """
        Get candlestick data (klines).
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            interval: Kline interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
            limit: Number of candles to fetch (max 1000)
            start_time: Start time in milliseconds
            end_time: End time in milliseconds
        
        Returns:
            List of klines, each kline is a list:
            [
                open_time, open, high, low, close, volume,
                close_time, quote_volume, trades, taker_buy_base, taker_buy_quote, ignore
            ]
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        return await self._request('GET', '/api/v3/klines', params)
    
    async def get_24h_ticker(self, symbol: str) -> Dict:
        """Get 24-hour price change statistics."""
        params = {'symbol': symbol}
        return await self._request('GET', '/api/v3/ticker/24hr', params)
    
    async def get_price(self, symbol: str) -> Dict:
        """Get latest price for a symbol."""
        params = {'symbol': symbol}
        return await self._request('GET', '/api/v3/ticker/price', params)
    
    async def batch_get_klines(
        self,
        symbols: List[str],
        interval: str = '5m',
        limit: int = 100,
        batch_size: int = 20
    ) -> Dict[str, List[List]]:
        """
        Get klines for multiple symbols in batches.
        
        Args:
            symbols: List of trading pairs
            interval: Kline interval
            limit: Number of candles per symbol
            batch_size: Number of concurrent requests
        
        Returns:
            Dictionary mapping symbol to klines
        """
        results = {}
        
        # Process in batches to avoid overwhelming the API
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            logger.info(f"Fetching klines for batch {i//batch_size + 1} ({len(batch)} symbols)")
            
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
            
            # Small delay between batches
            if i + batch_size < len(symbols):
                await asyncio.sleep(0.5)
        
        return results
    
    async def close(self):
        """Close the client session."""
        if self.session:
            await self.session.close()
            self.session = None
