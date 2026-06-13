import React, { useEffect, useCallback } from 'react';
import { Signal as SignalIcon, RefreshCw } from 'lucide-react';
import useDayTradeStore from '../store/useDayTradeStore';
import DayTradeSignalCard from '../components/signals/DayTradeSignalCard';

const DayTradeSignals = () => {
  const { signals, summary, loading, error, fetchAll } = useDayTradeStore();
  const refresh = useCallback(() => { fetchAll(); }, [fetchAll]);
  const confPct = summary?.min_confidence != null ? Math.round(summary.min_confidence * 100) : 70;

  useEffect(() => {
    refresh();
    const interval = setInterval(() => { if (!document.hidden) refresh(); }, 30000);
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gradient-to-br dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 px-4 py-4 sm:p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-gradient-to-br from-indigo-100 to-cyan-100 dark:from-indigo-500/20 dark:to-cyan-500/20 rounded-lg border border-indigo-300 dark:border-indigo-500/50">
              <SignalIcon className="w-7 h-7 text-indigo-500 dark:text-indigo-400" />
            </div>
            <div>
              <h1 className="text-xl sm:text-3xl font-bold text-gray-900 dark:text-white">Day Trading Signals</h1>
              <p className="text-gray-600 dark:text-gray-400 text-xs sm:text-base">15m Market Structure Pullback · signals ≥{confPct}% confidence</p>
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
            <p className="text-gray-500 dark:text-gray-400">No signals above {confPct}% confidence yet</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {signals.map((s) => (
              <DayTradeSignalCard key={s.id} signal={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DayTradeSignals;
