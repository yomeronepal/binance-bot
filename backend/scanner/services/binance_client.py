"""
Binance REST API client with async support and rate limiting.
"""
import aiohttp
import asyncio
import time
import socket
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimiter:
    """
    Thread-safe adaptive rate limiter for Binance API calls.

    Binance Limits (per IP):
    - Raw Request: 1200/min, 6000/5min
    - Order Rate: 10/sec, 100/10sec
    - Weight System: Each endpoint has weight (1-50)

    We use conservative limits to prevent 429 errors.
    """
    max_requests_per_minute: int = 800  # Conservative: 800/min (vs 1200 limit)
    max_requests_per_second: int = 10   # Conservative: 10/sec to avoid bursts
    max_weight_per_minute: int = 1000   # Conservative weight limit

    requests: List[float] = None
    _lock: asyncio.Lock = None
    _weight_tracker: List[tuple] = None  # (timestamp, weight) pairs
    _last_request_time: float = 0
    _consecutive_rate_limits: int = 0

    # Constants
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_PER_SECOND_WINDOW: float = 1.0
    RATE_LIMIT_BUFFER_SECONDS: float = 0.1
    MIN_REQUEST_INTERVAL: float = 0.1  # Minimum 100ms between requests

    def __post_init__(self):
        if self.requests is None:
            self.requests = []
        if self._weight_tracker is None:
            self._weight_tracker = []
        if self._lock is None:
            self._lock = asyncio.Lock()

    async def wait_if_needed(self, weight: int = 1):
        """
        Wait if rate limit is about to be exceeded. Thread-safe with asyncio.Lock.

        Args:
            weight: API weight of the request (default: 1)
        """
        async with self._lock:  # Ensure thread safety
            now = time.time()

            # Adaptive rate limiting: If we're getting rate limited, slow down
            if self._consecutive_rate_limits > 0:
                # Reduce to 50% capacity after rate limit
                effective_max_per_min = self.max_requests_per_minute // (2 ** self._consecutive_rate_limits)
                effective_max_per_sec = self.max_requests_per_second // 2
                logger.debug(f"Adaptive limit active: {effective_max_per_min}/min, {effective_max_per_sec}/sec")
            else:
                effective_max_per_min = self.max_requests_per_minute
                effective_max_per_sec = self.max_requests_per_second

            # 1. Enforce minimum interval between requests (prevent bursts)
            time_since_last = now - self._last_request_time
            if time_since_last < self.MIN_REQUEST_INTERVAL:
                sleep_time = self.MIN_REQUEST_INTERVAL - time_since_last
                await asyncio.sleep(sleep_time)
                now = time.time()

            # 2. Clean old requests (older than 1 minute)
            self.requests = [
                req_time for req_time in self.requests
                if now - req_time < self.RATE_LIMIT_WINDOW_SECONDS
            ]

            # 3. Clean old weight tracking (older than 1 minute)
            self._weight_tracker = [
                (ts, w) for ts, w in self._weight_tracker
                if now - ts < self.RATE_LIMIT_WINDOW_SECONDS
            ]

            # 4. Check per-second rate limit
            recent_requests = [
                req_time for req_time in self.requests
                if now - req_time < self.RATE_LIMIT_PER_SECOND_WINDOW
            ]

            if len(recent_requests) >= effective_max_per_sec:
                wait_time = self.RATE_LIMIT_PER_SECOND_WINDOW - (now - recent_requests[0]) + self.RATE_LIMIT_BUFFER_SECONDS
                logger.debug(f"⏸️  Per-second limit reached ({len(recent_requests)}/{effective_max_per_sec}). Waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                now = time.time()
                # Recalculate after sleep
                self.requests = [r for r in self.requests if now - r < self.RATE_LIMIT_WINDOW_SECONDS]

            # 5. Check per-minute rate limit
            if len(self.requests) >= effective_max_per_min:
                wait_time = (
                    self.RATE_LIMIT_WINDOW_SECONDS -
                    (now - self.requests[0]) +
                    self.RATE_LIMIT_BUFFER_SECONDS
                )
                logger.warning(f"⏸️  Per-minute limit reached ({len(self.requests)}/{effective_max_per_min}). Waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                now = time.time()
                self.requests = []

            # 6. Check weight limit
            current_weight = sum(w for _, w in self._weight_tracker)
            if current_weight + weight > self.max_weight_per_minute:
                # Wait for oldest weight to expire
                oldest_ts = min(ts for ts, _ in self._weight_tracker) if self._weight_tracker else now
                wait_time = self.RATE_LIMIT_WINDOW_SECONDS - (now - oldest_ts) + self.RATE_LIMIT_BUFFER_SECONDS
                logger.warning(f"⚖️  Weight limit reached ({current_weight + weight}/{self.max_weight_per_minute}). Waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                now = time.time()
                self._weight_tracker = []

            # Record this request
            self.requests.append(now)
            self._weight_tracker.append((now, weight))
            self._last_request_time = now

    def on_rate_limit_hit(self):
        """Call this when a 429 response is received."""
        self._consecutive_rate_limits += 1
        logger.warning(f"⚠️  Rate limit hit! Consecutive hits: {self._consecutive_rate_limits}")

    def on_successful_request(self):
        """Call this after successful request to reset adaptive limiting."""
        if self._consecutive_rate_limits > 0:
            self._consecutive_rate_limits = max(0, self._consecutive_rate_limits - 1)


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

    async def check_connectivity(self) -> bool:
        """
        Check if we can connect to Binance API.
        Returns True if connection successful, False otherwise.
        """
        try:
            # Simple ping to Binance API
            if not self.session:
                timeout = aiohttp.ClientTimeout(total=10, connect=5)
                connector = aiohttp.TCPConnector(ssl=True)
                self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)

            async with self.session.get(f"{self.BASE_URL}/api/v3/ping") as response:
                return response.status == 200
        except Exception as e:
            logger.warning(f"Connectivity check failed: {type(e).__name__}: {e}")
            return False

    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make an API request with rate limiting and retry logic.
        Handles DNS resolution, connection timeouts, and network failures.
        """
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=10)
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ssl=True,
                ttl_dns_cache=300,  # Cache DNS for 5 minutes
                force_close=False,  # Reuse connections
                enable_cleanup_closed=True
            )
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)

        url = f"{self.BASE_URL}{endpoint}"
        headers = {}

        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key

        # Enhanced retry configuration
        MAX_RETRIES = 5
        BASE_BACKOFF = 2
        MAX_BACKOFF = 60

        for attempt in range(MAX_RETRIES):
            try:
                # Determine endpoint weight (most klines endpoints are weight 1-2)
                weight = 2 if '/klines' in endpoint else 1
                await self.rate_limiter.wait_if_needed(weight=weight)

                async with self.session.request(method, url, params=params, headers=headers) as response:
                    if response.status == 429:  # Too many requests
                        self.rate_limiter.on_rate_limit_hit()  # Adaptive slowdown
                        retry_after = int(response.headers.get('Retry-After', BASE_BACKOFF * (2 ** attempt)))
                        logger.warning(
                            f"⏸️  Rate limited by Binance API (429). "
                            f"Retrying after {retry_after}s (attempt {attempt + 1}/{MAX_RETRIES})"
                        )
                        await asyncio.sleep(min(retry_after, MAX_BACKOFF))
                        continue

                    if response.status == 418:  # IP banned
                        logger.error("🚫 IP has been banned by Binance.")
                        raise Exception("IP banned by Binance API")

                    response.raise_for_status()

                    # Successful request - reset adaptive limiting
                    self.rate_limiter.on_successful_request()
                    return await response.json()

            except socket.gaierror as e:
                # DNS resolution failure
                backoff = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                logger.error(
                    f"🌐 DNS resolution failed for {self.BASE_URL}: {e}\n"
                    f"   Attempt {attempt + 1}/{MAX_RETRIES}. Retrying in {backoff}s...\n"
                    f"   This usually means: No internet connection or DNS server unavailable"
                )
                if attempt == MAX_RETRIES - 1:
                    raise ConnectionError(
                        f"Cannot resolve {self.BASE_URL} after {MAX_RETRIES} attempts. "
                        "Check internet connection and DNS settings."
                    ) from e
                await asyncio.sleep(backoff)

            except (aiohttp.ClientConnectorError, aiohttp.ServerTimeoutError) as e:
                # Connection or timeout errors
                backoff = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                logger.warning(
                    f"🔌 Connection error to {self.BASE_URL}: {type(e).__name__}\n"
                    f"   Attempt {attempt + 1}/{MAX_RETRIES}. Retrying in {backoff}s..."
                )
                if attempt == MAX_RETRIES - 1:
                    raise ConnectionError(
                        f"Cannot connect to {self.BASE_URL} after {MAX_RETRIES} attempts. "
                        "Check internet connection, firewall, or VPN settings."
                    ) from e
                await asyncio.sleep(backoff)

            except aiohttp.ClientError as e:
                # Other client errors
                backoff = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                logger.error(
                    f"❌ Request failed: {type(e).__name__}: {e}\n"
                    f"   Attempt {attempt + 1}/{MAX_RETRIES}. Retrying in {backoff}s..."
                )
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(backoff)

            except asyncio.TimeoutError as e:
                # Async timeout
                backoff = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                logger.warning(
                    f"⏱️  Request timeout to {endpoint}\n"
                    f"   Attempt {attempt + 1}/{MAX_RETRIES}. Retrying in {backoff}s..."
                )
                if attempt == MAX_RETRIES - 1:
                    raise TimeoutError(
                        f"Request to {endpoint} timed out after {MAX_RETRIES} attempts"
                    ) from e
                await asyncio.sleep(backoff)

        raise Exception(f"Failed to complete request to {endpoint} after {MAX_RETRIES} attempts")
    
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
        batch_size: int = 5,  # Reduced from 20 to 5 concurrent requests
        delay_between_batches: float = 1.0  # Increased delay between batches
    ) -> Dict[str, List[List]]:
        """
        Get klines for multiple symbols in batches with optimized rate limiting.

        Optimizations:
        - Reduced concurrent requests from 20 to 5 (prevents overwhelming API)
        - Increased delay between batches to 1 second
        - Better error handling and progress tracking
        - Semaphore-based concurrency control

        Args:
            symbols: List of trading pairs
            interval: Kline interval
            limit: Number of candles per symbol
            batch_size: Number of concurrent requests (default: 5, max recommended: 10)
            delay_between_batches: Seconds to wait between batches (default: 1.0)

        Returns:
            Dictionary mapping symbol to klines
        """
        results = {}
        total_batches = (len(symbols) + batch_size - 1) // batch_size

        logger.info(
            f"📊 Fetching klines for {len(symbols)} symbols in {total_batches} batches "
            f"(batch_size={batch_size}, delay={delay_between_batches}s)"
        )

        # Use semaphore to limit concurrent requests within batch
        semaphore = asyncio.Semaphore(batch_size)

        async def fetch_with_semaphore(symbol: str) -> tuple:
            """Fetch klines with semaphore-controlled concurrency."""
            async with semaphore:
                try:
                    klines = await self.get_klines(symbol, interval, limit)
                    return symbol, klines, None
                except Exception as e:
                    logger.debug(f"⚠️  Failed to fetch {symbol}: {type(e).__name__}: {e}")
                    return symbol, None, e

        # Process in batches to avoid overwhelming the API
        for batch_num, i in enumerate(range(0, len(symbols), batch_size), 1):
            batch = symbols[i:i + batch_size]
            batch_start_time = time.time()

            logger.info(f"  Batch {batch_num}/{total_batches}: Fetching {len(batch)} symbols...")

            # Create tasks for this batch
            tasks = [fetch_with_semaphore(symbol) for symbol in batch]

            # Execute batch with timeout
            try:
                batch_results = await asyncio.wait_for(
                    asyncio.gather(*tasks),
                    timeout=30.0  # 30 second timeout per batch
                )

                # Process results
                success_count = 0
                error_count = 0
                for symbol, klines, error in batch_results:
                    if error is None and klines:
                        results[symbol] = klines
                        success_count += 1
                    else:
                        error_count += 1
                        logger.warning(f"    ❌ {symbol}: {error}")

                batch_duration = time.time() - batch_start_time
                logger.info(
                    f"  ✅ Batch {batch_num}/{total_batches} complete: "
                    f"{success_count} succeeded, {error_count} failed "
                    f"({batch_duration:.1f}s)"
                )

            except asyncio.TimeoutError:
                logger.error(f"  ⏱️  Batch {batch_num} timed out after 30 seconds")
                # Continue to next batch

            # Delay between batches (except after last batch)
            if i + batch_size < len(symbols):
                logger.debug(f"  ⏸️  Waiting {delay_between_batches}s before next batch...")
                await asyncio.sleep(delay_between_batches)

        logger.info(
            f"✅ Batch fetch complete: {len(results)}/{len(symbols)} symbols fetched successfully "
            f"({len(results)/len(symbols)*100:.1f}%)"
        )

        return results
    
    async def close(self):
        """Close the client session."""
        if self.session:
            await self.session.close()
            self.session = None
