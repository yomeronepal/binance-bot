"""
Public Paper Trading Views - Optimized for production performance.
No authentication required - shows ALL system paper trading activity.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from decimal import Decimal
from django.db.models import Sum, Avg, Count, Q, Max, Min, F, ExpressionWrapper, DurationField
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import asyncio
import hashlib
import logging

from signals.models import PaperTrade
from signals.serializers import PaperTradeSerializer
from signals.models_blacklist import BlacklistedSymbol

logger = logging.getLogger(__name__)

CACHE_TTL_PERFORMANCE = 10
CACHE_TTL_SUMMARY = 10
CACHE_TTL_OPEN_POSITIONS = 5


def _build_cache_key(prefix, params):
    """
    Build a deterministic cache key from request params.

    Args:
        prefix: Cache key prefix
        params: Dict of query parameters

    Returns:
        Hashed cache key string
    """
    raw = ":".join(f"{k}={v}" for k, v in sorted(params.items()) if v)
    suffix = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"{prefix}:{suffix}"


def _maybe_apply_asset_class(queryset, params):
    """
    Whitelisted asset_class filter (CRYPTO/STOCK/COMMODITY). Used by
    endpoints that bypass _apply_common_filters (public_performance,
    public_open_positions).
    """
    asset_class = str(params.get('asset_class', '')).upper()
    if asset_class in ('CRYPTO', 'STOCK', 'COMMODITY'):
        return queryset.filter(asset_class=asset_class)
    return queryset


def _apply_common_filters(queryset, params):
    """
    Apply shared filter logic to a PaperTrade queryset.

    Args:
        queryset: Base PaperTrade queryset
        params: Dict of filter parameters

    Returns:
        Filtered queryset
    """
    status_filter = params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    market_type = params.get('market_type')
    if market_type:
        queryset = queryset.filter(market_type=market_type)

    asset_class = str(params.get('asset_class', '')).upper()
    if asset_class in ('CRYPTO', 'STOCK', 'COMMODITY'):
        queryset = queryset.filter(asset_class=asset_class)

    symbol = params.get('symbol')
    if symbol:
        queryset = queryset.filter(symbol__icontains=symbol)

    direction = params.get('direction')
    if direction and direction != 'ALL':
        queryset = queryset.filter(direction=direction.upper())

    if str(params.get('top_performer', '')).lower() == 'true':
        queryset = _apply_top_performer_filter(queryset)

    queryset = _apply_macro_filter(queryset, params)
    queryset = _apply_golden_window_filter(queryset, params)
    queryset = _apply_time_filters(queryset, params)

    return queryset


def _apply_top_performer_filter(queryset):
    """
    Restrict the queryset to symbols in the latest TopPerformingSymbol
    snapshot. Falls back to a 'never matches' filter when no snapshot
    exists yet — fail closed rather than fail open, so the user sees
    'no data' instead of every trade unfiltered.
    """
    from signals.services.top_performers_calculator import latest_top_performer_symbols
    symbols = latest_top_performer_symbols(n=10)
    if not symbols:
        return queryset.none()
    return queryset.filter(symbol__in=symbols)


def _maybe_apply_top_performer(queryset, params):
    """
    Apply the top-performer filter iff the request asked for it.

    Wrapper used by views that don't go through ``_apply_common_filters``
    (currently ``public_performance`` and ``public_open_positions``) so
    the toggle works uniformly across every endpoint the Bot Performance
    page calls — summary, open positions, and the trade list.
    """
    if str(params.get('top_performer', '')).lower() == 'true':
        return _apply_top_performer_filter(queryset)
    return queryset


def _apply_macro_filter(queryset, params):
    """
    Filter PaperTrade rows by what the macro filter said at signal time.

    ``?macro_filter=allow``  → only rows whose Signal.meta tagged
                                ``macro_at_signal.decision = 'ALLOW'``.
    ``?macro_filter=block``  → only rows tagged ``BLOCK`` (so you can
                                inspect what the filter would have
                                vetoed).
    Anything else (incl. ``all`` or empty)  → no change.

    Rows whose Signal pre-dates the tagging release have no
    ``macro_at_signal`` key. They are excluded from both ``allow``
    and ``block`` views (as discussed: "data we don't have an opinion
    on yet").
    """
    mode = str(params.get('macro_filter', '')).lower()
    if mode not in ('allow', 'block'):
        return queryset
    target = 'ALLOW' if mode == 'allow' else 'BLOCK'
    # PaperTrade has signal FK; signal.meta is JSONField. Use the
    # nested-key lookup which Postgres serves through a ``->>`` op.
    return queryset.filter(signal__meta__macro_at_signal__decision=target)


def _maybe_apply_macro_filter(queryset, params):
    """
    Macro filter wrapper for views that bypass ``_apply_common_filters``
    (``public_performance`` and ``public_open_positions``). Same shape
    as ``_maybe_apply_top_performer``.
    """
    return _apply_macro_filter(queryset, params)


def _apply_golden_window_filter(queryset, params):
    """
    Apply golden window filters including AI-optimized windows.

    Args:
        queryset: Base queryset
        params: Dict of filter parameters

    Returns:
        Filtered queryset
    """
    if params.get('golden_window', '').lower() == 'true':
        queryset = queryset.filter(is_priority=True)

    if params.get('golden_window_2', '').lower() == 'true':
        queryset = queryset.filter(is_golden_2=True)

    if params.get('outside_golden_window', '').lower() == 'true':
        queryset = queryset.filter(is_priority=False, is_golden_2=False)

    if params.get('gw1_ai', '').lower() == 'true':
        queryset = _filter_by_ai_sessions('ACTIVE_TRADING_WINDOW', queryset)

    if params.get('gw2_ai', '').lower() == 'true':
        queryset = _filter_by_ai_sessions('GOLDEN_WINDOW', queryset)

    return queryset


def _filter_by_ai_sessions(session_type, queryset):
    """
    Filter trades to only those whose entry_time falls within
    auto-generated TradingSession windows. Uses exact NPT minute-level matching.

    Args:
        session_type: ACTIVE_TRADING_WINDOW or GOLDEN_WINDOW
        queryset: Base trade queryset

    Returns:
        Filtered queryset
    """
    from signals.models import TradingSession
    from datetime import timedelta

    sessions = list(TradingSession.objects.filter(
        auto_generated=True, active=True, session_type=session_type
    ))

    if not sessions:
        return queryset.none()

    nepal_offset = timedelta(hours=5, minutes=45)
    matching_ids = []

    for trade_id, entry_time in queryset.filter(
        entry_time__isnull=False
    ).values_list('id', 'entry_time'):
        npt = entry_time + nepal_offset
        npt_minutes = npt.hour * 60 + npt.minute
        npt_weekday = npt.weekday()

        for s in sessions:
            start = s.start_hour * 60 + s.start_minute
            end = s.end_hour * 60 + s.end_minute

            if npt_minutes < start or npt_minutes >= end:
                continue

            if s.active_days and len(s.active_days) > 0:
                if npt_weekday not in s.active_days:
                    continue

            matching_ids.append(trade_id)
            break

    if not matching_ids:
        return queryset.none()

    return queryset.filter(id__in=matching_ids)


def _apply_time_filters(queryset, params):
    """
    Apply weekday, hour, month, year filters.

    Args:
        queryset: Base queryset
        params: Dict of filter parameters

    Returns:
        Filtered queryset
    """
    weekday = params.get('weekday')
    if weekday and weekday != 'ALL':
        try:
            weekday_int = int(weekday)
            queryset = _filter_by_npt_weekday(queryset, weekday_int)
        except (ValueError, TypeError):
            pass

    hour = params.get('hour')
    if hour and hour != 'ALL':
        try:
            hour_int = int(hour)
            if 0 <= hour_int <= 23:
                queryset = _filter_by_npt_hour(queryset, hour_int)
        except (ValueError, TypeError):
            pass

    month = params.get('month')
    if month and month != 'ALL':
        try:
            month_int = int(month)
            if 1 <= month_int <= 12:
                queryset = queryset.filter(entry_time__month=month_int)
        except (ValueError, TypeError):
            pass

    year = params.get('year')
    if year and year != 'ALL':
        try:
            queryset = queryset.filter(entry_time__year=int(year))
        except (ValueError, TypeError):
            pass

    return queryset


def _filter_by_npt_weekday(queryset, iso_weekday):
    """
    Filter trades by exact Nepal Time weekday.
    Frontend sends ISO weekday: 1=Monday, 7=Sunday.
    Python weekday: 0=Monday, 6=Sunday.

    Args:
        queryset: PaperTrade queryset
        iso_weekday: ISO weekday (1=Mon, 7=Sun)

    Returns:
        Filtered queryset
    """
    from datetime import timedelta

    python_weekday = iso_weekday - 1
    nepal_offset = timedelta(hours=5, minutes=45)
    matching_ids = []

    for trade_id, entry_time in queryset.filter(
        entry_time__isnull=False
    ).values_list('id', 'entry_time'):
        npt = entry_time + nepal_offset
        if npt.weekday() == python_weekday:
            matching_ids.append(trade_id)

    if not matching_ids:
        return queryset.none()

    return queryset.filter(id__in=matching_ids)


def _filter_by_npt_hour(queryset, npt_hour):
    """
    Filter trades by exact Nepal Time hour using entry_time + 5:45 offset.

    Args:
        queryset: PaperTrade queryset
        npt_hour: NPT hour (0-23)

    Returns:
        Filtered queryset
    """
    from datetime import timedelta

    nepal_offset = timedelta(hours=5, minutes=45)
    matching_ids = []

    for trade_id, entry_time in queryset.filter(
        entry_time__isnull=False
    ).values_list('id', 'entry_time'):
        npt = entry_time + nepal_offset
        if npt.hour == npt_hour:
            matching_ids.append(trade_id)

    if not matching_ids:
        return queryset.none()

    return queryset.filter(id__in=matching_ids)


def _get_filter_params(request):
    """
    Extract all filter params from request into a dict.

    Args:
        request: DRF request object

    Returns:
        Dict of filter parameters
    """
    keys = [
        'status', 'market_type', 'asset_class', 'symbol', 'direction',
        'golden_window', 'golden_window_2', 'outside_golden_window',
        'gw1_ai', 'gw2_ai',
        'weekday', 'hour', 'month', 'year', 'days',
        'top_performer',
        'macro_filter',
    ]
    return {k: request.query_params.get(k, '') for k in keys}


async def _fetch_prices_from_client(client, symbols):
    """
    Fetch ticker prices for a list of symbols using one Binance client.

    Returns (prices_dict, failed_dict). 400 / Bad Request errors land in
    failed_dict so the caller can decide what to do; transient errors
    return neither.
    """
    if not symbols:
        return {}, {}

    prices = {}
    failed = {}
    semaphore = asyncio.Semaphore(10)

    async def fetch_one(sym):
        async with semaphore:
            try:
                price_data = await client.get_price(sym)
                if price_data and 'price' in price_data:
                    return sym, Decimal(str(price_data['price'])), None
            except Exception as e:
                error_msg = str(e)
                if '400' in error_msg or 'Bad Request' in error_msg:
                    return sym, None, error_msg
            return sym, None, None

    results = await asyncio.gather(*[fetch_one(s) for s in symbols])
    for sym, price, error in results:
        if price:
            prices[sym] = price
        elif error:
            failed[sym] = error
    return prices, failed


def _fetch_prices_batch(symbol_market_map):
    """
    Fetch prices for multiple symbols, futures-first with spot fallback.

    The bot trades on Binance Futures (fapi.binance.com), so paper-trade
    SL/TP simulation must use futures prices to match real execution.
    For the rare symbol that has no futures listing, fall back to spot.

    Args:
        symbol_market_map: Dict of {symbol: 'SPOT'|'FUTURES'}. The value
            is accepted for API compatibility but no longer affects
            routing — every symbol is tried on futures first.

    Returns:
        Tuple of (prices dict, failed_symbols dict)
    """
    from scanner.services.binance_client import BinanceClient
    from scanner.services.binance_futures_client import BinanceFuturesClient

    all_symbols = list(symbol_market_map.keys())

    async def fetch_all():
        prices = {}
        failed = {}

        async with BinanceFuturesClient() as fut_client, BinanceClient() as spot_client:
            fut_prices, fut_failed = await _fetch_prices_from_client(
                fut_client, all_symbols
            )
            prices.update(fut_prices)

            fallback_symbols = [s for s in all_symbols if s not in prices]
            if fallback_symbols:
                spot_prices, spot_failed = await _fetch_prices_from_client(
                    spot_client, fallback_symbols
                )
                prices.update(spot_prices)
                for sym in fallback_symbols:
                    if sym not in spot_prices:
                        failed[sym] = spot_failed.get(sym) or fut_failed.get(sym) or 'No price available'

        return prices, failed

    try:
        return asyncio.run(fetch_all())
    except Exception as e:
        logger.error(f"Batch price fetch failed: {e}")
        return {}, {}


def _handle_failing_symbol(symbol, error_msg, trade=None):
    """
    Blacklist a failing symbol and optionally close the trade.

    Args:
        symbol: The failing symbol string
        error_msg: Error message from API
        trade: PaperTrade to close (optional)
    """
    try:
        if BlacklistedSymbol.is_blacklisted(symbol):
            return

        BlacklistedSymbol.objects.create(
            symbol=symbol,
            reason='DELISTED',
            notes=f'Auto-blacklisted: {error_msg}. Coin likely delisted or unavailable on Binance.',
            active=True
        )
        logger.warning(f"Auto-blacklisted {symbol}: {error_msg}")

        if trade and trade.status == 'OPEN':
            trade.status = 'CLOSED_MANUAL'
            trade.exit_price = trade.entry_price
            trade.profit_loss = Decimal('0')
            trade.profit_loss_percentage = Decimal('0')
            trade.exit_time = timezone.now()
            trade.save(update_fields=[
                'status', 'exit_price', 'profit_loss',
                'profit_loss_percentage', 'exit_time'
            ])

    except Exception as e:
        logger.error(f"Error handling failing symbol {symbol}: {e}")


def _compute_max_drawdown(closed_trades_qs):
    """
    Compute max drawdown from closed trades using a single values_list query.

    Args:
        closed_trades_qs: Queryset of closed PaperTrade objects

    Returns:
        Decimal max drawdown value
    """
    pnl_list = closed_trades_qs.order_by('exit_time').values_list('profit_loss', flat=True)

    current_pnl = Decimal('0')
    peak_pnl = Decimal('0')
    max_dd = Decimal('0')

    for pnl in pnl_list:
        if pnl is None:
            continue
        current_pnl += pnl
        if current_pnl > peak_pnl:
            peak_pnl = current_pnl
        drawdown = peak_pnl - current_pnl
        if drawdown > max_dd:
            max_dd = drawdown

    return max_dd


def _compute_performance_metrics(base_queryset):
    """
    Compute all performance metrics in a single aggregation query.

    Args:
        base_queryset: Filtered PaperTrade queryset (all statuses)

    Returns:
        Dict of performance metrics
    """
    closed_qs = base_queryset.filter(status__startswith='CLOSED')

    stats = closed_qs.aggregate(
        total_closed=Count('id'),
        winners=Count('id', filter=Q(profit_loss__gt=0)),
        losers=Count('id', filter=Q(profit_loss__lt=0)),
        total_pnl=Sum('profit_loss'),
        avg_pnl=Avg('profit_loss'),
        best=Max('profit_loss'),
        worst=Min('profit_loss'),
    )

    total_closed = stats['total_closed'] or 0
    winners = stats['winners'] or 0
    losers = stats['losers'] or 0

    avg_duration_seconds = 0
    if total_closed > 0:
        duration_agg = closed_qs.filter(
            entry_time__isnull=False,
            exit_time__isnull=False
        ).annotate(
            duration=ExpressionWrapper(
                F('exit_time') - F('entry_time'),
                output_field=DurationField()
            )
        ).aggregate(avg_duration=Avg('duration'))

        avg_td = duration_agg['avg_duration']
        if avg_td:
            avg_duration_seconds = avg_td.total_seconds()

    open_count = base_queryset.filter(status='OPEN').count()
    max_dd = _compute_max_drawdown(closed_qs)

    return {
        'total_trades': total_closed,
        'open_trades': open_count,
        'win_rate': (winners / total_closed * 100) if total_closed > 0 else 0,
        'total_profit_loss': float(stats['total_pnl'] or 0),
        'avg_profit_loss': float(stats['avg_pnl'] or 0),
        'best_trade': float(stats['best'] or 0),
        'worst_trade': float(stats['worst'] or 0),
        'avg_duration_hours': round(avg_duration_seconds / 3600, 2),
        'max_drawdown': float(max_dd),
        'profitable_trades': winners,
        'losing_trades': losers,
    }


@api_view(['GET'])
@permission_classes([AllowAny])
def public_paper_trades_list(request):
    """
    PUBLIC paginated list of SYSTEM paper trades.

    GET /api/public/paper-trading/?page=1&page_size=20&status=OPEN&symbol=BTC
    """
    params = _get_filter_params(request)
    queryset = PaperTrade.objects.filter(user__isnull=True)
    queryset = _apply_common_filters(queryset, params)
    queryset = queryset.select_related('signal').order_by('-entry_time')

    paginator = PageNumberPagination()
    paginator.page_size = 20
    paginator.page_size_query_param = 'page_size'
    paginator.max_page_size = 100

    result_page = paginator.paginate_queryset(queryset, request)
    serializer = PaperTradeSerializer(result_page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_performance(request):
    """
    PUBLIC cached performance metrics for SYSTEM paper trades.

    GET /api/public/paper-trading/performance/?days=7&direction=ALL
    """
    params = _get_filter_params(request)
    cache_key = _build_cache_key('perf:metrics', params)

    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    queryset = PaperTrade.objects.filter(user__isnull=True)

    days = params.get('days')
    if days:
        try:
            cutoff = timezone.now() - timedelta(days=int(days))
            queryset = queryset.filter(created_at__gte=cutoff)
        except (ValueError, TypeError):
            pass

    queryset = _apply_golden_window_filter(queryset, params)
    queryset = _maybe_apply_top_performer(queryset, params)
    queryset = _maybe_apply_macro_filter(queryset, params)
    queryset = _maybe_apply_asset_class(queryset, params)

    direction = params.get('direction', 'ALL').upper()
    if direction == 'LONG':
        queryset = queryset.filter(direction='LONG')
    elif direction == 'SHORT':
        queryset = queryset.filter(direction='SHORT')

    metrics = _compute_performance_metrics(queryset)

    open_trades_qs = PaperTrade.objects.filter(
        status='OPEN', user__isnull=True
    ).only('id', 'symbol', 'direction', 'entry_price', 'quantity',
           'position_size', 'market_type', 'leverage')

    if open_trades_qs.exists():
        try:
            symbol_market = dict(open_trades_qs.values_list('symbol', 'market_type'))
            current_prices, failed_symbols = _fetch_prices_batch(symbol_market)

            for sym, error_msg in failed_symbols.items():
                for trade in open_trades_qs.filter(symbol=sym):
                    _handle_failing_symbol(sym, error_msg, trade)

            total_unrealized = Decimal('0')
            for trade in open_trades_qs.filter(status='OPEN'):
                price = current_prices.get(trade.symbol)
                if price:
                    pnl, _ = trade.calculate_profit_loss(price)
                    total_unrealized += Decimal(str(pnl))

            metrics['unrealized_pnl'] = float(total_unrealized)
            metrics['total_pnl'] = float(Decimal(str(metrics['total_profit_loss'])) + total_unrealized)
        except Exception:
            metrics['unrealized_pnl'] = 0.0
            metrics['total_pnl'] = metrics['total_profit_loss']
    else:
        metrics['unrealized_pnl'] = 0.0
        metrics['total_pnl'] = metrics['total_profit_loss']

    cache.set(cache_key, metrics, CACHE_TTL_PERFORMANCE)
    return Response(metrics)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_open_positions(request):
    """
    PUBLIC SYSTEM open positions with real-time prices.

    GET /api/public/paper-trading/open-positions/
    """
    params = _get_filter_params(request)
    queryset = PaperTrade.objects.filter(status='OPEN', user__isnull=True)
    queryset = _apply_golden_window_filter(queryset, params)
    queryset = _apply_time_filters(queryset, params)
    queryset = _maybe_apply_top_performer(queryset, params)
    queryset = _maybe_apply_macro_filter(queryset, params)
    queryset = _maybe_apply_asset_class(queryset, params)

    direction = params.get('direction')
    if direction and direction != 'ALL':
        queryset = queryset.filter(direction=direction.upper())

    open_trades = list(queryset.select_related('signal').only(
        'id', 'symbol', 'direction', 'market_type', 'asset_class',
        'entry_price', 'entry_time', 'position_size', 'stop_loss',
        'take_profit', 'leverage', 'quantity', 'status', 'user_id',
        'is_priority', 'signal__meta'
    ).order_by('-entry_time'))

    if not open_trades:
        return Response({
            'total_investment': 0,
            'total_current_value': 0,
            'total_unrealized_pnl': 0,
            'total_unrealized_pnl_pct': 0,
            'total_open_trades': 0,
            'positions': []
        })

    symbol_market = {t.symbol: t.market_type for t in open_trades}
    current_prices, failed_symbols = _fetch_prices_batch(symbol_market)

    for sym, error_msg in failed_symbols.items():
        failing = [t for t in open_trades if t.symbol == sym]
        for trade in failing:
            _handle_failing_symbol(sym, error_msg, trade)
            open_trades.remove(trade)

    total_investment = Decimal('0')
    total_current_value = Decimal('0')
    total_unrealized_pnl = Decimal('0')
    positions = []

    for trade in open_trades:
        current_price = current_prices.get(trade.symbol)

        position = {
            'trade_id': trade.id,
            'user': 'System',
            'symbol': trade.symbol,
            'direction': trade.direction,
            'market_type': trade.market_type,
            'asset_class': trade.asset_class,
            'entry_price': float(trade.entry_price),
            'entry_time': trade.entry_time,
            'position_size': float(trade.position_size),
            'stop_loss': float(trade.stop_loss),
            'take_profit': float(trade.take_profit),
            'leverage': trade.leverage,
            'risk_reward_ratio': trade.risk_reward_ratio,
            'is_priority': trade.is_priority,
            'is_neutral_reversal': bool(
                trade.signal and
                isinstance(getattr(trade.signal, 'meta', None), dict) and
                trade.signal.meta.get('neutral_reversal')
            ),
        }

        if current_price:
            unrealized_pnl, unrealized_pnl_pct = trade.calculate_profit_loss(current_price)
            current_value = float(trade.position_size) * (1 + float(unrealized_pnl_pct) / 100)
            price_change = float(current_price - trade.entry_price)
            price_change_pct = (price_change / float(trade.entry_price)) * 100

            position.update({
                'current_price': float(current_price),
                'current_value': round(current_value, 2),
                'unrealized_pnl': float(unrealized_pnl),
                'unrealized_pnl_pct': float(unrealized_pnl_pct),
                'price_change': round(price_change, 8),
                'price_change_pct': round(price_change_pct, 2),
                'has_real_time_price': True
            })
            total_current_value += Decimal(str(current_value))
            total_unrealized_pnl += Decimal(str(unrealized_pnl))
        else:
            position.update({
                'current_price': None,
                'current_value': float(trade.position_size),
                'unrealized_pnl': 0.0,
                'unrealized_pnl_pct': 0.0,
                'price_change': 0.0,
                'price_change_pct': 0.0,
                'has_real_time_price': False
            })

        total_investment += Decimal(str(trade.position_size))
        positions.append(position)

    total_unrealized_pnl_pct = 0.0
    if total_investment > 0:
        total_unrealized_pnl_pct = float((total_unrealized_pnl / total_investment) * 100)

    return Response({
        'total_investment': float(total_investment),
        'total_current_value': float(total_current_value),
        'total_unrealized_pnl': float(total_unrealized_pnl),
        'total_unrealized_pnl_pct': total_unrealized_pnl_pct,
        'total_open_trades': len(positions),
        'positions': positions
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def public_close_trade(request, trade_id):
    """
    Manually close a SYSTEM paper trade at current market price.

    POST /api/public/paper-trading/<trade_id>/close/
    """
    try:
        trade = PaperTrade.objects.get(id=trade_id, user__isnull=True, status='OPEN')
    except PaperTrade.DoesNotExist:
        return Response(
            {'error': 'Trade not found or not open'},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        prices, failed = _fetch_prices_batch({trade.symbol: trade.market_type})
        current_price = prices.get(trade.symbol)

        if not current_price:
            error_msg = failed.get(trade.symbol)
            if error_msg and ('400' in error_msg or 'Bad Request' in error_msg):
                _handle_failing_symbol(trade.symbol, error_msg, trade)
                return Response({
                    'message': f'Symbol {trade.symbol} blacklisted and trade closed due to API error',
                    'error': error_msg
                })

            return Response(
                {'error': 'Could not fetch current price'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        pnl, _ = trade.calculate_profit_loss(current_price)
        close_status = 'CLOSED_TP' if pnl >= 0 else 'CLOSED_SL'
        trade.close_trade(current_price, status=close_status)

        _invalidate_performance_cache()

        serializer = PaperTradeSerializer(trade)
        return Response({
            'message': f'Trade closed successfully at ${float(current_price):.4f}',
            'trade': serializer.data,
            'exit_price': float(current_price),
            'profit_loss': float(trade.profit_loss) if trade.profit_loss else 0,
            'profit_loss_pct': float(trade.profit_loss_percentage) if trade.profit_loss_percentage else 0,
        })

    except Exception as e:
        logger.error("Failed to close trade: %s", e, exc_info=True)
        return Response(
            {'error': 'Failed to close trade'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def public_summary(request):
    """
    PUBLIC cached comprehensive summary of SYSTEM paper trades.

    GET /api/public/paper-trading/summary/?direction=ALL&page=1&page_size=10
    """
    params = _get_filter_params(request)
    cache_key = _build_cache_key('perf:summary', params)

    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    all_system_trades = PaperTrade.objects.filter(user__isnull=True)

    gw_counts = all_system_trades.aggregate(
        total=Count('id'),
        gw1=Count('id', filter=Q(is_priority=True)),
        gw2=Count('id', filter=Q(is_golden_2=True)),
        outside=Count('id', filter=Q(is_priority=False, is_golden_2=False)),
    )

    queryset = _apply_common_filters(all_system_trades, params)

    metrics = _compute_performance_metrics(queryset)
    metrics['unrealized_pnl'] = 0.0
    metrics['total_pnl'] = metrics['total_profit_loss']

    open_count = queryset.filter(status='OPEN').count()

    page_size = min(int(request.query_params.get('recent_limit', 10)), 50)

    recent_closed_qs = queryset.filter(
        status__startswith='CLOSED'
    ).select_related('signal').order_by('-exit_time')[:page_size]

    recent_closed_data = PaperTradeSerializer(recent_closed_qs, many=True).data

    summary = {
        'performance': metrics,
        'open_trades_count': open_count,
        'recent_closed_trades': recent_closed_data,
        'bot_total_pnl': metrics['total_pnl'],
        'bot_win_rate': metrics['win_rate'],
        'bot_total_trades': metrics['total_trades'],
        'bot_realized_pnl': metrics['total_profit_loss'],
        'bot_unrealized_pnl': metrics['unrealized_pnl'],
        'gw_distribution': {
            'total_trades': gw_counts['total'] or 0,
            'gw1_trades': gw_counts['gw1'] or 0,
            'gw2_trades': gw_counts['gw2'] or 0,
            'outside_gw_trades': gw_counts['outside'] or 0,
        },
    }

    cache.set(cache_key, summary, CACHE_TTL_SUMMARY)
    return Response(summary)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_report(request):
    """
    Bot performance report with breakdowns by symbol, direction, timeframe, priority.

    GET /api/public/paper-trading/report/
    """
    params = _get_filter_params(request)
    cache_key = _build_cache_key('perf:report', params)
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    all_trades = PaperTrade.objects.filter(user__isnull=True)
    filtered = _apply_common_filters(all_trades, params)
    closed = filtered.filter(status__startswith='CLOSED')
    overall = _compute_performance_metrics(filtered)

    report = {
        'overall': overall,
        'by_symbol': _aggregate_by_field(closed, 'symbol'),
        'by_direction': _aggregate_by_field(closed, 'direction'),
        'by_timeframe': _aggregate_by_field(closed, 'timeframe'),
        'by_priority': _build_priority_stats(closed),
        'daily_pnl': _build_daily_pnl(closed),
        'top_winners': _build_top_trades(closed, winners=True),
        'top_losers': _build_top_trades(closed, winners=False),
        'streaks': _compute_streaks(closed),
    }
    cache.set(cache_key, report, 30)
    return Response(report)


def _aggregate_by_field(closed_qs, field_name):
    rows = list(
        closed_qs.values(field_name).annotate(
            total=Count('id'),
            wins=Count('id', filter=Q(profit_loss__gt=0)),
            losses=Count('id', filter=Q(profit_loss__lt=0)),
            pnl=Sum('profit_loss'),
            avg_pnl=Avg('profit_loss'),
            best=Max('profit_loss'),
            worst=Min('profit_loss'),
        ).order_by('-pnl')
    )
    for row in rows:
        row['win_rate'] = round((row['wins'] / row['total']) * 100, 1) if row['total'] > 0 else 0
        for k in ['pnl', 'avg_pnl', 'best', 'worst']:
            row[k] = float(row[k] or 0)
    return rows


def _build_priority_stats(closed_qs):
    result = {}
    for label, qs in [('priority', closed_qs.filter(is_priority=True)), ('non_priority', closed_qs.filter(is_priority=False))]:
        stats = qs.aggregate(total=Count('id'), wins=Count('id', filter=Q(profit_loss__gt=0)), pnl=Sum('profit_loss'))
        t = stats['total'] or 0
        result[label] = {
            'total': t,
            'wins': stats['wins'] or 0,
            'win_rate': round(((stats['wins'] or 0) / t) * 100, 1) if t > 0 else 0,
            'pnl': float(stats['pnl'] or 0),
        }
    return result


def _build_daily_pnl(closed_qs):
    rows = list(
        closed_qs.filter(exit_time__isnull=False)
        .extra(select={'day': "DATE(exit_time)"})
        .values('day')
        .annotate(trades=Count('id'), pnl=Sum('profit_loss'), wins=Count('id', filter=Q(profit_loss__gt=0)))
        .order_by('day')
    )
    cumulative = 0
    for row in rows:
        row['pnl'] = float(row['pnl'] or 0)
        cumulative += row['pnl']
        row['cumulative_pnl'] = round(cumulative, 2)
        row['day'] = str(row['day'])
    return rows


def _build_top_trades(closed_qs, winners=True, limit=5):
    if winners:
        qs = closed_qs.filter(profit_loss__gt=0).order_by('-profit_loss')[:limit]
    else:
        qs = closed_qs.filter(profit_loss__lt=0).order_by('profit_loss')[:limit]
    rows = list(qs.values('id', 'symbol', 'direction', 'entry_price', 'exit_price',
                          'profit_loss', 'profit_loss_percentage', 'is_priority'))
    for t in rows:
        for k in ['entry_price', 'exit_price', 'profit_loss', 'profit_loss_percentage']:
            t[k] = float(t[k] or 0)
    return rows


def _compute_streaks(closed_qs):
    pnl_list = list(closed_qs.order_by('exit_time').values_list('profit_loss', flat=True))
    max_win = max_lose = 0
    streak = 0
    for pnl in pnl_list:
        if pnl and pnl > 0:
            streak = streak + 1 if streak > 0 else 1
            max_win = max(max_win, streak)
        elif pnl and pnl < 0:
            streak = streak - 1 if streak < 0 else -1
            max_lose = max(max_lose, abs(streak))
    return {'current': streak, 'max_win': max_win, 'max_loss': max_lose}


@api_view(['GET'])
@permission_classes([AllowAny])
def signal_chart(request, signal_id):
    """
    GET /api/public/signal/{signal_id}/chart/
    Returns candles + indicators + price levels for signal detail chart.
    """
    from signals.models import Signal
    import requests as req

    try:
        sig = Signal.objects.select_related('symbol').get(id=signal_id)
    except Signal.DoesNotExist:
        return Response({'error': 'Signal not found'}, status=404)

    symbol = sig.symbol.symbol
    timeframe = sig.timeframe or '1h'
    created = sig.created_at

    tf_minutes = {
        '1m': 1, '5m': 5, '15m': 15, '30m': 30,
        '1h': 60, '4h': 240, '1d': 1440,
    }
    minutes = tf_minutes.get(timeframe, 60)
    padding = timedelta(minutes=minutes * 50)
    start_time = created - padding
    end_time = created + padding

    candles = _load_candles_from_csv(symbol, timeframe, start_time, end_time)

    if not candles:
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        params = {
            'symbol': symbol, 'interval': timeframe,
            'startTime': start_ms, 'endTime': end_ms, 'limit': 500,
        }
        for url in ['https://fapi.binance.com/fapi/v1/klines', 'https://api.binance.com/api/v3/klines']:
            try:
                resp = req.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    for c in resp.json():
                        candles.append({
                            'time': int(c[0]) // 1000,
                            'open': float(c[1]),
                            'high': float(c[2]),
                            'low': float(c[3]),
                            'close': float(c[4]),
                            'volume': float(c[5]),
                        })
                    if candles:
                        break
            except Exception as e:
                logger.warning(f"Binance fetch failed: {e}")

    if not candles:
        return Response({'error': 'No candle data available'}, status=404)

    indicators = _compute_indicators(candles)

    entry_ts = int(created.timestamp())
    closest = min(candles, key=lambda c: abs(c['time'] - entry_ts))
    markers = [{
        'time': closest['time'],
        'position': 'belowBar' if sig.direction == 'LONG' else 'aboveBar',
        'color': '#22c55e' if sig.direction == 'LONG' else '#ef4444',
        'shape': 'arrowUp' if sig.direction == 'LONG' else 'arrowDown',
        'text': f'{sig.direction} @ {float(sig.entry):.4f}',
    }]

    lines = [
        {'price': float(sig.entry), 'color': '#3b82f6', 'title': 'Entry', 'lineWidth': 2, 'lineStyle': 0},
        {'price': float(sig.sl), 'color': '#ef4444', 'title': 'Stop Loss', 'lineWidth': 1, 'lineStyle': 2},
        {'price': float(sig.tp), 'color': '#22c55e', 'title': 'Take Profit', 'lineWidth': 1, 'lineStyle': 2},
    ]

    return Response({
        'signal': {
            'id': sig.id,
            'symbol': symbol,
            'direction': sig.direction,
            'timeframe': timeframe,
            'entry': float(sig.entry),
            'sl': float(sig.sl),
            'tp': float(sig.tp),
            'confidence': sig.confidence,
            'meta': sig.meta,
            'created_at': sig.created_at.isoformat(),
        },
        'candles': candles,
        'indicators': indicators,
        'markers': markers,
        'lines': lines,
    })


def _compute_indicators(candles):
    """Compute EMA, BB, RSI, MACD from candle data for chart overlays."""
    import numpy as np

    closes = np.array([c['close'] for c in candles])
    highs = np.array([c['high'] for c in candles])
    lows = np.array([c['low'] for c in candles])
    times = [c['time'] for c in candles]
    n = len(closes)

    def ema(data, period):
        result = np.full(len(data), np.nan)
        if len(data) < period:
            return result
        k = 2 / (period + 1)
        result[period - 1] = np.mean(data[:period])
        for i in range(period, len(data)):
            result[i] = data[i] * k + result[i - 1] * (1 - k)
        return result

    def rsi(data, period=14):
        result = np.full(len(data), np.nan)
        if len(data) < period + 1:
            return result
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            rs = avg_gain / avg_loss if avg_loss != 0 else 100
            result[i + 1] = 100 - (100 / (1 + rs))
        return result

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema50 = ema(closes, 50)
    rsi_vals = rsi(closes, 14)

    bb_period = 20
    bb_mid = ema(closes, bb_period)
    bb_std = np.full(n, np.nan)
    for i in range(bb_period - 1, n):
        bb_std[i] = np.std(closes[i - bb_period + 1:i + 1])
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    result = {
        'ema9': [], 'ema21': [], 'ema50': [],
        'bb_upper': [], 'bb_mid': [], 'bb_lower': [],
        'rsi': [],
    }

    for i in range(n):
        t = times[i]
        if not np.isnan(ema9[i]):
            result['ema9'].append({'time': t, 'value': round(ema9[i], 8)})
        if not np.isnan(ema21[i]):
            result['ema21'].append({'time': t, 'value': round(ema21[i], 8)})
        if not np.isnan(ema50[i]):
            result['ema50'].append({'time': t, 'value': round(ema50[i], 8)})
        if not np.isnan(bb_upper[i]):
            result['bb_upper'].append({'time': t, 'value': round(bb_upper[i], 8)})
            result['bb_mid'].append({'time': t, 'value': round(bb_mid[i], 8)})
            result['bb_lower'].append({'time': t, 'value': round(bb_lower[i], 8)})
        if not np.isnan(rsi_vals[i]):
            result['rsi'].append({'time': t, 'value': round(rsi_vals[i], 2)})

    return result


def _load_candles_from_csv(symbol, timeframe, start_time, end_time):
    """Load candles from local CSV backtest data if available."""
    import csv
    import os
    from django.conf import settings

    volatility_map = {
        'BTCUSDT': 'low', 'ETHUSDT': 'low',
        'ADAUSDT': 'medium', 'SOLUSDT': 'medium', 'BNBUSDT': 'medium', 'XRPUSDT': 'medium',
        'DOGEUSDT': 'high', 'SHIBUSDT': 'high', 'PEPEUSDT': 'high',
    }
    vol = volatility_map.get(symbol)
    if not vol:
        return []

    csv_path = os.path.join(settings.BASE_DIR, 'backtest_data', vol, f'{symbol}_{timeframe}.csv')
    if not os.path.exists(csv_path):
        return []

    candles = []
    start_str = start_time.strftime('%Y-%m-%d %H:%M')
    end_str = end_time.strftime('%Y-%m-%d %H:%M')

    try:
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                ts_str = row[0][:16]
                if ts_str < start_str:
                    continue
                if ts_str > end_str:
                    break
                from datetime import datetime as dt
                ts = int(dt.strptime(row[0][:19], '%Y-%m-%d %H:%M:%S').timestamp())
                candles.append({
                    'time': ts,
                    'open': float(row[1]),
                    'high': float(row[2]),
                    'low': float(row[3]),
                    'close': float(row[4]),
                    'volume': float(row[5]),
                })
    except Exception as e:
        logger.warning(f"CSV load failed for replay: {e}")
        return []

    return candles


@api_view(['GET'])
@permission_classes([AllowAny])
def trade_replay(request, trade_id):
    """
    GET /api/public/paper-trading/replay/{trade_id}/
    Fetch candles around a trade for visual replay on a candlestick chart.
    Returns candles from 30 candles before entry to 30 candles after exit.
    """

    try:
        trade = PaperTrade.objects.get(id=trade_id, user__isnull=True)
    except PaperTrade.DoesNotExist:
        return Response({'error': 'Trade not found'}, status=404)

    symbol = trade.symbol
    timeframe = trade.timeframe or '1h'
    entry_time = trade.entry_time or trade.created_at
    exit_time = trade.exit_time or trade.updated_at

    tf_minutes = {
        '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
        '1h': 60, '2h': 120, '4h': 240, '1d': 1440,
    }
    minutes = tf_minutes.get(timeframe, 60)
    padding = timedelta(minutes=minutes * 30)

    start_time = entry_time - padding
    end_time = exit_time + padding

    candles = _load_candles_from_csv(symbol, timeframe, start_time, end_time)

    if not candles:
        import requests as req
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        params = {
            'symbol': symbol, 'interval': timeframe,
            'startTime': start_ms, 'endTime': end_ms, 'limit': 500,
        }
        for url in ['https://fapi.binance.com/fapi/v1/klines', 'https://api.binance.com/api/v3/klines']:
            try:
                resp = req.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    for c in resp.json():
                        candles.append({
                            'time': int(c[0]) // 1000,
                            'open': float(c[1]),
                            'high': float(c[2]),
                            'low': float(c[3]),
                            'close': float(c[4]),
                            'volume': float(c[5]),
                        })
                    if candles:
                        break
            except Exception as e:
                logger.warning(f"Binance {url} failed: {e}")

    if not candles:
        return Response({'error': 'No candle data available for this trade'}, status=404)

    markers = []
    entry_ts = int(entry_time.timestamp())
    closest_entry = min(candles, key=lambda c: abs(c['time'] - entry_ts), default=None)
    if closest_entry:
        markers.append({
            'time': closest_entry['time'],
            'position': 'belowBar' if trade.direction == 'LONG' else 'aboveBar',
            'color': '#22c55e' if trade.direction == 'LONG' else '#ef4444',
            'shape': 'arrowUp' if trade.direction == 'LONG' else 'arrowDown',
            'text': f'ENTRY ${float(trade.entry_price):.2f}',
        })

    if trade.exit_price and exit_time:
        exit_ts = int(exit_time.timestamp())
        closest_exit = min(candles, key=lambda c: abs(c['time'] - exit_ts), default=None)
        if closest_exit:
            is_win = float(trade.profit_loss or 0) >= 0
            markers.append({
                'time': closest_exit['time'],
                'position': 'aboveBar' if trade.direction == 'LONG' else 'belowBar',
                'color': '#22c55e' if is_win else '#ef4444',
                'shape': 'arrowDown' if trade.direction == 'LONG' else 'arrowUp',
                'text': f'EXIT ${float(trade.exit_price):.2f}',
            })

    lines = []
    if trade.entry_price:
        lines.append({'price': float(trade.entry_price), 'color': '#3b82f6', 'title': 'Entry', 'lineWidth': 2})
    if trade.stop_loss:
        lines.append({'price': float(trade.stop_loss), 'color': '#ef4444', 'title': 'Stop Loss', 'lineWidth': 1, 'lineStyle': 2})
    if trade.take_profit:
        lines.append({'price': float(trade.take_profit), 'color': '#22c55e', 'title': 'Take Profit', 'lineWidth': 1, 'lineStyle': 2})

    fg_value = None
    fg_label = 'Unknown'
    fg_source = 'live'
    try:
        if trade.fear_greed_at_entry is not None:
            fg_value = trade.fear_greed_at_entry
            fg_source = 'at_entry'
        else:
            signal_obj = getattr(trade, 'signal', None)
            if signal_obj and isinstance(getattr(signal_obj, 'meta', None), dict):
                stored_fg = signal_obj.meta.get('fg_value') or signal_obj.meta.get('neutral_reversal', {}).get('fg_value')
                if stored_fg:
                    fg_value = int(stored_fg)
                    fg_source = 'at_entry'

        if fg_value is None:
            from signals.services.fear_greed import get_fear_greed_value
            fg_value = get_fear_greed_value()
            fg_source = 'live'

        if fg_value is not None:
            if fg_value <= 25:
                fg_label = 'Extreme Fear'
            elif fg_value <= 40:
                fg_label = 'Fear'
            elif fg_value <= 60:
                fg_label = 'Neutral'
            elif fg_value <= 75:
                fg_label = 'Greed'
            else:
                fg_label = 'Extreme Greed'
    except Exception:
        pass

    is_neutral_reversal = False
    original_direction = None
    signal = getattr(trade, 'signal', None)
    if signal and isinstance(getattr(signal, 'meta', None), dict):
        nr = signal.meta.get('neutral_reversal')
        if nr:
            is_neutral_reversal = True
            original_direction = nr.get('original_direction')

    return Response({
        'trade': {
            'id': trade.id,
            'symbol': symbol,
            'direction': trade.direction,
            'entry_price': float(trade.entry_price),
            'exit_price': float(trade.exit_price) if trade.exit_price else None,
            'stop_loss': float(trade.stop_loss) if trade.stop_loss else None,
            'take_profit': float(trade.take_profit) if trade.take_profit else None,
            'profit_loss': float(trade.profit_loss) if trade.profit_loss else None,
            'status': trade.status,
            'timeframe': timeframe,
            'entry_time': entry_time.isoformat(),
            'exit_time': exit_time.isoformat() if exit_time else None,
            'is_priority': getattr(trade, 'is_priority', False),
            'is_neutral_reversal': is_neutral_reversal,
            'original_direction': original_direction,
        },
        'candles': candles,
        'markers': markers,
        'lines': lines,
        'fear_greed': {
            'value': fg_value,
            'label': fg_label,
            'source': fg_source,
        },
    })


def _invalidate_performance_cache():
    """Clear all performance-related caches after trade changes."""
    try:
        cache.delete_pattern('perf:*')
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Export — Bot Performance trade history as CSV / JSON / XLSX, honouring the
# same filters the Bot Performance UI uses (window, direction, weekday/hour/
# month/year, top_performer). Single endpoint dispatches by ?format=.
# ---------------------------------------------------------------------------

EXPORT_COLUMNS = [
    'id', 'symbol', 'direction', 'market_type', 'timeframe',
    'is_priority', 'is_golden_2', 'fear_greed_at_entry',
    'entry_price', 'exit_price', 'quantity', 'position_size',
    'stop_loss', 'take_profit',
    'profit_loss', 'profit_loss_percentage',
    'duration_hours',
    'status', 'entry_time', 'exit_time', 'created_at',
    'confidence', 'signal_id',
]


def _row_for_export(t):
    """Return a JSON/CSV-safe dict for a PaperTrade row."""
    duration_hours = ''
    if t.entry_time and t.exit_time:
        duration_hours = round(
            (t.exit_time - t.entry_time).total_seconds() / 3600.0, 3,
        )

    sig = getattr(t, 'signal', None)
    timeframe = getattr(sig, 'timeframe', '') if sig else ''
    confidence = getattr(sig, 'confidence', '') if sig else ''

    def _num(v):
        if v is None:
            return ''
        return float(v) if isinstance(v, Decimal) else v

    def _ts(v):
        return v.isoformat() if v else ''

    return {
        'id': t.id,
        'symbol': t.symbol,
        'direction': t.direction,
        'market_type': t.market_type,
        'timeframe': timeframe,
        'is_priority': bool(t.is_priority),
        'is_golden_2': bool(getattr(t, 'is_golden_2', False)),
        'fear_greed_at_entry': t.fear_greed_at_entry if t.fear_greed_at_entry is not None else '',
        'entry_price': _num(t.entry_price),
        'exit_price': _num(t.exit_price),
        'quantity': _num(t.quantity),
        'position_size': _num(t.position_size),
        'stop_loss': _num(t.stop_loss),
        'take_profit': _num(t.take_profit),
        'profit_loss': _num(t.profit_loss),
        'profit_loss_percentage': _num(t.profit_loss_percentage),
        'duration_hours': duration_hours,
        'status': t.status,
        'entry_time': _ts(t.entry_time),
        'exit_time': _ts(t.exit_time),
        'created_at': _ts(t.created_at),
        'confidence': _num(confidence) if confidence != '' else '',
        'signal_id': getattr(t, 'signal_id', None) or '',
    }


def _filter_label(params):
    """Short slug describing the active filter set, used in export filenames."""
    parts = []
    if str(params.get('top_performer', '')).lower() == 'true':
        parts.append('top')
    if str(params.get('golden_window', '')).lower() == 'true':
        parts.append('gw1')
    if str(params.get('golden_window_2', '')).lower() == 'true':
        parts.append('gw2')
    if str(params.get('outside_golden_window', '')).lower() == 'true':
        parts.append('outside-gw')
    if str(params.get('gw1_ai', '')).lower() == 'true':
        parts.append('gw1-ai')
    if str(params.get('gw2_ai', '')).lower() == 'true':
        parts.append('gw2-ai')
    direction = (params.get('direction') or '').upper()
    if direction in ('LONG', 'SHORT'):
        parts.append(direction.lower())
    for k in ('weekday', 'hour', 'month', 'year'):
        v = params.get(k)
        if v and v != 'ALL':
            parts.append(f'{k}{v}')
    return '-'.join(parts) or 'all'


def _export_filename(params, ext):
    ts = timezone.now().strftime('%Y%m%d-%H%M%S')
    return f'bot-performance_{_filter_label(params)}_{ts}.{ext}'


def _build_export_queryset(params):
    """Reuse the page's filter logic so the export matches the UI exactly."""
    qs = (
        PaperTrade.objects
        .filter(user__isnull=True)
        .select_related('signal')
    )
    qs = _apply_common_filters(qs, params)
    return qs.order_by('-entry_time')


def _stream_csv(params, queryset):
    """Yield CSV rows lazily so multi-thousand-row exports don't OOM."""
    import csv
    import io

    class _Echo:
        """File-like that returns the value written by csv.writer (Django docs pattern)."""
        def write(self, value):
            return value

    writer = csv.writer(_Echo())

    def _generator():
        yield writer.writerow(EXPORT_COLUMNS)
        for row in queryset.iterator(chunk_size=500):
            payload = _row_for_export(row)
            yield writer.writerow([payload.get(c, '') for c in EXPORT_COLUMNS])

    from django.http import StreamingHttpResponse
    response = StreamingHttpResponse(_generator(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{_export_filename(params, "csv")}"'
    return response


def _build_json_response(params, queryset):
    """JSON exports are always materialised — small enough to fit in memory and
    callers benefit from a single well-formed array. ``iterator`` keeps the
    queryset itself stream-friendly even though we collect the dict result."""
    from django.http import JsonResponse
    rows = [_row_for_export(t) for t in queryset.iterator(chunk_size=500)]
    response = JsonResponse(
        {'count': len(rows), 'filters': params, 'results': rows},
        json_dumps_params={'indent': 2},
    )
    response['Content-Disposition'] = f'attachment; filename="{_export_filename(params, "json")}"'
    return response


def _build_xlsx_response(params, queryset):
    """Materialise then write through pandas → openpyxl. ``ExcelWriter`` doesn't
    support streaming so the whole result lives in memory; cap is enforced by
    the caller when ?max= is supplied."""
    import io
    import pandas as pd
    from django.http import HttpResponse

    rows = [_row_for_export(t) for t in queryset.iterator(chunk_size=500)]
    df = pd.DataFrame(rows, columns=EXPORT_COLUMNS)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Trades', index=False)
        # Auto-fit-ish column widths (cap to keep the file svelte)
        ws = writer.sheets['Trades']
        for col_idx, col in enumerate(df.columns, start=1):
            sample = df[col].astype(str).head(200)
            width = min(max(len(col), int(sample.str.len().max() or 0)) + 2, 32)
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width
    buf.seek(0)

    response = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{_export_filename(params, "xlsx")}"'
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
def public_export(request):
    """
    Export the Bot Performance trade history as CSV / JSON / XLSX.

    Same filter surface as the Bot Performance page — passes through to
    ``_apply_common_filters`` so what you download is what you see.

    Query params:
      ?fmt=csv|json|xlsx          Required. Default ``csv``.
                                  (We use ``fmt`` rather than ``format``
                                  because DRF reserves ``format`` for
                                  content-negotiation and would 404 the
                                  request before our view runs.)
      ?max=NNNN                   Hard cap on row count (default 50000,
                                  set 0 for unlimited).

    Plus every filter the page already accepts: ``direction``,
    ``status``, ``market_type``, ``symbol``, ``golden_window``,
    ``golden_window_2``, ``outside_golden_window``, ``gw1_ai``,
    ``gw2_ai``, ``top_performer``, ``weekday``, ``hour``, ``month``,
    ``year``, ``days``.
    """
    # Accept either ``fmt`` (preferred) or ``format`` (legacy) — DRF
    # only intercepts the request when ``format`` resolves to an unknown
    # renderer, so a known value like ``json`` would actually route to
    # the JSON renderer instead of our handler. ``fmt`` is unambiguous.
    fmt = (request.query_params.get('fmt')
           or request.query_params.get('format')
           or 'csv').lower()
    if fmt not in ('csv', 'json', 'xlsx'):
        return Response(
            {'error': "fmt must be one of 'csv', 'json', 'xlsx'"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        max_rows = int(request.query_params.get('max', 50000))
    except (ValueError, TypeError):
        max_rows = 50000

    params = _get_filter_params(request)
    qs = _build_export_queryset(params)
    if max_rows and max_rows > 0:
        qs = qs[:max_rows]

    if fmt == 'csv':
        return _stream_csv(params, qs)
    if fmt == 'json':
        return _build_json_response(params, qs)
    return _build_xlsx_response(params, qs)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_macro_status(request):
    """
    Live read of the BTC daily-trend snapshot and the macro filter's
    decisions for both directions. Drives the Bot Performance "BTC
    regime" readout so users can see why the filter is blocking or
    allowing right now.

    Cached for 5 min inside ``btc_trend.get_btc_snapshot`` so this
    endpoint is cheap to poll (every minute is fine).
    """
    from scanner.services.macro_filter import macro_summary
    return Response(macro_summary())


@api_view(['GET'])
@permission_classes([AllowAny])
def public_equity_macro_status(request):
    """
    Live read of the SPY+QQQ daily-trend snapshot and the equity macro
    filter's decisions for both directions. Drives the Bot Performance
    "Equity regime" widget for STOCK signals.

    Cached for 5 min inside ``equity_trend.get_equity_snapshot``.
    """
    from scanner.services.equity_filter import equity_macro_summary
    return Response(equity_macro_summary())


@api_view(['GET'])
@permission_classes([AllowAny])
def public_commodity_macro_status(request):
    """
    Live read of the GLD+CL daily-trend snapshot and the commodity
    macro filter's decisions for both directions. Drives the
    "Commodity regime" widget for COMMODITY signals.

    Cached for 5 min inside ``commodity_trend.get_commodity_snapshot``.
    """
    from scanner.services.commodity_filter import commodity_macro_summary
    return Response(commodity_macro_summary())
