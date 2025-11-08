"""
Alpha Vantage API Client for Forex Data
Provides OHLCV data for forex currency pairs using Alpha Vantage free API

API Documentation: https://www.alphavantage.co/documentation/
Free Tier: 500 requests/day
Supported Intervals: 1min, 5min, 15min, 30min, 60min (intraday), daily, weekly, monthly
"""
import os
import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


class AlphaVantageClient:
    """
    Alpha Vantage API client for forex data
    """

    BASE_URL = "https://www.alphavantage.co/query"

    # Interval mapping from our format to Alpha Vantage format
    INTERVAL_MAP = {
        '1m': '1min',
        '5m': '5min',
        '15m': '15min',
        '30m': '30min',
        '1h': '60min',
        '4h': '60min',  # Will need to aggregate
        '1d': 'daily',
        'daily': 'daily',
        'weekly': 'weekly',
        'monthly': 'monthly'
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Alpha Vantage client

        Args:
            api_key: Alpha Vantage API key (defaults to environment variable)
        """
        self.api_key = api_key or os.getenv('ALPHAVANTAGE_API_KEY', 'demo')

        if self.api_key == 'demo':
            logger.warning(
                "⚠️ Using demo API key for Alpha Vantage. "
                "Get a free key at https://www.alphavantage.co/support/#api-key"
            )

    def _format_symbol(self, symbol: str) -> tuple:
        """
        Convert symbol to Alpha Vantage format

        Args:
            symbol: Symbol like 'EURUSD' or 'EUR/USD'

        Returns:
            Tuple of (from_currency, to_currency)
        """
        # Remove slashes and spaces
        symbol = symbol.replace('/', '').replace(' ', '').upper()

        # Currency pairs are 6 characters (e.g., EURUSD)
        if len(symbol) == 6:
            from_currency = symbol[:3]
            to_currency = symbol[3:]
            return from_currency, to_currency
        else:
            raise ValueError(f"Invalid forex symbol format: {symbol}")

    async def get_forex_intraday(
        self,
        symbol: str,
        interval: str = '15m',
        outputsize: str = 'compact'
    ) -> List[List]:
        """
        Fetch intraday forex data

        Args:
            symbol: Currency pair (e.g., 'EURUSD')
            interval: Timeframe ('1m', '5m', '15m', '30m', '1h')
            outputsize: 'compact' (100 data points) or 'full' (full history)

        Returns:
            List of klines in Binance-compatible format:
            [timestamp_ms, open, high, low, close, volume, ...]
        """
        try:
            from_currency, to_currency = self._format_symbol(symbol)
            av_interval = self.INTERVAL_MAP.get(interval, '15min')

            params = {
                'function': 'FX_INTRADAY',
                'from_symbol': from_currency,
                'to_symbol': to_currency,
                'interval': av_interval,
                'outputsize': outputsize,
                'apikey': self.api_key
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Alpha Vantage API error: {response.status}")
                        return []

                    data = await response.json()

                    # Check for error messages
                    if 'Error Message' in data:
                        logger.error(f"Alpha Vantage error: {data['Error Message']}")
                        return []

                    if 'Note' in data:
                        logger.warning(f"Alpha Vantage rate limit: {data['Note']}")
                        return []

                    # Parse time series data
                    time_series_key = f'Time Series FX ({av_interval})'
                    if time_series_key not in data:
                        logger.warning(f"No data returned for {symbol} {interval}")
                        return []

                    time_series = data[time_series_key]

                    # Convert to Binance-compatible format
                    klines = []
                    for timestamp_str, ohlc in time_series.items():
                        try:
                            # Parse timestamp
                            dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                            timestamp_ms = int(dt.timestamp() * 1000)

                            # Extract OHLC values
                            open_price = float(ohlc['1. open'])
                            high_price = float(ohlc['2. high'])
                            low_price = float(ohlc['3. low'])
                            close_price = float(ohlc['4. close'])

                            # Forex doesn't have volume, use 0
                            volume = 0

                            # Binance-compatible format
                            kline = [
                                timestamp_ms,       # Open time
                                str(open_price),    # Open
                                str(high_price),    # High
                                str(low_price),     # Low
                                str(close_price),   # Close
                                str(volume),        # Volume (not available for forex)
                                timestamp_ms,       # Close time
                                "0",                # Quote asset volume
                                0,                  # Number of trades
                                "0",                # Taker buy base asset volume
                                "0",                # Taker buy quote asset volume
                                "0"                 # Ignore
                            ]

                            klines.append(kline)

                        except Exception as e:
                            logger.error(f"Error parsing kline data: {e}")
                            continue

                    # Sort by timestamp (oldest first)
                    klines.sort(key=lambda x: x[0])

                    logger.info(f"✅ Fetched {len(klines)} candles for {symbol} ({interval})")
                    return klines

        except Exception as e:
            logger.error(f"Error fetching forex data for {symbol}: {e}", exc_info=True)
            return []

    async def get_forex_daily(
        self,
        symbol: str,
        outputsize: str = 'compact'
    ) -> List[List]:
        """
        Fetch daily forex data

        Args:
            symbol: Currency pair (e.g., 'EURUSD')
            outputsize: 'compact' (100 data points) or 'full' (20+ years)

        Returns:
            List of klines in Binance-compatible format
        """
        try:
            from_currency, to_currency = self._format_symbol(symbol)

            params = {
                'function': 'FX_DAILY',
                'from_symbol': from_currency,
                'to_symbol': to_currency,
                'outputsize': outputsize,
                'apikey': self.api_key
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Alpha Vantage API error: {response.status}")
                        return []

                    data = await response.json()

                    # Check for errors
                    if 'Error Message' in data:
                        logger.error(f"Alpha Vantage error: {data['Error Message']}")
                        return []

                    if 'Note' in data:
                        logger.warning(f"Alpha Vantage rate limit: {data['Note']}")
                        return []

                    # Parse time series data
                    time_series_key = 'Time Series FX (Daily)'
                    if time_series_key not in data:
                        logger.warning(f"No data returned for {symbol} daily")
                        return []

                    time_series = data[time_series_key]

                    # Convert to Binance-compatible format
                    klines = []
                    for date_str, ohlc in time_series.items():
                        try:
                            # Parse date (daily data doesn't have time)
                            dt = datetime.strptime(date_str, '%Y-%m-%d')
                            timestamp_ms = int(dt.timestamp() * 1000)

                            # Extract OHLC values
                            open_price = float(ohlc['1. open'])
                            high_price = float(ohlc['2. high'])
                            low_price = float(ohlc['3. low'])
                            close_price = float(ohlc['4. close'])
                            volume = 0  # No volume for forex

                            # Binance-compatible format
                            kline = [
                                timestamp_ms,
                                str(open_price),
                                str(high_price),
                                str(low_price),
                                str(close_price),
                                str(volume),
                                timestamp_ms,
                                "0", "0", "0", "0", "0"
                            ]

                            klines.append(kline)

                        except Exception as e:
                            logger.error(f"Error parsing daily kline data: {e}")
                            continue

                    # Sort by timestamp
                    klines.sort(key=lambda x: x[0])

                    logger.info(f"✅ Fetched {len(klines)} daily candles for {symbol}")
                    return klines

        except Exception as e:
            logger.error(f"Error fetching daily forex data for {symbol}: {e}", exc_info=True)
            return []

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 200
    ) -> List[List]:
        """
        Unified method to fetch forex klines

        Args:
            symbol: Currency pair
            interval: Timeframe ('15m', '1h', '4h', '1d')
            limit: Number of candles (Alpha Vantage limits: 100 compact, full for more)

        Returns:
            List of klines
        """
        # Determine output size based on limit
        outputsize = 'full' if limit > 100 else 'compact'

        # Route to appropriate endpoint
        if interval in ['1d', 'daily']:
            klines = await self.get_forex_daily(symbol, outputsize)
        else:
            klines = await self.get_forex_intraday(symbol, interval, outputsize)

        # Limit results
        if len(klines) > limit:
            klines = klines[-limit:]

        # Handle 4h aggregation (Alpha Vantage doesn't have 4h, so aggregate from 1h)
        if interval == '4h' and klines:
            klines = self._aggregate_to_4h(klines)

        return klines

    def _aggregate_to_4h(self, hourly_klines: List[List]) -> List[List]:
        """
        Aggregate 1-hour candles into 4-hour candles

        Args:
            hourly_klines: List of 1h klines

        Returns:
            List of 4h klines
        """
        if not hourly_klines:
            return []

        aggregated = []
        temp_candles = []

        for kline in hourly_klines:
            timestamp_ms = kline[0]
            dt = datetime.fromtimestamp(timestamp_ms / 1000)

            # Check if this hour is a 4h boundary (0, 4, 8, 12, 16, 20)
            if dt.hour % 4 == 0 and temp_candles:
                # Aggregate previous 4 hours
                agg_kline = self._merge_klines(temp_candles)
                aggregated.append(agg_kline)
                temp_candles = []

            temp_candles.append(kline)

        # Add remaining candles
        if temp_candles:
            agg_kline = self._merge_klines(temp_candles)
            aggregated.append(agg_kline)

        return aggregated

    def _merge_klines(self, klines: List[List]) -> List:
        """Merge multiple klines into one"""
        if not klines:
            return []

        if len(klines) == 1:
            return klines[0]

        # First candle's open time
        open_time = klines[0][0]

        # First candle's open price
        open_price = klines[0][1]

        # Highest high
        high_price = max(float(k[2]) for k in klines)

        # Lowest low
        low_price = min(float(k[3]) for k in klines)

        # Last candle's close price
        close_price = klines[-1][4]

        # Last candle's close time
        close_time = klines[-1][6]

        # Volume (sum, though forex doesn't use it)
        volume = sum(float(k[5]) for k in klines)

        return [
            open_time,
            open_price,
            str(high_price),
            str(low_price),
            close_price,
            str(volume),
            close_time,
            "0", "0", "0", "0", "0"
        ]

    async def batch_get_klines(
        self,
        pairs: List[str],
        interval: str,
        limit: int = 200
    ) -> Dict[str, List]:
        """
        Fetch klines for multiple pairs (with rate limiting)

        Args:
            pairs: List of currency pairs
            interval: Timeframe
            limit: Number of candles per pair

        Returns:
            Dict mapping symbol to klines
        """
        result = {}

        for i, pair in enumerate(pairs):
            try:
                klines = await self.get_klines(pair, interval, limit)

                if klines:
                    result[pair] = klines

                # Rate limiting: 5 requests per minute (free tier)
                # Wait 12 seconds between requests to stay under limit
                if i < len(pairs) - 1:
                    await asyncio.sleep(12)

            except Exception as e:
                logger.error(f"Error fetching {pair}: {e}")
                continue

        return result
