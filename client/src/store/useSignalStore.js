/**
 * Trading signals state management with Zustand and WebSocket support
 */
import { create } from 'zustand';
import { signalService } from '../services/signalService';

export const useSignalStore = create((set, get) => ({
  // State
  signals: [],
  futuresSignals: [],
  currentSignal: null,
  isLoading: false,
  error: null,
  spotSymbolsCount: 0,
  futuresSymbolsCount: 0,
  filters: {
    direction: 'ALL',
    timeframe: 'ALL',
    minConfidence: 0,
    symbol: '',
    status: 'ACTIVE',
  },
  sortBy: 'created_at',
  sortOrder: 'desc',

  // WebSocket state
  wsConnected: false,
  lastUpdate: null,

  /**
   * Set filters
   */
  setFilters: (newFilters) => {
    set({ filters: { ...get().filters, ...newFilters } });
  },

  /**
   * Set sorting
   */
  setSorting: (sortBy, sortOrder) => {
    set({ sortBy, sortOrder });
  },

  /**
   * Get filtered and sorted signals
   */
  getFilteredSignals: () => {
    const { signals, filters, sortBy, sortOrder } = get();

    let filtered = [...signals];

    // Apply filters
    if (filters.direction !== 'ALL') {
      filtered = filtered.filter((s) => s.direction === filters.direction);
    }

    if (filters.timeframe !== 'ALL') {
      filtered = filtered.filter((s) => s.timeframe === filters.timeframe);
    }

    if (filters.minConfidence > 0) {
      filtered = filtered.filter((s) => s.confidence >= filters.minConfidence);
    }

    if (filters.symbol) {
      filtered = filtered.filter((s) =>
        s.symbol_detail?.symbol?.toLowerCase().includes(filters.symbol.toLowerCase())
      );
    }

    if (filters.status) {
      filtered = filtered.filter((s) => s.status === filters.status);
    }

    // Apply sorting
    filtered.sort((a, b) => {
      let aVal, bVal;

      switch (sortBy) {
        case 'confidence':
          aVal = a.confidence;
          bVal = b.confidence;
          break;
        case 'created_at':
          aVal = new Date(a.created_at);
          bVal = new Date(b.created_at);
          break;
        case 'entry':
          aVal = parseFloat(a.entry);
          bVal = parseFloat(b.entry);
          break;
        case 'profit_percentage':
          aVal = a.profit_percentage || 0;
          bVal = b.profit_percentage || 0;
          break;
        case 'risk_reward_ratio':
          aVal = a.risk_reward_ratio || 0;
          bVal = b.risk_reward_ratio || 0;
          break;
        default:
          aVal = a[sortBy];
          bVal = b[sortBy];
      }

      if (sortOrder === 'asc') {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });

    return filtered;
  },

  /**
   * Fetch all signals from API
   */
  fetchSignals: async (params = {}) => {
    set({ isLoading: true, error: null });
    try {
      const data = await signalService.getAll({ ...params, market_type: 'SPOT' });
      set({ signals: data.results || data, isLoading: false });
    } catch (error) {
      set({
        error: error.response?.data?.detail || 'Failed to fetch signals',
        isLoading: false,
      });
    }
  },

  /**
   * Fetch futures signals from API
   */
  fetchFuturesSignals: async (params = {}) => {
    set({ isLoading: true, error: null });
    try {
      const data = await signalService.getAll({ ...params, market_type: 'FUTURES' });
      set({ futuresSignals: data.results || data, isLoading: false });
    } catch (error) {
      set({
        error: error.response?.data?.detail || 'Failed to fetch futures signals',
        isLoading: false,
      });
    }
  },

  /**
   * Fetch spot symbols count
   */
  fetchSpotSymbolsCount: async () => {
    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
      const response = await fetch(`${API_URL}/symbols/?market_type=SPOT`);
      const data = await response.json();
      set({ spotSymbolsCount: data.count || 0 });
    } catch (error) {
      console.error('Failed to fetch spot symbols count:', error);
    }
  },

  /**
   * Fetch futures symbols count
   */
  fetchFuturesSymbolsCount: async () => {
    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
      const response = await fetch(`${API_URL}/symbols/?market_type=FUTURES`);
      const data = await response.json();
      set({ futuresSymbolsCount: data.count || 0 });
    } catch (error) {
      console.error('Failed to fetch futures symbols count:', error);
    }
  },

  /**
   * Fetch signal by ID
   */
  fetchSignalById: async (id) => {
    set({ isLoading: true, error: null });
    try {
      const data = await signalService.getById(id);
      set({ currentSignal: data, isLoading: false });
    } catch (error) {
      set({
        error: error.response?.data?.detail || 'Failed to fetch signal',
        isLoading: false,
      });
    }
  },

  // ==================== WebSocket Handlers ====================

  /**
   * Handle WebSocket connection status
   */
  setWsConnected: (connected) => {
    set({ wsConnected: connected });
  },

  /**
   * Handle new signal from WebSocket (signal_created)
   */
  handleSignalCreated: (signal) => {
    const { signals, futuresSignals } = get();
    const marketType = signal.market_type || 'SPOT';

    if (marketType === 'FUTURES') {
      // Check if futures signal already exists
      const exists = futuresSignals.some((s) => s.id === signal.id);
      if (!exists) {
        set({
          futuresSignals: [signal, ...futuresSignals],
          lastUpdate: new Date().toISOString(),
        });
      }
    } else {
      // Check if spot signal already exists
      const exists = signals.some((s) => s.id === signal.id);
      if (!exists) {
        set({
          signals: [signal, ...signals],
          lastUpdate: new Date().toISOString(),
        });
      }
    }
  },

  /**
   * Handle signal update from WebSocket (signal_updated)
   */
  handleSignalUpdated: (updatedSignal) => {
    const { signals, futuresSignals, currentSignal } = get();
    const marketType = updatedSignal.market_type || 'SPOT';

    if (marketType === 'FUTURES') {
      // Update in futures signals list
      const updatedFuturesSignals = futuresSignals.map((signal) =>
        signal.id === updatedSignal.id ? updatedSignal : signal
      );

      // Update current signal if it's the same
      const newCurrentSignal =
        currentSignal?.id === updatedSignal.id ? updatedSignal : currentSignal;

      set({
        futuresSignals: updatedFuturesSignals,
        currentSignal: newCurrentSignal,
        lastUpdate: new Date().toISOString(),
      });
    } else {
      // Update in spot signals list
      const updatedSignals = signals.map((signal) =>
        signal.id === updatedSignal.id ? updatedSignal : signal
      );

      // Update current signal if it's the same
      const newCurrentSignal =
        currentSignal?.id === updatedSignal.id ? updatedSignal : currentSignal;

      set({
        signals: updatedSignals,
        currentSignal: newCurrentSignal,
        lastUpdate: new Date().toISOString(),
      });
    }
  },

  /**
   * Handle signal deletion from WebSocket (signal_deleted)
   */
  handleSignalDeleted: (signalId, marketType = 'SPOT') => {
    const { signals, futuresSignals, currentSignal } = get();

    if (marketType === 'FUTURES') {
      const updatedFuturesSignals = futuresSignals.filter((signal) => signal.id !== signalId);

      // Clear current signal if it's the deleted one
      const newCurrentSignal = currentSignal?.id === signalId ? null : currentSignal;

      set({
        futuresSignals: updatedFuturesSignals,
        currentSignal: newCurrentSignal,
        lastUpdate: new Date().toISOString(),
      });
    } else {
      const updatedSignals = signals.filter((signal) => signal.id !== signalId);

      // Clear current signal if it's the deleted one
      const newCurrentSignal = currentSignal?.id === signalId ? null : currentSignal;

      set({
        signals: updatedSignals,
        currentSignal: newCurrentSignal,
        lastUpdate: new Date().toISOString(),
      });
    }
  },

  /**
   * Handle signal status change from WebSocket
   */
  handleSignalStatusChanged: (data) => {
    const { signal, old_status, new_status } = data;
    get().handleSignalUpdated(signal);

    // You can add notifications here
    console.log(
      `Signal ${signal.id} status changed: ${old_status} → ${new_status}`
    );
  },

  /**
   * Handle active signals list (connection_established)
   */
  handleActiveSignals: (signalsData) => {
    set({
      signals: signalsData,
      lastUpdate: new Date().toISOString(),
    });
  },

  /**
   * Process WebSocket message
   */
  processWebSocketMessage: (message) => {
    const { type } = message;

    switch (type) {
      case 'connection_established':
        console.log('WebSocket connected:', message.user, message.subscription_tier);
        break;

      case 'active_signals':
        get().handleActiveSignals(message.signals);
        break;

      case 'signal_created':
        get().handleSignalCreated(message.signal);
        break;

      case 'signal_updated':
        get().handleSignalUpdated(message.signal);
        break;

      case 'signal_deleted':
        get().handleSignalDeleted(message.signal_id);
        break;

      case 'signal_status_changed':
        get().handleSignalStatusChanged(message);
        break;

      case 'signal_details':
        set({ currentSignal: message.signal });
        break;

      case 'pong':
        // Heartbeat response
        break;

      case 'error':
        console.error('WebSocket error:', message.message);
        set({ error: message.message });
        break;

      default:
        console.log('Unknown message type:', type, message);
    }
  },

  /**
   * Clear all signals
   */
  clearSignals: () => {
    set({ signals: [], futuresSignals: [], currentSignal: null });
  },

  /**
   * Clear error
   */
  clearError: () => {
    set({ error: null });
  },

  /**
   * Reset filters
   */
  resetFilters: () => {
    set({
      filters: {
        direction: 'ALL',
        timeframe: 'ALL',
        minConfidence: 0,
        symbol: '',
        status: 'ACTIVE',
      },
    });
  },
}));

export default useSignalStore;
