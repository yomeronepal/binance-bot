import React, { useEffect, useState } from 'react';
import { Target, TrendingUp, AlertCircle, RefreshCw, Plus, X } from 'lucide-react';
import usePaperTradeStore from '../store/usePaperTradeStore';
import PerformanceMetrics from '../components/paper-trading/PerformanceMetrics';
import PaperTradeCard from '../components/paper-trading/PaperTradeCard';
import TradeHistory from '../components/paper-trading/TradeHistory';
import TradingSessionStatus from '../components/common/TradingSessionStatus';

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
    createManualTrade, // Add creation action
  } = usePaperTradeStore();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTrade, setNewTrade] = useState({
    symbol: 'BTCUSDT',
    direction: 'LONG',
    entry_price: '',
    position_size: '100',
    stop_loss: '',
    take_profit: '',
    leverage: 1
  });
  const [creating, setCreating] = useState(false);

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      await createManualTrade({
        symbol: newTrade.symbol.toUpperCase(),
        direction: newTrade.direction,
        entry_price: parseFloat(newTrade.entry_price),
        position_size: parseFloat(newTrade.position_size),
        stop_loss: parseFloat(newTrade.stop_loss),
        take_profit: parseFloat(newTrade.take_profit),
        leverage: parseInt(newTrade.leverage),
        market_type: 'FUTURES'
      });
      setShowCreateModal(false);
      setNewTrade({
        symbol: 'BTCUSDT',
        direction: 'LONG',
        entry_price: '',
        position_size: '100',
        stop_loss: '',
        take_profit: '',
        leverage: 1
      });
    } catch (err) {
      alert(err.message);
    } finally {
      setCreating(false);
    }
  };

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
        const trade = openTrades.find(t => t.id === tradeId);
        const currentPrice = trade?.current_price || trade?.entry_price; // Fallback to entry price if live price missing

        await closeTrade(tradeId, currentPrice);
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

              {/* Create Trade Button */}
              <button
                onClick={() => setShowCreateModal(true)}
                className="flex items-center gap-2 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200"
              >
                <Plus className="w-4 h-4" />
                Create Trade
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

          {/* Trading Session Status */}
          <div className="mt-6">
            <TradingSessionStatus />
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
            className={`flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all duration-200 ${activeTab === 'open'
              ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg'
              : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
              }`}
          >
            <TrendingUp className="w-4 h-4" />
            Open Positions
            {openTrades.length > 0 && (
              <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${activeTab === 'open' ? 'bg-white/20' : 'bg-purple-500/20 text-purple-400'
                }`}>
                {openTrades.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all duration-200 ${activeTab === 'history'
              ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg'
              : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
              }`}
          >
            <Target className="w-4 h-4" />
            Trade History
            {closedTrades.length > 0 && (
              <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${activeTab === 'history' ? 'bg-white/20' : 'bg-purple-500/20 text-purple-400'
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

      {/* Create Trade Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-xl border border-gray-700 w-full max-w-md p-6 relative shadow-2xl">
            <button
              onClick={() => setShowCreateModal(false)}
              className="absolute top-4 right-4 text-gray-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-purple-400" />
              Create Manual Trade
            </h2>

            <form onSubmit={handleCreateSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Symbol</label>
                <input
                  type="text"
                  required
                  value={newTrade.symbol}
                  onChange={e => setNewTrade({ ...newTrade, symbol: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                  placeholder="BTCUSDT"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Direction</label>
                  <select
                    value={newTrade.direction}
                    onChange={e => setNewTrade({ ...newTrade, direction: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                  >
                    <option value="LONG">LONG</option>
                    <option value="SHORT">SHORT</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Leverage</label>
                  <input
                    type="number"
                    required
                    min="1"
                    max="125"
                    value={newTrade.leverage}
                    onChange={e => setNewTrade({ ...newTrade, leverage: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Entry Price (USDT)</label>
                <input
                  type="number"
                  required
                  step="any"
                  value={newTrade.entry_price}
                  onChange={e => setNewTrade({ ...newTrade, entry_price: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                  placeholder="0.00"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Stop Loss</label>
                  <input
                    type="number"
                    required
                    step="any"
                    value={newTrade.stop_loss}
                    onChange={e => setNewTrade({ ...newTrade, stop_loss: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                    placeholder="0.00"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Take Profit</label>
                  <input
                    type="number"
                    required
                    step="any"
                    value={newTrade.take_profit}
                    onChange={e => setNewTrade({ ...newTrade, take_profit: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                    placeholder="0.00"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Position Size (USDT)</label>
                <input
                  type="number"
                  required
                  min="10"
                  step="any"
                  value={newTrade.position_size}
                  onChange={e => setNewTrade({ ...newTrade, position_size: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={creating}
                  className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white font-bold py-3 rounded-lg transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {creating ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Plus className="w-5 h-5" />}
                  Create Trade
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default PaperTrading;
