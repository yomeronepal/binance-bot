"""Live Binance execution for day-trade signals.

When a day-trade signal fires inside an active optimized Day-Trade Session, place
a REAL Binance futures order, sized from the shared futures pool
(FuturesTradingSettings.total_trading_capital / max_active_gw_trades x leverage).

The resulting position is recorded as a FuturesTrade so the existing 30s sync
(sync_futures_trades_with_binance) manages mark price, SL/TP detection and the
SL/TP push notification. Gated hard by FuturesTradingSettings.is_enabled (global
live master switch) AND daytrade_live_enabled; deduped per signal and per symbol.
"""
import asyncio
import logging
import threading
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone as dj_timezone

from signals.services.futures_trader import BinanceFuturesTrader

logger = logging.getLogger(__name__)

NEPAL_OFFSET = timedelta(hours=5, minutes=45)


LIVE_ENTRY_NOTE = 'Day-trade live entry'


def _active_session():
    """The active Day-Trade Session covering the current Nepal time, or None."""
    from signals.models.daytrade import DayTradeSession

    npt = dj_timezone.now() + NEPAL_OFFSET
    hour, weekday = npt.hour, npt.weekday()
    for session in DayTradeSession.objects.filter(is_active=True).order_by('start_hour'):
        if session.covers(hour, weekday):
            return session
    return None


def _now_in_active_session():
    """True if the current Nepal time falls inside any active Day-Trade Session."""
    return _active_session() is not None


def _session_window_start_utc(session):
    """UTC datetime for the start of today's occurrence of this session window."""
    npt = dj_timezone.now() + NEPAL_OFFSET
    window_start_npt = npt.replace(hour=session.start_hour, minute=0, second=0, microsecond=0)
    return window_start_npt - NEPAL_OFFSET


def _consecutive_sl_halt(threshold, scope_start, engine_filter):
    """True after `threshold` consecutive SLs since the last TP for one engine.

    Counts that engine's live futures closes since scope_start, ordered by exit
    time. A CLOSED_TP resets the streak; other close reasons are ignored.
    """
    if not threshold or threshold <= 0 or scope_start is None:
        return False
    from signals.models.futures import FuturesTrade

    closes = (FuturesTrade.objects
              .filter(exit_time__gte=scope_start, status__in=['CLOSED_TP', 'CLOSED_SL'])
              .filter(**engine_filter)
              .order_by('exit_time')
              .values_list('status', flat=True))
    streak = 0
    for status in closes:
        streak = 0 if status == 'CLOSED_TP' else streak + 1
    return streak >= threshold


def daytrade_trading_halted(threshold):
    """Per-engine breaker for the DAY-TRADE engine within its DayTradeSession window."""
    session = _active_session()
    if session is None:
        return False
    return _consecutive_sl_halt(
        threshold, _session_window_start_utc(session),
        {'signal__isnull': True, 'error_message__startswith': LIVE_ENTRY_NOTE},
    )


def _active_trading_session():
    """Active V1 golden-window TradingSession covering the current Nepal time, or None."""
    from signals.models.base import TradingSession

    npt = dj_timezone.now() + NEPAL_OFFSET
    minutes, weekday = npt.hour * 60 + npt.minute, npt.weekday()
    for session in TradingSession.objects.filter(active=True).order_by('start_hour', 'start_minute'):
        start = session.start_hour * 60 + session.start_minute
        end = session.end_hour * 60 + session.end_minute
        if start <= minutes < end and (not session.active_days or weekday in session.active_days):
            return session
    return None


def _trading_session_window_start(session):
    """UTC start of today's occurrence of this V1 golden-window session."""
    npt = dj_timezone.now() + NEPAL_OFFSET
    start_npt = npt.replace(hour=session.start_hour, minute=session.start_minute, second=0, microsecond=0)
    return start_npt - NEPAL_OFFSET


def golden_window_trading_halted(threshold):
    """Per-engine breaker for the V1 GOLDEN-WINDOW engine within its TradingSession window."""
    session = _active_trading_session()
    if session is None:
        return False
    return _consecutive_sl_halt(
        threshold, _trading_session_window_start(session),
        {'signal__isnull': False},
    )


def _place_orders(symbol, direction, leverage, margin, stop_loss, take_profit):
    """Place entry + SL/TP orders on Binance in a worker thread.

    Returns (result, exception); result is None on failure.
    """
    result = [None]
    error = [None]

    def run():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                async def _execute():
                    trader = BinanceFuturesTrader(use_testnet=False)
                    try:
                        symbol_info = await trader.get_symbol_info(symbol)
                        if not symbol_info:
                            raise Exception(f"No symbol info for {symbol}")
                        price = await trader.get_current_price(symbol)
                        if not price:
                            raise Exception(f"No current price for {symbol}")
                        return await trader.place_trade_orders(
                            symbol, direction, leverage, margin,
                            stop_loss, take_profit, symbol_info, price,
                        )
                    finally:
                        await trader.close()
                result[0] = loop.run_until_complete(_execute())
            finally:
                loop.close()
        except Exception as exc:
            error[0] = exc

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=60)
    return result[0], error[0]


def _live_gates_open(signal):
    """Return (settings, reason). settings is None when execution must be skipped."""
    from signals.models.futures import FuturesTradingSettings, FuturesTrade

    settings = FuturesTradingSettings.get_settings()
    if not settings.is_enabled:
        return None, 'futures_master_disabled'
    if not settings.daytrade_live_enabled:
        return None, 'daytrade_live_disabled'
    if signal.meta and signal.meta.get('live_order_id'):
        return None, 'already_executed'
    session = _active_session()
    if session is None:
        return None, 'not_in_session'
    if daytrade_trading_halted(settings.consecutive_sl_halt_threshold):
        return None, 'sl_streak_halt'
    if settings.get_available_gw_trade_slots() <= 0:
        return None, 'no_slots'
    if FuturesTrade.objects.filter(
        symbol=signal.symbol, direction=signal.direction, status__in=['OPEN', 'PENDING']
    ).exists():
        return None, 'existing_position'
    return settings, 'ok'


def _record_live_trade(signal, settings, result):
    """Persist the filled order as an OPEN FuturesTrade and tag the signal.

    Records the SL/TP order ids that place_trade_orders actually opened and
    folds any SL/TP warnings into error_message, so a missing SL/TP is visible
    instead of looking like a protected position.
    """
    from signals.models.futures import FuturesTrade

    sl_order_id = result.get('sl_order_id')
    tp_order_id = result.get('tp_order_id')
    warnings = result.get('warnings') or []

    note = f'{LIVE_ENTRY_NOTE} (in-session)'
    if not sl_order_id:
        note += ' | WARNING: no SL order on Binance'
    if not tp_order_id:
        note += ' | WARNING: no TP order on Binance'
    if warnings:
        note += ' | ' + '; '.join(str(w) for w in warnings)
    if not sl_order_id or not tp_order_id or warnings:
        logger.warning(
            "DayTrade live %s %s: SL=%s TP=%s warnings=%s",
            signal.direction, signal.symbol, sl_order_id, tp_order_id, warnings,
        )

    trade = FuturesTrade.objects.create(
        signal=None,
        symbol=signal.symbol,
        direction=signal.direction,
        leverage=settings.leverage,
        quantity=result['quantity'],
        entry_price=result['entry_price'],
        entry_time=dj_timezone.now(),
        stop_loss=signal.stop_loss,
        take_profit=signal.tp1,
        position_size_usdt=settings.per_trade_amount,
        status='OPEN',
        binance_order_id=result['order_id'],
        sl_order_id=str(sl_order_id) if sl_order_id else None,
        tp_order_id=str(tp_order_id) if tp_order_id else None,
        error_message=note,
    )
    signal.meta = {**(signal.meta or {}), 'live_order_id': str(result['order_id']),
                   'live_futures_trade_id': trade.id}
    signal.save(update_fields=['meta', 'updated_at'])
    return trade


def maybe_execute_live_daytrade(signal):
    """Execute a real Binance order for a day-trade signal if all live gates pass.

    Failure-isolated and idempotent: returns the FuturesTrade on success, else None.
    """
    settings, reason = _live_gates_open(signal)
    if settings is None:
        logger.debug("DayTrade live skip %s: %s", signal.symbol, reason)
        return None

    result, error = _place_orders(
        signal.symbol, signal.direction, settings.leverage,
        settings.per_trade_amount, signal.stop_loss, signal.tp1,
    )
    if error or not result:
        logger.error("DayTrade live order failed for %s: %s", signal.symbol, error or 'no result')
        return None

    trade = _record_live_trade(signal, settings, result)
    logger.info(
        "DayTrade LIVE opened: %s %s qty=%s @ %s (FuturesTrade %s)",
        signal.direction, signal.symbol, result['quantity'], result['entry_price'], trade.id,
    )
    return trade
