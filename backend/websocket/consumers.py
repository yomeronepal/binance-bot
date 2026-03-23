"""
WebSocket consumers for real-time data
"""
import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class NoOpConsumer(AsyncWebsocketConsumer):
    """Silently accept and close connections to unused WebSocket paths."""

    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data=None, bytes_data=None):
        pass


class SignalConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time trading signals with keepalive support
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.keepalive_task = None
        self.keepalive_interval = 30  # Send keepalive every 30 seconds

    async def connect(self):
        self.room_group_name = 'signals'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"WebSocket connected: {self.channel_name}")

        # Start keepalive task
        self.keepalive_task = asyncio.create_task(self.send_keepalive())

    async def disconnect(self, close_code):
        # Cancel keepalive task
        if self.keepalive_task:
            self.keepalive_task.cancel()
            try:
                await self.keepalive_task
            except asyncio.CancelledError:
                pass

        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected: {self.channel_name}, code: {close_code}")

    async def send_keepalive(self):
        """
        Send periodic keepalive messages to prevent connection timeout
        """
        try:
            while True:
                await asyncio.sleep(self.keepalive_interval)
                await self.send(text_data=json.dumps({
                    'type': 'keepalive',
                    'timestamp': asyncio.get_event_loop().time()
                }))
        except asyncio.CancelledError:
            logger.debug("Keepalive task cancelled")
        except Exception as e:
            logger.error(f"Error in keepalive task: {e}")

    # Receive message from WebSocket
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', '')
            
            # Handle pong responses (client acknowledgment)
            if message_type == 'pong':
                logger.debug("Received pong from client")
                return
            
            message = text_data_json.get('message', '')

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'signal_message',
                    'message': message
                }
            )
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error in receive: {e}")

    # Receive message from room group
    async def signal_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))
