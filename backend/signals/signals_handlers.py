"""
Django signal handlers for automatic real-time broadcasting and auto-trading.
These handlers trigger WebSocket broadcasts when Signal model instances change,
and automatically execute paper trades when new signals are created.
"""
import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import Signal
from .services.realtime import realtime_signal_service

logger = logging.getLogger(__name__)


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
            # New signal created
            logger.info(f"Signal created: {instance.id} - Broadcasting...")
            realtime_signal_service.broadcast_signal_created(instance)
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


@receiver(pre_save, sender=Signal)
def signal_pre_save_handler(sender, instance, **kwargs):
    """
    Handler triggered before a Signal is saved.
    Used to detect status changes.

    Args:
        sender: The Signal model class
        instance: The actual Signal instance being saved
        kwargs: Additional keyword arguments
    """
    try:
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
    Automatically execute a paper trade when a new signal is created.

    This handler integrates with the PaperAccount auto-trading system:
    - Only executes on new signals (created=True)
    - Only executes if signal is ACTIVE
    - Checks all PaperAccounts with auto_trading_enabled=True
    - Prevents duplicate trades (same symbol + direction)
    - Respects account risk management settings

    Args:
        sender: Signal model class
        instance: Signal instance that was saved
        created: Boolean indicating if this is a new signal
        **kwargs: Additional keyword arguments
    """
    # Only execute on new signals, not updates
    if not created:
        return

    # Only execute if signal is ACTIVE
    if instance.status != 'ACTIVE':
        logger.debug(f"Signal {instance.id} not ACTIVE (status={instance.status}), skipping auto-trade")
        return

    try:
        # Import here to avoid circular imports
        from .services.auto_trader import auto_trading_service

        # Execute trade via auto-trading service
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

    except Exception as e:
        logger.error(
            f"❌ Failed to auto-execute trade for signal {instance.id}: {e}",
            exc_info=True
        )


@receiver(post_save, sender=Signal)
def create_system_paper_trade(sender, instance, created, **kwargs):
    """
    Automatically create a SYSTEM-WIDE paper trade for every signal.

    This is different from user auto-trading - this creates a public paper trade
    to track the bot's overall accuracy and performance that everyone can see.

    - Creates paper trade with user=None (system-wide)
    - Fixed position size of $100 per trade
    - Only executes on new ACTIVE signals
    - Results displayed on public dashboard

    Args:
        sender: Signal model class
        instance: Signal instance that was saved
        created: Boolean indicating if this is a new signal
        **kwargs: Additional keyword arguments
    """
    # Only execute on new signals
    if not created:
        return

    # Only execute if signal is ACTIVE
    if instance.status != 'ACTIVE':
        logger.debug(f"Signal {instance.id} not ACTIVE, skipping system paper trade")
        return

    try:
        # Import here to avoid circular imports
        from .services.paper_trader import paper_trading_service

        # Create system-wide paper trade (user=None)
        trade = paper_trading_service.create_paper_trade(
            signal=instance,
            user=None,  # System-wide trade
            position_size=100.0  # Fixed $100 per trade
        )

        logger.info(
            f"🤖 System paper trade created: {trade.direction} {trade.symbol} "
            f"@ {trade.entry_price} (Trade ID: {trade.id}, Signal ID: {instance.id})"
        )

    except Exception as e:
        logger.error(
            f"❌ Failed to create system paper trade for signal {instance.id}: {e}",
            exc_info=True
        )
