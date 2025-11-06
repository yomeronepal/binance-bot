import React, { useEffect, useState } from 'react';
import { Bot, TrendingUp, TrendingDown, Target, BarChart3, Clock, DollarSign, Percent, Activity } from 'lucide-react';
import axios from 'axios';

const BotPerformance = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [openPositions, setOpenPositions] = useState([]);
  const [recentTrades, setRecentTrades] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [tradesPerPage] = useState(20); // Show 20 trades per page
  const [positionsPerPage] = useState(12); // Show 12 positions per page

  // Reset pagination when switching tabs
  useEffect(() => {
    setCurrentPage(1);
  }, [activeTab]);

  // Fetch data without authentication - with LIVE prices
  const fetchData = async () => {
    try {
      setLoading(true);
      const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

      // Fetch summary - includes performance metrics
      const summaryRes = await axios.get(`${baseURL}/public/paper-trading/summary/`);
      setSummary(summaryRes.data);

      // Fetch open positions with REAL-TIME PRICES
      const positionsRes = await axios.get(`${baseURL}/public/paper-trading/open-positions/`);
      const positionsData = positionsRes.data;

      // Set open positions with live prices
      setOpenPositions(positionsData.positions || []);

      // Update summary with live unrealized PNL
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
      }

      // Fetch all trades and get recent closed ones
      const tradesRes = await axios.get(`${baseURL}/public/paper-trading/`);
      const allTrades = tradesRes.data.trades || tradesRes.data || [];
      const closed = allTrades.filter(t => t.status && t.status.startsWith('CLOSED'));
      setRecentTrades(closed.slice(0, 20));

      setError(null);
    } catch (err) {
      console.error('Error fetching bot performance:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Note: Auto-refresh removed - user can manually refresh the page
  }, []);

  // Show loading only on initial load (when summary is null)
  if (loading && !summary) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 flex items-center justify-center">
        <div className="text-center">
          <Activity className="w-12 h-12 text-blue-400 animate-pulse mx-auto mb-4" />
          <p className="text-gray-400">Loading bot performance...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-8 text-center">
            <p className="text-red-400">Failed to load bot performance: {error}</p>
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
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-3 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-lg border border-blue-500/50">
              <Bot className="w-8 h-8 text-blue-400" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-white">Bot Performance Dashboard</h1>
              <p className="text-gray-400">Live tracking of all signals with automated paper trading</p>
            </div>
          </div>

          {/* Info Banner */}
          <div className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/30 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <p className="text-blue-300 text-sm flex items-center">
                <Activity className="w-4 h-4 inline mr-2 animate-pulse" />
                Every signal generated by the bot is automatically paper traded with $100 position size.
                <span className="ml-2 px-2 py-0.5 bg-green-500/20 border border-green-500/50 rounded text-xs text-green-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse"></span>
                  LIVE PRICES
                </span>
              </p>
              <button
                onClick={fetchData}
                disabled={loading}
                className="text-xs text-blue-400 hover:text-blue-300 transition-colors flex items-center gap-1 disabled:opacity-50"
              >
                <Activity className="w-3 h-3" />
                {loading ? 'Refreshing...' : 'Manual Refresh'}
              </button>
            </div>
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {stats.map((stat, index) => (
            <div key={index} className="relative overflow-hidden bg-gray-800/30 backdrop-blur-sm border border-gray-700 rounded-lg p-6 hover:border-gray-600 transition-all group">
              <div className={`absolute inset-0 bg-gradient-to-br ${stat.bgGradient} opacity-0 group-hover:opacity-100 transition-opacity`} />
              <div className="relative">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400 text-sm">{stat.label}</span>
                    {stat.isLive && (
                      <span className="flex items-center gap-1 px-2 py-0.5 bg-green-500/20 border border-green-500/50 rounded text-xs text-green-400">
                        <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse"></span>
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
          <div className="flex gap-2 border-b border-gray-700">
            <button
              onClick={() => setActiveTab('overview')}
              className={`px-6 py-3 font-medium transition-all ${
                activeTab === 'overview'
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Overview
            </button>
            <button
              onClick={() => setActiveTab('open')}
              className={`px-6 py-3 font-medium transition-all ${
                activeTab === 'open'
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Open Positions ({openTradesCount})
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`px-6 py-3 font-medium transition-all ${
                activeTab === 'history'
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-400 hover:text-white'
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
              <h2 className="text-xl font-bold text-white mb-4">Current Open Positions</h2>
              {openPositions.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {openPositions.slice(0, 6).map((position) => (
                    <PositionCard key={position.trade_id} position={position} />
                  ))}
                </div>
              ) : (
                <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-8 text-center">
                  <p className="text-gray-400">No open positions at the moment</p>
                </div>
              )}
            </div>

            {/* Recent Closed Trades */}
            <div>
              <h2 className="text-xl font-bold text-white mb-4">Recent Closed Trades</h2>
              {recentTrades.length > 0 ? (
                <div className="bg-gray-800/30 border border-gray-700 rounded-lg overflow-hidden">
                  <TradeHistoryTable trades={recentTrades.slice(0, 10)} />
                </div>
              ) : (
                <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-8 text-center">
                  <p className="text-gray-400">No closed trades yet</p>
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
                      <PositionCard key={position.trade_id} position={position} />
                    ))}
                </div>

                {/* Pagination Controls for Open Positions */}
                {openPositions.length > positionsPerPage && (
                  <div className="flex items-center justify-between px-4 py-3 bg-gray-800/30 border border-gray-700 rounded-lg">
                    <div className="text-sm text-gray-400">
                      Showing {((currentPage - 1) * positionsPerPage) + 1} to {Math.min(currentPage * positionsPerPage, openPositions.length)} of {openPositions.length} positions
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                        disabled={currentPage === 1}
                        className="px-4 py-2 bg-gray-700 text-white rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        Previous
                      </button>
                      <span className="text-white px-4">
                        Page {currentPage} of {Math.ceil(openPositions.length / positionsPerPage)}
                      </span>
                      <button
                        onClick={() => setCurrentPage(prev => Math.min(Math.ceil(openPositions.length / positionsPerPage), prev + 1))}
                        disabled={currentPage >= Math.ceil(openPositions.length / positionsPerPage)}
                        className="px-4 py-2 bg-gray-700 text-white rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-12 text-center">
                <Activity className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400 text-lg">No open positions</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <div>
            {recentTrades.length > 0 ? (
              <>
                <div className="bg-gray-800/30 border border-gray-700 rounded-lg overflow-hidden mb-4">
                  <TradeHistoryTable
                    trades={recentTrades.slice(
                      (currentPage - 1) * tradesPerPage,
                      currentPage * tradesPerPage
                    )}
                  />
                </div>

                {/* Pagination Controls */}
                {recentTrades.length > tradesPerPage && (
                  <div className="flex items-center justify-between px-4 py-3 bg-gray-800/30 border border-gray-700 rounded-lg">
                    <div className="text-sm text-gray-400">
                      Showing {((currentPage - 1) * tradesPerPage) + 1} to {Math.min(currentPage * tradesPerPage, recentTrades.length)} of {recentTrades.length} trades
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                        disabled={currentPage === 1}
                        className="px-4 py-2 bg-gray-700 text-white rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        Previous
                      </button>
                      <span className="text-white px-4">
                        Page {currentPage} of {Math.ceil(recentTrades.length / tradesPerPage)}
                      </span>
                      <button
                        onClick={() => setCurrentPage(prev => Math.min(Math.ceil(recentTrades.length / tradesPerPage), prev + 1))}
                        disabled={currentPage >= Math.ceil(recentTrades.length / tradesPerPage)}
                        className="px-4 py-2 bg-gray-700 text-white rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-12 text-center">
                <BarChart3 className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400 text-lg">No trade history yet</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// Position Card Component
const PositionCard = ({ position }) => {
  const pnl = parseFloat(position.unrealized_pnl || 0);
  const pnlPct = parseFloat(position.unrealized_pnl_pct || 0);
  const priceChangePct = parseFloat(position.price_change_pct || 0);
  const hasLivePrice = position.has_real_time_price;

  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 hover:border-blue-500/50 transition-all">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-white font-semibold text-lg">{position.symbol}</h3>
            {hasLivePrice && (
              <span className="flex items-center gap-1 px-1.5 py-0.5 bg-green-500/20 border border-green-500/50 rounded text-xs text-green-400">
                <span className="w-1 h-1 bg-green-400 rounded-full animate-pulse"></span>
              </span>
            )}
          </div>
          <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
            position.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
          }`}>
            {position.direction}
          </span>
        </div>
        <span className={`text-sm px-2 py-1 rounded ${
          position.market_type === 'FUTURES'
            ? 'bg-purple-500/20 text-purple-400'
            : 'bg-blue-500/20 text-blue-400'
        }`}>
          {position.market_type}
        </span>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-400">Entry Price:</span>
          <span className="text-white font-mono">${parseFloat(position.entry_price).toFixed(4)}</span>
        </div>
        {hasLivePrice && (
          <>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Current Price:</span>
              <div className="text-right">
                <span className="text-white font-mono">${parseFloat(position.current_price).toFixed(4)}</span>
                {priceChangePct !== 0 && (
                  <div className={`text-xs ${priceChangePct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {priceChangePct >= 0 ? '↑' : '↓'} {Math.abs(priceChangePct).toFixed(2)}%
                  </div>
                )}
              </div>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Current Value:</span>
              <span className="text-white">${parseFloat(position.current_value || position.position_size).toFixed(2)}</span>
            </div>
          </>
        )}
        <div className="flex justify-between">
          <span className="text-gray-400">Position Size:</span>
          <span className="text-white">${parseFloat(position.position_size).toFixed(2)}</span>
        </div>
        <div className="border-t border-gray-700 pt-2 mt-2">
          <div className="flex justify-between items-center">
            <span className="text-gray-400">
              {hasLivePrice ? 'Live P/L:' : 'Unrealized P/L:'}
            </span>
            <div className="text-right">
              <div className={`font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {pnl >= 0 ? '+' : ''}${Math.abs(pnl).toFixed(2)}
              </div>
              <div className={`text-xs ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                ({pnl >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%)
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-700 flex items-center justify-between text-xs">
        <div className="flex items-center text-gray-500">
          <Clock className="w-3 h-3 mr-1" />
          {new Date(position.entry_time).toLocaleDateString()}
        </div>
        {hasLivePrice && (
          <span className="text-green-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse"></span>
            LIVE
          </span>
        )}
      </div>
    </div>
  );
};

// Trade History Table Component
const TradeHistoryTable = ({ trades }) => {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead className="bg-gray-800/50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Symbol</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Direction</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Entry</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Exit</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">P/L</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Date</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700">
          {trades.map((trade) => {
            const pnl = parseFloat(trade.realized_pnl || 0);
            const pnlPct = parseFloat(trade.profit_loss_pct || 0);

            return (
              <tr key={trade.id} className="hover:bg-gray-800/30">
                <td className="px-4 py-3 text-white font-medium">{trade.symbol}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                    trade.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                  }`}>
                    {trade.direction}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-300 font-mono text-sm">${parseFloat(trade.entry_price).toFixed(4)}</td>
                <td className="px-4 py-3 text-gray-300 font-mono text-sm">
                  {trade.exit_price ? `$${parseFloat(trade.exit_price).toFixed(4)}` : '-'}
                </td>
                <td className="px-4 py-3">
                  <div className={`font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                  </div>
                  <div className={`text-xs ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ({pnl >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%)
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-1 rounded text-xs ${
                    trade.status === 'CLOSED_TP' ? 'bg-green-500/20 text-green-400' :
                    trade.status === 'CLOSED_SL' ? 'bg-red-500/20 text-red-400' :
                    'bg-gray-500/20 text-gray-400'
                  }`}>
                    {trade.status?.replace('CLOSED_', '')}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-400 text-sm">
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

export default BotPerformance;
