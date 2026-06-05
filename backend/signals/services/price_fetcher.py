"""
Batched, short-cached Binance price fetching.

Fetches ticker prices for many symbols concurrently (futures-first with a
spot fallback) instead of serially, and caches each symbol's price in Redis
for a few seconds so concurrent requests share the same fetch.
"""
import asyncio
import logging
from decimal import Decimal

from django.core.cache import cache

logger = logging.getLogger(__name__)

PRICE_CACHE_TTL = 3
_PRICE_CACHE_KEY = 'price:{symbol}'
_CONCURRENCY = 10


async def _fetch_from_client(client, symbols):
    """Fetch prices for symbols using one Binance client, concurrently."""
    if not symbols:
        return {}

    semaphore = asyncio.Semaphore(_CONCURRENCY)

    async def fetch_one(symbol):
        async with semaphore:
            try:
                price_data = await client.get_price(symbol)
                if price_data and 'price' in price_data:
                    return symbol, Decimal(str(price_data['price']))
            except Exception:
                pass
            return symbol, None

    results = await asyncio.gather(*[fetch_one(s) for s in symbols])
    return {symbol: price for symbol, price in results if price is not None}


async def _fetch_uncached(symbols):
    """Fetch uncached symbols futures-first, then spot for any that miss."""
    from scanner.services.binance_client import BinanceClient
    from scanner.services.binance_futures_client import BinanceFuturesClient

    prices = {}
    async with BinanceFuturesClient() as fut_client, BinanceClient() as spot_client:
        prices.update(await _fetch_from_client(fut_client, symbols))

        fallback = [s for s in symbols if s not in prices]
        if fallback:
            prices.update(await _fetch_from_client(spot_client, fallback))

    return prices


def fetch_prices_batch(symbols, cache_ttl=PRICE_CACHE_TTL):
    """
    Return current prices for symbols as a dict of {symbol: Decimal}.

    Reads each symbol from a short-lived Redis cache first and only fetches
    the misses from Binance, concurrently.

    Args:
        symbols: Iterable of symbol strings.
        cache_ttl: Seconds to cache each freshly fetched price.

    Returns:
        Dict mapping symbol to Decimal price (missing symbols are omitted).
    """
    unique_symbols = list(dict.fromkeys(symbols))
    if not unique_symbols:
        return {}

    prices = {}
    missing = []
    for symbol in unique_symbols:
        cached = cache.get(_PRICE_CACHE_KEY.format(symbol=symbol))
        if cached is not None:
            prices[symbol] = Decimal(str(cached))
        else:
            missing.append(symbol)

    if missing:
        try:
            fetched = asyncio.run(_fetch_uncached(missing))
        except Exception as exc:
            logger.error("Batch price fetch failed: %s", exc, exc_info=True)
            fetched = {}
        for symbol, price in fetched.items():
            cache.set(_PRICE_CACHE_KEY.format(symbol=symbol), str(price), cache_ttl)
            prices[symbol] = price

    return prices
