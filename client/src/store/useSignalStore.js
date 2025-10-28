/**
 * Trading signals state management with Zustand
 */
import { create } from 'zustand';
import { signalService } from '../services/signalService';

export const useSignalStore = create((set, get) => ({
  signals: [],
  currentSignal: null,
  isLoading: false,
  error: null,
  ws: null,
  isConnected: false,

  /**
   * Fetch all signals
   */
  fetchSignals: async (params) => {
    set({ isLoading: true, error: null });
    try {
      const data = await signalService.getAll(params);
      set({ signals: data.results || data, isLoading: false });
    } catch (error) {
      set({
        error: error.response?.data?.detail || 'Failed to fetch signals',
        isLoading: false
      });
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
        isLoading: false
      });
    }
  },

  /**
   * Create new signal
   */
  createSignal: async (signalData) => {
    set({ isLoading: true, error: null });
    try {
      const data = await signalService.create(signalData);
      set((state) => ({
        signals: [data, ...state.signals],
        isLoading: false
      }));
      return { success: true, data };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Failed to create signal';
      set({ error: errorMessage, isLoading: false });
      return { success: false, error: errorMessage };
    }
  },

  /**
   * Update signal
   */
  updateSignal: async (id, signalData) => {
    set({ isLoading: true, error: null });
    try {
      const data = await signalService.update(id, signalData);
      set((state) => ({
        signals: state.signals.map((signal) =>
          signal.id === id ? data : signal
        ),
        currentSignal: state.currentSignal?.id === id ? data : state.currentSignal,
        isLoading: false
      }));
      return { success: true, data };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Failed to update signal';
      set({ error: errorMessage, isLoading: false });
      return { success: false, error: errorMessage };
    }
  },

  /**
   * Delete signal
   */
  deleteSignal: async (id) => {
    set({ isLoading: true, error: null });
    try {
      await signalService.delete(id);
      set((state) => ({
        signals: state.signals.filter((signal) => signal.id !== id),
        isLoading: false
      }));
      return { success: true };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Failed to delete signal';
      set({ error: errorMessage, isLoading: false });
      return { success: false, error: errorMessage };
    }
  },

  /**
   * Connect to WebSocket for real-time updates
   */
  connectWebSocket: () => {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/signals/';
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      set({ isConnected: true });
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const { type, signal } = data;

      set((state) => {
        if (type === 'new_signal') {
          return { signals: [signal, ...state.signals] };
        } else if (type === 'update_signal') {
          return {
            signals: state.signals.map((s) =>
              s.id === signal.id ? signal : s
            )
          };
        } else if (type === 'delete_signal') {
          return {
            signals: state.signals.filter((s) => s.id !== signal.id)
          };
        }
        return state;
      });
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      set({ error: 'WebSocket connection error' });
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      set({ isConnected: false });
      // Attempt to reconnect after 5 seconds
      setTimeout(() => {
        if (get().ws) {
          get().connectWebSocket();
        }
      }, 5000);
    };

    set({ ws });
  },

  /**
   * Disconnect WebSocket
   */
  disconnectWebSocket: () => {
    const { ws } = get();
    if (ws) {
      ws.close();
      set({ ws: null, isConnected: false });
    }
  },

  /**
   * Add signal from WebSocket
   */
  addSignal: (signal) => {
    set((state) => ({
      signals: [signal, ...state.signals]
    }));
  },

  /**
   * Clear error
   */
  clearError: () => set({ error: null }),
}));

export default useSignalStore;
