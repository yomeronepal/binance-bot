import React, { useEffect, useState } from 'react';
import { BarChart3, Activity, Zap } from 'lucide-react';
import axios from 'axios';

const Card = ({ title, children, className = '' }) => (
  <div className={`bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-5 shadow-sm ${className}`}>
    <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-4">{title}</h3>
    {children}
  </div>
);

const Stat = ({ label, value, sub, positive }) => (
  <div className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
    <span className="text-sm text-gray-600 dark:text-gray-400">{label}</span>
    <div className="text-right">
      <span className={`text-sm font-semibold ${positive === undefined ? 'text-gray-900 dark:text-white' : positive ? 'text-green-500' : 'text-red-500'}`}>
        {value}
      </span>
      {sub && <div className="text-xs text-gray-400">{sub}</div>}
    </div>
  </div>
);

const Pnl = ({ value, prefix = '$' }) => {
  const v = parseFloat(value || 0);
  return (
    <span className={`font-semibold ${v >= 0 ? 'text-green-500' : 'text-red-500'}`}>
      {v >= 0 ? '+' : ''}{prefix}{v.toFixed(2)}
    </span>
  );
};

const TradeReport = ({ apiUrl, useAuth = false, filters = {} }) => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchReport = async () => {
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => {
        if (v && v !== 'ALL' && v !== 'all') params.append(k, v);
      });
      const qs = params.toString() ? `?${params.toString()}` : '';
      let res;
      if (useAuth) {
        const api = (await import('../../services/api')).default;
        res = await api.get(`${apiUrl}${qs}`);
      } else {
        const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
        res = await axios.get(`${baseURL}${apiUrl}${qs}`);
      }
      setReport(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.statusText || err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchReport(); }, [apiUrl, JSON.stringify(filters)]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Activity className="w-8 h-8 text-blue-500 animate-pulse" />
        <span className="ml-3 text-gray-500">Generating report...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-lg p-8 text-center">
        <p className="text-red-600 dark:text-red-400">Failed to load report: {error}</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-12 text-center shadow-sm">
        <BarChart3 className="w-16 h-16 text-gray-400 dark:text-gray-600 mx-auto mb-4" />
        <p className="text-gray-600 dark:text-gray-400 text-lg">No report data</p>
      </div>
    );
  }

  const { overall, by_symbol, by_direction, by_priority, daily_pnl, top_winners, top_losers, streaks } = report;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card title="Overall Performance">
          <Stat label="Total Trades" value={overall?.total_trades || 0} />
          <Stat label="Win Rate" value={`${(overall?.win_rate || 0).toFixed(1)}%`} positive={(overall?.win_rate || 0) >= 50} />
          <Stat label="Total P/L" value={<Pnl value={overall?.total_pnl ?? overall?.total_profit_loss} />} />
          <Stat label="Avg P/L" value={<Pnl value={overall?.avg_pnl ?? overall?.avg_profit_loss} />} />
          {overall?.unrealized_pnl !== undefined && (
            <Stat label="Unrealized P/L" value={<Pnl value={overall.unrealized_pnl} />} />
          )}
        </Card>

        <Card title="Best & Worst">
          <Stat label="Best Trade" value={<Pnl value={overall?.best_trade} />} />
          <Stat label="Worst Trade" value={<Pnl value={overall?.worst_trade} />} />
          {overall?.avg_duration_hours !== undefined && (
            <Stat label="Avg Duration" value={`${(overall.avg_duration_hours || 0).toFixed(1)}h`} />
          )}
          {overall?.max_drawdown !== undefined && (
            <Stat label="Max Drawdown" value={`$${(overall.max_drawdown || 0).toFixed(2)}`} positive={false} />
          )}
          <Stat label="Win Streak" value={streaks?.max_win || 0} positive={true} />
          <Stat label="Loss Streak" value={streaks?.max_loss || 0} positive={false} />
        </Card>

        <Card title="Priority vs Non-Priority">
          <Stat
            label="Priority"
            value={`${by_priority?.priority?.win_rate || 0}% WR`}
            sub={`${by_priority?.priority?.total || 0} trades | $${(by_priority?.priority?.pnl || 0).toFixed(2)}`}
            positive={(by_priority?.priority?.pnl || 0) >= 0}
          />
          <Stat
            label="Non-Priority"
            value={`${by_priority?.non_priority?.win_rate || 0}% WR`}
            sub={`${by_priority?.non_priority?.total || 0} trades | $${(by_priority?.non_priority?.pnl || 0).toFixed(2)}`}
            positive={(by_priority?.non_priority?.pnl || 0) >= 0}
          />
        </Card>

        <Card title="By Direction">
          {by_direction?.map((d) => (
            <Stat
              key={d.direction}
              label={d.direction}
              value={`${d.win_rate}% WR`}
              sub={`${d.total} trades | $${d.pnl?.toFixed(2)}`}
              positive={d.pnl >= 0}
            />
          ))}
          {report.by_timeframe?.map((t) => (
            <Stat
              key={t.timeframe}
              label={t.timeframe}
              value={`${t.win_rate}% WR`}
              sub={`${t.total} trades | $${t.pnl?.toFixed(2)}`}
              positive={t.pnl >= 0}
            />
          ))}
        </Card>
      </div>

      <Card title="Performance by Symbol">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 dark:text-gray-400 uppercase">
                <th className="pb-3 pr-4">Symbol</th>
                <th className="pb-3 pr-4">Trades</th>
                <th className="pb-3 pr-4">W/L</th>
                <th className="pb-3 pr-4">Win Rate</th>
                <th className="pb-3 pr-4">P/L</th>
                <th className="pb-3 pr-4">Avg</th>
                <th className="pb-3 pr-4">Best</th>
                <th className="pb-3">Worst</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
              {by_symbol?.slice(0, 20).map((s) => (
                <tr key={s.symbol} className="hover:bg-gray-50 dark:hover:bg-gray-800/30">
                  <td className="py-2 pr-4 font-medium text-gray-900 dark:text-white">{s.symbol}</td>
                  <td className="py-2 pr-4 text-gray-500">{s.total}</td>
                  <td className="py-2 pr-4 text-gray-500">{s.wins}/{s.losses}</td>
                  <td className="py-2 pr-4"><span className={s.win_rate >= 50 ? 'text-green-500' : 'text-red-500'}>{s.win_rate}%</span></td>
                  <td className="py-2 pr-4"><Pnl value={s.pnl} /></td>
                  <td className="py-2 pr-4 text-gray-500">${s.avg_pnl?.toFixed(2)}</td>
                  <td className="py-2 pr-4 text-green-500">+${s.best?.toFixed(2)}</td>
                  <td className="py-2 text-red-500">${s.worst?.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Top 5 Winners">
          {top_winners?.length > 0 ? top_winners.map((t, i) => (
            <div key={t.id} className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-gray-400 w-5">#{i + 1}</span>
                <span className="font-medium text-gray-900 dark:text-white text-sm">{t.symbol}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded ${t.direction === 'LONG' ? 'bg-green-100 dark:bg-green-500/20 text-green-600' : 'bg-red-100 dark:bg-red-500/20 text-red-600'}`}>
                  {t.direction}
                </span>
                {t.is_priority && <Zap className="w-3 h-3 text-amber-500" />}
              </div>
              <span className="text-green-500 font-semibold text-sm">+${t.profit_loss?.toFixed(2)}</span>
            </div>
          )) : <p className="text-sm text-gray-400">No winning trades yet</p>}
        </Card>

        <Card title="Top 5 Losers">
          {top_losers?.length > 0 ? top_losers.map((t, i) => (
            <div key={t.id} className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-gray-400 w-5">#{i + 1}</span>
                <span className="font-medium text-gray-900 dark:text-white text-sm">{t.symbol}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded ${t.direction === 'LONG' ? 'bg-green-100 dark:bg-green-500/20 text-green-600' : 'bg-red-100 dark:bg-red-500/20 text-red-600'}`}>
                  {t.direction}
                </span>
              </div>
              <span className="text-red-500 font-semibold text-sm">${t.profit_loss?.toFixed(2)}</span>
            </div>
          )) : <p className="text-sm text-gray-400">No losing trades yet</p>}
        </Card>
      </div>

      {daily_pnl?.length > 0 && (
        <Card title="Daily P/L">
          <div className="overflow-x-auto max-h-80 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white dark:bg-gray-800">
                <tr className="text-left text-xs text-gray-500 dark:text-gray-400 uppercase">
                  <th className="pb-2 pr-4">Date</th>
                  <th className="pb-2 pr-4">Trades</th>
                  <th className="pb-2 pr-4">Wins</th>
                  <th className="pb-2 pr-4">Daily P/L</th>
                  <th className="pb-2">Cumulative</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
                {daily_pnl.map((d) => (
                  <tr key={d.day}>
                    <td className="py-2 pr-4 text-gray-500">{d.day}</td>
                    <td className="py-2 pr-4 text-gray-500">{d.trades}</td>
                    <td className="py-2 pr-4 text-gray-500">{d.wins}</td>
                    <td className="py-2 pr-4"><Pnl value={d.pnl} /></td>
                    <td className="py-2"><Pnl value={d.cumulative_pnl} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
};

export default TradeReport;
