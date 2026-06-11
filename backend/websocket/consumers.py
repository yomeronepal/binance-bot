"""
WebSocket consumers for real-time data
"""
import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class NoOpConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data=None, bytes_data=None):
        pass


class BacktestConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time backtest progress updates.
    Client connects to ws/backtest/{id}/ to receive live logs.
    """

    async def connect(self):
        self.backtest_id = self.scope['url_route']['kwargs']['backtest_id']
        self.group_name = f'backtest_{self.backtest_id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"Backtest WS connected: #{self.backtest_id}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        data = json.loads(text_data)
        if data.get('type') == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))

    async def backtest_progress(self, event):
        await self.send(text_data=json.dumps(event['data']))

    async def backtest_completed(self, event):
        await self.send(text_data=json.dumps(event['data']))


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
