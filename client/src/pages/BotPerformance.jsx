import React, { useEffect, useState } from 'react';
import { Bot, TrendingUp, TrendingDown, Target, BarChart3, Clock, DollarSign, Percent, Activity, X, Calendar, Zap, RefreshCw, FileBarChart, LineChart, CirclePlay, Download, ChevronDown, FileText, FileSpreadsheet, FileJson, Shield, ShieldOff } from 'lucide-react';
import TradeReport from '../components/common/TradeReport';
import TradeCharts from '../components/common/TradeCharts';
import MarketRegimePanel from '../components/common/MarketRegimePanel';
import AssetClassBadge from '../components/common/AssetClassBadge';
import { lazy, Suspense } from 'react';
const LazyTradeReplay = lazy(() => import('../components/common/TradeReplay'));

const SafeTradeReplay = ({ tradeId, onClose }) => (
  <Suspense fallback={
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center">
      <div className="bg-gray-900 rounded-xl p-8 text-gray-300">Loading chart...</div>
    </div>
  }>
    <LazyTradeReplay tradeId={tradeId} onClose={onClose} />
  </Suspense>
);
import axios from 'axios';
import { useAuthStore } from '../store/useAuthStore';
import api from '../services/api';
import PullToRefresh from '../components/common/PullToRefresh';

export const DEFAULT_BOT_SOURCE = {
  title: 'Bot Performance',
  subtitle: 'Live tracking of all signals with automated paper trading',
  summaryUrl: '/public/paper-trading/summary/',
  positionsUrl: '/public/paper-trading/open-positions/',
  listUrl: '/public/paper-trading/',
  exportUrl: '/public/paper-trading/export/',
  reportUrl: '/public/paper-trading/report/',
  closeUrl: (id) => `/public/paper-trading/${id}/close/`,
  features: { filters: true, export: true, report: true, graphs: true, replay: true },
};

const BotPerformance = ({ source = DEFAULT_BOT_SOURCE }) => {
  const feat = source.features || {};
  const { user } = useAuthStore();
  const isSuperUser = user?.is_superuser;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [openPositions, setOpenPositions] = useState([]);
  const [recentTrades, setRecentTrades] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  const [replayTradeId, setReplayTradeId] = useState(null);
  const [activeWindow, setActiveWindow] = useState(() => {
    return localStorage.getItem('bot_perf_active_window') || 'all';
  });
  const [direction, setDirection] = useState(() => {
    return localStorage.getItem('bot_perf_direction') || 'ALL';
  });
  const [weekday, setWeekday] = useState(() => {
    return localStorage.getItem('bot_perf_weekday') || 'ALL';
  });
  const [hour, setHour] = useState(() => {
    return localStorage.getItem('bot_perf_hour') || 'ALL';
  });
  const [month, setMonth] = useState(() => {
    return localStorage.getItem('bot_perf_month') || 'ALL';
  });
  const [year, setYear] = useState(() => {
    return localStorage.getItem('bot_perf_year') || 'ALL';
  });
  const [totalTradesCount, setTotalTradesCount] = useState(0);
  const [exportOpen, setExportOpen] = useState(false);

  // Build the export URL with the same filter params the page is using.
  // Caller picks `format` (csv|json|xlsx). Returns an absolute URL so we can
  // either window.open() it or assign to <a download> for a clean filename.
  const buildExportUrl = (format) => {
    const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
    const params = new URLSearchParams();
    // 'fmt' rather than 'format' — DRF reserves '?format=' for content
    // negotiation and would short-circuit the request before our view runs.
    params.append('fmt', format);
    if (activeWindow === 'gw1') params.append('golden_window', 'true');
    if (activeWindow === 'gw2') params.append('golden_window_2', 'true');
    if (activeWindow === 'outside_gw') params.append('outside_golden_window', 'true');
    if (activeWindow === 'gw1_ai') params.append('gw1_ai', 'true');
    if (activeWindow === 'gw2_ai') params.append('gw2_ai', 'true');
    if (activeWindow === 'top') params.append('top_performer', 'true');
    if (activeWindow === 'macro_allow') params.append('macro_filter', 'allow');
    if (activeWindow === 'macro_block') params.append('macro_filter', 'block');
    if (direction !== 'ALL') params.append('direction', direction);
    if (weekday !== 'ALL') params.append('weekday', weekday);
    if (hour !== 'ALL') params.append('hour', hour);
    if (month !== 'ALL') params.append('month', month);
    if (year !== 'ALL') params.append('year', year);
    return `${baseURL}${source.exportUrl}?${params.toString()}`;
  };

  const handleExport = (format) => {
    setExportOpen(false);
    // window.open in a new tab triggers the browser's download flow because
    // the backend sets Content-Disposition: attachment.
    window.open(buildExportUrl(format), '_blank');
  };

  // Close the export menu on outside click.
  useEffect(() => {
    if (!exportOpen) return;
    const handler = (e) => {
      if (!e.target.closest('[data-export-menu]')) setExportOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [exportOpen]);

  useEffect(() => {
    localStorage.setItem('bot_perf_active_window', activeWindow);
  }, [activeWindow]);

  useEffect(() => {
    localStorage.setItem('bot_perf_direction', direction);
  }, [direction]);

  useEffect(() => {
    localStorage.setItem('bot_perf_weekday', weekday);
  }, [weekday]);

  useEffect(() => {
    localStorage.setItem('bot_perf_hour', hour);
  }, [hour]);

  useEffect(() => {
    localStorage.setItem('bot_perf_month', month);
  }, [month]);

  useEffect(() => {
    localStorage.setItem('bot_perf_year', year);
  }, [year]);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [tradesPerPage] = useState(20); // Show 20 trades per page
  const [positionsPerPage] = useState(12); // Show 12 positions per page

  // Reset pagination when switching tabs
  useEffect(() => {
    setCurrentPage(1);
  }, [activeTab]);

  const handleCloseTrade = async (tradeId) => {
    if (!window.confirm('ADMIN ACTION: Are you sure you want to CLOSE this trade immediately at market price?')) return;

    try {
      await api.post(source.closeUrl(tradeId));
      alert('Trade closed successfully by Admin.');
      fetchPerformanceData();
      fetchTradeHistory();
    } catch (err) {
      console.error(err);
      alert('Failed to close trade: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Fetch data ...


  // Fetch data without authentication - with LIVE prices
  // Fetch Summary and Open Positions (Fast)
  const fetchPerformanceData = async () => {
    try {
      if (!summary) setLoading(true); // Initial load
      const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

      // Build query params
      const params = new URLSearchParams();
      if (activeWindow === 'gw1') params.append('golden_window', 'true');
      if (activeWindow === 'gw2') params.append('golden_window_2', 'true');
      if (activeWindow === 'outside_gw') params.append('outside_golden_window', 'true');
      if (activeWindow === 'gw1_ai') params.append('gw1_ai', 'true');
      if (activeWindow === 'gw2_ai') params.append('gw2_ai', 'true');
      if (activeWindow === 'top') params.append('top_performer', 'true');
    if (activeWindow === 'macro_allow') params.append('macro_filter', 'allow');
    if (activeWindow === 'macro_block') params.append('macro_filter', 'block');
      if (direction !== 'ALL') params.append('direction', direction);
      if (weekday !== 'ALL') params.append('weekday', weekday);
      if (hour !== 'ALL') params.append('hour', hour);
      if (month !== 'ALL') params.append('month', month);
      if (year !== 'ALL') params.append('year', year);

      const queryParams = params.toString() ? `?${params.toString()}` : '';

      const [summaryRes, positionsRes] = await Promise.all([
        axios.get(`${baseURL}${source.summaryUrl}${queryParams}`),
        axios.get(`${baseURL}${source.positionsUrl}${queryParams}`)
      ]);

      const positionsData = positionsRes.data;
      setOpenPositions(positionsData.positions || []);

      if (summaryRes.data && positionsData) {
        const liveUnrealizedPnl = positionsData.total_unrealized_pnl || 0;
        const performanceData = summaryRes.data.performance || {};

        setSummary({
          ...summaryRes.data,
          performance: {
            ...performanceData,
            unrealized_pnl: liveUnrealizedPnl,
            total_pnl: (performanceData.total_profit_loss || 0) + liveUnrealizedPnl,
          },
          total_investment: positionsData.total_investment || 0,
          total_current_value: positionsData.total_current_value || 0,
          total_unrealized_pnl: liveUnrealizedPnl,
        });
      } else {
        setSummary(summaryRes.data);
      }
      setError(null);
    } catch (err) {
      console.error('Error fetching performance:', err);
      if (!summary) setError(err.message);
    } finally {
      if (!summary) setLoading(false);
    }
  };

  // Fetch Trade History (Paginated)
  const fetchTradeHistory = async () => {
    try {
      const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
      // Construct query params
      const params = new URLSearchParams();
      params.append('page', currentPage);
      if (activeWindow === 'gw1') params.append('golden_window', 'true');
      if (activeWindow === 'gw2') params.append('golden_window_2', 'true');
      if (activeWindow === 'outside_gw') params.append('outside_golden_window', 'true');
      if (activeWindow === 'gw1_ai') params.append('gw1_ai', 'true');
      if (activeWindow === 'gw2_ai') params.append('gw2_ai', 'true');
      if (activeWindow === 'top') params.append('top_performer', 'true');
    if (activeWindow === 'macro_allow') params.append('macro_filter', 'allow');
    if (activeWindow === 'macro_block') params.append('macro_filter', 'block');
      if (direction !== 'ALL') params.append('direction', direction);
      if (weekday !== 'ALL') params.append('weekday', weekday);
      if (hour !== 'ALL') params.append('hour', hour);
      if (month !== 'ALL') params.append('month', month);
      if (year !== 'ALL') params.append('year', year);

      const res = await axios.get(`${baseURL}${source.listUrl}?${params.toString()}`);

      // DRF Pagination returns { count: ..., results: ... }
      if (res.data.results) {
        setRecentTrades(res.data.results);
        setTotalTradesCount(res.data.count);
      } else {
        // Fallback if pagination disabled (legacy)
        setRecentTrades(res.data.trades || []);
        setTotalTradesCount(res.data.count || 0);
      }
    } catch (err) {
      console.error('Error fetching trades:', err);
    }
  };



  useEffect(() => {
    fetchPerformanceData();
  }, [activeWindow, direction, weekday, hour, month, year]);

  useEffect(() => {
    fetchTradeHistory();
  }, [activeWindow, direction, weekday, hour, month, year, currentPage]);

  // Show loading only on initial load (when summary is null)
  if (loading && !summary) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gradient-to-br dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 flex items-center justify-center">
        <div className="text-center">
          <Activity className="w-12 h-12 text-blue-500 dark:text-blue-400 animate-pulse mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading bot performance...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gradient-to-br dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-lg p-8 text-center">
            <p className="text-red-600 dark:text-red-400">Failed to load bot performance: {error}</p>
          </div>
        </div>
      </div>
    );
  }

  // Extract bot-wide performance metrics from API
  const botTotalPnl = parseFloat(summary?.bot_total_pnl || summary?.performance?.total_pnl || 0);
  const botWinRate = parseFloat(summary?.bot_win_rate || summary?.performance?.win_rate || 0);
  const botTotalTrades = parseInt(summary?.bot_total_trades || summary?.performance?.total_trades || 0);
  const botRealizedPnl = parseFloat(summary?.bot_realized_pnl || summary?.performance?.total_profit_loss || 0);
  const botUnrealizedPnl = parseFloat(summary?.bot_unrealized_pnl || summary?.total_unrealized_pnl || 0);
  const avgDuration = parseFloat(summary?.performance?.avg_duration_hours || 0);

  // For backward compatibility
  const performance = summary?.performance || {};
  const realizedPnl = botRealizedPnl;
  const unrealizedPnl = botUnrealizedPnl;
  const totalPnl = botTotalPnl;
  const winRate = botWinRate;
  const totalTrades = botTotalTrades;
  const openTradesCount = parseInt(summary?.open_trades_count || 0);
  const totalInvestment = parseFloat(summary?.total_investment || 0);
  const totalCurrentValue = parseFloat(summary?.total_current_value || 0);

  const stats = [
    {
      label: 'Total P/L (Live)',
      value: `${totalPnl >= 0 ? '+' : ''}$${Math.abs(totalPnl).toFixed(2)}`,
      subtext: `Realized: $${realizedPnl.toFixed(2)} | Unrealized: $${unrealizedPnl.toFixed(2)}`,
      icon: DollarSign,
      color: totalPnl >= 0 ? 'text-green-400' : 'text-red-400',
      bgGradient: totalPnl >= 0 ? 'from-green-500/20 to-green-600/10' : 'from-red-500/20 to-red-600/10',
      isLive: true,
    },
    {
      label: 'Win Rate',
      value: `${winRate.toFixed(1)}%`,
      subtext: `${performance.profitable_trades || 0}W / ${performance.losing_trades || 0}L`,
      icon: Target,
      color: winRate >= 50 ? 'text-green-400' : 'text-red-400',
      bgGradient: 'from-blue-500/20 to-purple-600/10',
    },
    {
      label: 'Portfolio Value (Live)',
      value: `$${totalCurrentValue.toFixed(2)}`,
      subtext: `Investment: $${totalInvestment.toFixed(2)} | ${openTradesCount} positions`,
      icon: Activity,
      color: totalCurrentValue >= totalInvestment ? 'text-green-400' : 'text-red-400',
      bgGradient: 'from-blue-500/20 to-cyan-600/10',
      isLive: true,
    },
    {
      label: 'Unrealized P/L (Live)',
      value: `${unrealizedPnl >= 0 ? '+' : ''}$${Math.abs(unrealizedPnl).toFixed(2)}`,
      subtext: `From ${openTradesCount} open positions`,
      icon: TrendingUp,
      color: unrealizedPnl >= 0 ? 'text-green-400' : 'text-red-400',
      bgGradient: unrealizedPnl >= 0 ? 'from-green-500/20 to-emerald-600/10' : 'from-red-500/20 to-orange-600/10',
      isLive: true,
    },
    {
      label: 'Realized P/L',
      value: `${realizedPnl >= 0 ? '+' : ''}$${Math.abs(realizedPnl).toFixed(2)}`,
      subtext: `From closed trades`,
      icon: TrendingDown,
      color: realizedPnl >= 0 ? 'text-green-400' : 'text-red-400',
      bgGradient: 'from-purple-500/20 to-pink-600/10',
    },
    {
      label: 'Total Signals',
      value: totalTrades,
      subtext: 'Tracked automatically',
      icon: BarChart3,
      color: 'text-purple-400',
      bgGradient: 'from-purple-500/20 to-pink-600/10',
    },
    {
      label: 'Avg Duration',
      value: `${avgDuration.toFixed(1)}h`,
      subtext: 'Average trade holding time',
      icon: Clock,
      color: 'text-indigo-400',
      bgGradient: 'from-indigo-500/20 to-blue-600/10',
    },
    {
      label: 'Max Drawdown',
      value: (() => {
        const drawdown = parseFloat(summary?.performance?.max_drawdown || 0);
        const totalPnl = parseFloat(summary?.performance?.total_profit_loss || 0);
        const initialCapital = 10000; // Default initial capital

        // Calculate peak capital (initial + total realized profit at peak)
        const peakCapital = initialCapital + Math.max(0, totalPnl);

        // Calculate drawdown percentage
        const drawdownPct = peakCapital > 0 ? (drawdown / peakCapital * 100) : 0;

        return drawdownPct > 0 ? `-${drawdownPct.toFixed(2)}%` : '0.00%';
      })(),
      subtext: 'Peak to trough decline',
      icon: TrendingDown,
      color: 'text-red-400',
      bgGradient: 'from-red-500/20 to-orange-600/10',
    },
  ];

  // Handle pull-to-refresh
  const handleRefresh = async () => {
    await Promise.all([
      fetchPerformanceData(),
      fetchTradeHistory()
    ]);
  };

  return (
    <PullToRefresh onRefresh={handleRefresh}>
    <div className="min-h-screen bg-gray-50 dark:bg-gradient-to-br dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 px-4 py-4 sm:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-3 bg-gradient-to-br from-blue-100 to-purple-100 dark:from-blue-500/20 dark:to-purple-500/20 rounded-lg border border-blue-300 dark:border-blue-500/50">
              <Bot className="w-8 h-8 text-blue-500 dark:text-blue-400" />
            </div>
            <div>
              <h1 className="text-xl sm:text-3xl font-bold text-gray-900 dark:text-white">{source.title}</h1>
              <p className="text-gray-600 dark:text-gray-400 text-xs sm:text-base">{source.subtitle}</p>
            </div>
          </div>

          {/* Info Banner */}
          <div className="bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-500/10 dark:to-purple-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-3 sm:p-4">
            <div className="flex items-start sm:items-center justify-between gap-2">
              <p className="text-blue-600 dark:text-blue-300 text-xs sm:text-sm flex items-center flex-wrap gap-1">
                <Activity className="w-3.5 h-3.5 sm:w-4 sm:h-4 animate-pulse flex-shrink-0" />
                <span>Auto paper trading $100 per signal</span>
                <span className="px-1.5 py-0.5 bg-green-100 dark:bg-green-500/20 border border-green-300 dark:border-green-500/50 rounded text-[10px] sm:text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span>
                  LIVE
                </span>
              </p>
            </div>
          </div>


          {/* New Trading Sessions & Filter Bar */}
          {feat.filters && (
          <div className="mt-6 mb-6 space-y-4">
            {/* BTC / equity / commodity macro filter readout — what the strict
                trade-time gate will say right now. Drives confidence in the
                Macro Allowed / Macro Blocked tabs and surfaces regime shifts. */}
            <MarketRegimePanel />

            {/* Golden Window Filter */}
            <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-2 bg-white dark:bg-gray-800 rounded-xl p-2 shadow-sm border border-gray-100 dark:border-gray-700">

              {/* Session Tabs */}
              <div className="flex items-center gap-1.5 sm:gap-2 overflow-x-auto w-full md:w-auto p-1 no-scrollbar">
                <button
                  onClick={() => setActiveWindow('all')}
                  className={`flex-shrink-0 px-2.5 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-medium rounded-lg transition-all ${activeWindow === 'all'
                    ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                    }`}
                >
                  All Trades
                </button>

                <button
                  onClick={() => setActiveWindow('gw1')}
                  className={`flex-shrink-0 px-2.5 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${activeWindow === 'gw1'
                    ? 'bg-amber-500 text-white shadow-md shadow-amber-500/20'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                    }`}
                >
                  <Clock className="w-4 h-4" />
                  GW 1
                </button>

                <button
                  onClick={() => setActiveWindow('gw2')}
                  title="Sun, Wed, Thu (21:00-23:00 NPT)"
                  className={`flex-shrink-0 px-2.5 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${activeWindow === 'gw2'
                    ? 'bg-purple-600 text-white shadow-md shadow-purple-500/20'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                    }`}
                >
                  <Clock className="w-4 h-4" />
                  GW 2
                </button>

                <button
                  onClick={() => setActiveWindow('outside_gw')}
                  className={`flex-shrink-0 px-2.5 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${activeWindow === 'outside_gw'
                    ? 'bg-gray-700 text-white shadow-md shadow-gray-500/20 dark:bg-gray-600'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                    }`}
                >
                  <Clock className="w-4 h-4" />
                  Outside GW
                </button>

                <span className="text-gray-300 dark:text-gray-600">|</span>

                <button
                  onClick={() => setActiveWindow('gw1_ai')}
                  title="Auto-optimized GW1 windows (all days, >= 60% win rate)"
                  className={`flex-shrink-0 px-2.5 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${activeWindow === 'gw1_ai'
                    ? 'bg-cyan-600 text-white shadow-md shadow-cyan-500/20'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                    }`}
                >
                  <Zap className="w-4 h-4" />
                  GW1 AI
                </button>

                <button
                  onClick={() => setActiveWindow('gw2_ai')}
                  title="Auto-optimized GW2 windows (specific days, >= 60% win rate)"
                  className={`flex-shrink-0 px-2.5 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${activeWindow === 'gw2_ai'
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/20'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                    }`}
                >
                  <Zap className="w-4 h-4" />
                  GW2 AI
                </button>

                <span className="text-gray-300 dark:text-gray-600">|</span>

                <button
                  onClick={() => setActiveWindow('top')}
                  title="Symbols in the latest top-10 performers snapshot"
                  className={`flex-shrink-0 px-2.5 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${activeWindow === 'top'
                    ? 'bg-amber-500 text-white shadow-md shadow-amber-500/20'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                    }`}
                >
                  <Zap className="w-4 h-4" />
                  Top Performers
                </button>

                <button
                  onClick={() => setActiveWindow('macro_allow')}
                  title="Only signals the BTC macro filter would have allowed"
                  className={`flex-shrink-0 px-2.5 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${activeWindow === 'macro_allow'
                    ? 'bg-emerald-600 text-white shadow-md shadow-emerald-500/20'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                    }`}
                >
                  <Shield className="w-4 h-4" />
                  Macro Allowed
                </button>

                <button
                  onClick={() => setActiveWindow('macro_block')}
                  title="Only signals the BTC macro filter would have blocked (analysis)"
                  className={`flex-shrink-0 px-2.5 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${activeWindow === 'macro_block'
                    ? 'bg-rose-600 text-white shadow-md shadow-rose-500/20'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                    }`}
                >
                  <ShieldOff className="w-4 h-4" />
                  Macro Blocked
                </button>
              </div>

              <div className="flex items-center gap-2 w-full md:w-auto">
                {/* Export dropdown — applies the page's current filters */}
                <div className="relative w-full md:w-auto" data-export-menu>
                  <button
                    type="button"
                    onClick={() => setExportOpen((v) => !v)}
                    title="Export the filtered trade history for offline analysis"
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 rounded-lg transition-colors w-full md:w-auto justify-center"
                  >
                    <Download className="w-4 h-4" />
                    Export
                    <ChevronDown className={`w-3.5 h-3.5 transition-transform ${exportOpen ? 'rotate-180' : ''}`} />
                  </button>

                  {exportOpen && (
                    <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-20 overflow-hidden">
                      <button
                        onClick={() => handleExport('csv')}
                        className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700/60 text-left"
                      >
                        <FileText className="w-4 h-4 text-gray-500" />
                        Export as CSV
                      </button>
                      <button
                        onClick={() => handleExport('xlsx')}
                        className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700/60 text-left"
                      >
                        <FileSpreadsheet className="w-4 h-4 text-emerald-500" />
                        Export as Excel
                      </button>
                      <button
                        onClick={() => handleExport('json')}
                        className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700/60 text-left"
                      >
                        <FileJson className="w-4 h-4 text-amber-500" />
                        Export as JSON
                      </button>
                      <div className="px-3 py-2 text-[10px] text-gray-500 dark:text-gray-400 border-t border-gray-100 dark:border-gray-700">
                        Uses current filters · max 50,000 rows
                      </div>
                    </div>
                  )}
                </div>

                {/* Refresh Button */}
                <button
                  onClick={() => { fetchPerformanceData(); fetchTradeHistory(); }}
                  disabled={loading}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors disabled:opacity-50 w-full md:w-auto justify-center"
                >
                  <Activity className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                  {loading ? 'Refreshing...' : 'Refresh Data'}
                </button>
              </div>
            </div>

            {/* Direction Filter + Top Performer toggle */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2 bg-white dark:bg-gray-800 rounded-xl p-2 shadow-sm border border-gray-100 dark:border-gray-700">
              <div className="flex items-center gap-2 overflow-x-auto no-scrollbar w-full p-1">
                {[
                  { val: 'ALL', label: 'All', color: 'blue' },
                  { val: 'LONG', label: 'LONG', color: 'green', icon: TrendingUp },
                  { val: 'SHORT', label: 'SHORT', color: 'red', icon: TrendingDown },
                ].map((d) => (
                  <button
                    key={d.val}
                    onClick={() => setDirection(d.val)}
                    className={`flex-shrink-0 px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-lg transition-all flex items-center gap-1.5 ${direction === d.val
                      ? `bg-${d.color}-600 text-white shadow-md`
                      : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                      }`}
                  >
                    {d.icon && <d.icon className="w-3.5 h-3.5" />}
                    {d.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Dropdowns Row */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <select
                value={weekday}
                onChange={(e) => setWeekday(e.target.value)}
                className="px-3 py-2 text-xs sm:text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
              >
                <option value="ALL">All Days</option>
                {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, index) => (
                  <option key={day} value={String(index + 1)}>{day}</option>
                ))}
              </select>

              <select
                value={hour}
                onChange={(e) => setHour(e.target.value)}
                className="px-3 py-2 text-xs sm:text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
              >
                <option value="ALL">All Hours</option>
                {Array.from({ length: 24 }, (_, i) => i).map((h) => (
                  <option key={h} value={String(h)}>{String(h).padStart(2, '0')}:00</option>
                ))}
              </select>

              <select
                value={month}
                onChange={(e) => setMonth(e.target.value)}
                className="px-3 py-2 text-xs sm:text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
              >
                <option value="ALL">All Months</option>
                {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].map((m, index) => (
                  <option key={m} value={String(index + 1)}>{m}</option>
                ))}
              </select>

              <select
                value={year}
                onChange={(e) => setYear(e.target.value)}
                className="px-3 py-2 text-xs sm:text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
              >
                <option value="ALL">All Years</option>
                {Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i).map((y) => (
                  <option key={y} value={String(y)}>{y}</option>
                ))}
              </select>
            </div>
          </div>
          )}
        </div>

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
            {[
              { key: 'overview', label: 'Overview' },
              { key: 'open', label: `Open (${openTradesCount})` },
              { key: 'history', label: 'History' },
              ...(feat.report ? [{ key: 'report', label: 'Report', icon: FileBarChart }] : []),
              ...(feat.graphs ? [{ key: 'graphs', label: 'Graphs', icon: LineChart }] : []),
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex-shrink-0 px-4 sm:px-6 py-3 text-sm font-medium transition-all whitespace-nowrap flex items-center gap-1.5 ${activeTab === tab.key
                  ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                  }`}
              >
                {tab.icon && <tab.icon className="w-4 h-4" />}
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        {
          activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Open Positions Summary */}
              <div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Current Open Positions</h2>
                {openPositions.length > 0 ? (
                  <div className="grid gap-3 sm:gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
                    {openPositions.slice(0, 6).map((position) => (
                      <PositionCard
                        key={position.trade_id}
                        position={position}
                        isSuperUser={isSuperUser}
                        onClose={isSuperUser ? () => handleCloseTrade(position.trade_id) : null}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-8 text-center shadow-sm">
                    <p className="text-gray-600 dark:text-gray-400">No open positions at the moment</p>
                  </div>
                )}
              </div>

              {/* Recent Closed Trades */}
              <div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Recent Closed Trades</h2>
                {recentTrades.length > 0 ? (
                  <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden shadow-sm">
                    <TradeHistoryTable trades={recentTrades.slice(0, 10)} onReplay={feat.replay ? setReplayTradeId : undefined} />
                  </div>
                ) : (
                  <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-8 text-center shadow-sm">
                    <p className="text-gray-600 dark:text-gray-400">No closed trades yet</p>
                  </div>
                )}
              </div>
            </div>
          )
        }

        {
          activeTab === 'open' && (
            <div>
              {openPositions.length > 0 ? (
                <>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 mb-4">
                    {openPositions
                      .slice(
                        (currentPage - 1) * positionsPerPage,
                        currentPage * positionsPerPage
                      )
                      .map((position) => (
                        <PositionCard
                          key={position.trade_id}
                          position={position}
                          isSuperUser={isSuperUser}
                          onClose={isSuperUser ? () => handleCloseTrade(position.trade_id) : null}
                        />
                      ))}
                  </div>

                  {/* Pagination Controls for Open Positions */}
                  {openPositions.length > positionsPerPage && (
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-2 px-3 sm:px-4 py-2 sm:py-3 bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm">
                      <div className="text-xs sm:text-sm text-gray-600 dark:text-gray-400">
                        {((currentPage - 1) * positionsPerPage) + 1}-{Math.min(currentPage * positionsPerPage, openPositions.length)} of {openPositions.length}
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                          disabled={currentPage === 1}
                          className="px-3 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-white rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          Previous
                        </button>
                        <span className="text-gray-800 dark:text-white text-xs sm:text-sm px-2 sm:px-4">
                          {currentPage}/ {Math.ceil(openPositions.length / positionsPerPage)}
                        </span>
                        <button
                          onClick={() => setCurrentPage(prev => Math.min(Math.ceil(openPositions.length / positionsPerPage), prev + 1))}
                          disabled={currentPage >= Math.ceil(openPositions.length / positionsPerPage)}
                          className="px-3 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-white rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          Next
                        </button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-12 text-center shadow-sm">
                  <Activity className="w-16 h-16 text-gray-400 dark:text-gray-600 mx-auto mb-4" />
                  <p className="text-gray-600 dark:text-gray-400 text-lg">No open positions</p>
                </div>
              )}
            </div>
          )
        }

        {
          activeTab === 'history' && (
            <div>
              {recentTrades.length > 0 ? (
                <>
                  <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden mb-4 shadow-sm">
                    <TradeHistoryTable
                      trades={recentTrades}
                      onReplay={feat.replay ? setReplayTradeId : undefined}
                    />
                  </div>

                  {/* Pagination Controls */}
                  {totalTradesCount > tradesPerPage && (
                    <div className="flex items-center justify-between px-4 py-3 bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm">
                      <div className="text-sm text-gray-600 dark:text-gray-400">
                        Showing {((currentPage - 1) * tradesPerPage) + 1} to {Math.min(currentPage * tradesPerPage, totalTradesCount)} of {totalTradesCount} trades
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                          disabled={currentPage === 1}
                          className="px-3 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-white rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          Previous
                        </button>
                        <span className="text-gray-800 dark:text-white text-xs sm:text-sm px-2 sm:px-4">
                          {currentPage}/ {Math.ceil(totalTradesCount / tradesPerPage)}
                        </span>
                        <button
                          onClick={() => setCurrentPage(prev => Math.min(Math.ceil(totalTradesCount / tradesPerPage), prev + 1))}
                          disabled={currentPage >= Math.ceil(totalTradesCount / tradesPerPage)}
                          className="px-3 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-white rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          Next
                        </button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-12 text-center shadow-sm">
                  <BarChart3 className="w-16 h-16 text-gray-400 dark:text-gray-600 mx-auto mb-4" />
                  <p className="text-gray-600 dark:text-gray-400 text-lg">No trade history yet</p>
                </div>
              )}
            </div>
          )
        }

        {activeTab === 'report' && (
          <TradeReport
            apiUrl="/public/paper-trading/report/"
            filters={{
              golden_window: activeWindow === 'gw1' ? 'true' : undefined,
              golden_window_2: activeWindow === 'gw2' ? 'true' : undefined,
              outside_golden_window: activeWindow === 'outside_gw' ? 'true' : undefined,
              gw1_ai: activeWindow === 'gw1_ai' ? 'true' : undefined,
              gw2_ai: activeWindow === 'gw2_ai' ? 'true' : undefined,
              direction: direction,
              weekday: weekday,
              hour: hour,
              month: month,
              year: year,
            }}
          />
        )}

        {activeTab === 'graphs' && (
          <TradeCharts
            apiUrl="/public/paper-trading/report/"
            filters={{
              golden_window: activeWindow === 'gw1' ? 'true' : undefined,
              golden_window_2: activeWindow === 'gw2' ? 'true' : undefined,
              outside_golden_window: activeWindow === 'outside_gw' ? 'true' : undefined,
              gw1_ai: activeWindow === 'gw1_ai' ? 'true' : undefined,
              gw2_ai: activeWindow === 'gw2_ai' ? 'true' : undefined,
              direction: direction,
              weekday: weekday,
              hour: hour,
              month: month,
              year: year,
            }}
          />
        )}
      </div >
    </div >
    {replayTradeId && (
      <SafeTradeReplay tradeId={replayTradeId} onClose={() => setReplayTradeId(null)} />
    )}
    </PullToRefresh>
  );
};

const formatPrice = (price) => {
  const p = parseFloat(price);
  if (p === 0) return '$0';
  if (p >= 1000) return `$${p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (p >= 1) return `$${p.toFixed(4)}`;
  if (p >= 0.01) return `$${p.toFixed(6)}`;
  return `$${p.toPrecision(4)}`;
};

const PositionCard = ({ position, isSuperUser, onClose }) => {
  const pnl = parseFloat(position.unrealized_pnl || 0);
  const pnlPct = parseFloat(position.unrealized_pnl_pct || 0);
  const priceChangePct = parseFloat(position.price_change_pct || 0);
  const hasLivePrice = position.has_real_time_price;

  return (
    <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden hover:border-blue-400 dark:hover:border-blue-500/50 transition-all shadow-sm relative group">
      <div className={`h-1 ${pnl >= 0 ? 'bg-green-500' : 'bg-red-500'}`} />

      {isSuperUser && onClose && (
        <button
          onClick={(e) => { e.stopPropagation(); onClose(); }}
          className="absolute top-3 right-2 p-1 bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 rounded opacity-0 group-hover:opacity-100 transition-opacity"
          title="Close Trade"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}

      <div className="p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
            <span className="text-gray-900 dark:text-white font-bold text-sm truncate">{position.symbol}</span>
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${position.direction === 'LONG' ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'}`}>
              {position.direction}
            </span>
            <AssetClassBadge assetClass={position.asset_class} />
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            {position.is_priority && <Zap className="w-3.5 h-3.5 text-amber-500" />}
            {position.is_neutral_reversal && <RefreshCw className="w-3.5 h-3.5 text-cyan-500" />}
            {hasLivePrice && <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />}
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${position.market_type === 'FUTURES' ? 'bg-purple-500/20 text-purple-400' : 'bg-blue-500/20 text-blue-400'}`}>
              {position.market_type === 'FUTURES' ? 'FUT' : 'SPOT'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
          <div>
            <span className="text-gray-500 dark:text-gray-500">Entry</span>
            <div className="text-gray-900 dark:text-white font-mono text-xs">{formatPrice(position.entry_price)}</div>
          </div>
          {position.confidence != null && (
            <div>
              <span className="text-gray-500 dark:text-gray-500">Confidence</span>
              <div className="text-indigo-600 dark:text-indigo-400 font-semibold text-xs">{(parseFloat(position.confidence) * 100).toFixed(0)}%</div>
            </div>
          )}
          {hasLivePrice && (
            <div>
              <span className="text-gray-500 dark:text-gray-500">Current</span>
              <div className="text-gray-900 dark:text-white font-mono text-xs">
                {formatPrice(position.current_price)}
                {priceChangePct !== 0 && (
                  <span className={`ml-1 text-[10px] ${priceChangePct >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    {priceChangePct >= 0 ? '+' : ''}{priceChangePct.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
          )}
          {position.take_profit != null && (
            <div>
              <span className="text-gray-500 dark:text-gray-500">TP</span>
              <div className="text-green-600 dark:text-green-400 font-mono text-xs">{formatPrice(position.take_profit)}</div>
            </div>
          )}
          {position.stop_loss != null && (
            <div>
              <span className="text-gray-500 dark:text-gray-500">SL</span>
              <div className="text-red-600 dark:text-red-400 font-mono text-xs">{formatPrice(position.stop_loss)}</div>
            </div>
          )}
          <div>
            <span className="text-gray-500 dark:text-gray-500">Size</span>
            <div className="text-gray-900 dark:text-white text-xs">${parseFloat(position.position_size).toFixed(2)}</div>
          </div>
          {hasLivePrice && (
            <div>
              <span className="text-gray-500 dark:text-gray-500">Value</span>
              <div className="text-gray-900 dark:text-white text-xs">${parseFloat(position.current_value || position.position_size).toFixed(2)}</div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-200 dark:border-gray-700/50">
          <div className="text-right">
            <span className={`text-sm font-bold ${pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
            </span>
            <span className={`ml-1 text-[10px] ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ({pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%)
            </span>
          </div>
          <div className="flex items-center text-[10px] text-gray-500">
            <Clock className="w-3 h-3 mr-0.5" />
            {new Date(position.entry_time).toLocaleDateString([], { month: 'numeric', day: 'numeric' })}
          </div>
        </div>
      </div>
    </div>
  );
};

const TradeHistoryTable = ({ trades, onReplay }) => {
  return (
    <div>
      <table className="w-full text-xs sm:text-sm">
        <thead className="bg-gray-100 dark:bg-gray-800/50">
          <tr>
            <th className="px-2 sm:px-4 py-2 sm:py-3 text-left text-[10px] sm:text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Symbol</th>
            <th className="px-2 sm:px-4 py-2 sm:py-3 text-left text-[10px] sm:text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Dir</th>
            <th className="px-2 sm:px-4 py-2 sm:py-3 text-left text-[10px] sm:text-xs font-medium text-gray-600 dark:text-gray-400 uppercase hidden sm:table-cell">Conf</th>
            <th className="px-2 sm:px-4 py-2 sm:py-3 text-left text-[10px] sm:text-xs font-medium text-gray-600 dark:text-gray-400 uppercase hidden sm:table-cell">Entry</th>
            <th className="px-2 sm:px-4 py-2 sm:py-3 text-left text-[10px] sm:text-xs font-medium text-gray-600 dark:text-gray-400 uppercase hidden md:table-cell">Exit</th>
            <th className="px-2 sm:px-4 py-2 sm:py-3 text-left text-[10px] sm:text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">P/L</th>
            <th className="px-2 sm:px-4 py-2 sm:py-3 text-left text-[10px] sm:text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Status</th>
            <th className="px-2 sm:px-4 py-2 sm:py-3 text-left text-[10px] sm:text-xs font-medium text-gray-600 dark:text-gray-400 uppercase hidden lg:table-cell">Duration</th>
            <th className="px-2 sm:px-4 py-2 sm:py-3 text-left text-[10px] sm:text-xs font-medium text-gray-600 dark:text-gray-400 uppercase hidden sm:table-cell">Date</th>
            <th className="px-2 sm:px-4 py-2 sm:py-3 text-[10px] sm:text-xs font-medium text-gray-600 dark:text-gray-400 uppercase w-8"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
          {trades.map((trade) => {
            const pnl = parseFloat(trade.profit_loss || 0);
            const pnlPct = parseFloat(trade.profit_loss_percentage || 0);

            return (
              <tr key={trade.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/30">
                <td className="px-2 sm:px-4 py-2 sm:py-3">
                  <div className="flex flex-col sm:flex-row sm:items-center gap-1">
                    <span className="text-gray-900 dark:text-white font-medium text-xs sm:text-sm">{trade.symbol}</span>
                    <div className="flex items-center gap-1 flex-wrap">
                      <AssetClassBadge assetClass={trade.asset_class} />
                      {trade.is_priority && (
                        <Zap className="w-3 h-3 text-amber-500" />
                      )}
                      {trade.is_neutral_reversal && (
                        <RefreshCw className="w-3 h-3 text-cyan-500" />
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-2 sm:px-4 py-2 sm:py-3">
                  <span className={`inline-block px-1.5 sm:px-2 py-0.5 sm:py-1 rounded text-[10px] sm:text-xs font-medium ${trade.direction === 'LONG' ? 'bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400' : 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400'}`}>
                    {trade.direction}
                  </span>
                </td>
                <td className="px-2 sm:px-4 py-2 sm:py-3 hidden sm:table-cell">
                  {trade.confidence != null
                    ? <span className="text-indigo-600 dark:text-indigo-400 font-semibold text-xs">{(parseFloat(trade.confidence) * 100).toFixed(0)}%</span>
                    : <span className="text-gray-400">-</span>}
                </td>
                <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-700 dark:text-gray-300 font-mono hidden sm:table-cell">${parseFloat(trade.entry_price).toFixed(2)}</td>
                <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-700 dark:text-gray-300 font-mono hidden md:table-cell">
                  {trade.exit_price ? `$${parseFloat(trade.exit_price).toFixed(2)}` : '-'}
                </td>
                <td className="px-2 sm:px-4 py-2 sm:py-3">
                  <div className={`font-semibold ${pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                  </div>
                  <div className={`text-[10px] ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%
                  </div>
                </td>
                <td className="px-2 sm:px-4 py-2 sm:py-3">
                  <span className={`inline-block px-1.5 sm:px-2 py-0.5 sm:py-1 rounded text-[10px] sm:text-xs ${trade.status === 'CLOSED_TP' ? 'bg-green-100 dark:bg-green-500/20 text-green-600' :
                    trade.status === 'CLOSED_SL' ? 'bg-red-100 dark:bg-red-500/20 text-red-600' :
                      trade.status === 'CLOSED_MANUAL' ? 'bg-yellow-100 dark:bg-yellow-500/20 text-yellow-600' :
                        'bg-gray-100 dark:bg-gray-500/20 text-gray-600'
                    }`}>
                    {trade.status?.replace('CLOSED_', '') || 'CLOSED'}
                  </span>
                </td>
                <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-500 hidden lg:table-cell">
                  {trade.duration_hours ? `${parseFloat(trade.duration_hours).toFixed(1)}h` : '-'}
                </td>
                <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-500 hidden sm:table-cell">
                  <div>{new Date(trade.entry_time).toLocaleDateString()}</div>
                </td>
                <td className="px-2 sm:px-4 py-2 sm:py-3">
                  <button onClick={() => onReplay?.(trade.id)} title="Replay trade"
                    className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
                    <CirclePlay className="w-4 h-4 text-blue-500" />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default BotPerformance;
