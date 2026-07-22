"""Liquidity + volatility screening for the futures signal universe.

Mirrors the day-trade engine's universe screen so the live futures bot stops
executing illiquid or parabolic symbols. Fetches the 24h ticker snapshot once
(cached briefly) and returns the subset of requested symbols that clear a
minimum 24h quote-volume floor and sit inside a 24h range band. Fails open: any
fetch/cache error returns the requested symbols unchanged so trading is never
halted by a transient issue.
"""
import asyncio
import logging
import threading

from django.conf import settings as dj_settings
from django.core.cache import cache

from scanner.services.binance_futures_client import BinanceFuturesClient

logger = logging.getLogger(__name__)

CACHE_KEY = 'futures:screen:tickers24h'
CACHE_TTL = 60


def _thresholds():
    """Return (min 24h quote volume, min 24h range %, max 24h range %)."""
    return (
        getattr(dj_settings, 'FUTURES_MIN_QUOTE_VOLUME_USDT', 10_000_000),
        getattr(dj_settings, 'FUTURES_MIN_24H_RANGE_PCT', 2.0),
        getattr(dj_settings, 'FUTURES_MAX_24H_RANGE_PCT', 40.0),
    )


def _range_pct(ticker):
    """24h high-low range as a percent of last price (volatility proxy)."""
    try:
        last = float(ticker.get('lastPrice') or 0)
        high = float(ticker.get('highPrice') or 0)
        low = float(ticker.get('lowPrice') or 0)
    except (TypeError, ValueError):
        return None
    if last <= 0 or high <= 0 or low <= 0:
        return None
    return (high - low) / last * 100.0


def _cache_get(key):
    """cache.get that treats any backend failure as a miss."""
    try:
        return cache.get(key)
    except Exception:
        return None


def _cache_set(key, value, ttl):
    """cache.set that never raises if the cache backend is unavailable."""
    try:
        cache.set(key, value, ttl)
    except Exception:
        pass


def _fetch_tickers():
    """Fetch the 24h ticker snapshot via the async client in a worker thread."""
    box = [None]

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def go():
                async with BinanceFuturesClient() as client:
                    return await client._request('GET', '/fapi/v1/ticker/24hr')
            box[0] = loop.run_until_complete(go())
        finally:
            loop.close()

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=20)
    return box[0]


def _load_tickers():
    """Return the cached 24h tickers, fetching + caching on a miss."""
    tickers = _cache_get(CACHE_KEY)
    if tickers is not None:
        return tickers
    tickers = _fetch_tickers()
    if tickers:
        _cache_set(CACHE_KEY, tickers, CACHE_TTL)
    return tickers


def screen_futures_symbols(symbols):
    """Return the subset of ``symbols`` passing the liquidity/volatility screen.

    Fails open: on any fetch error (or empty ticker set), returns the requested
    symbols unchanged so the trading loop is never blocked.

    Args:
        symbols: Iterable of symbol strings (e.g. ``BTCUSDT``).

    Returns:
        Set of symbols that clear the volume floor and range band.
    """
    wanted = set(symbols)
    if not wanted:
        return set()

    try:
        tickers = _load_tickers()
    except Exception as exc:
        logger.warning("Futures screen fetch failed, failing open: %s", exc)
        return set(wanted)

    if not tickers:
        logger.warning("Futures screen: no tickers returned, failing open")
        return set(wanted)

    min_vol, min_range, max_range = _thresholds()
    passing = set()
    for ticker in tickers:
        symbol = ticker.get('symbol')
        if symbol not in wanted:
            continue
        if float(ticker.get('quoteVolume') or 0) < min_vol:
            continue
        rng = _range_pct(ticker)
        if rng is None or rng < min_range or rng > max_range:
            continue
        passing.add(symbol)

    logger.info(
        "Futures screen: %d/%d symbols pass (floor=$%s range=%s-%s%%)",
        len(passing), len(wanted), f"{min_vol:,}", min_range, max_range,
    )
    return passing
