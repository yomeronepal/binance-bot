"""WebSocket dispatcher for broadcasting trading signals."""
import asyncio
import logging
from typing import Dict
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings

logger = logging.getLogger(__name__)

# Import Discord notifier
try:
    from .discord_notifier import discord_notifier
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    logger.warning("Discord notifier not available")


class SignalDispatcher:
    """Dispatches trading signals via Django Channels WebSocket."""

    def __init__(self):
        self.channel_layer = get_channel_layer()

    def _is_running_in_async_context(self):
        """Check if we're running in an async context."""
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    def broadcast_signal(self, signal_data: Dict):
        """
        Broadcast signal to all connected WebSocket clients.
        Works in both sync and async contexts.

        Args:
            signal_data: Signal dictionary with keys:
                - symbol: str
                - direction: str ('LONG' or 'SHORT')
                - entry: Decimal
                - sl: Decimal
                - tp: Decimal
                - confidence: float
                - timeframe: str
                - description: str (optional)
        """
        if not self.channel_layer:
            logger.error("Channel layer not configured")
            return

        try:
            # Convert Decimal to float for JSON serialization
            broadcast_data = {
                'symbol': signal_data['symbol'],
                'direction': signal_data['direction'],
                'entry': float(signal_data['entry']),
                'sl': float(signal_data['sl']),
                'tp': float(signal_data['tp']),
                'confidence': float(signal_data['confidence']),
                'timeframe': signal_data['timeframe'],
                'description': signal_data.get('description', ''),
            }

            message = {
                'type': 'signal_created',
                'signal': broadcast_data
            }

            # Check if we're in an async context
            if self._is_running_in_async_context():
                # Schedule the coroutine to run in the event loop
                asyncio.create_task(
                    self.channel_layer.group_send('signals_global', message)
                )
            else:
                # Use async_to_sync for sync contexts
                async_to_sync(self.channel_layer.group_send)(
                    'signals_global',
                    message
                )

            logger.info(
                f"Broadcasted {broadcast_data['direction']} signal for {broadcast_data['symbol']} "
                f"(confidence: {broadcast_data['confidence']:.2%})"
            )

            # Send to Discord if available
            if DISCORD_AVAILABLE and discord_notifier.is_enabled():
                try:
                    discord_notifier.send_signal(signal_data)
                except Exception as discord_error:
                    logger.error(f"Failed to send Discord notification: {discord_error}")

        except Exception as e:
            logger.error(f"Failed to broadcast signal: {e}", exc_info=True)
    
    def broadcast_scanner_status(self, status: str, message: str = ""):
        """
        Broadcast scanner status update.
        Works in both sync and async contexts.

        Args:
            status: Status string ('running', 'stopped', 'error')
            message: Optional status message
        """
        if not self.channel_layer:
            return

        try:
            msg = {
                'type': 'scanner_status',
                'status': status,
                'message': message
            }

            # Check if we're in an async context
            if self._is_running_in_async_context():
                # Schedule the coroutine to run in the event loop
                asyncio.create_task(
                    self.channel_layer.group_send('signals_global', msg)
                )
            else:
                # Use async_to_sync for sync contexts
                async_to_sync(self.channel_layer.group_send)(
                    'signals_global',
                    msg
                )

            logger.debug(f"Broadcasted scanner status: {status}")
        except Exception as e:
            logger.error(f"Failed to broadcast status: {e}")


# Global dispatcher instance
signal_dispatcher = SignalDispatcher()
