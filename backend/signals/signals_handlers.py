"""
Django signal handlers for automatic real-time broadcasting and auto-trading.
These handlers trigger WebSocket broadcasts when Signal model instances change,
and automatically execute paper trades when new signals are created.
"""
import logging
from datetime import datetime, timezone, timedelta
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import Signal, TradingSession
from .services.realtime import realtime_signal_service

logger = logging.getLogger(__name__)

NEPAL_TZ_OFFSET = timedelta(hours=5, minutes=45)


def _store_fg_in_meta(signal):
    """Store current Fear & Greed value in signal meta at creation time."""
    try:
        from .services.fear_greed import get_fear_greed_value
        fg = get_fear_greed_value()
        if fg is not None:
            if not signal.meta:
                signal.meta = {}
            signal.meta['fg_value'] = fg
            signal.save(update_fields=['meta'])
    except Exception as e:
        logger.warning(f"Failed to store F&G in signal {signal.id}: {e}")


def _get_nepal_now():
    """Get current Nepal Time datetime."""
    return datetime.now(timezone.utc) + NEPAL_TZ_OFFSET


def is_within_trading_window():
    """
    Check if current Nepal Time is within any active TradingSession.
    Reads from database (auto-updated by optimizer).
    """
    nepal_now = _get_nepal_now()
    session = TradingSession.get_matching_session(nepal_now)
    return session is not None


def get_nepal_time_str():
    """Get current Nepal time as formatted string."""
    return _get_nepal_now().strftime("%H:%M NPT")


# ============================================================================
# Paper Trade Signal Handlers (for optimization tracking)
# ============================================================================

@receiver(post_save, sender='signals.PaperTrade')
def track_closed_paper_trade(sender, instance, created, **kwargs):
    """
    Track closed paper trades and increment trade counter for optimization.

    When a paper trade closes (status changes to CLOSED), increment the trade
    counter for its volatility level. When threshold is reached, trigger optimization.

    Args:
        sender: PaperTrade model class
        instance: PaperTrade instance that was saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    # Skip if this is a new trade (not closed yet)
    if created:
        return

    # Only track CLOSED trades
    if instance.status != 'CLOSED':
        return

    # Skip if we already counted this trade
    if hasattr(instance, '_already_counted_for_optimization'):
        return

    try:
        from .services.optimizer_service import TradeCounterService
        from .tasks_optimization import auto_optimize_strategy

        # Determine volatility level based on symbol
        volatility_level = _determine_volatility_from_symbol(instance.symbol)

        # Increment counter and check if optimization should trigger
        should_optimize = TradeCounterService.increment_and_check(volatility_level)

        # Mark as counted to avoid double counting
        instance._already_counted_for_optimization = True

        if should_optimize:
            logger.info(f"🎯 Trade threshold reached! Triggering optimization for {volatility_level}")

            # Trigger optimization asynchronously
            auto_optimize_strategy.delay(
                volatility_level=volatility_level,
                lookback_days=30,
                trigger='TRADE_COUNT'
            )

    except Exception as e:
        logger.error(f"Error tracking closed paper trade: {str(e)}", exc_info=True)


def _determine_volatility_from_symbol(symbol):
    """Determine volatility level from trading symbol"""
    high_vol = {'DOGEUSDT', 'SHIBUSDT', 'PEPEUSDT', 'FLOKIUSDT', 'WIFUSDT', 'BONKUSDT'}
    low_vol = {'BTCUSDT', 'ETHUSDT', 'BNBUSDT'}

    if symbol in high_vol:
        return 'HIGH'
    elif symbol in low_vol:
        return 'LOW'
    else:
        return 'MEDIUM'


# ============================================================================
# Signal Handlers (existing)
# ============================================================================


def _send_push_for_signal(signal):
    """
    Send a Firebase push notification for every new signal.

    Args:
        signal: Signal model instance.
    """
    try:
        from signals.services.push_notification import send_signal_notification
        result = send_signal_notification(signal)
        if result['total'] > 0:
            logger.info(
                "Push notification for signal %s (priority=%s): %d/%d sent",
                signal.id, getattr(signal, 'is_priority', False),
                result['sent'], result['total']
            )
    except Exception as e:
        logger.error("Push notification failed for signal %s: %s", signal.id, e)


@receiver(post_save, sender=Signal)
def signal_post_save_handler(sender, instance, created, **kwargs):
    """
    Handler triggered after a Signal is saved (created or updated).

    Args:
        sender: The Signal model class
        instance: The actual Signal instance
        created: Boolean indicating if this is a new instance
        kwargs: Additional keyword arguments
    """
    try:
        if created:
            _store_fg_in_meta(instance)
            logger.info(f"Signal created: {instance.id} - Broadcasting...")
            realtime_signal_service.broadcast_signal_created(instance)
            _send_push_for_signal(instance)
        else:
            # Existing signal updated
            logger.info(f"Signal updated: {instance.id} - Broadcasting...")

            # Get updated fields if available (Django 3.2+)
            updated_fields = kwargs.get('update_fields')
            realtime_signal_service.broadcast_signal_updated(
                instance,
                updated_fields=list(updated_fields) if updated_fields else None
            )

    except Exception as e:
        logger.error(f"Error in signal_post_save_handler: {str(e)}", exc_info=True)


def _flag_top_performer_priority(instance):
    """
    Mark a *new* FUTURES Signal as ``is_priority=True`` if its symbol is
    in the most recent ``TopPerformingSymbol`` snapshot.

    Pre-save (not post-save) so the flag is already True when the
    existing ``execute_futures_trade_on_signal`` post-save handler runs
    — that handler reads ``instance.is_priority`` to bypass the trading
    window and force-execute the futures trade. Net effect: top-performer
    symbols auto-trade regardless of trading window.

    Only fires for new rows (``instance.pk is None``) and never flips a
    priority flag *off* — if a Signal was already marked priority by
    another path (e.g., generated during a Golden Window), we leave it.
    """
    if instance.pk is not None:
        return  # Existing row: leave is_priority alone.
    if getattr(instance, 'market_type', None) != 'FUTURES':
        return  # Spot signals don't auto-trade futures.
    if getattr(instance, 'is_priority', False):
        return  # Already flagged; nothing to do.

    try:
        symbol = getattr(getattr(instance, 'symbol', None), 'symbol', None)
        if not symbol:
            return
        from .services.top_performers_calculator import is_top_performer
        if is_top_performer(symbol):
            instance.is_priority = True
            instance._priority_reason = 'top_performer'
            logger.info(
                "Signal pre-save: %s flagged is_priority=True (top performer); "
                "futures auto-trade will fire post-save.",
                symbol,
            )
    except Exception as exc:
        # Never block signal creation on a top-performer lookup failure.
        logger.warning(
            "Top-performer pre-save check failed for symbol %s: %s",
            getattr(getattr(instance, 'symbol', None), 'symbol', '?'), exc,
        )


@receiver(pre_save, sender=Signal)
def signal_pre_save_handler(sender, instance, **kwargs):
    """
    Handler triggered before a Signal is saved.
    Used to detect status changes and flag top-performer signals as
    priority so the futures auto-trader picks them up.

    Args:
        sender: The Signal model class
        instance: The actual Signal instance being saved
        kwargs: Additional keyword arguments
    """
    try:
        # New-row hook: flip is_priority for top-performer FUTURES signals
        # *before* the post-save futures-trade receiver fires.
        _flag_top_performer_priority(instance)

        # Only check for status changes on existing instances
        if instance.pk:
            try:
                old_instance = Signal.objects.get(pk=instance.pk)

                # Check if status has changed
                if old_instance.status != instance.status:
                    # Store old status for post_save handler
                    instance._old_status = old_instance.status
                    instance._status_changed = True
                else:
                    instance._status_changed = False

            except Signal.DoesNotExist:
                # Instance doesn't exist yet (shouldn't happen with pk set)
                pass

    except Exception as e:
        logger.error(f"Error in signal_pre_save_handler: {str(e)}", exc_info=True)


@receiver(post_save, sender=Signal)
def signal_status_change_handler(sender, instance, created, **kwargs):
    """
    Handler for broadcasting signal status changes.
    Works in conjunction with pre_save handler.

    Args:
        sender: The Signal model class
        instance: The actual Signal instance
        created: Boolean indicating if this is a new instance
        kwargs: Additional keyword arguments
    """
    try:
        # Only process status changes for existing signals
        if not created and hasattr(instance, '_status_changed') and instance._status_changed:
            old_status = getattr(instance, '_old_status', 'UNKNOWN')

            logger.info(
                f"Signal {instance.id} status changed: {old_status} -> {instance.status}"
            )

            realtime_signal_service.broadcast_signal_status_changed(
                instance,
                old_status=old_status,
                new_status=instance.status
            )

            # Clean up temporary attributes
            delattr(instance, '_old_status')
            delattr(instance, '_status_changed')

    except Exception as e:
        logger.error(f"Error in signal_status_change_handler: {str(e)}", exc_info=True)


@receiver(post_delete, sender=Signal)
def signal_post_delete_handler(sender, instance, **kwargs):
    """
    Handler triggered after a Signal is deleted.

    Args:
        sender: The Signal model class
        instance: The deleted Signal instance
        kwargs: Additional keyword arguments
    """
    try:
        logger.info(f"Signal deleted: {instance.id} - Broadcasting...")

        realtime_signal_service.broadcast_signal_deleted(
            signal_id=instance.id,
            symbol=instance.symbol.symbol
        )

    except Exception as e:
        logger.error(f"Error in signal_post_delete_handler: {str(e)}", exc_info=True)


@receiver(post_save, sender=Signal)
def auto_execute_trade_on_signal(sender, instance, created, **kwargs):
    """
    Automatically execute a paper trade when a new FUTURES signal is created.

    This handler integrates with the PaperAccount auto-trading system:
    - Only executes on new FUTURES signals (created=True)
    - Only executes if signal is ACTIVE
    - Skips blacklisted symbols
    - Checks all PaperAccounts with auto_trading_enabled=True
    - Prevents duplicate trades (same symbol + direction)
    - Respects account risk management settings

    Args:
        sender: Signal model class
        instance: Signal instance that was saved
        created: Boolean indicating if this is a new signal
        **kwargs: Additional keyword arguments
    """
    if not created:
        return

    if instance.status != 'ACTIVE':
        logger.debug(f"Signal {instance.id} not ACTIVE (status={instance.status}), skipping auto-trade")
        return

    if instance.market_type != 'FUTURES':
        logger.debug(f"Signal {instance.id} is {instance.market_type}, skipping auto-trade (FUTURES only)")
        return

    # Check if symbol is blacklisted
    from .models_blacklist import BlacklistedSymbol
    if BlacklistedSymbol.is_blacklisted(instance.symbol.symbol):
        logger.info(f"📛 Signal {instance.id} ({instance.symbol.symbol}) is blacklisted, skipping auto-trade")
        return

    if not is_within_trading_window():
        logger.debug(f"Signal {instance.id} outside trading window, skipping auto-trade")
        return

    try:
        from .services.auto_trader import auto_trading_service

        trade = auto_trading_service.execute_signal(instance)

        if trade:
            logger.info(
                f"✅ Auto-trade executed: {trade.direction} {trade.symbol} "
                f"@ {trade.entry_price} (Trade ID: {trade.id}, Signal ID: {instance.id})"
            )
        else:
            logger.debug(
                f"ℹ️  No auto-trade for signal {instance.id}: "
                f"criteria not met or no accounts enabled"
            )

    except ValueError as e:
        # Duplicate trade - expected during signal upgrades
        logger.info(f"ℹ️  Skipping auto-trade for signal {instance.id}: {e}")

    except Exception as e:
        logger.error(
            f"❌ Failed to auto-execute trade for signal {instance.id}: {e}",
            exc_info=True
        )


@receiver(post_save, sender=Signal)
def create_system_paper_trade(sender, instance, created, **kwargs):
    """
    Automatically create a SYSTEM-WIDE paper trade for FUTURES signals only.

    This is different from user auto-trading - this creates a public paper trade
    to track the bot's overall accuracy and performance that everyone can see.

    - Creates paper trade with user=None (system-wide)
    - Fixed position size of $100 per trade
    - Only executes on new ACTIVE FUTURES signals
    - Skips blacklisted symbols
    - Only executes within trading windows (Nepal Time):
      - 16:00-17:00 NPT
      - 21:00-23:00 NPT
    - Results displayed on public dashboard
    - Prevents duplicate trades for same symbol+direction

    Args:
        sender: Signal model class
        instance: Signal instance that was saved
        created: Boolean indicating if this is a new signal
        **kwargs: Additional keyword arguments
    """
    if not created:
        return

    if instance.status != 'ACTIVE':
        logger.debug(f"Signal {instance.id} not ACTIVE, skipping system paper trade")
        return

    if instance.market_type != 'FUTURES':
        logger.debug(f"Signal {instance.id} is {instance.market_type}, skipping (FUTURES only)")
        return

    # Check if symbol is blacklisted
    from .models_blacklist import BlacklistedSymbol
    if BlacklistedSymbol.is_blacklisted(instance.symbol.symbol):
        logger.info(f"📛 Signal {instance.id} ({instance.symbol.symbol}) is blacklisted, skipping system paper trade")
        return

    # Removed trading window restriction to allow all trades to be recorded
    # Golden Window trades are marked via is_priority flag in the model
    # if not is_within_trading_window():
    #     current_time = get_nepal_time_str()
    #     logger.info(
    #         f"⏰ Signal {instance.id} ({instance.symbol.symbol}) outside trading window "
    #         f"(current: {current_time}). Windows: 16:00-17:00 & 21:00-23:00 NPT"
    #     )
    #     return

    try:
        from .services.paper_trader import paper_trading_service

        trade = paper_trading_service.create_paper_trade(
            signal=instance,
            user=None,
            position_size=100.0
        )

        current_time = get_nepal_time_str()
        logger.info(
            f"🤖 System paper trade created at {current_time}: {trade.direction} {trade.symbol} "
            f"@ {trade.entry_price} (Trade ID: {trade.id}, Signal ID: {instance.id})"
        )

    except ValueError as e:
        logger.info(f"ℹ️  Skipping paper trade for signal {instance.id}: {e}")

    except Exception as e:
        logger.error(
            f"❌ Failed to create system paper trade for signal {instance.id}: {e}",
            exc_info=True
        )


@receiver(post_save, sender=Signal)
def execute_futures_trade_on_signal(sender, instance, created, **kwargs):
    """
    Execute a real futures trade on Binance when a new signal is created.

    Uses a Redis-backed distributed lock so duplicate handler fires across
    multiple Celery workers / API processes cannot open two positions for
    the same Signal.

    Args:
        sender: Signal model class
        instance: Signal instance that was saved
        created: Boolean indicating if this is a new signal
        **kwargs: Additional keyword arguments
    """
    if not created:
        return

    if instance.status != 'ACTIVE':
        return

    if instance.market_type != 'FUTURES':
        logger.debug(f"Signal {instance.id} is {instance.market_type}, skipping futures trade (FUTURES only)")
        return

    from .services.distributed_lock import signal_execution_lock

    with signal_execution_lock(instance.id) as acquired:
        if not acquired:
            logger.info(
                f"Signal {instance.id} already being processed by another worker, "
                "skipping duplicate futures execution"
            )
            return
        _execute_futures_trade(instance)


def _execute_futures_trade(instance):
    """
    Run the trading-window / blacklist checks and dispatch to the trader.

    Extracted from the post_save handler so the lock context stays narrow
    and the trade logic is testable without going through Django signals.

    Args:
        instance: Signal instance to execute.
    """
    try:
        in_window = is_within_trading_window()
        current_time = get_nepal_time_str()
        is_neutral_signal = bool(
            isinstance(getattr(instance, 'meta', None), dict) and
            instance.meta.get('neutral_reversal')
        )

        logger.info(
            f"Signal {instance.id} ({instance.symbol.symbol}): "
            f"is_priority={instance.is_priority}, in_window={in_window}, "
            f"is_neutral={is_neutral_signal}, time={current_time}"
        )

        if not instance.is_priority and not in_window:
            logger.info(
                f"Signal {instance.id} ({instance.symbol.symbol}) outside trading window "
                f"at {current_time} and not priority, skipping futures trade"
            )
            return

        from .models_blacklist import BlacklistedSymbol
        if BlacklistedSymbol.is_blacklisted(instance.symbol.symbol):
            logger.warning(f"Signal {instance.id} ({instance.symbol.symbol}) blacklisted, blocking futures trade")
            return

        from .services.futures_trader import futures_trading_service

        logger.info(
            f"Calling futures_trading_service.execute_signal for signal {instance.id} "
            f"({instance.symbol.symbol} {instance.direction}), "
            f"force_execute={instance.is_priority}, is_neutral={is_neutral_signal}"
        )

        trade = futures_trading_service.execute_signal(
            instance, force_execute=instance.is_priority
        )

        if trade:
            logger.info(
                f"REAL Futures trade executed at {current_time}: "
                f"{trade.direction} {trade.quantity} {trade.symbol} @ {trade.entry_price} "
                f"(Leverage: {trade.leverage}x, Trade ID: {trade.id}, Signal ID: {instance.id})"
            )
        else:
            logger.warning(
                f"Futures trade NOT created for signal {instance.id} ({instance.symbol.symbol}). "
                f"execute_signal returned None. Check service logs for reason."
            )

    except Exception as e:
        logger.error(
            f"Failed to execute futures trade for signal {instance.id}: {e}",
            exc_info=True,
        )
