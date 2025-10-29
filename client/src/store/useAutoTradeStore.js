import { create } from 'zustand';
import api from '../services/api';

const useAutoTradeStore = create((set, get) => ({
  account: null,
  trades: [],
  summary: null,
  loading: false,
  error: null,

  // Fetch auto-trading account status
  fetchAccount: async () => {
    set({ loading: true, error: null });
    try {
      const response = await api.get('/dev/paper/status/');
      set({ account: response.data, loading: false });
      return response.data;
    } catch (error) {
      console.error('Error fetching account:', error);
      set({
        error: error.response?.data?.error || error.message,
        loading: false,
      });
      throw error;
    }
  },

  // Fetch trades for auto-trading account
  fetchTrades: async (status = null) => {
    set({ loading: true, error: null });
    try {
      const params = status ? { status } : {};
      const response = await api.get('/dev/paper/trades/', { params });
      set({ trades: response.data.trades || [], loading: false });
      return response.data;
    } catch (error) {
      console.error('Error fetching trades:', error);
      set({
        error: error.response?.data?.error || error.message,
        loading: false,
      });
      throw error;
    }
  },

  // Fetch summary
  fetchSummary: async () => {
    set({ loading: true, error: null });
    try {
      const response = await api.get('/dev/paper/summary/');
      set({ summary: response.data, loading: false });
      return response.data;
    } catch (error) {
      console.error('Error fetching summary:', error);
      set({
        error: error.response?.data?.error || error.message,
        loading: false,
      });
      throw error;
    }
  },

  // Start auto-trading
  startAutoTrading: async (config = {}) => {
    set({ loading: true, error: null });
    try {
      const response = await api.post('/dev/paper/start/', {
        initial_balance: config.initial_balance || 1000.00,
        auto_trade_spot: config.auto_trade_spot !== undefined ? config.auto_trade_spot : true,
        auto_trade_futures: config.auto_trade_futures !== undefined ? config.auto_trade_futures : true,
        min_signal_confidence: config.min_signal_confidence || 0.70,
        max_position_size: config.max_position_size || 10.00,
        max_open_trades: config.max_open_trades || 5,
      });
      set({ account: response.data, loading: false });
      return response.data;
    } catch (error) {
      console.error('Error starting auto-trading:', error);
      set({
        error: error.response?.data?.error || error.message,
        loading: false,
      });
      throw error;
    }
  },

  // Reset account
  resetAccount: async () => {
    set({ loading: true, error: null });
    try {
      const response = await api.post('/dev/paper/reset/');
      set({ account: response.data, trades: [], loading: false });
      return response.data;
    } catch (error) {
      console.error('Error resetting account:', error);
      set({
        error: error.response?.data?.error || error.message,
        loading: false,
      });
      throw error;
    }
  },

  // Update settings
  updateSettings: async (settings) => {
    set({ loading: true, error: null });
    try {
      const response = await api.patch('/dev/paper/settings/', settings);
      set({ account: response.data, loading: false });
      return response.data;
    } catch (error) {
      console.error('Error updating settings:', error);
      set({
        error: error.response?.data?.error || error.message,
        loading: false,
      });
      throw error;
    }
  },

  // Close trade manually
  closeTrade: async (tradeId) => {
    set({ loading: true, error: null });
    try {
      // Get current price from trade (you might need to fetch this from Binance API)
      const trade = get().trades.find(t => t.id === tradeId);
      if (!trade) {
        throw new Error('Trade not found');
      }

      // Use paper-trades endpoint to close trade
      const response = await api.post(`/paper-trades/${tradeId}/close_trade/`, {
        current_price: trade.entry_price, // In real scenario, get current market price
      });

      // Refresh trades
      await get().fetchTrades();
      await get().fetchAccount();

      set({ loading: false });
      return response.data;
    } catch (error) {
      console.error('Error closing trade:', error);
      set({
        error: error.response?.data?.error || error.message,
        loading: false,
      });
      throw error;
    }
  },

  // Clear error
  clearError: () => set({ error: null }),
}));

export default useAutoTradeStore;
