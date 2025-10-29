"""
Real-time broadcasting service for signal updates.
Uses Django Channels' channel layer to broadcast to WebSocket consumers.
"""
import logging
from typing import Optional, Dict, Any
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.serializers.json import DjangoJSONEncoder
import json

from ..models import Signal
from ..serializers import SignalSerializer

logger = logging.getLogger(__name__)


class RealtimeSignalService:
    """
    Service for broadcasting signal updates in real-time via WebSocket.

    Uses Django Channels' channel layer to send messages to consumer groups.
    """

    def __init__(self):
        self.channel_layer = get_channel_layer()

    def broadcast_signal_created(self, signal: Signal):
        """
        Broadcast new signal creation to all connected clients.

        Args:
            signal: The newly created Signal instance
        """
        try:
            serializer = SignalSerializer(signal)
            signal_data = serializer.data

            # Broadcast to global signals group
            async_to_sync(self.channel_layer.group_send)(
                'signals_global',
                {
                    'type': 'signal_created',
                    'signal': signal_data
                }
            )

            # Broadcast to symbol-specific group if needed
            symbol_group = f'signals_symbol_{signal.symbol.symbol}'
            async_to_sync(self.channel_layer.group_send)(
                symbol_group,
                {
                    'type': 'signal_created',
                    'signal': signal_data
                }
            )

            # Update analytics
            self._broadcast_analytics_update()

            logger.info(f"Broadcasted signal created: {signal.id} ({signal.symbol.symbol})")

        except Exception as e:
            logger.error(f"Error broadcasting signal created: {str(e)}", exc_info=True)

    def broadcast_signal_updated(self, signal: Signal, updated_fields: Optional[list] = None):
        """
        Broadcast signal update to all connected clients.

        Args:
            signal: The updated Signal instance
            updated_fields: List of field names that were updated (optional)
        """
        try:
            serializer = SignalSerializer(signal)
            signal_data = serializer.data

            if updated_fields:
                signal_data['updated_fields'] = updated_fields

            # Broadcast to global signals group
            async_to_sync(self.channel_layer.group_send)(
                'signals_global',
                {
                    'type': 'signal_updated',
                    'signal': signal_data
                }
            )

            # Broadcast to symbol-specific group
            symbol_group = f'signals_symbol_{signal.symbol.symbol}'
            async_to_sync(self.channel_layer.group_send)(
                symbol_group,
                {
                    'type': 'signal_updated',
                    'signal': signal_data
                }
            )

            logger.info(f"Broadcasted signal updated: {signal.id}")

        except Exception as e:
            logger.error(f"Error broadcasting signal updated: {str(e)}", exc_info=True)

    def broadcast_signal_deleted(self, signal_id: int, symbol: str):
        """
        Broadcast signal deletion to all connected clients.

        Args:
            signal_id: The ID of the deleted signal
            symbol: The symbol of the deleted signal
        """
        try:
            # Broadcast to global signals group
            async_to_sync(self.channel_layer.group_send)(
                'signals_global',
                {
                    'type': 'signal_deleted',
                    'signal_id': signal_id
                }
            )

            # Broadcast to symbol-specific group
            symbol_group = f'signals_symbol_{symbol}'
            async_to_sync(self.channel_layer.group_send)(
                symbol_group,
                {
                    'type': 'signal_deleted',
                    'signal_id': signal_id
                }
            )

            # Update analytics
            self._broadcast_analytics_update()

            logger.info(f"Broadcasted signal deleted: {signal_id}")

        except Exception as e:
            logger.error(f"Error broadcasting signal deleted: {str(e)}", exc_info=True)

    def broadcast_signal_status_changed(
        self,
        signal: Signal,
        old_status: str,
        new_status: str
    ):
        """
        Broadcast signal status change to all connected clients.

        Args:
            signal: The Signal instance
            old_status: Previous status
            new_status: New status
        """
        try:
            serializer = SignalSerializer(signal)
            signal_data = serializer.data

            # Broadcast to global signals group
            async_to_sync(self.channel_layer.group_send)(
                'signals_global',
                {
                    'type': 'signal_status_changed',
                    'signal': signal_data,
                    'old_status': old_status,
                    'new_status': new_status
                }
            )

            # Broadcast to symbol-specific group
            symbol_group = f'signals_symbol_{signal.symbol.symbol}'
            async_to_sync(self.channel_layer.group_send)(
                symbol_group,
                {
                    'type': 'signal_status_changed',
                    'signal': signal_data,
                    'old_status': old_status,
                    'new_status': new_status
                }
            )

            # Update analytics
            self._broadcast_analytics_update()

            logger.info(f"Broadcasted status change: {signal.id} ({old_status} -> {new_status})")

        except Exception as e:
            logger.error(f"Error broadcasting status change: {str(e)}", exc_info=True)

    def broadcast_user_specific_signal(self, user_id: int, signal: Signal, message: str):
        """
        Send signal update to a specific user.

        Args:
            user_id: The target user ID
            signal: The Signal instance
            message: Custom message for the user
        """
        try:
            serializer = SignalSerializer(signal)
            signal_data = serializer.data
            signal_data['message'] = message

            # Broadcast to user-specific group
            user_group = f'signals_user_{user_id}'
            async_to_sync(self.channel_layer.group_send)(
                user_group,
                {
                    'type': 'signal_created',
                    'signal': signal_data
                }
            )

            logger.info(f"Broadcasted signal to user {user_id}: {signal.id}")

        except Exception as e:
            logger.error(f"Error broadcasting to user {user_id}: {str(e)}", exc_info=True)

    def _broadcast_analytics_update(self):
        """
        Broadcast updated analytics to all connected analytics clients.
        """
        try:
            from ..repositories import signal_repository

            stats = signal_repository.get_signal_statistics()

            async_to_sync(self.channel_layer.group_send)(
                'signal_analytics',
                {
                    'type': 'analytics_update',
                    'data': stats
                }
            )

        except Exception as e:
            logger.error(f"Error broadcasting analytics: {str(e)}", exc_info=True)

    def broadcast_bulk_update(self, signals: list, action: str):
        """
        Broadcast bulk signal update.

        Args:
            signals: List of Signal instances
            action: Action performed (e.g., 'status_update', 'deletion')
        """
        try:
            signal_ids = [signal.id for signal in signals]

            async_to_sync(self.channel_layer.group_send)(
                'signals_global',
                {
                    'type': 'bulk_update',
                    'signal_ids': signal_ids,
                    'action': action,
                    'count': len(signal_ids)
                }
            )

            logger.info(f"Broadcasted bulk {action} for {len(signal_ids)} signals")

        except Exception as e:
            logger.error(f"Error broadcasting bulk update: {str(e)}", exc_info=True)


class RealtimeNotificationService:
    """
    Service for sending real-time notifications to users.
    """

    def __init__(self):
        self.channel_layer = get_channel_layer()

    def notify_user(
        self,
        user_id: int,
        notification_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """
        Send notification to a specific user.

        Args:
            user_id: Target user ID
            notification_type: Type of notification (e.g., 'signal_alert', 'system')
            message: Notification message
            data: Additional data (optional)
        """
        try:
            user_group = f'signals_user_{user_id}'

            async_to_sync(self.channel_layer.group_send)(
                user_group,
                {
                    'type': 'notification',
                    'notification_type': notification_type,
                    'message': message,
                    'data': data or {}
                }
            )

            logger.info(f"Sent notification to user {user_id}: {notification_type}")

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}", exc_info=True)

    def broadcast_system_message(self, message: str, level: str = 'info'):
        """
        Broadcast system-wide message to all connected clients.

        Args:
            message: System message
            level: Message level (info, warning, error)
        """
        try:
            async_to_sync(self.channel_layer.group_send)(
                'signals_global',
                {
                    'type': 'system_message',
                    'message': message,
                    'level': level
                }
            )

            logger.info(f"Broadcasted system message: {message}")

        except Exception as e:
            logger.error(f"Error broadcasting system message: {str(e)}", exc_info=True)


# Singleton instances
realtime_signal_service = RealtimeSignalService()
realtime_notification_service = RealtimeNotificationService()
