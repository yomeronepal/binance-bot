"""
Crypto Fear & Greed Index Service.
Uses CoinMarketCap's Fear & Greed Index (matches Binance app).

Index ranges:
    0-19:  Extreme Fear
    20-39: Fear
    40-59: Neutral
    60-79: Greed
    80-100: Extreme Greed
"""
import logging
import time
import json
from urllib.request import urlopen, Request
from typing import Optional, Dict
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_KEY = "fear_greed_index"
CACHE_TTL = 900
CMC_API_URL = "https://api.coinmarketcap.com/data-api/v3/fear-greed/chart"


def _http_get_json(url: str, timeout: int = 10):
    """
    HTTP GET returning parsed JSON using stdlib.

    Args:
        url: Full URL
        timeout: Timeout seconds

    Returns:
        Parsed JSON or None
    """
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning(f"HTTP GET failed: {e}")
        return None


def _fetch_coinmarketcap() -> Optional[Dict]:
    """
    Fetch Fear & Greed Index from CoinMarketCap.
    Uses the chart endpoint with a 24h window to get the latest value.

    Returns:
        Dict with score, name, btcPrice or None
    """
    now_ts = int(time.time())
    start_ts = now_ts - (7 * 86400)

    url = f"{CMC_API_URL}?start={start_ts}&end={now_ts}"
    data = _http_get_json(url)

    if not data or not data.get('data') or not data['data'].get('dataList'):
        return None

    entries = data['data']['dataList']
    latest = max(entries, key=lambda x: int(x.get('timestamp', 0)))

    return {
        'score': int(latest['score']),
        'name': latest['name'],
        'btc_price': latest.get('btcPrice', '0'),
        'btc_volume': latest.get('btcVolume', '0'),
        'timestamp': int(latest['timestamp']),
    }


def fetch_fear_greed_index() -> Optional[Dict]:
    """
    Fetch Fear & Greed Index from CoinMarketCap (same source as Binance app).
    Cached for 15 minutes.

    Returns:
        Dict with value (0-100), classification, source, components
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    cmc_data = _fetch_coinmarketcap()

    if not cmc_data:
        logger.warning("CoinMarketCap F&G unavailable")
        return None

    value = cmc_data['score']

    result = {
        'value': value,
        'classification': cmc_data['name'],
        'source': 'coinmarketcap',
        'components': {
            'btc_price': {'raw': cmc_data['btc_price'], 'score': float(value)},
            'btc_volume': {'raw': cmc_data['btc_volume'], 'score': float(value)},
        },
        'fetched_at': int(time.time()),
    }

    cache.set(CACHE_KEY, result, CACHE_TTL)
    logger.info(f"Fear & Greed: {value} ({cmc_data['name']}) [source: coinmarketcap]")
    return result


def get_fear_greed_value() -> Optional[int]:
    """
    Get just the numeric Fear & Greed value (0-100).

    Returns:
        Integer 0-100 or None if unavailable.
    """
    data = fetch_fear_greed_index()
    if data:
        return data['value']
    return None


def check_direction_allowed(direction: str, fg_value: int, short_threshold: int, long_threshold: int) -> tuple:
    """
    Check if a trade direction is allowed based on Fear & Greed value.

    Args:
        direction: LONG or SHORT
        fg_value: Fear & Greed index value (0-100)
        short_threshold: Below this = SHORT only
        long_threshold: Above this = LONG only

    Returns:
        Tuple of (allowed: bool, reason: str)
    """
    if fg_value <= short_threshold:
        if direction == 'LONG':
            return False, (
                f"F&G={fg_value} (Fear, <={short_threshold}): "
                f"LONG blocked, only SHORT in fearful market"
            )
        return True, f"F&G={fg_value}: SHORT allowed in fearful market"

    if fg_value >= long_threshold:
        if direction == 'SHORT':
            return False, (
                f"F&G={fg_value} (Greed, >={long_threshold}): "
                f"SHORT blocked, only LONG in greedy market"
            )
        return True, f"F&G={fg_value}: LONG allowed in greedy market"

    return True, f"F&G={fg_value}: Neutral zone ({short_threshold}-{long_threshold}), both directions allowed"
