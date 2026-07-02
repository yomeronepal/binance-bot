import { create } from 'zustand';
import axios from 'axios';

const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const useDayTradeStore = create((set) => ({
  summary: null,
  positions: [],
  trades: [],
  signals: [],
  loading: false,
  error: null,

  fetchAll: async () => {
    set({ loading: true, error: null });
    try {
      const [summaryRes, positionsRes, tradesRes, signalsRes] = await Promise.all([
        axios.get(`${baseURL}/daytrade/summary/`),
        axios.get(`${baseURL}/daytrade/positions/`),
        axios.get(`${baseURL}/daytrade/trades/?page_size=25`),
        axios.get(`${baseURL}/daytrade/signals/?status=ACTIVE&page_size=100`),
      ]);
      const rawSignals = signalsRes.data?.results || [];
      const seenSymbols = new Set();
      const dedupedSignals = rawSignals.filter((s) => {
        if (seenSymbols.has(s.symbol)) return false;
        seenSymbols.add(s.symbol);
        return true;
      });
      set({
        summary: summaryRes.data,
        positions: positionsRes.data?.positions || [],
        trades: tradesRes.data?.results || [],
        signals: dedupedSignals,
        loading: false,
      });
    } catch (err) {
      set({ error: err.response?.data?.detail || err.message, loading: false });
    }
  },
}));

export default useDayTradeStore;
