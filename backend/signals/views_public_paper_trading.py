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

    symbol = params.get('symbol')
    if symbol:
        queryset = queryset.filter(symbol__icontains=symbol)

    direction = params.get('direction')
    if direction and direction != 'ALL':
        queryset = queryset.filter(direction=direction.upper())

    queryset = _apply_golden_window_filter(queryset, params)
    queryset = _apply_time_filters(queryset, params)

    return queryset


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
        'status', 'market_type', 'symbol', 'direction',
        'golden_window', 'golden_window_2', 'outside_golden_window',
        'gw1_ai', 'gw2_ai',
        'weekday', 'hour', 'month', 'year', 'days'
    ]
    return {k: request.query_params.get(k, '') for k in keys}


def _fetch_prices_batch(symbols):
    """
    Fetch prices for multiple symbols concurrently using asyncio.gather.

    Args:
        symbols: List/set of symbol strings

    Returns:
        Tuple of (prices dict, failed_symbols dict)
    """
    from scanner.services.binance_client import BinanceClient

    async def fetch_all():
        prices = {}
        failed = {}
        async with BinanceClient() as client:
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
            symbols = set(open_trades_qs.values_list('symbol', flat=True))
            current_prices, failed_symbols = _fetch_prices_batch(symbols)

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

    direction = params.get('direction')
    if direction and direction != 'ALL':
        queryset = queryset.filter(direction=direction.upper())

    open_trades = list(queryset.select_related('signal').only(
        'id', 'symbol', 'direction', 'market_type', 'entry_price',
        'entry_time', 'position_size', 'stop_loss', 'take_profit',
        'leverage', 'quantity', 'status', 'user_id', 'is_priority',
        'signal__meta'
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

    symbols = set(t.symbol for t in open_trades)
    current_prices, failed_symbols = _fetch_prices_batch(symbols)

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
        prices, failed = _fetch_prices_batch([trade.symbol])
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
        return Response(
            {'error': f'Failed to close trade: {str(e)}'},
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


def _invalidate_performance_cache():
    """Clear all performance-related caches after trade changes."""
    try:
        cache.delete_pattern('perf:*')
    except Exception:
        pass
