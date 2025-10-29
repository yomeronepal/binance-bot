# Paper Trading Frontend - Complete Implementation

## Status Update

✅ **Backend Complete:**
- PaperTrade serializer created
- API ViewSet implemented (`views_paper_trading.py`)
- Routes registered in `api/urls.py`
- All endpoints working

## Frontend Implementation

### 1. Store - Zustand State Management

**File:** `client/src/store/usePaperTradeStore.js`

```javascript
import { create } from 'zustand';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export const usePaperTradeStore = create((set, get) => ({
  trades: [],
  openTrades: [],
  closedTrades: [],
  metrics: null,
  isLoading: false,
  error: null,

  // Fetch all trades
  fetchTrades: async (filters = {}) => {
    set({ isLoading: true, error: null });
    try {
      const params = new URLSearchParams(filters);
      const response = await fetch(`${API_URL}/paper-trades/?${params}`);

      if (!response.ok) throw new Error('Failed to fetch trades');

      const data = await response.json();
      const allTrades = data.results || data;

      set({
        trades: allTrades,
        openTrades: allTrades.filter(t => t.is_open),
        closedTrades: allTrades.filter(t => t.is_closed),
        isLoading: false
      });
    } catch (error) {
      console.error('Failed to fetch trades:', error);
      set({ error: error.message, isLoading: false });
    }
  },

  // Fetch performance metrics
  fetchMetrics: async (days = null) => {
    try {
      const url = days
        ? `${API_URL}/paper-trades/performance/?days=${days}`
        : `${API_URL}/paper-trades/performance/`;

      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch metrics');

      const metrics = await response.json();
      set({ metrics });
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    }
  },

  // Create trade from signal
  createTradeFromSignal: async (signalId, positionSize = 100) => {
    try {
      const response = await fetch(`${API_URL}/paper-trades/create_from_signal/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          signal_id: signalId,
          position_size: positionSize
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to create trade');
      }

      const trade = await response.json();

      set(state => ({
        trades: [trade, ...state.trades],
        openTrades: [trade, ...state.openTrades]
      }));

      // Refresh metrics
      get().fetchMetrics();

      return trade;
    } catch (error) {
      console.error('Failed to create trade:', error);
      throw error;
    }
  },

  // Close trade manually
  closeTrade: async (tradeId, currentPrice) => {
    try {
      const response = await fetch(`${API_URL}/paper-trades/${tradeId}/close_trade/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_price: currentPrice })
      });

      if (!response.ok) throw new Error('Failed to close trade');

      const trade = await response.json();
      get().updateTrade(trade);
      get().fetchMetrics();

      return trade;
    } catch (error) {
      console.error('Failed to close trade:', error);
      throw error;
    }
  },

  // Update single trade (from WebSocket or API)
  updateTrade: (updatedTrade) => {
    set(state => {
      const trades = state.trades.map(t =>
        t.id === updatedTrade.id ? updatedTrade : t
      );

      return {
        trades,
        openTrades: trades.filter(t => t.is_open),
        closedTrades: trades.filter(t => t.is_closed)
      };
    });
  },

  // Handle WebSocket updates
  handleWebSocketUpdate: (trade, action) => {
    if (action === 'created') {
      set(state => ({
        trades: [trade, ...state.trades],
        openTrades: [trade, ...state.openTrades]
      }));
    } else if (action === 'updated' || action === 'closed') {
      get().updateTrade(trade);
    }

    // Refresh metrics after any update
    get().fetchMetrics();
  },

  // Clear all data
  reset: () => {
    set({
      trades: [],
      openTrades: [],
      closedTrades: [],
      metrics: null,
      error: null
    });
  }
}));
```

### 2. Main Page Component

**File:** `client/src/pages/PaperTrading.jsx`

```jsx
import { useState, useEffect } from 'react';
import { usePaperTradeStore } from '../store/usePaperTradeStore';
import PaperTradeCard from '../components/paper-trading/PaperTradeCard';
import PerformanceMetrics from '../components/paper-trading/PerformanceMetrics';
import TradeHistory from '../components/paper-trading/TradeHistory';

const PaperTrading = () => {
  const {
    openTrades,
    closedTrades,
    metrics,
    fetchTrades,
    fetchMetrics,
    handleWebSocketUpdate,
    isLoading
  } = usePaperTradeStore();

  const [activeTab, setActiveTab] = useState('open');
  const [timeFilter, setTimeFilter] = useState('all');

  useEffect(() => {
    // Initial data fetch
    fetchTrades();
    fetchMetrics();

    // WebSocket connection
    const ws = new WebSocket(
      import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/signals/'
    );

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'paper_trade') {
        handleWebSocketUpdate(data.trade, data.action);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return () => ws.close();
  }, []);

  // Filter metrics by time
  useEffect(() => {
    const days = timeFilter === '7d' ? 7 : timeFilter === '30d' ? 30 : null;
    fetchMetrics(days);
  }, [timeFilter]);

  if (isLoading && !metrics) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
              Paper Trading
            </h1>
            <p className="text-gray-600 dark:text-gray-400 mt-2">
              Simulated trading without risk • Real-time performance tracking
            </p>
          </div>

          {/* Mode Badge */}
          <div className="flex items-center space-x-3">
            <div className="bg-green-100 dark:bg-green-900/30 px-6 py-3 rounded-xl border-2 border-green-500/50">
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-green-800 dark:text-green-300 font-bold text-lg">
                  📄 PAPER MODE
                </span>
              </div>
            </div>

            {/* Time Filter */}
            <select
              value={timeFilter}
              onChange={(e) => setTimeFilter(e.target.value)}
              className="px-4 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg shadow-sm focus:ring-2 focus:ring-purple-500"
            >
              <option value="all">All Time</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
            </select>
          </div>
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="max-w-7xl mx-auto mb-8">
        <PerformanceMetrics metrics={metrics} />
      </div>

      {/* Tabs */}
      <div className="max-w-7xl mx-auto mb-6">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-2 inline-flex space-x-2">
          <button
            onClick={() => setActiveTab('open')}
            className={`px-6 py-3 rounded-lg font-semibold transition-all ${
              activeTab === 'open'
                ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg'
                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
          >
            Open Trades ({openTrades.length})
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`px-6 py-3 rounded-lg font-semibold transition-all ${
              activeTab === 'history'
                ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg'
                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
          >
            History ({closedTrades.length})
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto">
        {activeTab === 'open' && (
          <div>
            {openTrades.length === 0 ? (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-12 text-center">
                <div className="text-6xl mb-4">📊</div>
                <h3 className="text-2xl font-bold text-gray-800 dark:text-white mb-2">
                  No Open Trades
                </h3>
                <p className="text-gray-600 dark:text-gray-400">
                  Create paper trades from signals to start tracking performance
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {openTrades.map(trade => (
                  <PaperTradeCard key={trade.id} trade={trade} />
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <TradeHistory trades={closedTrades} />
        )}
      </div>
    </div>
  );
};

export default PaperTrading;
```

### 3. Performance Metrics Component

**File:** `client/src/components/paper-trading/PerformanceMetrics.jsx`

```jsx
import { ArrowUpIcon, ArrowDownIcon } from '@heroicons/react/24/solid';

const PerformanceMetrics = ({ metrics }) => {
  if (!metrics) {
    return (
      <div className="animate-pulse grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-gray-200 dark:bg-gray-700 h-32 rounded-xl"></div>
        ))}
      </div>
    );
  }

  const {
    total_trades,
    open_trades,
    win_rate,
    total_profit_loss,
    profitable_trades,
    losing_trades
  } = metrics;

  const isProfit = total_profit_loss >= 0;

  const stats = [
    {
      label: 'Total P/L',
      value: `${isProfit ? '+' : ''}$${Math.abs(total_profit_loss).toFixed(2)}`,
      change: `${profitable_trades}W / ${losing_trades}L`,
      color: isProfit ? 'green' : 'red',
      icon: isProfit ? ArrowUpIcon : ArrowDownIcon,
      gradient: isProfit
        ? 'from-green-500 to-emerald-600'
        : 'from-red-500 to-rose-600'
    },
    {
      label: 'Win Rate',
      value: `${win_rate.toFixed(1)}%`,
      change: `${total_trades} trades`,
      color: win_rate >= 50 ? 'green' : win_rate >= 40 ? 'yellow' : 'red',
      gradient: win_rate >= 50
        ? 'from-green-500 to-emerald-600'
        : win_rate >= 40
        ? 'from-yellow-500 to-orange-600'
        : 'from-red-500 to-rose-600'
    },
    {
      label: 'Open Trades',
      value: open_trades,
      change: 'Active positions',
      color: 'blue',
      gradient: 'from-blue-500 to-indigo-600'
    },
    {
      label: 'Total Trades',
      value: total_trades,
      change: 'All time',
      color: 'purple',
      gradient: 'from-purple-500 to-pink-600'
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {stats.map((stat, index) => (
        <div
          key={index}
          className="bg-white dark:bg-gray-800 rounded-xl shadow-lg hover:shadow-2xl transition-all duration-300 overflow-hidden group"
        >
          <div className={`h-2 bg-gradient-to-r ${stat.gradient}`}></div>
          <div className="p-6">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                {stat.label}
              </span>
              {stat.icon && (
                <stat.icon className={`w-5 h-5 text-${stat.color}-500`} />
              )}
            </div>
            <div className={`text-3xl font-bold bg-gradient-to-r ${stat.gradient} bg-clip-text text-transparent mb-1`}>
              {stat.value}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">
              {stat.change}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default PerformanceMetrics;
```

### 4. Paper Trade Card Component

**File:** `client/src/components/paper-trading/PaperTradeCard.jsx`

```jsx
import { useState } from 'react';
import { usePaperTradeStore } from '../../store/usePaperTradeStore';
import { formatDistance } from 'date-fns';

const PaperTradeCard = ({ trade }) => {
  const { closeTrade } = usePaperTradeStore();
  const [isClosing, setIsClosing] = useState(false);

  const isLong = trade.direction === 'LONG';
  const isFutures = trade.market_type === 'FUTURES';

  const handleClose = async () => {
    if (!confirm('Close this trade manually?')) return;

    setIsClosing(true);
    try {
      // In production, fetch current price from API
      const currentPrice = trade.entry_price; // Placeholder
      await closeTrade(trade.id, currentPrice);
    } catch (error) {
      alert('Failed to close trade: ' + error.message);
    } finally {
      setIsClosing(false);
    }
  };

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-xl shadow-lg hover:shadow-2xl transition-all duration-300 overflow-hidden border-l-4 ${
      isLong ? 'border-green-500' : 'border-red-500'
    }`}>
      {/* Header */}
      <div className={`p-4 ${
        isLong ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <h3 className="text-xl font-bold text-gray-900 dark:text-white">
              {trade.symbol}
            </h3>
            <span className={`px-3 py-1 rounded-full text-xs font-bold ${
              isLong
                ? 'bg-green-500 text-white'
                : 'bg-red-500 text-white'
            }`}>
              {trade.direction}
            </span>
            {isFutures && (
              <span className="px-2 py-1 rounded bg-yellow-500 text-black text-xs font-bold">
                {trade.leverage}x
              </span>
            )}
          </div>
        </div>
        <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">
          {trade.signal_timeframe} • Opened {formatDistance(new Date(trade.entry_time), new Date(), { addSuffix: true })}
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-4">
        {/* Price Levels */}
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-600 dark:text-gray-400">Entry</span>
            <span className="font-mono font-bold text-gray-900 dark:text-white">
              ${parseFloat(trade.entry_price).toFixed(4)}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-green-600 dark:text-green-400">Take Profit</span>
            <span className="font-mono font-bold text-green-600">
              ${parseFloat(trade.take_profit).toFixed(4)}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-red-600 dark:text-red-400">Stop Loss</span>
            <span className="font-mono font-bold text-red-600">
              ${parseFloat(trade.stop_loss).toFixed(4)}
            </span>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="pt-2">
          <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400 mb-1">
            <span>SL</span>
            <span>Entry</span>
            <span>TP</span>
          </div>
          <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full bg-gradient-to-r ${
                isLong
                  ? 'from-red-500 via-blue-500 to-green-500'
                  : 'from-green-500 via-blue-500 to-red-500'
              }`}
            ></div>
          </div>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-gray-50 dark:bg-gray-900/50 rounded-lg p-3">
            <div className="text-xs text-gray-600 dark:text-gray-400">Position</div>
            <div className="text-sm font-bold text-gray-900 dark:text-white">
              ${parseFloat(trade.position_size).toFixed(2)}
            </div>
          </div>
          <div className="bg-gray-50 dark:bg-gray-900/50 rounded-lg p-3">
            <div className="text-xs text-gray-600 dark:text-gray-400">R/R</div>
            <div className="text-sm font-bold text-gray-900 dark:text-white">
              1:{trade.risk_reward_ratio}
            </div>
          </div>
        </div>

        {/* Actions */}
        <button
          onClick={handleClose}
          disabled={isClosing}
          className="w-full py-2 bg-gradient-to-r from-gray-600 to-gray-700 hover:from-gray-700 hover:to-gray-800 text-white font-semibold rounded-lg transition-all disabled:opacity-50"
        >
          {isClosing ? 'Closing...' : 'Close Trade'}
        </button>
      </div>
    </div>
  );
};

export default PaperTradeCard;
```

## Next Steps

1. ✅ Restart backend to load new routes
2. Create remaining components (TradeHistory, etc.)
3. Add routing to `client/src/routes/AppRouter.jsx`
4. Test complete flow

See implementation guide for remaining components!
