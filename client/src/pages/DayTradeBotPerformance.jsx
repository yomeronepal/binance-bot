import React, { useEffect, useState, useCallback } from 'react';
import {
  Bot, Activity, TrendingUp, TrendingDown, Target, Percent, DollarSign,
  RefreshCw, Wallet, BarChart3, Clock, Layers, Signal as SignalIcon,
} from 'lucide-react';
import useDayTradeStore from '../store/useDayTradeStore';

const num = (v) => {
  const n = Number(v);
  return Number.isNaN(n) ? 0 : n;
};
const fmt = (v, d = 2) => num(v).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
const signed = (v, d = 2) => `${num(v) >= 0 ? '+' : ''}${fmt(v, d)}`;

const DayTradeBotPerformance = () => {
  const { summary, positions, trades, signals, loading, error, fetchAll } = useDayTradeStore();
  const [activeTab, setActiveTab] = useState('overview');

  const refresh = useCallback(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
    refresh();
    const interval = setInterval(() => { if (!document.hidden) refresh(); }, 30000);
    return () => clearInterval(interval);
  }, [refresh]);

  const roi = num(summary?.roi_percent);
  const pnl = num(summary?.total_profit_loss);
  const balance = num(summary?.account?.balance ?? summary?.initial_balance);

  const stats = [
    { label: 'ROI', value: `${signed(roi)}%`, icon: Percent, color: roi >= 0 ? 'text-green-500' : 'text-red-500', bgGradient: 'from-green-500/10 to-emerald-500/10', subtext: 'Return on capital', isLive: true },
    { label: 'Total P/L', value: `$${signed(pnl)}`, icon: DollarSign, color: pnl >= 0 ? 'text-green-500' : 'text-red-500', bgGradient: 'from-blue-500/10 to-cyan-500/10', subtext: 'Realized profit/loss' },
    { label: 'Win Rate', value: `${fmt(summary?.win_rate)}%`, icon: Target, color: 'text-purple-500', bgGradient: 'from-purple-500/10 to-pink-500/10', subtext: `${summary?.profitable_trades ?? 0}W / ${summary?.losing_trades ?? 0}L` },
    { label: 'Open Positions', value: summary?.open_trades ?? 0, icon: Layers, color: 'text-amber-500', bgGradient: 'from-amber-500/10 to-orange-500/10', subtext: 'Currently running' },
    { label: 'Closed Trades', value: summary?.total_trades ?? 0, icon: BarChart3, color: 'text-blue-500', bgGradient: 'from-indigo-500/10 to-blue-500/10', subtext: 'Completed' },
    { label: 'Balance', value: `$${fmt(balance)}`, icon: Wallet, color: 'text-cyan-500', bgGradient: 'from-cyan-500/10 to-teal-500/10', subtext: 'Virtual account' },
  ];

  const tabs = [
    { key: 'overview', label: 'Overview' },
    { key: 'open', label: `Open (${positions.length})` },
    { key: 'history', label: 'History' },
    { key: 'signals', label: 'Signals', icon: SignalIcon },
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gradient-to-br dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 px-4 py-4 sm:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-gradient-to-br from-indigo-100 to-cyan-100 dark:from-indigo-500/20 dark:to-cyan-500/20 rounded-lg border border-indigo-300 dark:border-indigo-500/50">
                <Bot className="w-8 h-8 text-indigo-500 dark:text-indigo-400" />
              </div>
              <div>
                <h1 className="text-xl sm:text-3xl font-bold text-gray-900 dark:text-white">Day-Trade Bot</h1>
                <p className="text-gray-600 dark:text-gray-400 text-xs sm:text-base">15m Market Structure Pullback — automated paper trading</p>
              </div>
            </div>
            <button
              onClick={refresh}
              disabled={loading}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Refresh</span>
            </button>
          </div>

          {/* Info Banner */}
          <div className="bg-gradient-to-r from-indigo-50 to-cyan-50 dark:from-indigo-500/10 dark:to-cyan-500/10 border border-indigo-200 dark:border-indigo-500/30 rounded-lg p-3 sm:p-4">
            <p className="text-indigo-600 dark:text-indigo-300 text-xs sm:text-sm flex items-center flex-wrap gap-1">
              <Activity className="w-3.5 h-3.5 sm:w-4 sm:h-4 animate-pulse flex-shrink-0" />
              <span>Scans every minute · $100 margin · 10x leverage · TP1/TP2/runner exits · signals ≥70% confidence</span>
              <span className="px-1.5 py-0.5 bg-green-100 dark:bg-green-500/20 border border-green-300 dark:border-green-500/50 rounded text-[10px] sm:text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span>
                LIVE
              </span>
            </p>
          </div>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-500 text-sm mb-4">{error}</div>
        )}

        {/* Performance Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4 mb-8">
          {stats.map((stat, index) => (
            <div key={index} className="relative overflow-hidden bg-white dark:bg-gray-800/30 backdrop-blur-sm border border-gray-200 dark:border-gray-700 rounded-lg p-3 sm:p-6 hover:border-gray-300 dark:hover:border-gray-600 transition-all group shadow-sm">
              <div className={`absolute inset-0 bg-gradient-to-br ${stat.bgGradient} opacity-0 group-hover:opacity-100 transition-opacity`} />
              <div className="relative">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1 sm:gap-2">
                    <span className="text-gray-600 dark:text-gray-400 text-xs sm:text-sm truncate">{stat.label}</span>
                    {stat.isLive && (
                      <span className="flex items-center gap-1 px-2 py-0.5 bg-green-100 dark:bg-green-500/20 border border-green-300 dark:border-green-500/50 rounded text-xs text-green-600 dark:text-green-400">
                        <span className="w-1.5 h-1.5 bg-green-500 dark:bg-green-400 rounded-full animate-pulse"></span>
                        LIVE
                      </span>
                    )}
                  </div>
                  <stat.icon className={`w-5 h-5 ${stat.color}`} />
                </div>
                <div className={`text-lg sm:text-2xl font-bold ${stat.color} mb-1 truncate`}>{stat.value}</div>
                <div className="text-xs sm:text-sm text-gray-500 truncate">{stat.subtext}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="mb-6">
          <div className="flex overflow-x-auto no-scrollbar border-b border-gray-200 dark:border-gray-700">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex-shrink-0 px-4 sm:px-6 py-3 text-sm font-medium transition-all whitespace-nowrap flex items-center gap-1.5 ${activeTab === tab.key
                  ? 'text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-600 dark:border-indigo-400'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                  }`}
              >
                {tab.icon && <tab.icon className="w-4 h-4" />}
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Current Open Positions</h2>
              {positions.length > 0 ? (
                <div className="grid gap-3 sm:gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
                  {positions.slice(0, 6).map((p) => <PositionCard key={p.id} position={p} />)}
                </div>
              ) : <EmptyCard label="No open positions at the moment" />}
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Recent Closed Trades</h2>
              {trades.length > 0 ? (
                <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden shadow-sm">
                  <TradeHistoryTable trades={trades.slice(0, 10)} />
                </div>
              ) : <EmptyCard label="No closed trades yet" />}
            </div>
          </div>
        )}

        {activeTab === 'open' && (
          positions.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {positions.map((p) => <PositionCard key={p.id} position={p} />)}
            </div>
          ) : <EmptyCard label="No open positions" />
        )}

        {activeTab === 'history' && (
          trades.length > 0 ? (
            <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden shadow-sm">
              <TradeHistoryTable trades={trades} />
            </div>
          ) : <EmptyCard label="No trades yet" />
        )}

        {activeTab === 'signals' && (
          signals.length > 0 ? (
            <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden shadow-sm">
              <SignalsTable signals={signals} />
            </div>
          ) : <EmptyCard label="No signals above 70% confidence yet" />
        )}
      </div>
    </div>
  );
};

const DirBadge = ({ direction }) => (
  <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${direction === 'LONG' ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'}`}>
    {direction}
  </span>
);

const PositionCard = ({ position }) => {
  const pnl = num(position.profit_loss);
  const pnlPct = num(position.profit_loss_percentage);
  return (
    <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden hover:border-indigo-400 dark:hover:border-indigo-500/50 transition-all shadow-sm">
      <div className={`h-1 ${pnl >= 0 ? 'bg-green-500' : 'bg-red-500'}`} />
      <div className="p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
            <span className="text-gray-900 dark:text-white font-bold text-sm truncate">{position.symbol}</span>
            <DirBadge direction={position.direction} />
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400">FUT</span>
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            <span className={`px-1 py-0.5 rounded text-[9px] ${position.tp1_filled ? 'bg-green-500/20 text-green-500' : 'bg-gray-500/10 text-gray-400'}`}>TP1</span>
            <span className={`px-1 py-0.5 rounded text-[9px] ${position.tp2_filled ? 'bg-green-500/20 text-green-500' : 'bg-gray-500/10 text-gray-400'}`}>TP2</span>
            {position.trailing_stop && <span className="px-1 py-0.5 rounded text-[9px] bg-blue-500/20 text-blue-400">TRAIL</span>}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
          <Field label="Entry" value={fmt(position.entry_price, 4)} mono />
          <Field label="Stop" value={fmt(position.trailing_stop || position.stop_loss, 4)} mono />
          <Field label="TP1 / TP2" value={`${fmt(position.tp1_price, 2)} / ${fmt(position.tp2_price, 2)}`} mono />
          <Field label="Remaining" value={fmt(position.remaining_quantity, 4)} />
        </div>
        <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-200 dark:border-gray-700/50">
          <div className="text-right">
            <span className={`text-sm font-bold ${pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>{signed(pnl)}</span>
            <span className={`ml-1 text-[10px] ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>({signed(pnlPct, 1)}%)</span>
          </div>
          {position.entry_time && (
            <div className="flex items-center text-[10px] text-gray-500">
              <Clock className="w-3 h-3 mr-0.5" />
              {new Date(position.entry_time).toLocaleDateString([], { month: 'numeric', day: 'numeric' })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const Field = ({ label, value, mono }) => (
  <div>
    <span className="text-gray-500 dark:text-gray-500">{label}</span>
    <div className={`text-gray-900 dark:text-white text-xs ${mono ? 'font-mono' : ''}`}>{value}</div>
  </div>
);

const statusClass = (status) => {
  if (status === 'CLOSED_TP' || status === 'CLOSED_TRAIL') return 'bg-green-100 dark:bg-green-500/20 text-green-600';
  if (status === 'CLOSED_SL') return 'bg-red-100 dark:bg-red-500/20 text-red-600';
  if (status === 'CLOSED_MANUAL') return 'bg-yellow-100 dark:bg-yellow-500/20 text-yellow-600';
  return 'bg-gray-100 dark:bg-gray-500/20 text-gray-600';
};

const TradeHistoryTable = ({ trades }) => (
  <table className="w-full text-xs sm:text-sm">
    <thead className="bg-gray-100 dark:bg-gray-800/50">
      <tr>
        {['Symbol', 'Dir', 'Entry', 'Exit', 'P/L', 'Status', 'Date'].map((h, i) => (
          <th key={h} className={`px-2 sm:px-4 py-2 sm:py-3 text-left text-[10px] sm:text-xs font-medium text-gray-600 dark:text-gray-400 uppercase ${i === 3 ? 'hidden md:table-cell' : ''} ${i === 6 ? 'hidden sm:table-cell' : ''}`}>{h}</th>
        ))}
      </tr>
    </thead>
    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
      {trades.map((t) => {
        const pnl = num(t.profit_loss);
        return (
          <tr key={t.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/30">
            <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-900 dark:text-white font-medium">{t.symbol}</td>
            <td className="px-2 sm:px-4 py-2 sm:py-3"><DirBadge direction={t.direction} /></td>
            <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-700 dark:text-gray-300 font-mono">{fmt(t.entry_price, 4)}</td>
            <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-700 dark:text-gray-300 font-mono hidden md:table-cell">{t.exit_price ? fmt(t.exit_price, 4) : '-'}</td>
            <td className="px-2 sm:px-4 py-2 sm:py-3">
              <div className={`font-semibold ${pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>{signed(pnl)}</div>
              <div className={`text-[10px] ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>{signed(t.profit_loss_percentage, 1)}%</div>
            </td>
            <td className="px-2 sm:px-4 py-2 sm:py-3">
              <span className={`inline-block px-1.5 sm:px-2 py-0.5 sm:py-1 rounded text-[10px] sm:text-xs ${statusClass(t.status)}`}>
                {t.status?.replace('CLOSED_', '') || t.status}
              </span>
            </td>
            <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-500 hidden sm:table-cell">{t.entry_time ? new Date(t.entry_time).toLocaleDateString() : '-'}</td>
          </tr>
        );
      })}
    </tbody>
  </table>
);

const SignalsTable = ({ signals }) => (
  <table className="w-full text-xs sm:text-sm">
    <thead className="bg-gray-100 dark:bg-gray-800/50">
      <tr>
        {['Symbol', 'Dir', 'Entry', 'SL', 'TP1', 'TP2', 'Conf', 'Score', 'Status', 'Time'].map((h, i) => (
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
            <span className="px-1.5 py-0.5 rounded text-[10px] bg-indigo-100 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 font-semibold">
              {(num(s.confidence) * 100).toFixed(0)}%
            </span>
          </td>
          <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-600 dark:text-gray-400 hidden md:table-cell">{fmt(s.score)}</td>
          <td className="px-2 sm:px-4 py-2 sm:py-3"><span className="text-[10px] text-gray-500 dark:text-gray-400">{s.status}</span></td>
          <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-500 hidden sm:table-cell">{s.created_at}</td>
        </tr>
      ))}
    </tbody>
  </table>
);

const EmptyCard = ({ label }) => (
  <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-8 text-center shadow-sm">
    <p className="text-gray-600 dark:text-gray-400">{label}</p>
  </div>
);

export default DayTradeBotPerformance;
