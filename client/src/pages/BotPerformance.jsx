import React, { useEffect, useState } from 'react';
import { Bot, TrendingUp, TrendingDown, Target, BarChart3, Clock, DollarSign, Percent, Activity, X, Calendar } from 'lucide-react';
import axios from 'axios';
import { useAuthStore } from '../store/useAuthStore';
import api from '../services/api';

const BotPerformance = () => {
  const { user } = useAuthStore();
  const isSuperUser = user?.is_superuser;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [openPositions, setOpenPositions] = useState([]);
  const [recentTrades, setRecentTrades] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  const [isGoldenWindow, setIsGoldenWindow] = useState(() => {
    return localStorage.getItem('bot_perf_golden_window') === 'true';
  });
  const [totalTradesCount, setTotalTradesCount] = useState(0);

  useEffect(() => {
    localStorage.setItem('bot_perf_golden_window', isGoldenWindow);
  }, [isGoldenWindow]);

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
      await api.post(`/public/paper-trading/${tradeId}/close/`);
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
      const queryParams = isGoldenWindow ? '?golden_window=true' : '';

      const [summaryRes, positionsRes] = await Promise.all([
        axios.get(`${baseURL}/public/paper-trading/summary/${queryParams}`),
        axios.get(`${baseURL}/public/paper-trading/open-positions/${queryParams}`)
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
      if (isGoldenWindow) params.append('golden_window', 'true');

      const res = await axios.get(`${baseURL}/public/paper-trading/?${params.toString()}`);

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
  }, [isGoldenWindow]);

  useEffect(() => {
    fetchTradeHistory();
  }, [isGoldenWindow, currentPage]);

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
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gradient-to-br dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-3 bg-gradient-to-br from-blue-100 to-purple-100 dark:from-blue-500/20 dark:to-purple-500/20 rounded-lg border border-blue-300 dark:border-blue-500/50">
              <Bot className="w-8 h-8 text-blue-500 dark:text-blue-400" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Bot Performance Dashboard</h1>
              <p className="text-gray-600 dark:text-gray-400">Live tracking of all signals with automated paper trading</p>
            </div>
          </div>

          {/* Info Banner */}
          <div className="bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-500/10 dark:to-purple-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <p className="text-blue-600 dark:text-blue-300 text-sm flex items-center">
                <Activity className="w-4 h-4 inline mr-2 animate-pulse" />
                Every signal generated by the bot is automatically paper traded with $100 position size.
                <span className="ml-2 px-2 py-0.5 bg-green-100 dark:bg-green-500/20 border border-green-300 dark:border-green-500/50 rounded text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-green-500 dark:bg-green-400 rounded-full animate-pulse"></span>
                  LIVE PRICES
                </span>
              </p>
              <div className="flex items-center gap-3">
                <div className="flex items-center bg-white dark:bg-gray-800 rounded-lg p-1 border border-gray-200 dark:border-gray-700">
                  <button
                    onClick={() => setIsGoldenWindow(false)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${!isGoldenWindow
                      ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300 shadow-sm'
                      : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                      }`}
                  >
                    All Trades
                  </button>
                  <button
                    onClick={() => setIsGoldenWindow(true)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1 ${isGoldenWindow
                      ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300 shadow-sm'
                      : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                      }`}
                  >
                    <Clock className="w-3 h-3" />
                    Golden Window
                  </button>
                </div>
                <button
                  onClick={() => { fetchPerformanceData(); fetchTradeHistory(); }}
                  disabled={loading}
                  className="text-xs text-blue-500 dark:text-blue-400 hover:text-blue-600 dark:hover:text-blue-300 transition-colors flex items-center gap-1 disabled:opacity-50"
                >
                  <Activity className="w-3 h-3" />
                  {loading ? 'Refreshing...' : 'Manual Refresh'}
                </button>
              </div>
            </div>
          </div>

          {/* Trading Session Status */}
          <TradingSessionStatus />
        </div>

        {/* Performance Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {stats.map((stat, index) => (
            <div key={index} className="relative overflow-hidden bg-white dark:bg-gray-800/30 backdrop-blur-sm border border-gray-200 dark:border-gray-700 rounded-lg p-6 hover:border-gray-300 dark:hover:border-gray-600 transition-all group shadow-sm">
              <div className={`absolute inset-0 bg-gradient-to-br ${stat.bgGradient} opacity-0 group-hover:opacity-100 transition-opacity`} />
              <div className="relative">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-600 dark:text-gray-400 text-sm">{stat.label}</span>
                    {stat.isLive && (
                      <span className="flex items-center gap-1 px-2 py-0.5 bg-green-100 dark:bg-green-500/20 border border-green-300 dark:border-green-500/50 rounded text-xs text-green-600 dark:text-green-400">
                        <span className="w-1.5 h-1.5 bg-green-500 dark:bg-green-400 rounded-full animate-pulse"></span>
                        LIVE
                      </span>
                    )}
                  </div>
                  <stat.icon className={`w-5 h-5 ${stat.color}`} />
                </div>
                <div className={`text-2xl font-bold ${stat.color} mb-1`}>{stat.value}</div>
                <div className="text-sm text-gray-500">{stat.subtext}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="mb-6">
          <div className="flex gap-2 border-b border-gray-200 dark:border-gray-700">
            <button
              onClick={() => setActiveTab('overview')}
              className={`px-6 py-3 font-medium transition-all ${activeTab === 'overview'
                ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
            >
              Overview
            </button>
            <button
              onClick={() => setActiveTab('open')}
              className={`px-6 py-3 font-medium transition-all ${activeTab === 'open'
                ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
            >
              Open Positions ({openTradesCount})
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`px-6 py-3 font-medium transition-all ${activeTab === 'history'
                ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
            >
              Trade History
            </button>
          </div>
        </div>

        {/* Content */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Open Positions Summary */}
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Current Open Positions</h2>
              {openPositions.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
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
                  <TradeHistoryTable trades={recentTrades.slice(0, 10)} />
                </div>
              ) : (
                <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-8 text-center shadow-sm">
                  <p className="text-gray-600 dark:text-gray-400">No closed trades yet</p>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'open' && (
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
                  <div className="flex items-center justify-between px-4 py-3 bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm">
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      Showing {((currentPage - 1) * positionsPerPage) + 1} to {Math.min(currentPage * positionsPerPage, openPositions.length)} of {openPositions.length} positions
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                        disabled={currentPage === 1}
                        className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-white rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        Previous
                      </button>
                      <span className="text-gray-800 dark:text-white px-4">
                        Page {currentPage} of {Math.ceil(openPositions.length / positionsPerPage)}
                      </span>
                      <button
                        onClick={() => setCurrentPage(prev => Math.min(Math.ceil(openPositions.length / positionsPerPage), prev + 1))}
                        disabled={currentPage >= Math.ceil(openPositions.length / positionsPerPage)}
                        className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-white rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
        )}

        {activeTab === 'history' && (
          <div>
            {recentTrades.length > 0 ? (
              <>
                <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden mb-4 shadow-sm">
                  <TradeHistoryTable
                    trades={recentTrades}
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
                        className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-white rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        Previous
                      </button>
                      <span className="text-gray-800 dark:text-white px-4">
                        Page {currentPage} of {Math.ceil(totalTradesCount / tradesPerPage)}
                      </span>
                      <button
                        onClick={() => setCurrentPage(prev => Math.min(Math.ceil(totalTradesCount / tradesPerPage), prev + 1))}
                        disabled={currentPage >= Math.ceil(totalTradesCount / tradesPerPage)}
                        className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-white rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
        )}
      </div>
    </div>
  );
};

const PositionCard = ({ position, isSuperUser, onClose }) => {
  const pnl = parseFloat(position.unrealized_pnl || 0);
  const pnlPct = parseFloat(position.unrealized_pnl_pct || 0);
  const priceChangePct = parseFloat(position.price_change_pct || 0);
  const hasLivePrice = position.has_real_time_price;

  return (
    <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:border-blue-400 dark:hover:border-blue-500/50 transition-all shadow-sm relative group">
      {isSuperUser && onClose && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onClose();
          }}
          className="absolute top-2 right-2 p-1.5 bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-200 dark:hover:bg-red-500/30"
          title="Close Trade (Admin)"
        >
          <X className="w-4 h-4" />
        </button>
      )}
      <div className="flex items-start justify-between mb-3 pr-8">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-gray-900 dark:text-white font-semibold text-lg">{position.symbol}</h3>
            {hasLivePrice && (
              <span className="flex items-center gap-1 px-1.5 py-0.5 bg-green-100 dark:bg-green-500/20 border border-green-300 dark:border-green-500/50 rounded text-xs text-green-600 dark:text-green-400">
                <span className="w-1 h-1 bg-green-500 dark:bg-green-400 rounded-full animate-pulse"></span>
              </span>
            )}
          </div>
          <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${position.direction === 'LONG' ? 'bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400' : 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400'
            }`}>
            {position.direction}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-sm px-2 py-1 rounded ${position.market_type === 'FUTURES'
            ? 'bg-purple-100 dark:bg-purple-500/20 text-purple-600 dark:text-purple-400'
            : 'bg-blue-100 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400'
            }`}>
            {position.market_type}
          </span>
        </div>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-600 dark:text-gray-400">Entry Price:</span>
          <span className="text-gray-900 dark:text-white font-mono">${parseFloat(position.entry_price).toFixed(4)}</span>
        </div>
        {hasLivePrice && (
          <>
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400">Current Price:</span>
              <div className="text-right">
                <span className="text-gray-900 dark:text-white font-mono">${parseFloat(position.current_price).toFixed(4)}</span>
                {priceChangePct !== 0 && (
                  <div className={`text-xs ${priceChangePct >= 0 ? 'text-green-500 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
                    {priceChangePct >= 0 ? '↑' : '↓'} {Math.abs(priceChangePct).toFixed(2)}%
                  </div>
                )}
              </div>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Current Value:</span>
              <span className="text-gray-900 dark:text-white">${parseFloat(position.current_value || position.position_size).toFixed(2)}</span>
            </div>
          </>
        )}
        <div className="flex justify-between">
          <span className="text-gray-600 dark:text-gray-400">Position Size:</span>
          <span className="text-gray-900 dark:text-white">${parseFloat(position.position_size).toFixed(2)}</span>
        </div>
        <div className="border-t border-gray-200 dark:border-gray-700 pt-2 mt-2">
          <div className="flex justify-between items-center">
            <span className="text-gray-600 dark:text-gray-400">
              {hasLivePrice ? 'Live P/L:' : 'Unrealized P/L:'}
            </span>
            <div className="text-right">
              <div className={`font-semibold ${pnl >= 0 ? 'text-green-500 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
                {pnl >= 0 ? '+' : ''}${Math.abs(pnl).toFixed(2)}
              </div>
              <div className={`text-xs ${pnl >= 0 ? 'text-green-500 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
                ({pnl >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%)
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between text-xs">
        <div className="flex items-center text-gray-500">
          <Clock className="w-3 h-3 mr-1" />
          {new Date(position.entry_time).toLocaleDateString()}
        </div>
        {hasLivePrice && (
          <span className="text-green-500 dark:text-green-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-green-500 dark:bg-green-400 rounded-full animate-pulse"></span>
            LIVE
          </span>
        )}
      </div>
    </div>
  );
};

const TradeHistoryTable = ({ trades }) => {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead className="bg-gray-100 dark:bg-gray-800/50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Symbol</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Direction</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Entry</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Exit</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">P/L</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Status</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Date</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
          {trades.map((trade) => {
            const pnl = parseFloat(trade.profit_loss || 0);
            const pnlPct = parseFloat(trade.profit_loss_percentage || 0);

            return (
              <tr key={trade.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/30">
                <td className="px-4 py-3 text-gray-900 dark:text-white font-medium">{trade.symbol}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${trade.direction === 'LONG' ? 'bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400' : 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400'
                    }`}>
                    {trade.direction}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-700 dark:text-gray-300 font-mono text-sm">${parseFloat(trade.entry_price).toFixed(4)}</td>
                <td className="px-4 py-3 text-gray-700 dark:text-gray-300 font-mono text-sm">
                  {trade.exit_price ? `$${parseFloat(trade.exit_price).toFixed(4)}` : '-'}
                </td>
                <td className="px-4 py-3">
                  <div className={`font-semibold ${pnl >= 0 ? 'text-green-500 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                  </div>
                  <div className={`text-xs ${pnl >= 0 ? 'text-green-500 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
                    ({pnl >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%)
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-1 rounded text-xs ${trade.status === 'CLOSED_TP' ? 'bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400' :
                    trade.status === 'CLOSED_SL' ? 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400' :
                      trade.status === 'CLOSED_MANUAL' ? 'bg-yellow-100 dark:bg-yellow-500/20 text-yellow-600 dark:text-yellow-400' :
                        'bg-gray-100 dark:bg-gray-500/20 text-gray-600 dark:text-gray-400'
                    }`}>
                    {trade.status?.replace('CLOSED_', '') || 'CLOSED'}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500 dark:text-gray-400 text-sm">
                  {new Date(trade.entry_time).toLocaleDateString()}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

const TradingSessionStatus = () => {
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const NEPAL_OFFSET_MINUTES = 5 * 60 + 45;
  const US_EST_OFFSET_MINUTES = -5 * 60;

  const getNepalTime = (date) => {
    const utc = date.getTime() + date.getTimezoneOffset() * 60000;
    return new Date(utc + NEPAL_OFFSET_MINUTES * 60000);
  };

  const getUSTime = (date) => {
    const utc = date.getTime() + date.getTimezoneOffset() * 60000;
    const isDST = isUSDaylightSaving(date);
    const offset = isDST ? (US_EST_OFFSET_MINUTES + 60) : US_EST_OFFSET_MINUTES;
    return new Date(utc + offset * 60000);
  };

  const getUTCTime = (date) => {
    return new Date(date.getTime() + date.getTimezoneOffset() * 60000);
  };

  const isUSDaylightSaving = (date) => {
    const jan = new Date(date.getFullYear(), 0, 1);
    const jul = new Date(date.getFullYear(), 6, 1);
    const stdOffset = Math.max(jan.getTimezoneOffset(), jul.getTimezoneOffset());
    return date.getTimezoneOffset() < stdOffset;
  };

  const formatTime = (date) => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    });
  };

  const isWithinTradingWindow = () => {
    const nepalTime = getNepalTime(currentTime);
    const hour = nepalTime.getHours();
    const minute = nepalTime.getMinutes();
    const timeInMinutes = hour * 60 + minute;

    const windows = [
      { start: 17 * 60, end: 18 * 60 },
      { start: 21 * 60, end: 23 * 60 }
    ];

    return windows.some(w => timeInMinutes >= w.start && timeInMinutes < w.end);
  };

  const getNextWindow = () => {
    const nepalTime = getNepalTime(currentTime);
    const hour = nepalTime.getHours();
    const minute = nepalTime.getMinutes();
    const timeInMinutes = hour * 60 + minute;

    if (timeInMinutes < 17 * 60) return '17:00 NPT';
    if (timeInMinutes >= 18 * 60 && timeInMinutes < 21 * 60) return '21:00 NPT';
    return '17:00 NPT (tomorrow)';
  };

  const nepalTime = getNepalTime(currentTime);
  const usTime = getUSTime(currentTime);
  const utcTime = getUTCTime(currentTime);
  const isActive = isWithinTradingWindow();

  const tradingWindows = [
    {
      npt: '17:00 - 18:00',
      utc: '11:15 - 12:15',
      us: '06:15 - 07:15 EST'
    },
    {
      npt: '21:00 - 23:00',
      utc: '15:15 - 17:15',
      us: '10:15 - 12:15 EST'
    }
  ];

  return (
    <div className={`mt-4 rounded-lg border-2 p-4 ${isActive ? 'bg-green-50 dark:bg-green-500/10 border-green-400 dark:border-green-500/50' : 'bg-gray-100 dark:bg-gray-800/30 border-gray-300 dark:border-gray-700'}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className={`w-5 h-5 ${isActive ? 'text-green-500 dark:text-green-400 animate-pulse' : 'text-gray-400 dark:text-gray-500'}`} />
          <span className={`font-semibold ${isActive ? 'text-green-600 dark:text-green-400' : 'text-gray-600 dark:text-gray-400'}`}>
            Trading Session: {isActive ? 'ACTIVE' : 'INACTIVE'}
          </span>
          {isActive && (
            <span className="flex items-center gap-1 px-2 py-0.5 bg-green-100 dark:bg-green-500/20 border border-green-300 dark:border-green-500/50 rounded text-xs text-green-600 dark:text-green-400">
              <span className="w-1.5 h-1.5 bg-green-500 dark:bg-green-400 rounded-full animate-pulse"></span>
              LIVE
            </span>
          )}
        </div>
        {!isActive && (
          <span className="text-sm text-gray-500">
            Next: {getNextWindow()}
          </span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center p-2 bg-white dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
          <div className="flex items-center justify-center gap-1 text-xs text-gray-500 mb-1">
            <Clock className="w-3 h-3" />
            <span>Nepal (NPT)</span>
          </div>
          <div className="font-mono font-bold text-blue-600 dark:text-blue-400">{formatTime(nepalTime)}</div>
        </div>
        <div className="text-center p-2 bg-white dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
          <div className="flex items-center justify-center gap-1 text-xs text-gray-500 mb-1">
            <Clock className="w-3 h-3" />
            <span>US (EST/EDT)</span>
          </div>
          <div className="font-mono font-bold text-purple-600 dark:text-purple-400">{formatTime(usTime)}</div>
        </div>
        <div className="text-center p-2 bg-white dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
          <div className="flex items-center justify-center gap-1 text-xs text-gray-500 mb-1">
            <Clock className="w-3 h-3" />
            <span>UTC</span>
          </div>
          <div className="font-mono font-bold text-gray-700 dark:text-gray-300">{formatTime(utcTime)}</div>
        </div>
      </div>

      <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
        <div className="flex items-center gap-1 text-xs text-gray-500 mb-2">
          <Calendar className="w-3 h-3" />
          <span>Trading Windows (Paper trades only execute during these times)</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {tradingWindows.map((window, idx) => (
            <div key={idx} className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded p-2 text-xs shadow-sm">
              <div className="font-semibold text-blue-600 dark:text-blue-400 mb-1">Window {idx + 1}</div>
              <div className="space-y-0.5">
                <div><span className="text-gray-500">NPT:</span> <span className="font-mono text-gray-700 dark:text-gray-300">{window.npt}</span></div>
                <div><span className="text-gray-500">UTC:</span> <span className="font-mono text-gray-700 dark:text-gray-300">{window.utc}</span></div>
                <div><span className="text-gray-500">US:</span> <span className="font-mono text-gray-700 dark:text-gray-300">{window.us}</span></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default BotPerformance;
