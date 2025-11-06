"""
Historical Data Fetcher for Backtesting
Fetches historical candlestick data from Binance for backtesting purposes.
"""
import asyncio
import aiohttp
import logging
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd
from django.utils import timezone

logger = logging.getLogger(__name__)


class HistoricalDataFetcher:
    """
    Fetches historical OHLCV data from Binance.
    Handles rate limiting, pagination, and data validation.
    """

    def __init__(self):
        self.base_url = "https://api.binance.com"
        self.rate_limit_delay = 0.2  # seconds between requests

    async def fetch_historical_klines(
        self,
        symbol: str,
        interval: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 1000
    ) -> List[Dict]:
        """
        Fetch historical klines (candlestick data) for a symbol.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Timeframe (e.g., '1m', '5m', '15m', '1h', '4h', '1d')
            start_date: Start of historical period
            end_date: End of historical period
            limit: Max candles per request (max 1000)

        Returns:
            List of candle dictionaries with OHLCV data
        """
        all_klines = []
        current_start = start_date

        async with aiohttp.ClientSession() as session:
            while current_start < end_date:
                try:
                    # Build request params
                    params = {
                        'symbol': symbol,
                        'interval': interval,
                        'startTime': int(current_start.timestamp() * 1000),
                        'endTime': int(end_date.timestamp() * 1000),
                        'limit': limit
                    }

                    # Make API request
                    url = f"{self.base_url}/api/v3/klines"
                    async with session.get(url, params=params, timeout=30) as response:
                        if response.status == 200:
                            data = await response.json()

                            if not data:
                                logger.info(f"No more data for {symbol} after {current_start}")
                                break

                            # Parse klines
                            for kline in data:
                                candle = self._parse_kline(kline)
                                all_klines.append(candle)

                            # Update start time for next batch
                            last_timestamp = data[-1][6]  # Close time
                            current_start = datetime.fromtimestamp(last_timestamp / 1000) + timedelta(seconds=1)

                            logger.debug(
                                f"Fetched {len(data)} candles for {symbol} "
                                f"(Total: {len(all_klines)})"
                            )

                            # Rate limiting
                            await asyncio.sleep(self.rate_limit_delay)

                        elif response.status == 429:
                            # Rate limit hit, back off
                            logger.warning(f"Rate limit hit for {symbol}, backing off...")
                            await asyncio.sleep(5)

                        else:
                            logger.error(
                                f"Error fetching {symbol}: {response.status} - {await response.text()}"
                            )
                            break

                except Exception as e:
                    logger.error(f"Exception fetching historical data for {symbol}: {e}", exc_info=True)
                    break

        logger.info(f"✅ Fetched {len(all_klines)} total candles for {symbol}")
        return all_klines

    def _parse_kline(self, kline: List) -> Dict:
        """
        Parse raw Binance kline data into structured dictionary.

        Binance kline format:
        [
            0: Open time,
            1: Open,
            2: High,
            3: Low,
            4: Close,
            5: Volume,
            6: Close time,
            7: Quote asset volume,
            8: Number of trades,
            9: Taker buy base asset volume,
            10: Taker buy quote asset volume,
            11: Ignore
        ]
        """
        return {
            'timestamp': datetime.fromtimestamp(kline[0] / 1000),
            'open': Decimal(str(kline[1])),
            'high': Decimal(str(kline[2])),
            'low': Decimal(str(kline[3])),
            'close': Decimal(str(kline[4])),
            'volume': Decimal(str(kline[5])),
            'close_time': datetime.fromtimestamp(kline[6] / 1000),
            'quote_volume': Decimal(str(kline[7])),
            'trades': int(kline[8]),
            'taker_buy_base': Decimal(str(kline[9])),
            'taker_buy_quote': Decimal(str(kline[10])),
        }

    async def fetch_multiple_symbols(
        self,
        symbols: List[str],
        interval: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, List[Dict]]:
        """
        Fetch historical data for multiple symbols in parallel.

        Args:
            symbols: List of trading pairs
            interval: Timeframe
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary mapping symbol to list of candles
        """
        tasks = []
        for symbol in symbols:
            task = self.fetch_historical_klines(symbol, interval, start_date, end_date)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Map results to symbols
        symbol_data = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch {symbol}: {result}")
                symbol_data[symbol] = []
            else:
                symbol_data[symbol] = result

        return symbol_data

    def klines_to_dataframe(self, klines: List[Dict]) -> pd.DataFrame:
        """
        Convert klines list to pandas DataFrame for analysis.

        Args:
            klines: List of candle dictionaries

        Returns:
            DataFrame with OHLCV columns
        """
        if not klines:
            return pd.DataFrame()

        df = pd.DataFrame(klines)

        # Convert Decimal to float for pandas compatibility
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_volume',
                       'taker_buy_base', 'taker_buy_quote']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(float)

        # Set timestamp as index
        if 'timestamp' in df.columns:
            df.set_index('timestamp', inplace=True)

        return df

    def validate_data_completeness(
        self,
        klines: List[Dict],
        interval: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, any]:
        """
        Validate if historical data is complete (no gaps).

        Returns:
            Dictionary with validation results
        """
        if not klines:
            return {
                'is_complete': False,
                'expected_count': 0,
                'actual_count': 0,
                'missing_count': 0,
                'gaps': []
            }

        # Calculate expected candle count based on interval
        interval_minutes = self._interval_to_minutes(interval)
        if interval_minutes is None:
            return {'is_complete': False, 'error': 'Invalid interval'}

        total_minutes = (end_date - start_date).total_seconds() / 60
        expected_count = int(total_minutes / interval_minutes)

        actual_count = len(klines)
        missing_count = expected_count - actual_count

        # Find gaps
        gaps = []
        for i in range(len(klines) - 1):
            current_time = klines[i]['close_time']
            next_time = klines[i + 1]['timestamp']
            expected_next = current_time + timedelta(minutes=interval_minutes)

            if next_time > expected_next + timedelta(minutes=interval_minutes):
                gap_size = int((next_time - expected_next).total_seconds() / 60 / interval_minutes)
                gaps.append({
                    'start': current_time,
                    'end': next_time,
                    'missing_candles': gap_size
                })

        is_complete = missing_count <= (expected_count * 0.01)  # Allow 1% tolerance

        return {
            'is_complete': is_complete,
            'expected_count': expected_count,
            'actual_count': actual_count,
            'missing_count': missing_count,
            'completeness_percentage': (actual_count / expected_count * 100) if expected_count > 0 else 0,
            'gaps': gaps,
            'gap_count': len(gaps)
        }

    def _interval_to_minutes(self, interval: str) -> Optional[int]:
        """Convert interval string to minutes."""
        mappings = {
            '1m': 1,
            '3m': 3,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '2h': 120,
            '4h': 240,
            '6h': 360,
            '8h': 480,
            '12h': 720,
            '1d': 1440,
            '3d': 4320,
            '1w': 10080,
            '1M': 43200,
        }
        return mappings.get(interval)

    async def get_earliest_available_date(self, symbol: str, interval: str) -> Optional[datetime]:
        """
        Find the earliest date for which data is available.

        Args:
            symbol: Trading pair
            interval: Timeframe

        Returns:
            Earliest available datetime or None
        """
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'symbol': symbol,
                    'interval': interval,
                    'limit': 1
                }

                url = f"{self.base_url}/api/v3/klines"
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            timestamp = data[0][0]
                            return datetime.fromtimestamp(timestamp / 1000)

        except Exception as e:
            logger.error(f"Error getting earliest date for {symbol}: {e}")

        return None

    def fetch_from_csv(
        self,
        csv_path: str,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """
        Load historical data from CSV file.

        CSV format expected:
        datetime,open,high,low,close,volume,quote_volume,trades
        2024-12-01T05:45:00,96475.2,96594.8,96402.6,96576.2,348.573,33639893.9507,6698

        Args:
            csv_path: Path to CSV file
            symbol: Trading pair symbol
            start_date: Start date (timezone-aware)
            end_date: End date (timezone-aware)

        Returns:
            List of candle dictionaries
        """
        try:
            logger.info(f"Loading {symbol} from CSV: {csv_path}")

            # Read CSV
            df = pd.read_csv(csv_path)

            # Parse datetime column (handle both 'datetime' and 'timestamp' column names)
            datetime_col = 'datetime' if 'datetime' in df.columns else 'timestamp'
            df['datetime'] = pd.to_datetime(df[datetime_col])

            # Make start/end dates naive for comparison with CSV data
            if timezone.is_aware(start_date):
                start_date_naive = timezone.make_naive(start_date)
            else:
                start_date_naive = start_date

            if timezone.is_aware(end_date):
                end_date_naive = timezone.make_naive(end_date)
            else:
                end_date_naive = end_date

            # Filter date range
            df = df[(df['datetime'] >= start_date_naive) & (df['datetime'] <= end_date_naive)]

            logger.info(f"Filtered to {len(df)} candles in date range")

            # Convert to klines format
            klines = []
            for _, row in df.iterrows():
                # Make datetime timezone-aware
                dt = timezone.make_aware(row['datetime']) if timezone.is_naive(row['datetime']) else row['datetime']

                klines.append({
                    'timestamp': dt,
                    'open': Decimal(str(row['open'])),
                    'high': Decimal(str(row['high'])),
                    'low': Decimal(str(row['low'])),
                    'close': Decimal(str(row['close'])),
                    'volume': Decimal(str(row['volume'])),
                    'close_time': dt,
                    'quote_volume': Decimal(str(row['quote_volume'])),
                    'trades': int(row['trades']),
                    'taker_buy_base': Decimal('0'),
                    'taker_buy_quote': Decimal('0'),
                })

            logger.info(f"✅ Loaded {len(klines)} candles from CSV for {symbol}")
            return klines

        except Exception as e:
            logger.error(f"Error loading CSV for {symbol}: {e}", exc_info=True)
            return []

    async def fetch_multiple_symbols_from_csv(
        self,
        symbols: List[str],
        interval: str,
        start_date: datetime,
        end_date: datetime,
        data_dir: str = "backtest_data"
    ) -> Dict[str, List[Dict]]:
        """
        Load multiple symbols from CSV files.

        Expected directory structure:
        backtest_data/
          high/DOGEUSDT_5m.csv
          medium/ADAUSDT_5m.csv
          low/BTCUSDT_5m.csv

        Args:
            symbols: List of trading pairs
            interval: Timeframe (e.g., '5m')
            start_date: Start date (timezone-aware)
            end_date: End date (timezone-aware)
            data_dir: Base directory for CSV files

        Returns:
            Dictionary mapping symbol to list of candles
        """
        # Map symbols to volatility folders
        volatility_map = {
            'DOGEUSDT': 'high',
            'SHIBUSDT': 'high',
            'PEPEUSDT': 'high',
            'ADAUSDT': 'medium',
            'SOLUSDT': 'medium',
            'BNBUSDT': 'medium',
            'XRPUSDT': 'medium',
            'BTCUSDT': 'low',
            'ETHUSDT': 'low',
        }

        symbol_data = {}

        for symbol in symbols:
            # Determine volatility level (default to medium if unknown)
            vol_level = volatility_map.get(symbol, 'medium')

            # Try all volatility folders if symbol not in map
            if symbol not in volatility_map:
                for vol in ['high', 'medium', 'low']:
                    test_path = os.path.join(data_dir, vol, f"{symbol}_{interval}.csv")
                    if os.path.exists(test_path):
                        vol_level = vol
                        break

            csv_path = os.path.join(data_dir, vol_level, f"{symbol}_{interval}.csv")

            if os.path.exists(csv_path):
                logger.info(f"📂 Found CSV for {symbol}: {csv_path}")
                klines = self.fetch_from_csv(csv_path, symbol, start_date, end_date)
                symbol_data[symbol] = klines
            else:
                logger.warning(f"❌ CSV not found for {symbol}: {csv_path}")
                logger.info(f"   Will try fetching from Binance API instead...")
                # Fall back to API if CSV not found
                try:
                    klines = await self.fetch_historical_klines(
                        symbol, interval, start_date, end_date
                    )
                    symbol_data[symbol] = klines
                except Exception as e:
                    logger.error(f"Failed to fetch {symbol} from API: {e}")
                    symbol_data[symbol] = []

        return symbol_data


# Singleton instance
historical_data_fetcher = HistoricalDataFetcher()
