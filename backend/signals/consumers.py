"""
WebSocket consumers for real-time signal updates.
Uses Django Channels with AsyncWebsocketConsumer for performance.
"""
import json
import logging
from typing import Dict, Any
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from .repositories import signal_repository, subscription_repository
from .serializers import SignalSerializer

logger = logging.getLogger(__name__)


class SignalsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time trading signal updates.

    Features:
    - Authentication check on connect
    - Subscribe to personal and global signal channels
    - Real-time signal broadcasts (create, update, delete)
    - Subscription tier-based filtering
    - Heartbeat/ping-pong support
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.subscription = None
        self.room_group_name = 'signals_global'
        self.personal_group_name = None

    async def connect(self):
        """
        Handle WebSocket connection.
        - Authenticate user
        - Join appropriate channel groups
        - Send welcome message
        """
        # Get user from scope (set by AuthMiddlewareStack)
        self.user = self.scope.get('user')

        # Check authentication
        if not self.user or isinstance(self.user, AnonymousUser):
            logger.warning("Unauthenticated WebSocket connection attempt")
            await self.close(code=4001)  # Custom code for authentication failure
            return

        # Get user subscription for tier-based filtering
        self.subscription = await self.get_user_subscription()

        # Personal channel for user-specific signals
        self.personal_group_name = f'signals_user_{self.user.id}'

        # Accept connection
        await self.accept()

        # Join global signals channel
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Join personal signals channel
        await self.channel_layer.group_add(
            self.personal_group_name,
            self.channel_name
        )

        logger.info(f"User {self.user.username} connected to signals WebSocket")

        # Send welcome message with connection info
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to signals stream',
            'user': self.user.username,
            'subscription_tier': self.subscription.tier if self.subscription else 'free',
            'timestamp': self._get_timestamp()
        }))

        # Send current active signals on connection
        await self.send_active_signals()

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.
        - Leave all channel groups
        - Log disconnect
        """
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

        if hasattr(self, 'personal_group_name') and self.personal_group_name:
            await self.channel_layer.group_discard(
                self.personal_group_name,
                self.channel_name
            )

        logger.info(f"User {self.user.username if self.user else 'Unknown'} disconnected (code: {close_code})")

    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages from client.

        Supported message types:
        - ping: Heartbeat check
        - subscribe: Subscribe to specific signals
        - unsubscribe: Unsubscribe from signals
        - get_signal: Request specific signal details
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'ping':
                await self.send_pong()

            elif message_type == 'subscribe':
                await self.handle_subscribe(data)

            elif message_type == 'unsubscribe':
                await self.handle_unsubscribe(data)

            elif message_type == 'get_signal':
                await self.handle_get_signal(data)

            else:
                await self.send_error(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)
            await self.send_error("Internal server error")

    # ==================== Signal Broadcasting Methods ====================

    async def signal_created(self, event):
        """
        Handle signal_created event from channel layer.
        Broadcast new signal to connected clients.
        """
        signal_data = event['signal']

        # Apply subscription tier filtering
        if await self.should_send_signal(signal_data):
            await self.send(text_data=json.dumps({
                'type': 'signal_created',
                'signal': signal_data,
                'timestamp': self._get_timestamp()
            }))

    async def signal_updated(self, event):
        """
        Handle signal_updated event from channel layer.
        Broadcast signal update to connected clients.
        """
        signal_data = event['signal']

        if await self.should_send_signal(signal_data):
            await self.send(text_data=json.dumps({
                'type': 'signal_updated',
                'signal': signal_data,
                'timestamp': self._get_timestamp()
            }))

    async def signal_deleted(self, event):
        """
        Handle signal_deleted event from channel layer.
        Notify clients about signal deletion.
        """
        signal_id = event['signal_id']

        await self.send(text_data=json.dumps({
            'type': 'signal_deleted',
            'signal_id': signal_id,
            'timestamp': self._get_timestamp()
        }))

    async def signal_status_changed(self, event):
        """
        Handle signal status change (ACTIVE -> EXECUTED/EXPIRED/CANCELLED).
        """
        signal_data = event['signal']
        old_status = event.get('old_status')
        new_status = event.get('new_status')

        await self.send(text_data=json.dumps({
            'type': 'signal_status_changed',
            'signal': signal_data,
            'old_status': old_status,
            'new_status': new_status,
            'timestamp': self._get_timestamp()
        }))

    # ==================== Client Message Handlers ====================

    async def handle_subscribe(self, data):
        """
        Handle subscription to specific signal types or symbols.
        """
        filters = data.get('filters', {})
        symbol = filters.get('symbol')
        direction = filters.get('direction')

        # Store subscription preferences (could be in Redis/DB for persistence)
        # For now, just acknowledge
        await self.send(text_data=json.dumps({
            'type': 'subscribed',
            'filters': filters,
            'message': f'Subscribed to signals with filters: {filters}',
            'timestamp': self._get_timestamp()
        }))

    async def handle_unsubscribe(self, data):
        """
        Handle unsubscription from specific signal types.
        """
        await self.send(text_data=json.dumps({
            'type': 'unsubscribed',
            'message': 'Unsubscribed from signal updates',
            'timestamp': self._get_timestamp()
        }))

    async def handle_get_signal(self, data):
        """
        Request specific signal details by ID.
        """
        signal_id = data.get('signal_id')

        if not signal_id:
            await self.send_error("signal_id is required")
            return

        signal = await self.get_signal_by_id(signal_id)

        if signal:
            serializer = SignalSerializer(signal)
            await self.send(text_data=json.dumps({
                'type': 'signal_details',
                'signal': serializer.data,
                'timestamp': self._get_timestamp()
            }))
        else:
            await self.send_error(f"Signal {signal_id} not found")

    async def send_pong(self):
        """
        Respond to ping with pong (heartbeat).
        """
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': self._get_timestamp()
        }))

    async def send_error(self, message: str):
        """
        Send error message to client.
        """
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': self._get_timestamp()
        }))

    async def send_active_signals(self):
        """
        Send list of current active signals on connection.
        Respects user's subscription tier limits.
        """
        signals = await self.get_active_signals_for_user()

        await self.send(text_data=json.dumps({
            'type': 'active_signals',
            'signals': signals,
            'count': len(signals),
            'timestamp': self._get_timestamp()
        }))

    # ==================== Helper Methods ====================

    async def should_send_signal(self, signal_data: Dict[str, Any]) -> bool:
        """
        Determine if signal should be sent to this user based on subscription tier.

        Free users: Only high-confidence signals (>= 0.7)
        Pro users: All signals
        Premium users: All signals + advanced metadata
        """
        if not self.subscription:
            return signal_data.get('confidence', 0) >= 0.7

        tier = self.subscription.tier

        if tier == 'free':
            return signal_data.get('confidence', 0) >= 0.7
        elif tier in ['pro', 'premium']:
            return True

        return False

    @database_sync_to_async
    def get_user_subscription(self):
        """
        Get user's subscription from database.
        """
        return subscription_repository.get_by_user(self.user.id)

    @database_sync_to_async
    def get_signal_by_id(self, signal_id: int):
        """
        Get signal by ID from database.
        """
        return signal_repository.get_by_id(signal_id)

    @database_sync_to_async
    def get_active_signals_for_user(self):
        """
        Get active signals appropriate for user's subscription tier.
        """
        from .services import SignalManagementService

        signals = SignalManagementService.get_active_signals_for_user(self.user)
        serializer = SignalSerializer(signals, many=True)
        return serializer.data

    @staticmethod
    def _get_timestamp():
        """
        Get current timestamp in ISO format.
        """
        from django.utils import timezone
        return timezone.now().isoformat()


class SignalAnalyticsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time analytics and statistics.

    Broadcasts:
    - Signal statistics updates
    - Performance metrics
    - Top symbols
    """

    async def connect(self):
        """Connect to analytics stream."""
        self.user = self.scope.get('user')

        if not self.user or isinstance(self.user, AnonymousUser):
            await self.close(code=4001)
            return

        self.room_group_name = 'signal_analytics'

        await self.accept()

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        logger.info(f"User {self.user.username} connected to analytics WebSocket")

        # Send initial statistics
        await self.send_statistics()

    async def disconnect(self, close_code):
        """Disconnect from analytics stream."""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Handle incoming messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': SignalsConsumer._get_timestamp()
                }))
            elif message_type == 'refresh_stats':
                await self.send_statistics()

        except Exception as e:
            logger.error(f"Error in analytics consumer: {str(e)}")

    async def analytics_update(self, event):
        """
        Handle analytics update event from channel layer.
        """
        analytics_data = event['data']

        await self.send(text_data=json.dumps({
            'type': 'analytics_update',
            'data': analytics_data,
            'timestamp': SignalsConsumer._get_timestamp()
        }))

    async def send_statistics(self):
        """
        Send current statistics to client.
        """
        stats = await self.get_statistics()

        await self.send(text_data=json.dumps({
            'type': 'statistics',
            'data': stats,
            'timestamp': SignalsConsumer._get_timestamp()
        }))

    @database_sync_to_async
    def get_statistics(self):
        """
        Get signal statistics from database.
        """
        from .services import AnalyticsService
        return AnalyticsService.get_dashboard_stats()
