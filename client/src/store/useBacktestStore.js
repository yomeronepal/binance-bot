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

  fetchBacktestDetails: async (id) => {
    set({ loading: true, error: null });
    try {
      const response = await api.get(`/backtest/${id}/`);
      const current = get().currentBacktest;
      if (!current || current.id === id) {
        set({ currentBacktest: response.data, loading: false });
      } else {
        set({ loading: false });
      }
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

  connectBacktestWS: (id, onComplete) => {
    get().stopPolling();

    const wsBase = import.meta.env.VITE_WS_URL?.replace('/ws/signals/', '') || 'ws://localhost:8000';
    const wsUrl = `${wsBase}/ws/backtest/${id}/`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      set({ taskStatus: 'RUNNING' });
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'progress') {
          set((state) => {
            const current = state.currentBacktest;
            if (!current || current.id !== data.id) return {};

            const updatedLog = [...(current.progress_log || []), data.log_entry];
            return {
              currentBacktest: {
                ...current,
                progress_pct: data.progress_pct,
                progress_log: updatedLog,
                status: data.status,
              },
              taskStatus: data.status,
            };
          });
        }

        if (data.type === 'completed') {
          set((state) => ({
            taskStatus: 'COMPLETED',
            backtests: state.backtests.map(b => b.id === data.id ? { ...b, status: 'COMPLETED' } : b),
          }));
          if (onComplete) {
            api.get(`/backtest/${id}/`).then(res => onComplete(res.data));
          }
          ws.close();
        }

        if (data.type === 'failed') {
          set((state) => ({
            taskStatus: 'FAILED',
            error: data.error || 'Backtest failed',
            backtests: state.backtests.map(b => b.id === data.id ? { ...b, status: 'FAILED' } : b),
          }));
          ws.close();
        }
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    ws.onerror = (err) => {
      console.warn('Backtest WS error:', err);
    };

    ws.onclose = () => {
      set({ backtestWS: null });
    };

    set({ backtestWS: ws });
  },

  stopPolling: () => {
    const { backtestWS } = get();
    if (backtestWS) {
      backtestWS.close();
      set({ backtestWS: null });
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
