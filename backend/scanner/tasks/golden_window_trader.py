"""
Golden Window Auto-Trader Celery Task

This task runs during GW1 and GW2 sessions and automatically executes
futures trades based on active signals. It prioritizes signals by:
1. is_golden_2 (GW2 signals)
2. is_priority (GW1 signals)
3. timeframe (1h > 15m > others)
4. confidence (higher is better)

The task divides total_trading_capital equally among max_active_gw_trades.
"""
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from celery import shared_task
from django.db.models import Q, Case, When, Value, IntegerField
from django.utils import timezone as dj_timezone

from signals.models import Signal, TradingSession
from signals.models.futures import FuturesTradingSettings, FuturesTrade
from signals.models.blacklist import BlacklistedSymbol
from signals.services.futures_trader import BinanceFuturesTrader

logger = logging.getLogger(__name__)

# Nepal timezone offset
NEPAL_TZ_OFFSET = timedelta(hours=5, minutes=45)


def get_nepal_time():
    """Get current Nepal time."""
    utc_now = datetime.now(timezone.utc)
    return utc_now + NEPAL_TZ_OFFSET


def check_and_execute_cut_loser(
    trade: FuturesTrade,
    pnl_pct: Decimal,
    settings: FuturesTradingSettings
) -> Optional[dict]:
    """
    Check if a losing trade should be closed near breakeven (cut loser first).

    Logic:
    1. If trade is in loss >= trigger_loss_pct, mark cut_loser_triggered=True
    2. Track max_loss_pct_reached
    3. If cut_loser_triggered and trade recovers to close_at_pct, close it

    Args:
        trade: FuturesTrade instance
        pnl_pct: Current unrealized PnL percentage
        settings: FuturesTradingSettings instance

    Returns:
        dict with close info if trade should be closed, None otherwise
    """
    import asyncio
    import threading

    if not settings.cut_loser_enabled:
        return None

    trigger_loss = -abs(settings.cut_loser_trigger_loss_pct)
    close_at = settings.cut_loser_close_at_pct

    if pnl_pct < trade.max_loss_pct_reached:
        trade.max_loss_pct_reached = pnl_pct
        trade.save(update_fields=['max_loss_pct_reached'])

    if not trade.cut_loser_triggered and pnl_pct <= trigger_loss:
        trade.cut_loser_triggered = True
        trade.save(update_fields=['cut_loser_triggered'])
        logger.info(
            f"🔻 Cut-loser triggered for {trade.symbol}: "
            f"Loss {pnl_pct:.2f}% exceeded threshold {trigger_loss:.2f}%"
        )

    if trade.cut_loser_triggered and pnl_pct >= close_at:
        logger.info(
            f"✂️ Cut-loser closing {trade.symbol}: "
            f"Recovered to {pnl_pct:.2f}% (target: {close_at:.2f}%)"
        )

        close_result = [None]
        close_exception = [None]

        def close_position():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    async def _close():
                        trader = BinanceFuturesTrader(use_testnet=False)
                        try:
                            await trader.cancel_all_orders(trade.symbol)
                            result = await trader.close_position(
                                trade.symbol,
                                trade.direction,
                                trade.quantity
                            )
                            return result
                        finally:
                            await trader.close()
                    close_result[0] = loop.run_until_complete(_close())
                finally:
                    loop.close()
            except Exception as e:
                close_exception[0] = e

        thread = threading.Thread(target=close_position)
        thread.start()
        thread.join(timeout=30)

        if close_exception[0]:
            logger.error(f"Failed to close cut-loser trade {trade.symbol}: {close_exception[0]}")
            return None

        if close_result[0]:
            exit_price = Decimal(close_result[0].get('avgPrice', '0'))
            trade.close_trade(exit_price, 'CLOSED_MANUAL')
            trade.error_message = f"Cut-loser: Closed at {pnl_pct:.2f}% (max loss was {trade.max_loss_pct_reached:.2f}%)"
            trade.save()

            return {
                'trade_id': trade.id,
                'symbol': trade.symbol,
                'direction': trade.direction,
                'exit_price': str(exit_price),
                'pnl_pct': str(pnl_pct),
                'max_loss_reached': str(trade.max_loss_pct_reached),
                'reason': 'cut_loser'
            }

    return None


def check_and_update_dynamic_trailing(
    trade: FuturesTrade,
    pnl_pct: Decimal,
    settings: FuturesTradingSettings
) -> Optional[dict]:
    """
    Check if trailing stop should be activated or tightened based on profit tiers.

    When first tier is reached:
    - Cancel fixed SL order
    - Place trailing stop with tier's callback rate

    When subsequent tiers are reached:
    - Cancel old trailing order
    - Place new trailing stop with tighter callback rate

    Example tiers: [{profit_pct: 2, trailing_pct: 1}, {profit_pct: 3, trailing_pct: 2}]
    - When profit reaches 2%, set trailing to 1% (lock in ~1% profit)
    - When profit reaches 3%, set trailing to 2% (lock in ~1% profit)

    Args:
        trade: FuturesTrade instance
        pnl_pct: Current unrealized PnL percentage
        settings: FuturesTradingSettings instance

    Returns:
        dict with update info if trailing was updated, None otherwise
    """
    import asyncio
    import threading

    if not settings.dynamic_trailing_enabled:
        return None

    if not settings.dynamic_trailing_tiers:
        return None

    tiers = settings.dynamic_trailing_tiers
    if not isinstance(tiers, list) or len(tiers) == 0:
        return None

    tiers = sorted(tiers, key=lambda x: float(x.get('profit_pct', 0)))

    if pnl_pct > trade.max_profit_pct_reached:
        trade.max_profit_pct_reached = pnl_pct
        trade.save(update_fields=['max_profit_pct_reached'])

    new_tier_index = 0
    new_trailing_pct = None

    for i, tier in enumerate(tiers):
        tier_profit = Decimal(str(tier.get('profit_pct', 0)))
        tier_trailing = Decimal(str(tier.get('trailing_pct', 1)))

        if pnl_pct >= tier_profit:
            new_tier_index = i + 1
            new_trailing_pct = tier_trailing

    if new_tier_index <= trade.current_trailing_tier:
        return None

    if new_trailing_pct is None:
        return None

    is_first_tier = trade.current_trailing_tier == 0
    logger.info(
        f"📈 Dynamic trailing {'activated' if is_first_tier else 'upgraded'} for {trade.symbol}: "
        f"Profit {pnl_pct:.2f}% reached tier {new_tier_index}, "
        f"{'replacing fixed SL with ' if is_first_tier else 'tightening to '}{new_trailing_pct}% trailing"
    )

    update_result = [None]
    update_exception = [None]

    def update_trailing():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                async def _update():
                    trader = BinanceFuturesTrader(use_testnet=False)
                    try:
                        if is_first_tier:
                            await trader.cancel_all_orders(trade.symbol)
                            logger.info(f"Cancelled all orders (including fixed SL) for {trade.symbol}")
                        elif trade.trailing_order_id:
                            try:
                                await trader._request(
                                    'DELETE',
                                    '/fapi/v1/order',
                                    {
                                        'symbol': trade.symbol,
                                        'orderId': trade.trailing_order_id
                                    },
                                    signed=True
                                )
                                logger.info(f"Cancelled old trailing order {trade.trailing_order_id}")
                            except Exception as e:
                                logger.warning(f"Could not cancel old trailing order: {e}")

                        sl_side = 'SELL' if trade.direction == 'LONG' else 'BUY'

                        result = await trader.place_trailing_stop_order(
                            trade.symbol,
                            sl_side,
                            trade.quantity,
                            new_trailing_pct,
                            None
                        )
                        return result
                    finally:
                        await trader.close()
                update_result[0] = loop.run_until_complete(_update())
            finally:
                loop.close()
        except Exception as e:
            update_exception[0] = e

    thread = threading.Thread(target=update_trailing)
    thread.start()
    thread.join(timeout=30)

    if update_exception[0]:
        logger.error(f"Failed to update trailing stop for {trade.symbol}: {update_exception[0]}")
        return None

    if update_result[0]:
        new_order_id = str(update_result[0].get('orderId', ''))
        trade.current_trailing_tier = new_tier_index
        trade.trailing_order_id = new_order_id
        trade.save(update_fields=['current_trailing_tier', 'trailing_order_id'])

        return {
            'trade_id': trade.id,
            'symbol': trade.symbol,
            'direction': trade.direction,
            'profit_pct': str(pnl_pct),
            'new_tier': new_tier_index,
            'new_trailing_pct': str(new_trailing_pct),
            'order_id': new_order_id,
            'first_activation': is_first_tier
        }

    return None


def is_in_golden_window() -> Tuple[bool, bool, Optional[str]]:
    """
    Check if current time is within any golden window.

    Returns:
        Tuple of (is_in_gw, is_gw2, session_name)
        - is_in_gw: True if in any golden window (GW1 or GW2)
        - is_gw2: True if specifically in GW2 (21:00-23:00 on Sun/Wed/Thu)
        - session_name: Name of the matching session or None
    """
    nepal_now = get_nepal_time()
    day_minutes = nepal_now.hour * 60 + nepal_now.minute
    weekday = nepal_now.weekday()  # 0=Mon, 6=Sun

    # Check GW1: 16:00-17:00 (960-1020 minutes)
    is_gw1_time = 960 <= day_minutes < 1020

    # Check GW2 time: 21:00-23:00 (1260-1380 minutes)
    is_gw2_time = 1260 <= day_minutes < 1380

    # GW2 requires specific days: Sun=6, Wed=2, Thu=3
    is_gw2_day = weekday in [6, 2, 3]

    is_gw2 = is_gw2_time and is_gw2_day
    is_in_gw = is_gw1_time or is_gw2_time

    session_name = None
    if is_gw2:
        session_name = "GW2"
    elif is_gw1_time:
        session_name = "GW1"
    elif is_gw2_time:
        session_name = "GW1"  # GW2 time but not GW2 day = GW1

    return is_in_gw, is_gw2, session_name


def is_in_gw2_ai_window() -> bool:
    """Return True if now (NPT) is inside an auto-generated GOLDEN_WINDOW.

    The "GW2 AI" session is the optimizer's auto-generated GOLDEN_WINDOW
    trading sessions. Futures auto-trading is restricted to these windows.
    """
    from signals.models import TradingSession
    nepal_now = get_nepal_time()
    sessions = TradingSession.objects.filter(
        auto_generated=True, active=True, session_type='GOLDEN_WINDOW'
    )
    return any(session.matches(nepal_now) for session in sessions)


def get_prioritized_signals(settings: FuturesTradingSettings, limit: int) -> List[Signal]:
    """
    Get active FUTURES signals prioritized for golden window trading.

    IMPORTANT: Only signals with is_priority=True are considered.
    This ensures we only trade signals generated during trading windows:
    - GW1: 16:00-17:00 NPT (all days)
    - GW2: 21:00-23:00 NPT (Sun/Wed/Thu)

    Priority order:
    1. is_golden_2 = True (GW2 signals first)
    2. timeframe: 1h > 15m > 5m > others
    3. confidence: higher is better

    Args:
        settings: FuturesTradingSettings instance
        limit: Maximum number of signals to return

    Returns:
        List of Signal objects, prioritized (only trading window signals)
    """
    # Get blacklisted symbols to exclude
    blacklisted = set(BlacklistedSymbol.objects.filter(active=True).values_list('symbol', flat=True))

    # Base queryset: Active FUTURES signals generated during trading windows
    # is_priority=True means signal was generated during GW1 (16:00-17:00) or GW2 (21:00-23:00) NPT
    queryset = Signal.objects.filter(
        status='ACTIVE',
        market_type='FUTURES',
        is_priority=True,  # Only trade signals generated during trading windows
    ).select_related('symbol')

    # Exclude blacklisted symbols
    if blacklisted:
        queryset = queryset.exclude(symbol__symbol__in=blacklisted)

    # Apply settings filters
    if settings.allowed_symbols:
        queryset = queryset.filter(symbol__symbol__in=settings.allowed_symbols)

    if not settings.trade_long:
        queryset = queryset.exclude(direction='LONG')

    if not settings.trade_short:
        queryset = queryset.exclude(direction='SHORT')

    # Filter by minimum confidence
    queryset = queryset.filter(confidence__gte=float(settings.min_signal_confidence))

    open_or_pending_symbols = FuturesTrade.objects.filter(
        status__in=['OPEN', 'PENDING']
    ).values_list('symbol', flat=True)
    queryset = queryset.exclude(symbol__symbol__in=open_or_pending_symbols)

    already_traded_signal_ids = FuturesTrade.objects.exclude(
        status='FAILED'
    ).values_list('signal_id', flat=True)
    queryset = queryset.exclude(id__in=already_traded_signal_ids)

    # Add priority scoring for ordering
    # Higher score = higher priority
    queryset = queryset.annotate(
        gw2_priority=Case(
            When(is_priority=True, then=Value(100)),  # is_priority acts as GW indicator
            default=Value(0),
            output_field=IntegerField()
        ),
        timeframe_priority=Case(
            When(timeframe='1h', then=Value(40)),
            When(timeframe='15m', then=Value(30)),
            When(timeframe='5m', then=Value(20)),
            When(timeframe='30m', then=Value(25)),
            When(timeframe='4h', then=Value(35)),
            default=Value(10),
            output_field=IntegerField()
        )
    ).order_by(
        '-gw2_priority',      # GW signals first
        '-timeframe_priority', # Better timeframes first
        '-confidence',         # Higher confidence first
        '-created_at'          # Newer signals first
    )[:limit]

    return list(queryset)


def execute_futures_trade(
    signal: Signal,
    position_size: Decimal,
    leverage: int,
    settings: FuturesTradingSettings = None
) -> Optional[FuturesTrade]:
    """
    Execute a single futures trade from a signal.

    Args:
        signal: Signal to trade
        position_size: USDT amount for this trade (margin)
        leverage: Leverage to use
        settings: FuturesTradingSettings for trailing stop config

    Returns:
        FuturesTrade if successful, None otherwise
    """
    import asyncio
    import threading
    from django.db import transaction

    if settings is None:
        settings = FuturesTradingSettings.get_settings()

    symbol_name = signal.symbol.symbol
    direction = signal.direction

    with transaction.atomic():
        signal_already_traded = FuturesTrade.objects.select_for_update().filter(
            signal=signal
        ).exclude(status='FAILED').exists()

        if signal_already_traded:
            logger.info(f"Signal {signal.id} already has a futures trade, skipping")
            return None

        existing = FuturesTrade.objects.select_for_update().filter(
            symbol=symbol_name,
            direction=direction,
            status__in=['OPEN', 'PENDING']
        ).exists()

        if existing:
            logger.info(f"Already have open/pending {direction} on {symbol_name}, skipping")
            return None

        futures_trade = FuturesTrade.objects.create(
            signal=signal,
            symbol=symbol_name,
            direction=direction,
            leverage=leverage,
            quantity=Decimal('0'),
            stop_loss=signal.sl,
            take_profit=signal.tp,
            position_size_usdt=position_size,
            status='PENDING'
        )

    # Execute API calls in a separate thread
    api_result = [None]
    api_exception = [None]

    def run_api_calls():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                async def _execute():
                    trader = BinanceFuturesTrader(use_testnet=False)
                    try:
                        # Get market data
                        symbol_info = await trader.get_symbol_info(symbol_name)
                        if not symbol_info:
                            raise Exception(f"Could not get symbol info for {symbol_name}")

                        current_price = await trader.get_current_price(symbol_name)
                        if not current_price:
                            raise Exception(f"Could not get current price for {symbol_name}")

                        result = await trader.place_trade_orders(
                            symbol_name,
                            direction,
                            leverage,
                            position_size,
                            signal.sl,
                            signal.tp,
                            symbol_info,
                            current_price
                        )
                        return result
                    finally:
                        await trader.close()

                api_result[0] = loop.run_until_complete(_execute())
            finally:
                loop.close()
        except Exception as e:
            api_exception[0] = e

    thread = threading.Thread(target=run_api_calls)
    thread.start()
    thread.join(timeout=60)

    if api_exception[0]:
        futures_trade.status = 'FAILED'
        futures_trade.error_message = str(api_exception[0])
        futures_trade.save()
        logger.error(f"Trade failed for signal {signal.id}: {api_exception[0]}")
        return None

    if not api_result[0]:
        futures_trade.status = 'FAILED'
        futures_trade.error_message = "API call returned no result"
        futures_trade.save()
        return None

    # Update trade record with results
    result = api_result[0]
    futures_trade.quantity = result['quantity']
    futures_trade.entry_price = result['entry_price']
    futures_trade.binance_order_id = result['order_id']
    futures_trade.entry_time = dj_timezone.now()
    futures_trade.status = 'OPEN'
    futures_trade.save()

    logger.info(
        f"GW Trade opened: {direction} {result['quantity']} {symbol_name} "
        f"@ {result['entry_price']} (Trade ID: {futures_trade.id})"
    )

    return futures_trade


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def golden_window_auto_trader(self):
    """
    Celery task that runs during golden windows to auto-trade futures.

    This task:
    1. Checks if we're in a golden window (GW1 or GW2)
    2. Gets settings and checks if auto-trading is enabled
    3. Fetches prioritized signals
    4. Executes trades up to max_active_gw_trades

    Should be scheduled to run every 30-60 seconds.
    """
    try:
        # Futures auto-trading is restricted to the GW2 AI session
        # (auto-generated GOLDEN_WINDOW windows) only.
        if not is_in_gw2_ai_window():
            logger.debug("Not in GW2 AI window, skipping auto-trader")
            return {"status": "skipped", "reason": "not_in_gw2_ai_window"}

        is_gw2 = True
        session_name = "GW2 AI"

        # Get settings
        settings = FuturesTradingSettings.get_settings()

        # Check if auto-trader is enabled
        if not settings.gw_auto_trader_enabled:
            logger.debug("GW auto-trader is disabled")
            return {"status": "skipped", "reason": "auto_trader_disabled"}

        if not settings.is_enabled:
            logger.debug("Futures trading is disabled")
            return {"status": "skipped", "reason": "futures_disabled"}

        # Check GW2 setting if we're in GW2
        if is_gw2 and not settings.trade_on_golden_window_2:
            logger.debug("GW2 trading is disabled")
            return {"status": "skipped", "reason": "gw2_disabled"}

        # Get available trade slots
        available_slots = settings.get_available_gw_trade_slots()

        if available_slots <= 0:
            logger.info(f"No available trade slots (max: {settings.max_active_gw_trades})")
            return {"status": "skipped", "reason": "max_trades_reached"}

        # Calculate per-trade amount
        per_trade_amount = settings.per_trade_amount
        leverage = settings.leverage

        logger.info(
            f"GW Auto-Trader active in {session_name} | "
            f"Slots: {available_slots} | "
            f"Per-trade: ${per_trade_amount} x {leverage}x"
        )

        # Get prioritized signals
        signals = get_prioritized_signals(settings, limit=available_slots)

        if not signals:
            logger.info("No eligible signals found for trading")
            return {"status": "no_signals", "session": session_name}

        logger.info(f"Found {len(signals)} prioritized signals")

        # Execute trades
        trades_executed = []
        trades_failed = []

        for signal in signals:
            # Re-check slots (in case other trades opened)
            current_slots = settings.get_available_gw_trade_slots()
            if current_slots <= 0:
                logger.info("Max trades reached during execution")
                break

            try:
                trade = execute_futures_trade(signal, per_trade_amount, leverage, settings)
                if trade:
                    trades_executed.append({
                        'trade_id': trade.id,
                        'symbol': trade.symbol,
                        'direction': trade.direction,
                        'entry_price': str(trade.entry_price)
                    })
                    logger.info(
                        f"Executed GW trade: {trade.direction} {trade.symbol} "
                        f"@ {trade.entry_price}"
                    )
                else:
                    trades_failed.append({
                        'signal_id': signal.id,
                        'symbol': signal.symbol.symbol,
                        'reason': 'execution_failed'
                    })
            except Exception as e:
                logger.error(f"Error executing trade for signal {signal.id}: {e}")
                trades_failed.append({
                    'signal_id': signal.id,
                    'symbol': signal.symbol.symbol,
                    'reason': str(e)
                })

        result = {
            "status": "completed",
            "session": session_name,
            "is_gw2": is_gw2,
            "trades_executed": len(trades_executed),
            "trades_failed": len(trades_failed),
            "executed": trades_executed,
            "failed": trades_failed
        }

        if trades_executed:
            logger.info(
                f"GW Auto-Trader completed: {len(trades_executed)} trades executed, "
                f"{len(trades_failed)} failed"
            )

        return result

    except Exception as exc:
        logger.error(f"Golden window auto-trader error: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True)
def check_gw_trades_status(self):
    """
    Supplementary task to monitor and log GW trade status.
    Can be used for debugging and monitoring.
    """
    try:
        open_trades = FuturesTrade.objects.filter(status='OPEN')

        if not open_trades.exists():
            return {"status": "no_open_trades"}

        trades_info = []
        for trade in open_trades:
            trades_info.append({
                'id': trade.id,
                'symbol': trade.symbol,
                'direction': trade.direction,
                'entry_price': str(trade.entry_price),
                'quantity': str(trade.quantity),
                'leverage': trade.leverage,
                'opened_at': trade.entry_time.isoformat() if trade.entry_time else None
            })

        is_in_gw, is_gw2, session = is_in_golden_window()

        return {
            "status": "monitoring",
            "in_golden_window": is_in_gw,
            "session": session,
            "open_trades_count": len(trades_info),
            "trades": trades_info
        }

    except Exception as e:
        logger.error(f"Error checking GW trades status: {e}")
        return {"status": "error", "error": str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_futures_trades_with_binance(self):
    """
    Sync local FuturesTrade records with actual Binance positions.

    This task:
    1. Fetches all open positions from Binance
    2. Updates local OPEN trades with current unrealized PnL
    3. Detects closed positions and updates their status/PnL
    4. Creates records for positions opened outside our system (optional)

    Should be scheduled to run every 30-60 seconds.
    """
    import asyncio
    import threading

    try:
        settings = FuturesTradingSettings.get_settings()

        if not settings.is_enabled:
            return {"status": "skipped", "reason": "futures_disabled"}

        # Fetch Binance data in a separate thread
        binance_positions = [None]
        binance_exception = [None]

        def fetch_binance_data():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    async def _fetch():
                        trader = BinanceFuturesTrader(use_testnet=False)
                        try:
                            positions = await trader.get_open_positions()
                            return positions
                        finally:
                            await trader.close()
                    binance_positions[0] = loop.run_until_complete(_fetch())
                finally:
                    loop.close()
            except Exception as e:
                binance_exception[0] = e

        thread = threading.Thread(target=fetch_binance_data)
        thread.start()
        thread.join(timeout=30)

        if binance_exception[0]:
            logger.error(f"Failed to fetch Binance positions: {binance_exception[0]}")
            raise self.retry(exc=binance_exception[0], countdown=60)

        positions = binance_positions[0] or []

        # Build a map of Binance positions by symbol
        binance_position_map = {}
        for pos in positions:
            symbol = pos.get('symbol')
            position_amt = float(pos.get('positionAmt', 0))
            if position_amt != 0:
                direction = 'LONG' if position_amt > 0 else 'SHORT'
                binance_position_map[symbol] = {
                    'symbol': symbol,
                    'direction': direction,
                    'quantity': abs(position_amt),
                    'entry_price': Decimal(pos.get('entryPrice', '0')),
                    'mark_price': Decimal(pos.get('markPrice', '0')),
                    'unrealized_pnl': Decimal(pos.get('unRealizedProfit', '0')),
                    'leverage': int(pos.get('leverage', 1)),
                    'margin_type': pos.get('marginType', 'isolated'),
                    'liquidation_price': Decimal(pos.get('liquidationPrice', '0')),
                }

        # Get all local OPEN trades
        local_open_trades = FuturesTrade.objects.filter(status='OPEN')

        synced_trades = []
        closed_trades = []
        updated_trades = []

        for trade in local_open_trades:
            binance_pos = binance_position_map.get(trade.symbol)

            if binance_pos:
                # Position still open on Binance - update with current data
                # Check if direction matches
                if binance_pos['direction'] == trade.direction:
                    # Update unrealized PnL and live data
                    unrealized_pnl = binance_pos['unrealized_pnl']
                    mark_price = binance_pos['mark_price']
                    liquidation_price = binance_pos.get('liquidation_price', Decimal('0'))
                    margin_type = binance_pos.get('margin_type', 'ISOLATED')

                    # Calculate current PnL percentage
                    if trade.entry_price and trade.position_size_usdt:
                        pnl_pct = (unrealized_pnl / trade.position_size_usdt) * 100
                    else:
                        pnl_pct = Decimal('0')

                    # Update trade record with live data
                    trade.mark_price = mark_price
                    trade.unrealized_pnl = unrealized_pnl
                    trade.unrealized_pnl_percentage = pnl_pct
                    trade.liquidation_price = liquidation_price if liquidation_price > 0 else None
                    trade.margin_type = margin_type.upper()
                    trade.last_sync_time = dj_timezone.now()
                    trade.save()

                    updated_trades.append({
                        'trade_id': trade.id,
                        'symbol': trade.symbol,
                        'direction': trade.direction,
                        'entry_price': str(trade.entry_price),
                        'mark_price': str(mark_price),
                        'unrealized_pnl': str(unrealized_pnl),
                        'pnl_pct': str(pnl_pct),
                        'liquidation_price': str(liquidation_price),
                        'margin_type': margin_type,
                    })

                    cut_loser_result = check_and_execute_cut_loser(trade, pnl_pct, settings)
                    if cut_loser_result:
                        closed_trades.append(cut_loser_result)
                        logger.info(
                            f"✂️ Cut-loser closed: {trade.symbol} @ {cut_loser_result['exit_price']} "
                            f"(PnL: {cut_loser_result['pnl_pct']}%)"
                        )
                    else:
                        trailing_result = check_and_update_dynamic_trailing(trade, pnl_pct, settings)
                        if trailing_result:
                            logger.info(
                                f"📈 Dynamic trailing updated: {trade.symbol} "
                                f"Tier {trailing_result['new_tier']} ({trailing_result['new_trailing_pct']}%)"
                            )

                    del binance_position_map[trade.symbol]
                else:
                    # Direction mismatch - position may have been closed and reopened
                    logger.warning(
                        f"Direction mismatch for {trade.symbol}: "
                        f"Local={trade.direction}, Binance={binance_pos['direction']}"
                    )
            else:
                # Position not found on Binance - it was closed
                # Fetch the realized PnL from income history
                realized_pnl = Decimal('0')
                exit_price = Decimal('0')

                def fetch_trade_close_data():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            async def _fetch_close():
                                trader = BinanceFuturesTrader(use_testnet=False)
                                try:
                                    # Get recent income for this symbol
                                    income = await trader.get_income_history(
                                        symbol=trade.symbol,
                                        income_type='REALIZED_PNL',
                                        limit=10
                                    )
                                    # Get recent trade history
                                    trades = await trader.get_trade_history(
                                        symbol=trade.symbol,
                                        limit=20
                                    )
                                    return income, trades
                                finally:
                                    await trader.close()
                            return loop.run_until_complete(_fetch_close())
                        finally:
                            loop.close()
                    except Exception as e:
                        logger.error(f"Error fetching close data for {trade.symbol}: {e}")
                        return [], []

                income_data, trade_history = fetch_trade_close_data()

                # Sum up realized PnL from recent income
                for inc in income_data:
                    inc_time = int(inc.get('time', 0))
                    trade_time = trade.entry_time.timestamp() * 1000 if trade.entry_time else 0
                    if inc_time > trade_time:
                        realized_pnl += Decimal(str(inc.get('income', 0)))

                # Try to get exit price from recent trades
                if trade_history:
                    # Find the most recent closing trade
                    for t in reversed(trade_history):
                        t_time = int(t.get('time', 0))
                        trade_time = trade.entry_time.timestamp() * 1000 if trade.entry_time else 0
                        if t_time > trade_time:
                            exit_price = Decimal(str(t.get('price', 0)))
                            break

                # Determine close reason based on PnL
                if realized_pnl > 0:
                    close_status = 'CLOSED_TP'
                elif realized_pnl < 0:
                    close_status = 'CLOSED_SL'
                else:
                    close_status = 'CLOSED_MANUAL'

                # Update the trade record
                if exit_price > 0:
                    trade.exit_price = exit_price
                trade.profit_loss = realized_pnl
                if trade.position_size_usdt:
                    trade.profit_loss_percentage = (realized_pnl / trade.position_size_usdt) * 100
                trade.status = close_status
                trade.exit_time = dj_timezone.now()
                trade.save()

                closed_trades.append({
                    'trade_id': trade.id,
                    'symbol': trade.symbol,
                    'direction': trade.direction,
                    'entry_price': str(trade.entry_price),
                    'exit_price': str(exit_price),
                    'realized_pnl': str(realized_pnl),
                    'status': close_status,
                })

                logger.info(
                    f"Trade {trade.id} closed: {trade.symbol} {trade.direction} "
                    f"PnL: {realized_pnl} ({close_status})"
                )

        # Check for positions on Binance that we don't have locally (external trades)
        # Auto-import them into our system for tracking
        external_positions = []
        imported_trades = []
        for symbol, pos in binance_position_map.items():
            external_positions.append({
                'symbol': symbol,
                'direction': pos['direction'],
                'quantity': str(pos['quantity']),
                'entry_price': str(pos['entry_price']),
                'unrealized_pnl': str(pos['unrealized_pnl']),
            })
            logger.info(f"External position found: {pos['direction']} {symbol}")

            # Auto-import external position into local database
            try:
                # Calculate position size in USDT (margin used)
                position_size_usdt = pos['entry_price'] * Decimal(str(pos['quantity'])) / pos['leverage']

                # For external trades, set SL/TP to 0 (unknown)
                # Use liquidation price as a reference for SL if available
                liquidation = pos.get('liquidation_price', Decimal('0'))

                # Calculate unrealized PnL percentage
                unrealized_pnl = pos.get('unrealized_pnl', Decimal('0'))
                unrealized_pnl_pct = (unrealized_pnl / position_size_usdt * 100) if position_size_usdt else Decimal('0')

                new_trade = FuturesTrade.objects.create(
                    signal=None,  # No signal - external trade
                    symbol=symbol,
                    direction=pos['direction'],
                    leverage=pos['leverage'],
                    quantity=Decimal(str(pos['quantity'])),
                    entry_price=pos['entry_price'],
                    entry_time=dj_timezone.now(),  # We don't know exact entry time
                    stop_loss=liquidation if liquidation > 0 else pos['entry_price'] * Decimal('0.95'),  # Default 5% SL
                    take_profit=pos['entry_price'] * Decimal('1.10'),  # Default 10% TP
                    position_size_usdt=position_size_usdt,
                    status='OPEN',
                    # Live data fields
                    mark_price=pos.get('mark_price'),
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_percentage=unrealized_pnl_pct,
                    liquidation_price=liquidation if liquidation > 0 else None,
                    margin_type=pos.get('margin_type', 'ISOLATED').upper(),
                    last_sync_time=dj_timezone.now(),
                    error_message=f"Auto-imported from Binance. Margin type: {pos['margin_type']}"
                )

                imported_trades.append({
                    'trade_id': new_trade.id,
                    'symbol': symbol,
                    'direction': pos['direction'],
                    'quantity': str(pos['quantity']),
                    'entry_price': str(pos['entry_price']),
                })

                logger.info(
                    f"✅ Imported external position: {pos['direction']} {symbol} "
                    f"qty={pos['quantity']} @ {pos['entry_price']}"
                )
            except Exception as e:
                logger.error(f"Failed to import external position {symbol}: {e}")

        cut_loser_closed = [t for t in closed_trades if t.get('reason') == 'cut_loser']

        result = {
            "status": "completed",
            "binance_positions": len(positions),
            "local_open_trades": local_open_trades.count(),
            "updated": len(updated_trades),
            "closed": len(closed_trades),
            "cut_loser_closed": len(cut_loser_closed),
            "external": len(external_positions),
            "imported": len(imported_trades),
            "updated_trades": updated_trades,
            "closed_trades": closed_trades,
            "external_positions": external_positions,
            "imported_trades": imported_trades,
        }

        if cut_loser_closed:
            logger.info(f"✂️ Cut-loser: {len(cut_loser_closed)} trades closed near breakeven")
        if closed_trades:
            logger.info(f"Sync completed: {len(closed_trades)} trades closed")
        if imported_trades:
            logger.info(f"Sync completed: {len(imported_trades)} external positions imported")

        return result

    except Exception as exc:
        logger.error(f"Futures sync error: {exc}")
        raise self.retry(exc=exc, countdown=60)
