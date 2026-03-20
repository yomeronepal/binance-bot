import React, { useEffect, useState } from 'react';
import { BarChart3, Activity } from 'lucide-react';
import axios from 'axios';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Legend, LineChart, Line, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, ScatterChart, Scatter,
  ComposedChart
} from 'recharts';

const Card = ({ title, subtitle, children }) => (
  <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-5 shadow-sm">
    <div className="mb-4">
      <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{title}</h3>
      {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
    </div>
    {children}
  </div>
);

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 shadow-lg text-sm">
      <p className="font-medium text-gray-900 dark:text-white mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="text-xs">
          {p.name}: {typeof p.value === 'number' ? (p.name.includes('%') || p.name.includes('Rate') ? `${p.value.toFixed(1)}%` : `$${p.value.toFixed(2)}`) : p.value}
        </p>
      ))}
    </div>
  );
};

const EquityCurve = ({ data }) => {
  if (!data?.length) return null;
  const min = Math.min(...data.map(d => d.cumulative_pnl));
  const max = Math.max(...data.map(d => d.cumulative_pnl));
  const isPositive = data[data.length - 1]?.cumulative_pnl >= 0;

  return (
    <Card title="Equity Curve" subtitle="Cumulative P/L over time">
      <ResponsiveContainer width="100%" height={350}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="eqGreen" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="eqRed" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
          <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#9ca3af' }} tickFormatter={(v) => v.slice(5)} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => `$${v}`} domain={[min - 10, max + 10]} />
          <Tooltip content={<Tip />} />
          <Area type="monotone" dataKey="cumulative_pnl" name="Cumulative P/L"
            stroke={isPositive ? '#10b981' : '#ef4444'} fill={isPositive ? 'url(#eqGreen)' : 'url(#eqRed)'} strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  );
};

const DailyPnlBars = ({ data }) => {
  if (!data?.length) return null;
  const last30 = data.slice(-30);
  return (
    <Card title="Daily P/L" subtitle="Last 30 trading days">
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={last30}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
          <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#9ca3af' }} tickFormatter={(v) => v.slice(5)} />
          <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => `$${v}`} />
          <Tooltip content={<Tip />} />
          <Bar dataKey="pnl" name="Daily P/L" radius={[4, 4, 0, 0]}>
            {last30.map((e, i) => <Cell key={i} fill={e.pnl >= 0 ? '#10b981' : '#ef4444'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
};

const WinLossDonut = ({ wins, losses }) => {
  if (!wins && !losses) return null;
  const total = wins + losses;
  const data = [
    { name: 'Wins', value: wins, pct: ((wins / total) * 100).toFixed(1) },
    { name: 'Losses', value: losses, pct: ((losses / total) * 100).toFixed(1) },
  ];
  return (
    <Card title="Win / Loss Ratio">
      <ResponsiveContainer width="100%" height={250}>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={4} dataKey="value"
            label={({ name, pct }) => `${name} ${pct}%`} labelLine={{ stroke: '#6b7280' }}>
            <Cell fill="#10b981" />
            <Cell fill="#ef4444" />
          </Pie>
          <Tooltip formatter={(v, name) => [`${v} trades`, name]} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex justify-center gap-8 mt-2 text-sm">
        <span className="text-green-500 font-semibold">{wins} Wins</span>
        <span className="text-red-500 font-semibold">{losses} Losses</span>
        <span className="text-gray-400">{total} Total</span>
      </div>
    </Card>
  );
};

const SymbolPnlChart = ({ data }) => {
  if (!data?.length) return null;
  const top = data.slice(0, 10);
  return (
    <Card title="Top Symbols by P/L" subtitle="Top 10 performing symbols">
      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={top} layout="vertical" margin={{ left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
          <XAxis type="number" tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => `$${v}`} />
          <YAxis type="category" dataKey="symbol" tick={{ fontSize: 11, fill: '#9ca3af' }} width={85} />
          <Tooltip content={<Tip />} />
          <Bar dataKey="pnl" name="P/L" radius={[0, 4, 4, 0]}>
            {top.map((e, i) => <Cell key={i} fill={e.pnl >= 0 ? '#10b981' : '#ef4444'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
};

const SymbolWinRateChart = ({ data }) => {
  if (!data?.length) return null;
  const filtered = data.filter(s => s.total >= 3).slice(0, 15);
  if (!filtered.length) return null;
  return (
    <Card title="Win Rate by Symbol" subtitle="Symbols with 3+ trades">
      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={filtered} layout="vertical" margin={{ left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
          <XAxis type="number" tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => `${v}%`} domain={[0, 100]} />
          <YAxis type="category" dataKey="symbol" tick={{ fontSize: 11, fill: '#9ca3af' }} width={85} />
          <Tooltip content={<Tip />} />
          <Bar dataKey="win_rate" name="Win Rate %" radius={[0, 4, 4, 0]}>
            {filtered.map((e, i) => <Cell key={i} fill={e.win_rate >= 50 ? '#10b981' : e.win_rate >= 35 ? '#f59e0b' : '#ef4444'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
};

const DirectionCompare = ({ data }) => {
  if (!data?.length) return null;
  return (
    <Card title="LONG vs SHORT Performance">
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
          <XAxis dataKey="direction" tick={{ fontSize: 13, fill: '#9ca3af', fontWeight: 600 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => `${v}%`} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => `$${v}`} />
          <Tooltip content={<Tip />} />
          <Legend />
          <Bar yAxisId="left" dataKey="win_rate" name="Win Rate %" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={40} />
          <Bar yAxisId="right" dataKey="pnl" name="P/L $" radius={[4, 4, 0, 0]} barSize={40}>
            {data.map((e, i) => <Cell key={i} fill={e.pnl >= 0 ? '#10b981' : '#ef4444'} />)}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </Card>
  );
};

const PriorityCompare = ({ data }) => {
  if (!data) return null;
  const chartData = [
    { name: 'Priority', win_rate: data.priority?.win_rate || 0, pnl: data.priority?.pnl || 0, trades: data.priority?.total || 0 },
    { name: 'Non-Priority', win_rate: data.non_priority?.win_rate || 0, pnl: data.non_priority?.pnl || 0, trades: data.non_priority?.total || 0 },
  ];
  return (
    <Card title="Priority vs Non-Priority">
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
          <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#9ca3af' }} />
          <YAxis yAxisId="left" tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => `${v}%`} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => `$${v}`} />
          <Tooltip content={<Tip />} />
          <Legend />
          <Bar yAxisId="left" dataKey="win_rate" name="Win Rate %" fill="#8b5cf6" radius={[4, 4, 0, 0]} barSize={40} />
          <Bar yAxisId="right" dataKey="pnl" name="P/L $" radius={[4, 4, 0, 0]} barSize={40}>
            {chartData.map((e, i) => <Cell key={i} fill={e.pnl >= 0 ? '#10b981' : '#ef4444'} />)}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </Card>
  );
};

const TradesPerDayChart = ({ data }) => {
  if (!data?.length) return null;
  const last30 = data.slice(-30);
  return (
    <Card title="Trades Per Day" subtitle="Daily trade count with win rate">
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart data={last30}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
          <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#9ca3af' }} tickFormatter={(v) => v.slice(5)} />
          <YAxis yAxisId="left" tick={{ fontSize: 11, fill: '#9ca3af' }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => `${v}%`} domain={[0, 100]} />
          <Tooltip content={<Tip />} />
          <Legend />
          <Bar yAxisId="left" dataKey="trades" name="Trades" fill="#3b82f6" radius={[4, 4, 0, 0]} opacity={0.7} />
          <Line yAxisId="right" type="monotone" dataKey="win_pct" name="Win Rate %" stroke="#f59e0b" strokeWidth={2} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </Card>
  );
};

const TradeCharts = ({ apiUrl, useAuth = false, filters = {} }) => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
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
    fetchReport();
  }, [apiUrl, JSON.stringify(filters)]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Activity className="w-8 h-8 text-blue-500 animate-pulse" />
        <span className="ml-3 text-gray-500">Loading charts...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-lg p-8 text-center">
        <p className="text-red-600 dark:text-red-400">Failed to load charts: {error}</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-12 text-center shadow-sm">
        <BarChart3 className="w-16 h-16 text-gray-400 dark:text-gray-600 mx-auto mb-4" />
        <p className="text-gray-600 dark:text-gray-400 text-lg">No chart data available</p>
      </div>
    );
  }

  const { overall, by_symbol, by_direction, by_priority, daily_pnl } = report;

  const dailyWithWinPct = daily_pnl?.map(d => ({
    ...d,
    win_pct: d.trades > 0 ? parseFloat(((d.wins / d.trades) * 100).toFixed(1)) : 0,
  })) || [];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <EquityCurve data={daily_pnl} />
        <DailyPnlBars data={daily_pnl} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <WinLossDonut wins={overall?.profitable_trades || 0} losses={overall?.losing_trades || 0} />
        <DirectionCompare data={by_direction} />
        <PriorityCompare data={by_priority} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SymbolPnlChart data={by_symbol} />
        <SymbolWinRateChart data={by_symbol} />
      </div>

      <TradesPerDayChart data={dailyWithWinPct} />
    </div>
  );
};

export default TradeCharts;
