"""
Django signal handlers for automatic real-time broadcasting.
These handlers trigger WebSocket broadcasts when Signal model instances change.
"""
import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import Signal
from .services.realtime import realtime_signal_service

logger = logging.getLogger(__name__)


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
