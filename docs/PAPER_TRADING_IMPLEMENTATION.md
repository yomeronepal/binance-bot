# Paper Trading Implementation - Complete Guide

## Status: ✅ Foundation Complete, Implementation in Progress

## What's Been Implemented

### 1. ✅ Database Model - COMPLETE
**File:** `backend/signals/models.py`

- Created comprehensive `PaperTrade` model with:
  - Trade tracking (PENDING, OPEN, CLOSED_TP, CLOSED_SL, CLOSED_MANUAL, CANCELLED)
  - Entry/Exit price and time tracking
  - Profit/Loss calculation
  - Position sizing
  - Leverage support for futures
  - User association for multi-user support
  - Helper methods for SL/TP checking

**Migration:** Applied successfully (`0006_papertrade.py`)

### 2. ✅ Paper Trading Service - COMPLETE
**File:** `backend/signals/services/paper_trader.py`

Implemented full service with:
- `create_paper_trade()` - Create trades from signals
- `check_and_close_trades()` - Automatic SL/TP monitoring
- `close_trade_manually()` - Manual trade closure
- `cancel_trade()` - Cancel pending trades
- `get_open_trades()` - Retrieve active positions
- `get_trade_history()` - View past trades
- `calculate_performance_metrics()` - Win rate, P/L, etc.
- `get_current_positions_value()` - Real-time portfolio value

### 3. ✅ Increased Coin Scanning - COMPLETE
**File:** `backend/scanner/tasks/celery_tasks.py`

- Changed from 50/100 pairs to ALL available pairs
- Spot: Now scans ~436 pairs (was 200)
- Futures: Now scans ~530 pairs (was 100)

## Remaining Implementation Steps

### Step 4: Price Monitoring Task (Celery)

**File to Create:** `backend/signals/tasks/paper_trading_tasks.py`

```python
"""
Celery tasks for paper trading automation.
"""
from celery import shared_task
from decimal import Decimal
import logging
from scanner.services.binance_client import BinanceClient, BinanceFuturesClient
from signals.services.paper_trader import paper_trading_service

logger = logging.getLogger(__name__)


@shared_task(name='signals.monitor_paper_trades')
def monitor_paper_trades():
    """
    Monitor all open paper trades and close if SL/TP hit.
    Runs every minute.
    """
    try:
        from signals.models import PaperTrade
        import asyncio

        # Get all unique symbols from open trades
        open_trades = PaperTrade.objects.filter(status='OPEN')
        if not open_trades.exists():
            logger.debug("No open paper trades to monitor")
            return {
                'monitored': 0,
                'closed': 0
            }

        # Group by market type
        spot_symbols = set(
            open_trades.filter(market_type='SPOT').values_list('symbol', flat=True)
        )
        futures_symbols = set(
            open_trades.filter(market_type='FUTURES').values_list('symbol', flat=True)
        )

        # Fetch current prices
        current_prices = {}

        async def fetch_prices():
            nonlocal current_prices

            # Fetch spot prices
            if spot_symbols:
                async with BinanceClient() as client:
                    for symbol in spot_symbols:
                        try:
                            ticker = await client.get_ticker(symbol)
                            current_prices[symbol] = Decimal(str(ticker['lastPrice']))
                        except Exception as e:
                            logger.error(f"Error fetching {symbol} price: {e}")

            # Fetch futures prices
            if futures_symbols:
                async with BinanceFuturesClient() as client:
                    for symbol in futures_symbols:
                        try:
                            ticker = await client.get_ticker(symbol)
                            current_prices[symbol] = Decimal(str(ticker['lastPrice']))
                        except Exception as e:
                            logger.error(f"Error fetching {symbol} futures price: {e}")

        # Run async fetch
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(fetch_prices())
        finally:
            loop.close()

        # Check and close trades
        closed_trades = paper_trading_service.check_and_close_trades(current_prices)

        # Broadcast updates via WebSocket
        from signals.services.paper_trade_dispatcher import broadcast_trade_updates
        for trade in closed_trades:
            broadcast_trade_updates(trade, 'closed')

        logger.info(f"✅ Monitored {len(open_trades)} trades, closed {len(closed_trades)}")

        return {
            'monitored': len(open_trades),
            'closed': len(closed_trades),
            'closed_trades': [
                {
                    'id': t.id,
                    'symbol': t.symbol,
                    'status': t.status,
                    'pnl': float(t.profit_loss)
                } for t in closed_trades
            ]
        }

    except Exception as e:
        logger.error(f"Error monitoring paper trades: {e}", exc_info=True)
        raise


@shared_task(name='signals.auto_create_paper_trades')
def auto_create_paper_trades():
    """
    Automatically create paper trades for new ACTIVE signals.
    Optional: Can be disabled if users want to manually select signals.
    """
    try:
        from signals.models import Signal, PaperTrade

        # Get active signals without paper trades
        signals_without_trades = Signal.objects.filter(
            status='ACTIVE',
            paper_trades__isnull=True
        ).select_related('symbol')

        created_count = 0
        for signal in signals_without_trades:
            try:
                trade = paper_trading_service.create_paper_trade(signal)
                created_count += 1

                # Broadcast via WebSocket
                from signals.services.paper_trade_dispatcher import broadcast_trade_updates
                broadcast_trade_updates(trade, 'created')

            except Exception as e:
                logger.error(f"Error creating paper trade for signal {signal.id}: {e}")

        logger.info(f"📄 Auto-created {created_count} paper trades")

        return {
            'created': created_count
        }

    except Exception as e:
        logger.error(f"Error in auto_create_paper_trades: {e}", exc_info=True)
        raise
```

**Add to Celery Beat Schedule:**

File: `backend/config/celery.py`

```python
app.conf.beat_schedule = {
    # ... existing schedules ...

    'monitor-paper-trades': {
        'task': 'signals.monitor_paper_trades',
        'schedule': crontab(minute='*/1'),  # Every minute
    },

    'auto-create-paper-trades': {
        'task': 'signals.auto_create_paper_trades',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}
```

### Step 5: REST API Endpoints

**File:** `backend/signals/views.py` (Add to existing file)

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from signals.models import PaperTrade
from signals.serializers import PaperTradeSerializer
from signals.services.paper_trader import paper_trading_service
from decimal import Decimal


class PaperTradeViewSet(viewsets.ModelViewSet):
    """API endpoints for paper trading."""

    queryset = PaperTrade.objects.all()
    serializer_class = PaperTradeSerializer

    def get_queryset(self):
        """Filter by user if authenticated."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user=self.request.user)
        else:
            queryset = queryset.filter(user__isnull=True)

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by market type
        market_type = self.request.query_params.get('market_type')
        if market_type:
            queryset = queryset.filter(market_type=market_type)

        return queryset

    @action(detail=False, methods=['post'])
    def create_from_signal(self, request):
        """Create a paper trade from a signal."""
        signal_id = request.data.get('signal_id')
        position_size = request.data.get('position_size', 100)

        try:
            from signals.models import Signal
            signal = Signal.objects.get(id=signal_id)

            user = request.user if request.user.is_authenticated else None
            trade = paper_trading_service.create_paper_trade(
                signal,
                user=user,
                position_size=position_size
            )

            serializer = self.get_serializer(trade)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Signal.DoesNotExist:
            return Response(
                {'error': 'Signal not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def close_trade(self, request, pk=None):
        """Manually close a paper trade."""
        current_price = request.data.get('current_price')

        if not current_price:
            return Response(
                {'error': 'current_price is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        trade = paper_trading_service.close_trade_manually(
            int(pk),
            Decimal(str(current_price))
        )

        if trade:
            serializer = self.get_serializer(trade)
            return Response(serializer.data)
        else:
            return Response(
                {'error': 'Trade not found or cannot be closed'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def cancel_trade(self, request, pk=None):
        """Cancel a pending paper trade."""
        trade = paper_trading_service.cancel_trade(int(pk))

        if trade:
            serializer = self.get_serializer(trade)
            return Response(serializer.data)
        else:
            return Response(
                {'error': 'Trade not found or cannot be cancelled'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def performance(self, request):
        """Get performance metrics."""
        days = request.query_params.get('days')
        days = int(days) if days else None

        user = request.user if request.user.is_authenticated else None
        metrics = paper_trading_service.calculate_performance_metrics(
            user=user,
            days=days
        )

        return Response(metrics)

    @action(detail=False, methods=['get'])
    def open_positions(self, request):
        """Get all open positions with current values."""
        # In real implementation, fetch current prices
        current_prices = {}  # Would fetch from Binance

        user = request.user if request.user.is_authenticated else None
        positions = paper_trading_service.get_current_positions_value(
            current_prices,
            user=user
        )

        return Response(positions)
```

**Serializer:** `backend/signals/serializers.py`

```python
class PaperTradeSerializer(serializers.ModelSerializer):
    """Serializer for PaperTrade model."""

    symbol_detail = SymbolSerializer(source='signal.symbol', read_only=True)
    signal_id = serializers.IntegerField(source='signal.id', read_only=True)
    duration_hours = serializers.FloatField(read_only=True)
    risk_reward_ratio = serializers.FloatField(read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    is_profitable = serializers.BooleanField(read_only=True)

    class Meta:
        model = PaperTrade
        fields = [
            'id', 'signal_id', 'symbol', 'symbol_detail', 'direction',
            'market_type', 'entry_price', 'entry_time', 'position_size',
            'quantity', 'stop_loss', 'take_profit', 'exit_price',
            'exit_time', 'profit_loss', 'profit_loss_percentage',
            'leverage', 'status', 'created_at', 'updated_at',
            'duration_hours', 'risk_reward_ratio', 'is_open', 'is_profitable'
        ]
        read_only_fields = [
            'id', 'entry_time', 'exit_price', 'exit_time',
            'profit_loss', 'profit_loss_percentage', 'status',
            'created_at', 'updated_at'
        ]
```

**URLs:** `backend/api/urls.py`

```python
from signals.views import PaperTradeViewSet

router.register(r'paper-trades', PaperTradeViewSet, basename='paper-trade')
```

### Step 6: WebSocket Support

**File to Create:** `backend/signals/services/paper_trade_dispatcher.py`

```python
"""
WebSocket dispatcher for paper trade updates.
"""
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def broadcast_trade_updates(trade, action='updated'):
    """
    Broadcast paper trade updates via WebSocket.

    Args:
        trade: PaperTrade instance
        action: 'created', 'updated', 'closed', 'cancelled'
    """
    try:
        from signals.serializers import PaperTradeSerializer

        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning("No channel layer configured")
            return

        # Serialize trade
        serializer = PaperTradeSerializer(trade)

        # Broadcast to group
        async_to_sync(channel_layer.group_send)(
            'paper_trades',
            {
                'type': 'paper_trade_update',
                'action': action,
                'trade': serializer.data
            }
        )

        logger.debug(f"Broadcasted {action} for paper trade {trade.id}")

    except Exception as e:
        logger.error(f"Error broadcasting trade update: {e}", exc_info=True)
```

**Update Consumer:** `backend/signals/consumers.py`

```python
class SignalConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add('signals', self.channel_name)
        await self.channel_layer.group_add('paper_trades', self.channel_name)  # Add this
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('signals', self.channel_name)
        await self.channel_layer.group_discard('paper_trades', self.channel_name)  # Add this

    # Add handler
    async def paper_trade_update(self, event):
        """Handle paper trade updates."""
        await self.send(text_data=json.dumps({
            'type': 'paper_trade',
            'action': event['action'],
            'trade': event['trade']
        }))
```

### Step 7: React Frontend

**File to Create:** `client/src/pages/PaperTrading.jsx`

```jsx
import { useState, useEffect } from 'react';
import { usePaperTradeStore } from '../store/usePaperTradeStore';
import PaperTradeCard from '../components/paper-trading/PaperTradeCard';
import PerformanceMetrics from '../components/paper-trading/PerformanceMetrics';
import TradeHistory from '../components/paper-trading/TradeHistory';

const PaperTrading = () => {
  const {
    trades,
    openTrades,
    metrics,
    fetchTrades,
    fetchMetrics,
    handleTradeUpdate
  } = usePaperTradeStore();

  const [activeTab, setActiveTab] = useState('open'); // open, history, performance

  useEffect(() => {
    fetchTrades();
    fetchMetrics();

    // Connect to WebSocket
    const ws = new WebSocket(import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/signals/');

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'paper_trade') {
        handleTradeUpdate(data.trade, data.action);
      }
    };

    return () => ws.close();
  }, []);

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Paper Trading</h1>
        <div className="bg-green-100 px-4 py-2 rounded-lg">
          <span className="text-green-800 font-semibold">📄 PAPER MODE</span>
        </div>
      </div>

      {/* Performance Summary */}
      <PerformanceMetrics metrics={metrics} />

      {/* Tabs */}
      <div className="tabs mb-6">
        <button
          className={`tab ${activeTab === 'open' ? 'active' : ''}`}
          onClick={() => setActiveTab('open')}
        >
          Open Trades ({openTrades.length})
        </button>
        <button
          className={`tab ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          History
        </button>
        <button
          className={`tab ${activeTab === 'performance' ? 'active' : ''}`}
          onClick={() => setActiveTab('performance')}
        >
          Performance
        </button>
      </div>

      {/* Content */}
      <div className="trade-content">
        {activeTab === 'open' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {openTrades.map(trade => (
              <PaperTradeCard key={trade.id} trade={trade} />
            ))}
          </div>
        )}

        {activeTab === 'history' && (
          <TradeHistory trades={trades} />
        )}

        {activeTab === 'performance' && (
          <div>Performance charts and analysis</div>
        )}
      </div>
    </div>
  );
};

export default PaperTrading;
```

**Store:** `client/src/store/usePaperTradeStore.js`

```javascript
import { create } from 'zustand';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export const usePaperTradeStore = create((set, get) => ({
  trades: [],
  openTrades: [],
  metrics: {},
  isLoading: false,

  fetchTrades: async () => {
    set({ isLoading: true });
    try {
      const response = await fetch(`${API_URL}/paper-trades/`);
      const data = await response.json();
      set({
        trades: data.results || data,
        openTrades: (data.results || data).filter(t => t.is_open),
        isLoading: false
      });
    } catch (error) {
      console.error('Failed to fetch trades:', error);
      set({ isLoading: false });
    }
  },

  fetchMetrics: async () => {
    try {
      const response = await fetch(`${API_URL}/paper-trades/performance/`);
      const data = await response.json();
      set({ metrics: data });
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    }
  },

  createTradeFromSignal: async (signalId, positionSize = 100) => {
    try {
      const response = await fetch(`${API_URL}/paper-trades/create_from_signal/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signal_id: signalId, position_size: positionSize })
      });
      const trade = await response.json();
      set(state => ({
        trades: [trade, ...state.trades],
        openTrades: [trade, ...state.openTrades]
      }));
      return trade;
    } catch (error) {
      console.error('Failed to create trade:', error);
      throw error;
    }
  },

  closeTrade: async (tradeId, currentPrice) => {
    try {
      const response = await fetch(`${API_URL}/paper-trades/${tradeId}/close_trade/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_price: currentPrice })
      });
      const trade = await response.json();
      get().handleTradeUpdate(trade, 'closed');
    } catch (error) {
      console.error('Failed to close trade:', error);
      throw error;
    }
  },

  handleTradeUpdate: (trade, action) => {
    set(state => {
      let newTrades = [...state.trades];
      const index = newTrades.findIndex(t => t.id === trade.id);

      if (action === 'created') {
        newTrades = [trade, ...newTrades];
      } else if (action === 'closed' || action === 'updated') {
        if (index !== -1) {
          newTrades[index] = trade;
        }
      }

      return {
        trades: newTrades,
        openTrades: newTrades.filter(t => t.is_open)
      };
    });

    // Refresh metrics
    get().fetchMetrics();
  }
}));
```

### Step 8: Mode Toggle

**File:** `client/src/components/common/TradingModeToggle.jsx`

```jsx
import { useState } from 'react';

const TradingModeToggle = () => {
  const [isPaperMode, setIsPaperMode] = useState(true);

  const toggleMode = () => {
    if (!isPaperMode) {
      // Switching to paper mode - always allowed
      setIsPaperMode(true);
      localStorage.setItem('trading_mode', 'paper');
    } else {
      // Switching to live mode - show warning
      const confirmed = window.confirm(
        '⚠️ WARNING: You are switching to LIVE TRADING mode. ' +
        'Real orders will be executed on Binance. Continue?'
      );
      if (confirmed) {
        setIsPaperMode(false);
        localStorage.setItem('trading_mode', 'live');
      }
    }
  };

  return (
    <div className="flex items-center space-x-3 p-3 bg-white dark:bg-gray-800 rounded-lg shadow">
      <span className="text-sm font-medium">Trading Mode:</span>
      <button
        onClick={toggleMode}
        className={`relative inline-flex h-8 w-16 items-center rounded-full transition-colors ${
          isPaperMode ? 'bg-green-500' : 'bg-red-500'
        }`}
      >
        <span
          className={`inline-block h-6 w-6 transform rounded-full bg-white transition-transform ${
            isPaperMode ? 'translate-x-1' : 'translate-x-9'
          }`}
        />
      </button>
      <span className={`text-sm font-bold ${isPaperMode ? 'text-green-600' : 'text-red-600'}`}>
        {isPaperMode ? '📄 PAPER' : '🔴 LIVE'}
      </span>
    </div>
  );
};

export default TradingModeToggle;
```

## Testing Checklist

- [ ] Create paper trade from signal
- [ ] Monitor open trades
- [ ] Verify SL hit closes trade with loss
- [ ] Verify TP hit closes trade with profit
- [ ] Manual trade closure works
- [ ] Performance metrics calculate correctly
- [ ] WebSocket updates in real-time
- [ ] No real Binance orders triggered
- [ ] Mode toggle prevents accidental live trading

## Summary

**Completed:**
- ✅ PaperTrade model (database)
- ✅ Paper trading service (business logic)
- ✅ Performance metrics calculation
- ✅ All coin scanning enabled

**Remaining (see implementation above):**
- 🔄 Celery tasks for price monitoring
- 🔄 REST API endpoints
- 🔄 WebSocket dispatcher
- 🔄 React frontend dashboard
- 🔄 Mode toggle component

**Estimated Time to Complete:** 2-3 hours for full implementation

All code templates are provided above. Simply copy into the appropriate files and test!
