"""Celery scanner for the day-trade (15m Market Structure Pullback) engine.

Runs every minute: resolves the symbol universe (``*`` means all Binance
USDT pairs, otherwise the configured list), fetches 15m + 1h candles, and
runs DayTradeSignalEngine.generate() per symbol. 1h candles are cached
(they only change hourly) to keep the per-minute request load down, and a
Redis lock prevents overlapping runs.
"""
import asyncio
import logging

from asgiref.sync import sync_to_async
from celery import shared_task
from django.conf import settings
from django.core.cache import cache

from scanner.indicators.indicator_utils import klines_to_dataframe
from scanner.services.binance_futures_client import BinanceFuturesClient
from scanner.strategies.daytrade_signal_engine import (
    DayTradeSignalEngine,
    DayTradeSignalConfig,
)

logger = logging.getLogger(__name__)

MAJOR_PAIRS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
    'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'LTCUSDT',
]

SCAN_LOCK_KEY = 'daytrade_scan_lock'
SCAN_LOCK_TTL = 290
KLINES_1H_TTL = 300
ENTRY_KLINES_LIMIT = 150
BATCH_SIZE = 10


def _screen_thresholds():
    """Universe-screening thresholds, overridable via Django settings.

    Returns:
        Tuple of (min 24h quote volume, min 24h range %, max 24h range %).
    """
    return (
        getattr(settings, 'DAYTRADE_MIN_QUOTE_VOLUME_USDT', 10_000_000),
        getattr(settings, 'DAYTRADE_MIN_24H_RANGE_PCT', 2.0),
        getattr(settings, 'DAYTRADE_MAX_24H_RANGE_PCT', 40.0),
    )


async def _active_blacklist():
    """Return the set of currently-blacklisted symbols."""
    from signals.models.blacklist import BlacklistedSymbol
    symbols = await sync_to_async(BlacklistedSymbol.get_blacklisted_symbols)()
    return {s.upper() for s in symbols}


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


async def _screen_universe(client, pairs, top_n):
    """Filter pairs by liquidity + a volatility band, rank by volume, trim.

    Drops illiquid pairs (below the 24h quote-volume floor), dead pairs
    (24h range below the floor) and manipulation-prone/parabolic pairs
    (24h range above the ceiling), then ranks the survivors by volume.
    """
    valid = set(pairs)
    min_vol, min_range, max_range = _screen_thresholds()
    tickers = await client._request('GET', '/fapi/v1/ticker/24hr')

    survivors = []
    dropped_volume = 0
    dropped_range = 0
    for t in tickers:
        if t['symbol'] not in valid:
            continue
        if float(t.get('quoteVolume') or 0) < min_vol:
            dropped_volume += 1
            continue
        rng = _range_pct(t)
        if rng is None or rng < min_range or rng > max_range:
            dropped_range += 1
            continue
        survivors.append(t)

    survivors.sort(key=lambda t: float(t.get('quoteVolume') or 0), reverse=True)
    ranked = [t['symbol'] for t in survivors]
    if top_n and top_n > 0:
        ranked = ranked[:top_n]

    logger.info(
        "DayTrade screen: %d candidates -> %d pass "
        "(dropped %d low-volume, %d out-of-band); floor=$%s range=%s-%s%%",
        len(valid), len(ranked), dropped_volume, dropped_range,
        f"{min_vol:,}", min_range, max_range,
    )
    return ranked


async def _resolve_symbols(client, configured, top_n):
    """Resolve the scan universe.

    For ``*`` (or empty): all USDT perpetuals, screened by liquidity and a
    volatility band, ranked by volume and trimmed to top_n, with the major
    pairs always retained. Otherwise the configured list. The active
    blacklist is applied to every path.
    """
    blacklist = await _active_blacklist()

    if not configured or '*' in configured:
        pairs = await client.get_usdt_futures_pairs()
        pairs = [p for p in pairs if p.upper() not in blacklist]
        valid = set(pairs)
        screened = await _screen_universe(client, pairs, top_n)
        majors = [m for m in MAJOR_PAIRS if m in valid]
        universe = list(dict.fromkeys(screened + majors))
        logger.info(
            "DayTrade universe: %d screened + %d majors -> %d pairs "
            "(%d blacklisted)",
            len(screened), len(majors), len(universe), len(blacklist),
        )
        return universe

    symbols = [s.upper() for s in configured if s.upper() not in blacklist]
    logger.info(
        "DayTrade universe: %d configured symbols (%d blacklisted)",
        len(symbols), len(blacklist),
    )
    return symbols


async def _fetch_1h_cached(client, symbols, limit):
    """Fetch 1h klines, serving cached symbols and fetching only the misses."""
    result = {}
    missing = []
    for symbol in symbols:
        cached = cache.get(f'daytrade:1h:{symbol}')
        if cached is not None:
            result[symbol] = cached
        else:
            missing.append(symbol)

    if missing:
        fetched = await client.batch_get_klines(
            missing, interval='1h', limit=limit, batch_size=BATCH_SIZE
        )
        for symbol, klines in fetched.items():
            if klines:
                cache.set(f'daytrade:1h:{symbol}', klines, KLINES_1H_TTL)
                result[symbol] = klines
    return result


def _generate_for_symbol(engine, symbol, klines_15m, klines_1h):
    """Build frames and run the engine for one symbol (sync, ORM-safe)."""
    if not klines_15m or not klines_1h:
        return None
    df_15m = klines_to_dataframe(klines_15m)
    df_1h = klines_to_dataframe(klines_1h)
    return engine.generate(symbol, df_15m, df_1h)


def _expire_stale_signals():
    """Mark ACTIVE signals past their expiry as EXPIRED.

    A signal stays ACTIVE (like the v1 engine) and blocks new signals for its
    symbol until it expires, after which the symbol becomes eligible again.
    """
    from django.utils import timezone
    from signals.models.daytrade import DayTradeSignal
    return DayTradeSignal.objects.filter(
        status='ACTIVE', expires_at__lt=timezone.now()
    ).update(status='EXPIRED')


def _symbols_in_cooldown(cooldown_minutes):
    """Return symbols whose most recent trade closed within the cooldown.

    A symbol enters cooldown once any of its day-trade paper trades closes
    (SL or TP), suppressing new signals for it until the window elapses.
    """
    if not cooldown_minutes or cooldown_minutes <= 0:
        return set()
    from datetime import timedelta
    from django.utils import timezone as tz
    from signals.models.daytrade import DayTradePaperTrade
    cutoff = tz.now() - timedelta(minutes=cooldown_minutes)
    return set(
        DayTradePaperTrade.objects.filter(
            status__startswith='CLOSED', exit_time__gte=cutoff
        ).values_list('symbol', flat=True)
    )


async def _scan_daytrade_async():
    """Resolve the universe, fetch candles, and run the engine per symbol."""
    from signals.models.daytrade import DayTradeStrategyConfig

    db_config = await sync_to_async(DayTradeStrategyConfig.get_active)()
    cfg = DayTradeSignalConfig.from_db(db_config)
    engine = DayTradeSignalEngine(cfg)
    trend_limit = cfg.trend_ema_slow + 15

    await sync_to_async(_expire_stale_signals)()
    cooldown = await sync_to_async(_symbols_in_cooldown)(cfg.signal_cooldown_minutes)

    counts = {'symbols': 0, 'created': 0, 'errors': 0, 'cooldown_skipped': 0}

    async with BinanceFuturesClient() as client:
        symbols = await _resolve_symbols(client, cfg.symbols, cfg.universe_top_n)
        counts['symbols'] = len(symbols)

        klines_1h = await _fetch_1h_cached(client, symbols, trend_limit)
        klines_15m = await client.batch_get_klines(
            symbols, interval=cfg.entry_timeframe,
            limit=ENTRY_KLINES_LIMIT, batch_size=BATCH_SIZE
        )

        for symbol in symbols:
            if symbol in cooldown:
                counts['cooldown_skipped'] += 1
                continue
            try:
                signal = await sync_to_async(_generate_for_symbol)(
                    engine, symbol, klines_15m.get(symbol), klines_1h.get(symbol)
                )
                if signal:
                    counts['created'] += 1
            except Exception as exc:
                counts['errors'] += 1
                logger.error("DayTrade scan error for %s: %s", symbol, exc)

    logger.info(
        "DayTrade scan complete: %d symbols, %d signals, %d errors, %d cooldown-skipped",
        counts['symbols'], counts['created'], counts['errors'], counts['cooldown_skipped']
    )
    return counts


@shared_task(
    name='scanner.tasks.daytrade_scanner.scan_daytrade',
    bind=True,
    max_retries=0,
)
def scan_daytrade(self):
    """Run the day-trade scan once, guarded by a lock to avoid overlap."""
    if not cache.add(SCAN_LOCK_KEY, '1', timeout=SCAN_LOCK_TTL):
        logger.info("DayTrade scan already running, skipping this tick")
        return {'skipped': True}
    try:
        return asyncio.run(_scan_daytrade_async())
    finally:
        cache.delete(SCAN_LOCK_KEY)
