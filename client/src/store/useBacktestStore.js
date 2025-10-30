/**
 * Zustand store for backtesting state management
 */
import { create } from 'zustand';
import api from '../services/api';

const useBacktestStore = create((set, get) => ({
  // State
  backtests: [],
  currentBacktest: null,
  backtestTrades: [],
  backtestMetrics: null,
  loading: false,
  error: null,
  taskStatus: null,

  // Fetch all backtests
  fetchBacktests: async () => {
    set({ loading: true, error: null });
    try {
      const response = await api.get('/backtest/');
      const backtests = response.data.results || response.data;
      set({ backtests, loading: false });
    } catch (error) {
      console.error('Error fetching backtests:', error);
      set({ error: error.message, loading: false });
    }
  },

  // Fetch single backtest details
  fetchBacktestDetails: async (id) => {
    set({ loading: true, error: null });
    try {
      const response = await api.get(`/backtest/${id}/`);
      set({ currentBacktest: response.data, loading: false });
      return response.data;
    } catch (error) {
      console.error('Error fetching backtest details:', error);
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  // Fetch backtest trades
  fetchBacktestTrades: async (id) => {
    set({ loading: true, error: null });
    try {
      const response = await api.get(`/backtest/${id}/trades/`);
      const trades = response.data.trades || [];
      set({ backtestTrades: trades, loading: false });
      return trades;
    } catch (error) {
      console.error('Error fetching backtest trades:', error);
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  // Fetch backtest metrics and equity curve
  fetchBacktestMetrics: async (id) => {
    set({ loading: true, error: null });
    try {
      const response = await api.get(`/backtest/${id}/metrics/`);
      set({ backtestMetrics: response.data, loading: false });
      return response.data;
    } catch (error) {
      console.error('Error fetching backtest metrics:', error);
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  // Create and run new backtest
  createBacktest: async (config) => {
    set({ loading: true, error: null });
    try {
      const response = await api.post('/backtest/', config);
      const newBacktest = response.data;

      // Add to backtests list
      set((state) => ({
        backtests: [newBacktest, ...state.backtests],
        currentBacktest: newBacktest,
        loading: false,
        taskStatus: 'PENDING'
      }));

      return newBacktest;
    } catch (error) {
      console.error('Error creating backtest:', error);
      set({ error: error.response?.data?.error || error.message, loading: false });
      throw error;
    }
  },

  // Poll backtest status
  pollBacktestStatus: async (id, onComplete) => {
    const poll = async () => {
      try {
        const backtest = await get().fetchBacktestDetails(id);

        if (backtest.status === 'COMPLETED') {
          set({ taskStatus: 'COMPLETED' });
          if (onComplete) onComplete(backtest);
          return true; // Stop polling
        } else if (backtest.status === 'FAILED') {
          set({ taskStatus: 'FAILED', error: backtest.error_message || 'Backtest failed' });
          return true; // Stop polling
        } else {
          set({ taskStatus: backtest.status });
          return false; // Continue polling
        }
      } catch (error) {
        console.error('Error polling backtest status:', error);
        return false; // Continue polling on error
      }
    };

    // Initial poll
    const shouldStop = await poll();
    if (shouldStop) return;

    // Poll every 3 seconds
    const intervalId = setInterval(async () => {
      const shouldStop = await poll();
      if (shouldStop) {
        clearInterval(intervalId);
      }
    }, 3000);

    // Store interval ID for cleanup
    set({ pollingIntervalId: intervalId });
  },

  // Stop polling
  stopPolling: () => {
    const { pollingIntervalId } = get();
    if (pollingIntervalId) {
      clearInterval(pollingIntervalId);
      set({ pollingIntervalId: null });
    }
  },

  // Delete backtest
  deleteBacktest: async (id) => {
    try {
      await api.delete(`/backtest/${id}/`);
      set((state) => ({
        backtests: state.backtests.filter((b) => b.id !== id),
        currentBacktest: state.currentBacktest?.id === id ? null : state.currentBacktest
      }));
    } catch (error) {
      console.error('Error deleting backtest:', error);
      set({ error: error.message });
      throw error;
    }
  },

  // Run parameter optimization
  runOptimization: async (config) => {
    set({ loading: true, error: null });
    try {
      const response = await api.post('/optimization/run/', config);
      set({ loading: false });
      return response.data;
    } catch (error) {
      console.error('Error running optimization:', error);
      set({ error: error.response?.data?.error || error.message, loading: false });
      throw error;
    }
  },

  // Fetch best parameters
  fetchBestParameters: async (filters = {}) => {
    set({ loading: true, error: null });
    try {
      const response = await api.get('/optimization/best/', { params: filters });
      set({ loading: false });
      return response.data;
    } catch (error) {
      console.error('Error fetching best parameters:', error);
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  // Generate AI recommendations
  generateRecommendations: async (lookbackDays = 90) => {
    set({ loading: true, error: null });
    try {
      const response = await api.post('/recommendations/generate/', { lookback_days: lookbackDays });
      set({ loading: false });
      return response.data;
    } catch (error) {
      console.error('Error generating recommendations:', error);
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  // Clear current backtest
  clearCurrentBacktest: () => {
    set({
      currentBacktest: null,
      backtestTrades: [],
      backtestMetrics: null,
      taskStatus: null
    });
  },

  // Reset store
  reset: () => {
    get().stopPolling();
    set({
      backtests: [],
      currentBacktest: null,
      backtestTrades: [],
      backtestMetrics: null,
      loading: false,
      error: null,
      taskStatus: null,
      pollingIntervalId: null
    });
  }
}));

export default useBacktestStore;
