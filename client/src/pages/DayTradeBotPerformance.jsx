import React, { useEffect, useCallback } from 'react';
import {
  Activity, TrendingUp, TrendingDown, Target, Percent, DollarSign,
  RefreshCw, Layers, Clock,
} from 'lucide-react';
import useDayTradeStore from '../store/useDayTradeStore';

const fmt = (value, digits = 2) => {
  const num = Number(value);
  if (Number.isNaN(num)) return '-';
  return num.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
};

const signed = (value) => {
  const num = Number(value) || 0;
  return `${num >= 0 ? '+' : ''}${fmt(num)}`;
};

const pnlClass = (value) => (Number(value) >= 0 ? 'text-green-500' : 'text-red-500');

const StatCard = ({ icon: Icon, label, value, accent }) => (
  <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
    <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400 text-xs mb-2">
      <Icon className="w-4 h-4" />
      {label}
    </div>
    <div className={`text-2xl font-bold ${accent || 'text-gray-900 dark:text-white'}`}>{value}</div>
  </div>
);

const DirectionBadge = ({ direction }) => (
  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
    direction === 'LONG'
      ? 'bg-green-500/10 text-green-500'
      : 'bg-red-500/10 text-red-500'
  }`}>
    {direction === 'LONG' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
    {direction}
  </span>
);

const ScaleOutTag = ({ trade }) => (
  <div className="flex items-center gap-1">
    <span className={`px-1.5 py-0.5 rounded text-[10px] ${trade.tp1_filled ? 'bg-green-500/20 text-green-500' : 'bg-gray-500/10 text-gray-400'}`}>TP1</span>
    <span className={`px-1.5 py-0.5 rounded text-[10px] ${trade.tp2_filled ? 'bg-green-500/20 text-green-500' : 'bg-gray-500/10 text-gray-400'}`}>TP2</span>
    {trade.trailing_stop && (
      <span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-500/20 text-blue-400">TRAIL</span>
    )}
  </div>
);

const DayTradeBotPerformance = () => {
  const { summary, positions, trades, signals, loading, error, fetchAll } = useDayTradeStore();

  const refresh = useCallback(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
    refresh();
    const interval = setInterval(() => {
      if (!document.hidden) refresh();
    }, 30000);
    return () => clearInterval(interval);
  }, [refresh]);

  const roi = summary?.roi_percent ?? 0;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-gradient-to-br from-indigo-500/20 to-cyan-500/20 rounded-lg border border-indigo-500/40">
              <Activity className="w-7 h-7 text-indigo-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Day-Trade Bot</h1>
              <p className="text-gray-500 dark:text-gray-400 text-sm">15m Market Structure Pullback — paper trading</p>
            </div>
          </div>
          <button
            onClick={refresh}
            disabled={loading}
            className="flex items-center gap-2 bg-indigo-500 hover:bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-500 text-sm mb-4">{error}</div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
          <StatCard icon={Percent} label="ROI" value={`${signed(roi)}%`} accent={pnlClass(roi)} />
          <StatCard icon={DollarSign} label="Total P/L" value={`$${signed(summary?.total_profit_loss)}`} accent={pnlClass(summary?.total_profit_loss)} />
          <StatCard icon={Target} label="Win Rate" value={`${fmt(summary?.win_rate)}%`} />
          <StatCard icon={Layers} label="Open" value={summary?.open_trades ?? 0} />
          <StatCard icon={Activity} label="Closed Trades" value={summary?.total_trades ?? 0} />
          <StatCard icon={DollarSign} label="Balance" value={`$${fmt(summary?.account?.balance ?? summary?.initial_balance)}`} />
        </div>

        <Section title={`Open Positions (${positions.length})`}>
          {positions.length === 0 ? (
            <Empty label="No open positions" />
          ) : (
            <Table headers={['Symbol', 'Dir', 'Entry', 'Stop', 'TP1', 'TP2', 'Scale-out', 'Remaining', 'P/L']}>
              {positions.map((t) => (
                <tr key={t.id} className="border-t border-gray-100 dark:border-gray-700/50">
                  <Td className="font-medium">{t.symbol}</Td>
                  <Td><DirectionBadge direction={t.direction} /></Td>
                  <Td>{fmt(t.entry_price, 4)}</Td>
                  <Td>{fmt(t.trailing_stop || t.stop_loss, 4)}</Td>
                  <Td>{fmt(t.tp1_price, 4)}</Td>
                  <Td>{fmt(t.tp2_price, 4)}</Td>
                  <Td><ScaleOutTag trade={t} /></Td>
                  <Td>{fmt(t.remaining_quantity, 4)}</Td>
                  <Td className={pnlClass(t.profit_loss)}>{signed(t.profit_loss)}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Section>

        <Section title="Recent Trades">
          {trades.length === 0 ? (
            <Empty label="No trades yet" />
          ) : (
            <Table headers={['Symbol', 'Dir', 'Status', 'Entry', 'Exit', 'P/L', 'P/L %']}>
              {trades.map((t) => (
                <tr key={t.id} className="border-t border-gray-100 dark:border-gray-700/50">
                  <Td className="font-medium">{t.symbol}</Td>
                  <Td><DirectionBadge direction={t.direction} /></Td>
                  <Td><span className="text-xs text-gray-500 dark:text-gray-400">{t.status}</span></Td>
                  <Td>{fmt(t.entry_price, 4)}</Td>
                  <Td>{t.exit_price ? fmt(t.exit_price, 4) : '-'}</Td>
                  <Td className={pnlClass(t.profit_loss)}>{signed(t.profit_loss)}</Td>
                  <Td className={pnlClass(t.profit_loss_percentage)}>{signed(t.profit_loss_percentage)}%</Td>
                </tr>
              ))}
            </Table>
          )}
        </Section>

        <Section title="Recent Signals">
          {signals.length === 0 ? (
            <Empty label="No signals yet" />
          ) : (
            <Table headers={['Symbol', 'Dir', 'Entry', 'SL', 'TP1', 'TP2', 'Score', 'Status', 'Time']}>
              {signals.map((s) => (
                <tr key={s.id} className="border-t border-gray-100 dark:border-gray-700/50">
                  <Td className="font-medium">{s.symbol}</Td>
                  <Td><DirectionBadge direction={s.direction} /></Td>
                  <Td>{fmt(s.entry, 4)}</Td>
                  <Td>{fmt(s.stop_loss, 4)}</Td>
                  <Td>{fmt(s.tp1, 4)}</Td>
                  <Td>{fmt(s.tp2, 4)}</Td>
                  <Td>{fmt(s.score)}</Td>
                  <Td><span className="text-xs text-gray-500 dark:text-gray-400">{s.status}</span></Td>
                  <Td><span className="flex items-center gap-1 text-xs text-gray-500"><Clock className="w-3 h-3" />{s.created_at}</span></Td>
                </tr>
              ))}
            </Table>
          )}
        </Section>
      </div>
    </div>
  );
};

const Section = ({ title, children }) => (
  <div className="mb-6">
    <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">{title}</h2>
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden overflow-x-auto">
      {children}
    </div>
  </div>
);

const Table = ({ headers, children }) => (
  <table className="w-full text-sm">
    <thead>
      <tr className="text-left text-gray-500 dark:text-gray-400 text-xs">
        {headers.map((h) => <th key={h} className="px-3 py-2 font-medium whitespace-nowrap">{h}</th>)}
      </tr>
    </thead>
    <tbody className="text-gray-800 dark:text-gray-200">{children}</tbody>
  </table>
);

const Td = ({ children, className = '' }) => (
  <td className={`px-3 py-2 whitespace-nowrap ${className}`}>{children}</td>
);

const Empty = ({ label }) => (
  <div className="p-8 text-center text-gray-400 text-sm">{label}</div>
);

export default DayTradeBotPerformance;
