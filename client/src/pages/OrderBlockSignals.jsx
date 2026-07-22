import React, { useEffect, useCallback, useState } from 'react';
import axios from 'axios';
import { Boxes, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';

const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const fmt = (v) => {
  const n = parseFloat(v);
  if (Number.isNaN(n)) return 'N/A';
  if (n >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (n >= 1) return n.toLocaleString(undefined, { maximumFractionDigits: 4 });
  return n.toLocaleString(undefined, { maximumFractionDigits: 8 });
};

const localTime = (t) => (t ? new Date(t).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—');

const STATUS_STYLES = {
  ACTIVE: 'bg-blue-500/20 text-blue-500',
  EXECUTED: 'bg-emerald-500/20 text-emerald-500',
  SKIPPED: 'bg-amber-500/20 text-amber-500',
  EXPIRED: 'bg-gray-400/20 text-gray-400',
};

const OrderBlockSignalCard = ({ signal }) => {
  const isLong = signal.direction === 'LONG';
  const DirIcon = isLong ? TrendingUp : TrendingDown;
  return (
    <div className={`bg-white dark:bg-gray-800/90 rounded-xl border ${isLong ? 'border-emerald-500/30' : 'border-rose-500/30'} p-4 space-y-3 shadow-sm`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-bold text-gray-900 dark:text-white truncate">{signal.symbol}</span>
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${isLong ? 'bg-emerald-500/20 text-emerald-500' : 'bg-rose-500/20 text-rose-500'}`}>
            <DirIcon className="w-3 h-3" />{signal.direction}
          </span>
          {signal.structure && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-500 font-semibold">{signal.structure}</span>
          )}
        </div>
        <span className={`text-[10px] px-1.5 py-0.5 rounded ${STATUS_STYLES[signal.status] || 'bg-gray-400/20 text-gray-400'}`}>{signal.status}</span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="p-2 bg-gray-50 dark:bg-gray-900/40 rounded-lg">
          <div className="text-[10px] text-gray-500 uppercase">Entry</div>
          <div className="text-sm font-bold text-gray-900 dark:text-white">{fmt(signal.entry)}</div>
        </div>
        <div className="p-2 bg-gray-50 dark:bg-gray-900/40 rounded-lg">
          <div className="text-[10px] text-gray-500 uppercase">Stop</div>
          <div className="text-sm font-bold text-rose-500">{fmt(signal.stop_loss)}</div>
        </div>
        <div className="p-2 bg-gray-50 dark:bg-gray-900/40 rounded-lg">
          <div className="text-[10px] text-gray-500 uppercase">Target</div>
          <div className="text-sm font-bold text-emerald-500">{fmt(signal.take_profit)}</div>
        </div>
      </div>
      <div className="flex items-center justify-between pt-2 border-t border-gray-200 dark:border-gray-700/50 text-xs text-gray-500 dark:text-gray-400">
        <span>R:R <span className="font-semibold text-gray-900 dark:text-white">1:{signal.risk_reward_ratio ?? '—'}</span></span>
        <span>Conf <span className="font-semibold text-gray-900 dark:text-white">{signal.confidence ?? '—'}</span></span>
        <span>{localTime(signal.created_at)}</span>
      </div>
    </div>
  );
};

const OrderBlockSignals = () => {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${baseURL}/order-block/signals/?page_size=100`);
      setSignals(res.data?.results || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(() => { if (!document.hidden) refresh(); }, 60000);
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gradient-to-br dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 px-4 py-4 sm:p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-gradient-to-br from-indigo-100 to-cyan-100 dark:from-indigo-500/20 dark:to-cyan-500/20 rounded-lg border border-indigo-300 dark:border-indigo-500/50">
              <Boxes className="w-7 h-7 text-indigo-500 dark:text-indigo-400" />
            </div>
            <div>
              <h1 className="text-xl sm:text-3xl font-bold text-gray-900 dark:text-white">Order Block Signals (4h)</h1>
              <p className="text-gray-600 dark:text-gray-400 text-xs sm:text-base">4h ICT order-block · break of structure · fixed 2R</p>
            </div>
          </div>
          <button onClick={refresh} disabled={loading} className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>

        {error && <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-500 text-sm mb-4">{error}</div>}

        {signals.length === 0 ? (
          <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-12 text-center shadow-sm">
            <p className="text-gray-500 dark:text-gray-400">No order-block signals detected yet — the engine scans at each 4h close.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {signals.map((s) => (
              <OrderBlockSignalCard key={s.id} signal={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default OrderBlockSignals;
