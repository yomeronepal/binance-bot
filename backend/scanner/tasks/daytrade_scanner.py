"""Celery scanner for the day-trade (15m Market Structure Pullback) engine.

Runs 1 minute after each 15m candle close: resolves the symbol universe
(explicit symbols are always scanned; ``*`` adds the top-N by volume
excluding them), fetches 15m + 1h candles, drops the still-forming candle,
and runs DayTradeSignalEngine.generate() per symbol on the closed candle.
1h candles are cached (they only change hourly) to keep request load down,
and a Redis lock prevents overlapping runs.
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
        Tuple of (min 24h quote volume, min 24h range %, max 24h range %,
        min last price).
    """
    return (
        getattr(settings, 'DAYTRADE_MIN_QUOTE_VOLUME_USDT', 10_000_000),
        getattr(settings, 'DAYTRADE_MIN_24H_RANGE_PCT', 2.0),
        getattr(settings, 'DAYTRADE_MAX_24H_RANGE_PCT', 40.0),
        getattr(settings, 'DAYTRADE_MIN_PRICE_USDT', 0.01),
    )


async def _active_blacklist():
    """Return the set of currently-blacklisted symbols."""
    from signals.models.blacklist import BlacklistedSymbol
    symbols = await sync_to_async(BlacklistedSymbol.get_blacklisted_symbols)()
    return {s.upper() for s in symbols}


def _below_price_floor(ticker, min_price):
    """True if the ticker's last price is below the minimum price floor.

    Sub-cent coins are dropped from the auto-discovered universe: their wide
    tick/spread and quantity-precision make live futures fills unreliable.
    A missing or unparseable price is treated as below the floor (dropped).
    """
    try:
        last = float(ticker.get('lastPrice') or 0)
    except (TypeError, ValueError):
        return True
    return last < min_price


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
    min_vol, min_range, max_range, min_price = _screen_thresholds()
    tickers = await client._request('GET', '/fapi/v1/ticker/24hr')

    survivors = []
    dropped_volume = 0
    dropped_range = 0
    dropped_price = 0
    for t in tickers:
        if t['symbol'] not in valid:
            continue
        if float(t.get('quoteVolume') or 0) < min_vol:
            dropped_volume += 1
            continue
        if _below_price_floor(t, min_price):
            dropped_price += 1
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
        "(dropped %d low-volume, %d sub-$%s, %d out-of-band); floor=$%s range=%s-%s%%",
        len(valid), len(ranked), dropped_volume, min_price, dropped_price, dropped_range,
        f"{min_vol:,}", min_range, max_range,
    )
    return ranked


def _split_configured(configured):
    """Split a configured symbol list into wildcard flag and explicit list.

    The ``*`` token is a wildcard meaning "fill with the top-N by volume".
    Every other entry is an explicit, always-scan symbol. Explicit symbols
    are upper-cased, de-duplicated and returned in their configured order.
    An empty config is treated as a bare wildcard for backward compatibility.

    Args:
        configured: The raw symbol list from the strategy config.

    Returns:
        Tuple of (has_wildcard, explicit_symbols).
    """
    has_wildcard = not configured or '*' in configured
    explicit = []
    for entry in (configured or []):
        symbol = entry.upper()
        if symbol == '*' or symbol in explicit:
            continue
        explicit.append(symbol)
    return has_wildcard, explicit


def _pinned_symbols(explicit, blacklist):
    """Resolve the always-scan set: explicit config, else the major pairs.

    These symbols bypass the liquidity/volatility screen. The blacklist is
    always honoured. When no explicit symbols are configured alongside the
    wildcard, the major pairs are pinned so a bare ``*`` keeps its majors.

    Args:
        explicit: Explicit symbols from the config (may be empty).
        blacklist: Set of blacklisted symbols to exclude.

    Returns:
        Ordered, de-duplicated list of pinned symbols.
    """
    base = explicit or MAJOR_PAIRS
    return [s for s in dict.fromkeys(base) if s not in blacklist]


async def _resolve_symbols(client, configured, top_n):
    """Resolve the scan universe from a mixed wildcard + explicit config.

    The config may mix the ``*`` wildcard with explicit symbols, e.g.
    ``["*", "BTCUSDT", "ETHUSDT", "SOLUSDT"]``. Explicit symbols are always
    scanned and bypass the liquidity/volatility screen. ``*`` then adds the
    top-N pairs by 24h volume (screened), excluding the explicit symbols so
    it fills the remaining slots with other coins. Without a wildcard, only
    the explicit symbols are scanned. The blacklist is applied everywhere.

    Args:
        client: Binance futures client.
        configured: Raw symbol list from the strategy config.
        top_n: Number of screened coins the wildcard contributes.

    Returns:
        Ordered scan universe: pinned symbols first, then top-N others.
    """
    blacklist = await _active_blacklist()
    has_wildcard, explicit = _split_configured(configured)
    pinned = _pinned_symbols(explicit, blacklist)

    if not has_wildcard:
        logger.info(
            "DayTrade universe: %d explicit symbols, no wildcard (%d blacklisted)",
            len(pinned), len(blacklist),
        )
        return pinned

    pairs = await client.get_usdt_futures_pairs()
    pinned_set = set(pinned)
    pool = [
        p for p in pairs
        if p.upper() not in blacklist and p.upper() not in pinned_set
    ]
    screened = await _screen_universe(client, pool, top_n)
    universe = list(dict.fromkeys(pinned + screened))
    logger.info(
        "DayTrade universe: %d pinned + %d screened (top %s) -> %d pairs "
        "(%d blacklisted)",
        len(pinned), len(screened), top_n, len(universe), len(blacklist),
    )
    return universe


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


def _drop_forming_candle(df):
    """Drop the still-forming last candle so the engine reads closed data.

    Binance returns the in-progress candle as the last row; evaluating it
    makes signals repaint intra-candle. Removing it means the engine always
    acts on the most recent *closed* candle, matching the backtests.

    Args:
        df: OHLCV frame whose last row is the currently-forming candle.

    Returns:
        The frame without its final row (unchanged if it has one row or less).
    """
    return df.iloc[:-1] if len(df) > 1 else df


def _generate_for_symbol(engine, symbol, klines_15m, klines_1h):
    """Build frames and run the engine for one symbol (sync, ORM-safe)."""
    if not klines_15m or not klines_1h:
        return None
    df_15m = _drop_forming_candle(klines_to_dataframe(klines_15m))
    df_1h = _drop_forming_candle(klines_to_dataframe(klines_1h))
    if df_15m.empty or df_1h.empty:
        return None
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
