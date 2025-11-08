"""
Commodities API Client for Real-Time Commodity Data
Provides OHLCV data for commodities: Gold, Silver, Oil, Copper, Wheat, etc.

Supported APIs:
1. API Ninjas - Primary (Free tier: 50,000 requests/month with free account)
2. Commodities-API.com - Fallback (100 requests/month)

API Documentation: https://api-ninjas.com/api/commodityprice
"""
import os
import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


class CommodityClient:
    """
    Commodity price data client using API Ninjas (primary) and Commodities API (fallback)

    API Ninjas Free tier: 50,000 requests/month
    Provides OHLCV data for major commodities
    """

    # API Ninjas endpoints
    NINJAS_BASE_URL = "https://api.api-ninjas.com/v1"

    # Commodities API (fallback)
    COMMODITIES_BASE_URL = "https://commodities-api.com/api"

    # Commodity symbol mapping
    COMMODITY_SYMBOLS = {
        # Precious Metals (per troy ounce)
        'GOLD': 'XAU',      # Gold
        'SILVER': 'XAG',    # Silver
        'PLATINUM': 'XPT',  # Platinum
        'PALLADIUM': 'XPD', # Palladium

        # Energy (per barrel for oil, per MMBtu for gas)
        'WTI': 'WTI',       # WTI Crude Oil
        'BRENT': 'BRENTOIL',# Brent Crude Oil
        'NATGAS': 'NG',     # Natural Gas

        # Base Metals (per metric ton)
        'COPPER': 'COPPER',
        'ALUMINUM': 'ALU',
        'ZINC': 'ZINC',
        'NICKEL': 'NI',

        # Agricultural (varies by unit)
        'WHEAT': 'WHEAT',
        'CORN': 'CORN',
        'SOYBEAN': 'SOYBEAN',
        'SUGAR': 'SUGAR',
        'COFFEE': 'COFFEE',
        'COTTON': 'COTTON',
    }

    # Reverse mapping for display
    SYMBOL_TO_NAME = {v: k for k, v in COMMODITY_SYMBOLS.items()}

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Commodity API client with API Ninjas (primary) and Commodities API (fallback)

        Args:
            api_key: API key (checks both NINJAS_API_KEY and COMMODITIES_API_KEY)
        """
        # API Ninjas key (primary - 50,000 requests/month free)
        self.ninjas_key = os.getenv('NINJAS_API_KEY') or os.getenv('API_NINJAS_KEY')

        # Commodities API key (fallback - 100 requests/month)
        self.commodities_key = api_key or os.getenv('COMMODITIES_API_KEY')

        if not self.ninjas_key and not self.commodities_key:
            logger.warning(
                "⚠️ No commodity API keys found. Get free keys at:\n"
                "  API Ninjas: https://api-ninjas.com/ (50k req/month)\n"
                "  Commodities API: https://commodities-api.com/ (100 req/month)"
            )

        # Track which API to use
        self.use_ninjas = bool(self.ninjas_key)
        logger.info(f"✓ Commodity API: {'API Ninjas' if self.use_ninjas else 'Commodities API'}")

    def _get_symbol(self, commodity: str) -> str:
        """Convert commodity name to API symbol"""
        commodity_upper = commodity.upper()

        # Direct match
        if commodity_upper in self.COMMODITY_SYMBOLS:
            return self.COMMODITY_SYMBOLS[commodity_upper]

        # Already an API symbol
        if commodity_upper in self.SYMBOL_TO_NAME:
            return commodity_upper

        # Try partial match (e.g., "GOLD" in "XAUUSD")
        for name, symbol in self.COMMODITY_SYMBOLS.items():
            if name in commodity_upper:
                return symbol

        logger.warning(f"Unknown commodity: {commodity}, using as-is")
        return commodity_upper

    async def get_latest_price(self, commodity: str, base_currency: str = 'USD') -> Optional[Dict]:
        """
        Get latest price for a commodity

        Args:
            commodity: Commodity symbol (e.g., 'GOLD', 'WTI', 'COPPER')
            base_currency: Base currency for pricing (default: USD)

        Returns:
            Dict with price data or None
        """
        try:
            symbol = self._get_symbol(commodity)

            params = {
                'access_key': self.api_key,
                'base': base_currency,
                'symbols': symbol
            }

            url = f"{self.BASE_URL}/latest"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Commodities API error: {response.status}")
                        return None

                    data = await response.json()

                    if not data.get('success', False):
                        logger.error(f"Commodities API error: {data.get('error', {}).get('info')}")
                        return None

                    rates = data.get('data', {}).get('rates', {})

                    if symbol not in rates:
                        logger.warning(f"No data for {symbol}")
                        return None

                    # Commodities API returns rate (price per unit)
                    price = float(rates[symbol])

                    return {
                        'symbol': f"{commodity}USD",
                        'name': self.SYMBOL_TO_NAME.get(symbol, commodity),
                        'price': price,
                        'currency': base_currency,
                        'timestamp': data.get('data', {}).get('date'),
                        'unit': data.get('data', {}).get('unit', 'per unit')
                    }

        except Exception as e:
            logger.error(f"Error fetching commodity price for {commodity}: {e}", exc_info=True)
            return None

    async def get_historical_prices(
        self,
        commodity: str,
        start_date: str,
        end_date: str,
        base_currency: str = 'USD'
    ) -> List[Dict]:
        """
        Get historical prices for a commodity

        Args:
            commodity: Commodity symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            base_currency: Base currency

        Returns:
            List of price data points
        """
        try:
            symbol = self._get_symbol(commodity)

            params = {
                'access_key': self.api_key,
                'start_date': start_date,
                'end_date': end_date,
                'base': base_currency,
                'symbols': symbol
            }

            url = f"{self.BASE_URL}/timeseries"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Commodities API error: {response.status}")
                        return []

                    data = await response.json()

                    if not data.get('success', False):
                        logger.error(f"Commodities API error: {data.get('error', {}).get('info')}")
                        return []

                    rates_by_date = data.get('data', {}).get('rates', {})

                    historical_data = []
                    for date_str, rates in sorted(rates_by_date.items()):
                        if symbol in rates:
                            price = float(rates[symbol])
                            historical_data.append({
                                'date': date_str,
                                'price': price,
                                'symbol': f"{commodity}USD"
                            })

                    return historical_data

        except Exception as e:
            logger.error(f"Error fetching historical data for {commodity}: {e}", exc_info=True)
            return []

    async def convert_to_klines(
        self,
        commodity: str,
        interval: str = '1d',
        limit: int = 200
    ) -> List[List]:
        """
        Convert commodity prices to Binance-compatible klines format

        Note: Commodities API provides daily closing prices only, not OHLC
        We'll use the closing price for all OHLC values

        Args:
            commodity: Commodity symbol
            interval: Timeframe (only '1d' supported by free tier)
            limit: Number of candles

        Returns:
            List of klines in Binance format
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=limit + 10)  # Extra days for weekends

            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')

            # Fetch historical data
            historical = await self.get_historical_prices(
                commodity,
                start_str,
                end_str
            )

            if not historical:
                logger.warning(f"No historical data for {commodity}")
                return []

            # Convert to klines format
            klines = []
            for data_point in historical[:limit]:
                date_str = data_point['date']
                price = data_point['price']

                # Parse date
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                timestamp_ms = int(dt.timestamp() * 1000)

                # Use same price for OHLC (daily close only)
                kline = [
                    timestamp_ms,       # Open time
                    str(price),         # Open
                    str(price),         # High
                    str(price),         # Low
                    str(price),         # Close
                    "0",                # Volume (not available)
                    timestamp_ms,       # Close time
                    "0", "0", "0", "0", "0"  # Other fields
                ]

                klines.append(kline)

            logger.info(f"✅ Converted {len(klines)} commodity prices to klines for {commodity}")
            return klines

        except Exception as e:
            logger.error(f"Error converting commodity data to klines: {e}", exc_info=True)
            return []

    async def get_klines_from_ninjas(
        self,
        commodity: str,
        limit: int = 200
    ) -> List[List]:
        """
        Fetch commodity data from API Ninjas

        API Ninjas provides current price only, not historical OHLCV
        We'll use the latest price to create a simple kline

        Args:
            commodity: Commodity name (e.g., 'GOLD', 'WTI')
            limit: Number of candles (only returns 1 for current price)

        Returns:
            List with single kline representing current price
        """
        try:
            symbol = self._get_symbol(commodity)

            url = f"{self.NINJAS_BASE_URL}/commodityprice"
            # API Ninjas expects commodity names in lowercase (e.g., 'gold', 'silver', 'copper')
            # Not the ticker symbols (XAU, XAG, etc.)
            params = {'name': commodity.lower()}  # Use commodity name directly, not symbol
            headers = {'X-Api-Key': self.ninjas_key}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API Ninjas error: {response.status} - {error_text[:200]}")
                        return []

                    data = await response.json()

                    if not data or 'price' not in data:
                        logger.warning(f"No price data from API Ninjas for {commodity}")
                        return []

                    price = float(data['price'])
                    timestamp_ms = int(datetime.now().timestamp() * 1000)

                    # Create kline with current price (O=H=L=C)
                    kline = [
                        timestamp_ms,
                        str(price),
                        str(price),
                        str(price),
                        str(price),
                        "0",  # No volume
                        timestamp_ms,
                        "0", "0", "0", "0", "0"
                    ]

                    logger.info(f"✅ Fetched commodity price from API Ninjas: {commodity} = ${price}")
                    return [kline]  # Return single candle

        except Exception as e:
            logger.error(f"Error fetching from API Ninjas: {e}", exc_info=True)
            return []

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 200
    ) -> List[List]:
        """
        Unified method to fetch commodity klines

        Uses API Ninjas (primary) or Commodities API (fallback)

        Args:
            symbol: Commodity symbol (e.g., 'GOLD', 'WTI', 'COPPER')
            interval: Timeframe ('1d' - daily only for free tier)
            limit: Number of candles

        Returns:
            List of klines in Binance-compatible format
        """
        if interval != '1d':
            logger.warning(
                f"Commodity APIs only support daily data. "
                f"Requested: {interval}, using: 1d"
            )

        # Try API Ninjas first (50k requests/month free)
        if self.use_ninjas:
            klines = await self.get_klines_from_ninjas(symbol, limit)
            if klines:
                return klines
            logger.warning("API Ninjas failed, falling back to Commodities API")

        # Fallback to Commodities API (100 requests/month)
        if self.commodities_key:
            return await self.convert_to_klines(symbol, '1d', limit)

        logger.error("No commodity API available!")
        return []

    async def batch_get_klines(
        self,
        commodities: List[str],
        interval: str,
        limit: int = 200
    ) -> Dict[str, List]:
        """
        Fetch klines for multiple commodities

        Note: Commodities API free tier is limited to 100 requests/month
        Use sparingly!

        Args:
            commodities: List of commodity symbols
            interval: Timeframe
            limit: Number of candles per commodity

        Returns:
            Dict mapping symbol to klines
        """
        result = {}

        for commodity in commodities:
            try:
                klines = await self.get_klines(commodity, interval, limit)

                if klines:
                    # Convert to USD pair format (e.g., GOLDUSD, WTIUSD)
                    pair_symbol = f"{commodity}USD"
                    result[pair_symbol] = klines

                # Rate limiting: 1 request per 2 seconds
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error fetching {commodity}: {e}")
                continue

        return result


# List of supported commodities
SUPPORTED_COMMODITIES = [
    # Precious Metals
    'GOLD',
    'SILVER',
    'PLATINUM',
    'PALLADIUM',

    # Energy
    'WTI',       # WTI Crude Oil
    'BRENT',     # Brent Crude Oil
    'NATGAS',    # Natural Gas

    # Base Metals
    'COPPER',
    'ALUMINUM',
    'ZINC',
    'NICKEL',

    # Agricultural
    'WHEAT',
    'CORN',
    'SOYBEAN',
    'SUGAR',
    'COFFEE',
    'COTTON',
]
