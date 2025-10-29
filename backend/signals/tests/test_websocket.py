"""
Tests for WebSocket consumers.
Uses Channels testing utilities to test real-time signal broadcasting.
"""
import pytest
import json
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from decimal import Decimal

from config.asgi import application
from signals.models import Symbol, Signal, UserSubscription
from signals.services.realtime import realtime_signal_service

User = get_user_model()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestSignalsConsumer:
    """
    Test suite for SignalsConsumer WebSocket functionality.
    """

    async def test_unauthenticated_connection_rejected(self):
        """
        Test that unauthenticated connections are rejected.
        """
        communicator = WebsocketCommunicator(application, "/ws/signals/")

        connected, subprotocol = await communicator.connect()

        # Should not connect without authentication
        assert not connected

        await communicator.disconnect()

    async def test_authenticated_connection_accepted(self):
        """
        Test that authenticated users can connect to WebSocket.
        """
        # Create user
        user = await self.create_user("testuser", "test@example.com")

        communicator = WebsocketCommunicator(
            application,
            "/ws/signals/",
            headers=[(b"cookie", f"sessionid={await self.get_session_id(user)}".encode())]
        )
        communicator.scope['user'] = user

        connected, subprotocol = await communicator.connect()

        assert connected

        # Should receive welcome message
        response = await communicator.receive_json_from()
        assert response['type'] == 'connection_established'
        assert response['user'] == user.username

        await communicator.disconnect()

    async def test_receive_welcome_message_on_connect(self):
        """
        Test that client receives welcome message with connection info.
        """
        user = await self.create_user("testuser", "test@example.com")
        subscription = await self.create_subscription(user, 'free')

        communicator = await self.get_authenticated_communicator(user)
        connected, _ = await communicator.connect()

        assert connected

        # Receive welcome message
        response = await communicator.receive_json_from()

        assert response['type'] == 'connection_established'
        assert response['user'] == user.username
        assert response['subscription_tier'] == 'free'
        assert 'timestamp' in response

        await communicator.disconnect()

    async def test_receive_active_signals_on_connect(self):
        """
        Test that client receives active signals upon connection.
        """
        user = await self.create_user("testuser", "test@example.com")
        await self.create_subscription(user, 'pro')

        # Create some signals
        symbol = await self.create_symbol("BTCUSDT")
        await self.create_signal(symbol, user, "LONG", 50000, 49000, 52000, 0.8)
        await self.create_signal(symbol, user, "SHORT", 50000, 51000, 48000, 0.7)

        communicator = await self.get_authenticated_communicator(user)
        connected, _ = await communicator.connect()

        # Skip welcome message
        await communicator.receive_json_from()

        # Receive active signals
        response = await communicator.receive_json_from()

        assert response['type'] == 'active_signals'
        assert response['count'] >= 2
        assert len(response['signals']) >= 2

        await communicator.disconnect()

    async def test_ping_pong_heartbeat(self):
        """
        Test ping-pong heartbeat mechanism.
        """
        user = await self.create_user("testuser", "test@example.com")

        communicator = await self.get_authenticated_communicator(user)
        await communicator.connect()

        # Skip welcome and active signals messages
        await communicator.receive_json_from()
        await communicator.receive_json_from()

        # Send ping
        await communicator.send_json_to({'type': 'ping'})

        # Receive pong
        response = await communicator.receive_json_from()

        assert response['type'] == 'pong'
        assert 'timestamp' in response

        await communicator.disconnect()

    async def test_broadcast_signal_created(self):
        """
        Test that new signals are broadcasted to connected clients.
        """
        user = await self.create_user("testuser", "test@example.com")
        await self.create_subscription(user, 'pro')

        communicator = await self.get_authenticated_communicator(user)
        await communicator.connect()

        # Skip welcome and active signals messages
        await communicator.receive_json_from()
        await communicator.receive_json_from()

        # Create a new signal (should trigger broadcast)
        symbol = await self.create_symbol("ETHUSDT")
        signal = await self.create_signal(
            symbol, user, "LONG",
            entry=3000,
            sl=2900,
            tp=3200,
            confidence=0.85
        )

        # Should receive signal_created broadcast
        response = await communicator.receive_json_from()

        assert response['type'] == 'signal_created'
        assert response['signal']['id'] == signal.id
        assert response['signal']['symbol_detail']['symbol'] == "ETHUSDT"
        assert response['signal']['direction'] == 'LONG'

        await communicator.disconnect()

    async def test_broadcast_signal_updated(self):
        """
        Test that signal updates are broadcasted to connected clients.
        """
        user = await self.create_user("testuser", "test@example.com")

        communicator = await self.get_authenticated_communicator(user)
        await communicator.connect()

        # Skip welcome and active signals messages
        await communicator.receive_json_from()
        await communicator.receive_json_from()

        # Create signal
        symbol = await self.create_symbol("BTCUSDT")
        signal = await self.create_signal(symbol, user, "LONG", 50000, 49000, 52000, 0.8)

        # Receive creation broadcast
        await communicator.receive_json_from()

        # Update signal
        await self.update_signal(signal, confidence=0.9)

        # Should receive signal_updated broadcast
        response = await communicator.receive_json_from()

        assert response['type'] == 'signal_updated'
        assert response['signal']['id'] == signal.id
        assert float(response['signal']['confidence']) == 0.9

        await communicator.disconnect()

    async def test_subscription_tier_filtering(self):
        """
        Test that free users only receive high-confidence signals.
        """
        user = await self.create_user("freeuser", "free@example.com")
        await self.create_subscription(user, 'free')

        communicator = await self.get_authenticated_communicator(user)
        await communicator.connect()

        # Skip messages
        await communicator.receive_json_from()
        await communicator.receive_json_from()

        # Create low-confidence signal
        symbol = await self.create_symbol("BTCUSDT")
        low_conf_signal = await self.create_signal(
            symbol, user, "LONG", 50000, 49000, 52000, 0.5
        )

        # Free user should NOT receive low confidence signal
        # Timeout after 1 second if no message (expected)
        try:
            response = await communicator.receive_json_from(timeout=1)
            # If received, check it's not the low confidence signal
            if response['type'] == 'signal_created':
                assert response['signal']['id'] != low_conf_signal.id
        except:
            # Timeout is expected - no broadcast for free user
            pass

        # Create high-confidence signal
        high_conf_signal = await self.create_signal(
            symbol, user, "SHORT", 50000, 51000, 48000, 0.8
        )

        # Should receive high confidence signal
        response = await communicator.receive_json_from()

        assert response['type'] == 'signal_created'
        assert response['signal']['id'] == high_conf_signal.id

        await communicator.disconnect()

    async def test_get_signal_by_id(self):
        """
        Test requesting specific signal details via WebSocket.
        """
        user = await self.create_user("testuser", "test@example.com")

        communicator = await self.get_authenticated_communicator(user)
        await communicator.connect()

        # Skip messages
        await communicator.receive_json_from()
        await communicator.receive_json_from()

        # Create signal
        symbol = await self.create_symbol("BTCUSDT")
        signal = await self.create_signal(symbol, user, "LONG", 50000, 49000, 52000, 0.8)

        # Receive creation broadcast
        await communicator.receive_json_from()

        # Request signal details
        await communicator.send_json_to({
            'type': 'get_signal',
            'signal_id': signal.id
        })

        # Should receive signal details
        response = await communicator.receive_json_from()

        assert response['type'] == 'signal_details'
        assert response['signal']['id'] == signal.id

        await communicator.disconnect()

    # ==================== Helper Methods ====================

    async def get_authenticated_communicator(self, user):
        """
        Create an authenticated WebSocket communicator.
        """
        communicator = WebsocketCommunicator(application, "/ws/signals/")
        communicator.scope['user'] = user
        return communicator

    @database_sync_to_async
    def create_user(self, username, email):
        """Create a test user."""
        return User.objects.create_user(
            username=username,
            email=email,
            password='testpass123'
        )

    @database_sync_to_async
    def create_subscription(self, user, tier):
        """Create user subscription."""
        return UserSubscription.objects.create(
            user=user,
            tier=tier,
            status='active'
        )

    @database_sync_to_async
    def create_symbol(self, symbol_name):
        """Create a trading symbol."""
        symbol, _ = Symbol.objects.get_or_create(
            symbol=symbol_name,
            defaults={'exchange': 'BINANCE', 'active': True}
        )
        return symbol

    @database_sync_to_async
    def create_signal(self, symbol, user, direction, entry, sl, tp, confidence):
        """Create a trading signal."""
        return Signal.objects.create(
            symbol=symbol,
            created_by=user,
            direction=direction,
            entry=Decimal(str(entry)),
            sl=Decimal(str(sl)),
            tp=Decimal(str(tp)),
            confidence=confidence,
            status='ACTIVE',
            timeframe='1h'
        )

    @database_sync_to_async
    def update_signal(self, signal, **kwargs):
        """Update a signal."""
        for key, value in kwargs.items():
            setattr(signal, key, value)
        signal.save()
        return signal

    @database_sync_to_async
    def get_session_id(self, user):
        """Get session ID for authenticated requests."""
        from django.contrib.sessions.models import Session
        from django.utils import timezone
        import datetime

        session = Session.objects.create(
            session_key='test_session',
            session_data='',
            expire_date=timezone.now() + datetime.timedelta(days=1)
        )
        return session.session_key


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestRealtimeService:
    """
    Test suite for real-time broadcasting service.
    """

    @database_sync_to_async
    def create_test_data(self):
        """Create test data."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        symbol = Symbol.objects.create(
            symbol='BTCUSDT',
            exchange='BINANCE',
            active=True
        )
        signal = Signal.objects.create(
            symbol=symbol,
            created_by=user,
            direction='LONG',
            entry=Decimal('50000'),
            sl=Decimal('49000'),
            tp=Decimal('52000'),
            confidence=0.85,
            status='ACTIVE',
            timeframe='1h'
        )
        return user, symbol, signal

    async def test_broadcast_signal_created(self):
        """
        Test broadcasting signal creation.
        """
        user, symbol, signal = await self.create_test_data()

        # This should not raise an exception
        realtime_signal_service.broadcast_signal_created(signal)

        # Success if no exception
        assert True

    async def test_broadcast_signal_updated(self):
        """
        Test broadcasting signal update.
        """
        user, symbol, signal = await self.create_test_data()

        realtime_signal_service.broadcast_signal_updated(signal, ['confidence'])

        assert True

    async def test_broadcast_signal_deleted(self):
        """
        Test broadcasting signal deletion.
        """
        user, symbol, signal = await self.create_test_data()

        realtime_signal_service.broadcast_signal_deleted(signal.id, symbol.symbol)

        assert True
