import React, { useEffect, useCallback } from 'react';
import { Signal as SignalIcon, RefreshCw, TrendingUp, TrendingDown, Clock } from 'lucide-react';
import useDayTradeStore from '../store/useDayTradeStore';

const num = (v) => { const n = Number(v); return Number.isNaN(n) ? 0 : n; };
const fmt = (v, d = 2) => num(v).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });

const DirBadge = ({ direction }) => (
  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${direction === 'LONG' ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'}`}>
    {direction === 'LONG' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
    {direction}
  </span>
);

const DayTradeSignals = () => {
  const { signals, loading, error, fetchAll } = useDayTradeStore();
  const refresh = useCallback(() => { fetchAll(); }, [fetchAll]);

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
              <p className="text-gray-600 dark:text-gray-400 text-xs sm:text-base">15m Market Structure Pullback · signals ≥70% confidence</p>
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
            <p className="text-gray-500 dark:text-gray-400">No signals above 70% confidence yet</p>
          </div>
        ) : (
          <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden overflow-x-auto shadow-sm">
            <table className="w-full text-xs sm:text-sm">
              <thead className="bg-gray-100 dark:bg-gray-800/50">
                <tr>
                  {['Symbol', 'Dir', 'Entry', 'Stop', 'TP1', 'TP2', 'Conf', 'Score', 'Status', 'Time'].map((h, i) => (
                    <th key={h} className={`px-2 sm:px-4 py-2 sm:py-3 text-left text-[10px] sm:text-xs font-medium text-gray-600 dark:text-gray-400 uppercase ${[3, 4, 5, 7].includes(i) ? 'hidden md:table-cell' : ''} ${i === 9 ? 'hidden sm:table-cell' : ''}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {signals.map((s) => (
                  <tr key={s.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/30">
                    <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-900 dark:text-white font-medium">{s.symbol}</td>
                    <td className="px-2 sm:px-4 py-2 sm:py-3"><DirBadge direction={s.direction} /></td>
                    <td className="px-2 sm:px-4 py-2 sm:py-3 font-mono text-gray-700 dark:text-gray-300">{fmt(s.entry, 4)}</td>
                    <td className="px-2 sm:px-4 py-2 sm:py-3 font-mono text-gray-700 dark:text-gray-300 hidden md:table-cell">{fmt(s.stop_loss, 4)}</td>
                    <td className="px-2 sm:px-4 py-2 sm:py-3 font-mono text-gray-700 dark:text-gray-300 hidden md:table-cell">{fmt(s.tp1, 4)}</td>
                    <td className="px-2 sm:px-4 py-2 sm:py-3 font-mono text-gray-700 dark:text-gray-300 hidden md:table-cell">{fmt(s.tp2, 4)}</td>
                    <td className="px-2 sm:px-4 py-2 sm:py-3">
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-indigo-100 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 font-semibold">{(num(s.confidence) * 100).toFixed(0)}%</span>
                    </td>
                    <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-600 dark:text-gray-400 hidden md:table-cell">{fmt(s.score)}</td>
                    <td className="px-2 sm:px-4 py-2 sm:py-3"><span className="text-[10px] text-gray-500 dark:text-gray-400">{s.status}</span></td>
                    <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-500 hidden sm:table-cell"><span className="flex items-center gap-1"><Clock className="w-3 h-3" />{s.created_at}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default DayTradeSignals;
