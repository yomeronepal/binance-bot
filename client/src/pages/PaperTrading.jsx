import React, { useEffect, useState } from 'react';
import { Target, TrendingUp, AlertCircle, RefreshCw } from 'lucide-react';
import usePaperTradeStore from '../store/usePaperTradeStore';
import PerformanceMetrics from '../components/paper-trading/PerformanceMetrics';
import PaperTradeCard from '../components/paper-trading/PaperTradeCard';
import TradeHistory from '../components/paper-trading/TradeHistory';

const PaperTrading = () => {
  const [activeTab, setActiveTab] = useState('open'); // 'open' or 'history'
  const [metricsDays, setMetricsDays] = useState(7);

  const {
    trades = [],
    metrics,
    loading,
    error,
    fetchTrades,
    fetchMetrics,
    closeTrade,
    cancelTrade,
  } = usePaperTradeStore();

  const openTrades = (trades || []).filter(t => t.status === 'OPEN' || t.status === 'PENDING');
  const closedTrades = (trades || []).filter(t => t.status && t.status.startsWith('CLOSED'));

  useEffect(() => {
    const loadData = async () => {
      try {
        await fetchTrades();
        await fetchMetrics(metricsDays);
      } catch (err) {
        console.error('Error loading paper trading data:', err);
      }
    };

    loadData();

    // Refresh every 30 seconds
    const interval = setInterval(() => {
      loadData();
    }, 30000);

    return () => clearInterval(interval);
  }, [metricsDays, fetchTrades, fetchMetrics]);

  const handleCloseTrade = async (tradeId) => {
    if (window.confirm('Are you sure you want to close this trade at current market price?')) {
      try {
        await closeTrade(tradeId);
      } catch (error) {
        alert(`Failed to close trade: ${error.message}`);
      }
    }
  };

  const handleCancelTrade = async (tradeId) => {
    if (window.confirm('Are you sure you want to cancel this pending trade?')) {
      try {
        await cancelTrade(tradeId);
      } catch (error) {
        alert(`Failed to cancel trade: ${error.message}`);
      }
    }
  };

  const handleRefresh = () => {
    fetchTrades();
    fetchMetrics(metricsDays);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-lg border border-purple-500/50">
                <Target className="w-8 h-8 text-purple-400" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-white mb-1">Paper Trading</h1>
                <p className="text-gray-400">Practice trading without risking real money</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Days Filter */}
              <select
                value={metricsDays}
                onChange={(e) => setMetricsDays(Number(e.target.value))}
                className="bg-gray-800 border border-gray-700 text-white px-4 py-2 rounded-lg text-sm focus:outline-none focus:border-purple-500 transition-colors"
              >
                <option value={1}>Last 24 hours</option>
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
              </select>

              {/* Refresh Button */}
              <button
                onClick={handleRefresh}
                disabled={loading}
                className="flex items-center gap-2 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
          </div>

          {/* Info Banner */}
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-blue-300 text-sm font-medium mb-1">Paper Trading Mode Active</p>
              <p className="text-blue-400/80 text-xs">
                All trades are simulated. No real funds are being used. Go to the Dashboard to create trades from signals.
              </p>
            </div>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 mb-6 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400" />
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {/* Performance Metrics */}
        <PerformanceMetrics metrics={metrics} loading={loading} />

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setActiveTab('open')}
            className={`flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all duration-200 ${
              activeTab === 'open'
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg'
                : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
            }`}
          >
            <TrendingUp className="w-4 h-4" />
            Open Positions
            {openTrades.length > 0 && (
              <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                activeTab === 'open' ? 'bg-white/20' : 'bg-purple-500/20 text-purple-400'
              }`}>
                {openTrades.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all duration-200 ${
              activeTab === 'history'
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg'
                : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
            }`}
          >
            <Target className="w-4 h-4" />
            Trade History
            {closedTrades.length > 0 && (
              <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                activeTab === 'history' ? 'bg-white/20' : 'bg-purple-500/20 text-purple-400'
              }`}>
                {closedTrades.length}
              </span>
            )}
          </button>
        </div>

        {/* Content */}
        {activeTab === 'open' ? (
          <div>
            {loading && openTrades.length === 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="bg-gray-800 rounded-lg p-6 animate-pulse">
                    <div className="h-6 bg-gray-700 rounded w-1/2 mb-4"></div>
                    <div className="h-4 bg-gray-700 rounded w-3/4 mb-3"></div>
                    <div className="h-4 bg-gray-700 rounded w-2/3"></div>
                  </div>
                ))}
              </div>
            ) : openTrades.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {openTrades.map((trade) => (
                  <PaperTradeCard
                    key={trade.id}
                    trade={trade}
                    onClose={handleCloseTrade}
                    onCancel={handleCancelTrade}
                  />
                ))}
              </div>
            ) : (
              <div className="bg-gray-800/50 rounded-lg p-12 text-center">
                <div className="w-20 h-20 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
                  <TrendingUp className="w-10 h-10 text-purple-400" />
                </div>
                <h3 className="text-xl font-semibold text-white mb-2">No Open Positions</h3>
                <p className="text-gray-400 mb-6">
                  Start paper trading by creating trades from signals on the Dashboard
                </p>
                <a
                  href="/dashboard"
                  className="inline-flex items-center gap-2 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white px-6 py-3 rounded-lg font-medium transition-all duration-200"
                >
                  <Target className="w-5 h-5" />
                  Go to Dashboard
                </a>
              </div>
            )}
          </div>
        ) : (
          <TradeHistory trades={closedTrades} loading={loading} />
        )}
      </div>
    </div>
  );
};

export default PaperTrading;
