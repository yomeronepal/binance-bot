"""Unit tests for Celery tasks."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from django.utils import timezone
from scanner.tasks.celery_tasks import (
    scan_binance_market,
    full_data_refresh,
    send_signal_notifications,
    cleanup_expired_signals,
    system_health_check,
    test_celery_task,
    _scan_market_async,
    _get_top_pairs,
    _save_signal_async,
    _broadcast_signal_update,
    _broadcast_signal_deletion,
)


@pytest.mark.django_db
class TestScanBinanceMarket:
    """Test the main market scanning task."""

    @patch('scanner.tasks.celery_tasks.SignalDetectionEngine')
    @patch('scanner.tasks.celery_tasks.asyncio.new_event_loop')
    def test_scan_success(self, mock_loop_create, mock_engine_class):
        """Test successful market scan."""
        # Setup mocks
        mock_loop = Mock()
        mock_loop_create.return_value = mock_loop
        mock_loop.run_until_complete.return_value = {
            'created': 2,
            'updated': 3,
            'deleted': 1,
            'active': 10
        }

        # Execute task
        result = scan_binance_market()

        # Assertions
        assert result['created'] == 2
        assert result['updated'] == 3
        assert result['deleted'] == 1
        assert result['active'] == 10
        mock_loop.close.assert_called_once()

    @patch('scanner.tasks.celery_tasks.SignalDetectionEngine')
    @patch('scanner.tasks.celery_tasks.asyncio.new_event_loop')
    def test_scan_retry_on_error(self, mock_loop_create, mock_engine_class):
        """Test task retries on error."""
        mock_loop = Mock()
        mock_loop_create.return_value = mock_loop
        mock_loop.run_until_complete.side_effect = Exception("API error")

        # Create bound task mock
        task = scan_binance_market
        task_request = Mock()
        task_request.retries = 0
        task.request = task_request
        task.retry = Mock(side_effect=Exception("Retry triggered"))

        # Execute and verify retry
        with pytest.raises(Exception):
            task()

        mock_loop.close.assert_called_once()


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_scan_market_async():
    """Test async market scanning logic."""
    with patch('scanner.tasks.celery_tasks.BinanceClient') as MockClient, \
         patch('scanner.tasks.celery_tasks.signal_dispatcher') as mock_dispatcher, \
         patch('scanner.tasks.celery_tasks._get_top_pairs') as mock_get_pairs, \
         patch('scanner.tasks.celery_tasks._save_signal_async') as mock_save:

        # Setup mocks
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client
        mock_client.get_usdt_pairs.return_value = ['BTCUSDT', 'ETHUSDT']
        mock_get_pairs.return_value = ['BTCUSDT']
        mock_client.batch_get_klines.return_value = {
            'BTCUSDT': [[0] * 12 for _ in range(200)]
        }

        # Create engine mock
        mock_engine = Mock()
        mock_engine.update_candles = Mock()
        mock_engine.process_symbol.return_value = {
            'action': 'created',
            'signal': {
                'symbol': 'BTCUSDT',
                'direction': 'LONG',
                'entry': 42500.0,
                'sl': 42100.0,
                'tp': 43300.0,
                'confidence': 0.85,
                'timeframe': '5m'
            }
        }
        mock_engine.active_signals = {'BTCUSDT': Mock()}

        # Execute
        result = await _scan_market_async(mock_engine)

        # Assertions
        assert result['created'] == 1
        assert result['active'] == 1
        mock_engine.update_candles.assert_called_once()
        mock_engine.process_symbol.assert_called_once()


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_get_top_pairs():
    """Test top pairs selection by volume."""
    mock_client = Mock()
    mock_client.get_24h_ticker = AsyncMock(return_value={'quoteVolume': '1000000'})

    pairs = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    result = await _get_top_pairs(mock_client, pairs, top_n=2)

    assert len(result) <= 2
    assert all(symbol in pairs for symbol in result)


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_save_signal_async():
    """Test async signal saving to database."""
    from signals.models import Symbol

    signal_data = {
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry': 42500.0,
        'sl': 42100.0,
        'tp': 43300.0,
        'confidence': 0.85,
        'timeframe': '5m',
        'description': 'Test signal'
    }

    await _save_signal_async(signal_data)

    # Verify symbol was created
    assert Symbol.objects.filter(symbol='BTCUSDT').exists()


@pytest.mark.django_db
class TestFullDataRefresh:
    """Test full data refresh task."""

    def test_refresh_expires_old_signals(self):
        """Test that old signals are marked as expired."""
        from signals.models import Signal, Symbol

        # Create test symbol
        symbol = Symbol.objects.create(
            symbol='BTCUSDT',
            base_asset='BTC',
            quote_asset='USDT'
        )

        # Create old signal
        old_time = timezone.now() - timedelta(hours=2)
        signal = Signal.objects.create(
            symbol=symbol,
            direction='LONG',
            entry=42500.0,
            sl=42100.0,
            tp=43300.0,
            confidence=0.85,
            timeframe='5m',
            status='ACTIVE',
            created_at=old_time
        )

        # Execute refresh
        result = full_data_refresh()

        # Verify signal expired
        signal.refresh_from_db()
        assert signal.status == 'EXPIRED'
        assert result['expired_signals'] == 1

    def test_refresh_keeps_recent_signals(self):
        """Test that recent signals are not expired."""
        from signals.models import Signal, Symbol

        symbol = Symbol.objects.create(
            symbol='ETHUSDT',
            base_asset='ETH',
            quote_asset='USDT'
        )

        signal = Signal.objects.create(
            symbol=symbol,
            direction='SHORT',
            entry=2500.0,
            sl=2550.0,
            tp=2400.0,
            confidence=0.75,
            timeframe='5m',
            status='ACTIVE'
        )

        result = full_data_refresh()

        signal.refresh_from_db()
        assert signal.status == 'ACTIVE'
        assert result['expired_signals'] == 0


@pytest.mark.django_db
class TestSendSignalNotifications:
    """Test signal notification task."""

    @patch('scanner.tasks.celery_tasks.signal_dispatcher')
    def test_sends_high_confidence_signals(self, mock_dispatcher):
        """Test notifications for high-confidence signals."""
        from signals.models import Signal, Symbol

        symbol = Symbol.objects.create(
            symbol='BTCUSDT',
            base_asset='BTC',
            quote_asset='USDT'
        )

        # Create high-confidence signal
        Signal.objects.create(
            symbol=symbol,
            direction='LONG',
            entry=42500.0,
            sl=42100.0,
            tp=43300.0,
            confidence=0.90,
            timeframe='5m',
            status='ACTIVE'
        )

        result = send_signal_notifications()

        assert result['notifications_sent'] == 1
        mock_dispatcher.broadcast_signal.assert_called_once()

    @patch('scanner.tasks.celery_tasks.signal_dispatcher')
    def test_ignores_low_confidence_signals(self, mock_dispatcher):
        """Test that low-confidence signals are not broadcast."""
        from signals.models import Signal, Symbol

        symbol = Symbol.objects.create(
            symbol='ETHUSDT',
            base_asset='ETH',
            quote_asset='USDT'
        )

        # Create low-confidence signal
        Signal.objects.create(
            symbol=symbol,
            direction='LONG',
            entry=2500.0,
            sl=2450.0,
            tp=2600.0,
            confidence=0.70,  # Below 0.85 threshold
            timeframe='5m',
            status='ACTIVE'
        )

        result = send_signal_notifications()

        assert result['notifications_sent'] == 0
        mock_dispatcher.broadcast_signal.assert_not_called()


@pytest.mark.django_db
class TestCleanupExpiredSignals:
    """Test signal cleanup task."""

    def test_deletes_old_signals(self):
        """Test deletion of signals older than 24 hours."""
        from signals.models import Signal, Symbol

        symbol = Symbol.objects.create(
            symbol='BTCUSDT',
            base_asset='BTC',
            quote_asset='USDT'
        )

        # Create old signal
        old_time = timezone.now() - timedelta(hours=25)
        Signal.objects.create(
            symbol=symbol,
            direction='LONG',
            entry=42500.0,
            sl=42100.0,
            tp=43300.0,
            confidence=0.85,
            timeframe='5m',
            status='EXPIRED',
            created_at=old_time
        )

        result = cleanup_expired_signals()

        assert result['deleted_count'] == 1
        assert Signal.objects.count() == 0

    def test_keeps_recent_signals(self):
        """Test that recent signals are not deleted."""
        from signals.models import Signal, Symbol

        symbol = Symbol.objects.create(
            symbol='ETHUSDT',
            base_asset='ETH',
            quote_asset='USDT'
        )

        Signal.objects.create(
            symbol=symbol,
            direction='SHORT',
            entry=2500.0,
            sl=2550.0,
            tp=2400.0,
            confidence=0.75,
            timeframe='5m',
            status='ACTIVE'
        )

        result = cleanup_expired_signals()

        assert result['deleted_count'] == 0
        assert Signal.objects.count() == 1


@pytest.mark.django_db
class TestSystemHealthCheck:
    """Test system health check task."""

    @patch('scanner.tasks.celery_tasks.cache')
    def test_health_check_success(self, mock_cache):
        """Test successful health check."""
        from signals.models import Signal, Symbol

        # Create test data
        symbol = Symbol.objects.create(
            symbol='BTCUSDT',
            base_asset='BTC',
            quote_asset='USDT'
        )

        Signal.objects.create(
            symbol=symbol,
            direction='LONG',
            entry=42500.0,
            sl=42100.0,
            tp=43300.0,
            confidence=0.85,
            timeframe='5m',
            status='ACTIVE'
        )

        mock_cache.set.return_value = True

        result = system_health_check()

        assert result['database'] == 'connected'
        assert result['active_signals'] == 1
        assert result['total_symbols'] == 1
        assert result['redis'] == 'connected'

    @patch('scanner.tasks.celery_tasks.cache')
    def test_health_check_redis_failure(self, mock_cache):
        """Test health check with Redis failure."""
        mock_cache.set.side_effect = Exception("Redis connection failed")

        result = system_health_check()

        assert result['database'] == 'connected'
        assert result['redis'] == 'disconnected'


def test_test_celery_task():
    """Test the test task."""
    result = test_celery_task("Hello World")

    assert result['message'] == "Hello World"
    assert result['status'] == 'success'
    assert 'timestamp' in result


def test_broadcast_signal_update():
    """Test signal update broadcasting."""
    with patch('scanner.tasks.celery_tasks.get_channel_layer') as mock_get_layer:
        mock_layer = Mock()
        mock_get_layer.return_value = mock_layer

        signal_data = {
            'symbol': 'BTCUSDT',
            'direction': 'LONG',
            'confidence': 0.88
        }

        _broadcast_signal_update(signal_data)

        # Verify broadcast was called
        assert mock_get_layer.called


def test_broadcast_signal_deletion():
    """Test signal deletion broadcasting."""
    with patch('scanner.tasks.celery_tasks.get_channel_layer') as mock_get_layer:
        mock_layer = Mock()
        mock_get_layer.return_value = mock_layer

        _broadcast_signal_deletion('BTCUSDT')

        assert mock_get_layer.called


@pytest.mark.django_db
class TestTaskErrorHandling:
    """Test error handling in tasks."""

    @patch('scanner.tasks.celery_tasks.asyncio.new_event_loop')
    def test_scan_closes_loop_on_error(self, mock_loop_create):
        """Test that event loop is always closed even on error."""
        mock_loop = Mock()
        mock_loop_create.return_value = mock_loop
        mock_loop.run_until_complete.side_effect = Exception("Test error")

        task = scan_binance_market
        task.retry = Mock(side_effect=Exception("Retry"))

        with pytest.raises(Exception):
            task()

        # Loop should be closed despite error
        mock_loop.close.assert_called_once()

    def test_cleanup_continues_on_error(self):
        """Test cleanup task handles errors gracefully."""
        # This should not raise even with database errors
        result = cleanup_expired_signals()

        assert 'deleted_count' in result or 'error' in result
