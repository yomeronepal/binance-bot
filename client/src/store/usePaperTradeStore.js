import { create } from 'zustand';
import api from '../services/api';

const usePaperTradeStore = create((set, get) => ({
  // State
  trades: [],
  metrics: null,
  loading: false,
  error: null,
  selectedTrade: null,

  // Actions
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),

  // Fetch all trades with live prices for open positions
  fetchTrades: async () => {
    set({ loading: true, error: null });
    try {
      // Fetch all trades
      const tradesResponse = await api.get('/paper-trades/');
      let trades = tradesResponse.data.results || tradesResponse.data;

      // Fetch live prices for open positions
      try {
        const openPositionsResponse = await api.get('/paper-trades/open_positions/');
        const livePositions = openPositionsResponse.data.positions || [];

        // Merge live price data into open trades
        trades = trades.map(trade => {
          if (trade.status === 'OPEN') {
            const livePosition = livePositions.find(p => p.trade_id === trade.id);
            if (livePosition) {
              return {
                ...trade,
                current_price: livePosition.current_price,
                unrealized_pnl: livePosition.unrealized_pnl,
                unrealized_pnl_pct: livePosition.unrealized_pnl_pct,
                current_value: livePosition.current_value,
                price_change: livePosition.price_change,
                price_change_pct: livePosition.price_change_pct,
                has_live_price: true
              };
            }
          }
          return trade;
        });
      } catch (liveError) {
        console.warn('Could not fetch live prices:', liveError);
      }

      set({ trades, loading: false });
    } catch (error) {
      console.error('Error fetching paper trades:', error);
      set({ error: error.message, loading: false });
    }
  },

  // Fetch performance metrics
  fetchMetrics: async (days = 7) => {
    try {
      const response = await api.get(`/paper-trades/performance/?days=${days}`);
      set({ metrics: response.data });
    } catch (error) {
      console.error('Error fetching metrics:', error);
      set({ error: error.message });
    }
  },

  // Create trade from signal
  createTradeFromSignal: async (signalId, positionSize = 100) => {
    set({ loading: true, error: null });
    try {
      const response = await api.post('/paper-trades/create_from_signal/', {
        signal_id: signalId,
        position_size: positionSize,
      });

      const newTrade = response.data;
      set(state => ({
        trades: [newTrade, ...state.trades],
        loading: false,
      }));

      // Refresh metrics
      get().fetchMetrics();

      return newTrade;
    } catch (error) {
      console.error('Error creating trade:', error);
      const errorMessage = error.response?.data?.error ||
                          error.response?.data?.detail ||
                          error.message ||
                          'Failed to create trade';
      set({ error: errorMessage, loading: false });
      throw new Error(errorMessage);
    }
  },

  // Close trade manually
  closeTrade: async (tradeId, exitPrice = null) => {
    set({ loading: true, error: null });
    try {
      const body = exitPrice ? { exit_price: exitPrice } : {};
      const response = await api.post(`/paper-trades/${tradeId}/close_trade/`, body);

      const closedTrade = response.data;
      set(state => ({
        trades: state.trades.map(t => t.id === tradeId ? closedTrade : t),
        loading: false,
      }));

      // Refresh metrics
      get().fetchMetrics();

      return closedTrade;
    } catch (error) {
      console.error('Error closing trade:', error);
      const errorMessage = error.response?.data?.error || error.message || 'Failed to close trade';
      set({ error: errorMessage, loading: false });
      throw new Error(errorMessage);
    }
  },

  // Cancel pending trade
  cancelTrade: async (tradeId) => {
    set({ loading: true, error: null });
    try {
      const response = await api.post(`/paper-trades/${tradeId}/cancel_trade/`);
      const cancelledTrade = response.data;

      set(state => ({
        trades: state.trades.map(t => t.id === tradeId ? cancelledTrade : t),
        loading: false,
      }));

      return cancelledTrade;
    } catch (error) {
      console.error('Error cancelling trade:', error);
      const errorMessage = error.response?.data?.error || error.message || 'Failed to cancel trade';
      set({ error: errorMessage, loading: false });
      throw new Error(errorMessage);
    }
  },

  // Update single trade (for WebSocket updates)
  updateTrade: (updatedTrade) => {
    set(state => ({
      trades: state.trades.map(t =>
        t.id === updatedTrade.id ? { ...t, ...updatedTrade } : t
      ),
    }));
  },

  // Add new trade (for WebSocket updates)
  addTrade: (newTrade) => {
    set(state => ({
      trades: [newTrade, ...state.trades],
    }));
  },

  // Select trade for detail view
  selectTrade: (trade) => set({ selectedTrade: trade }),

  // WebSocket message handler
  handleWebSocketUpdate: (message) => {
    const { type, data } = message;

    switch (type) {
      case 'paper_trade_created':
        get().addTrade(data);
        break;

      case 'paper_trade_updated':
        get().updateTrade(data);
        break;

      case 'paper_trade_closed':
        get().updateTrade(data);
        get().fetchMetrics(); // Refresh metrics
        break;

      default:
        break;
    }
  },

  // Clear all state
  reset: () => set({
    trades: [],
    metrics: null,
    loading: false,
    error: null,
    selectedTrade: null,
  }),
}));

export default usePaperTradeStore;
