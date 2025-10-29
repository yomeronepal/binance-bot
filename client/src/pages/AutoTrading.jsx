import React, { useEffect, useState } from 'react';
import { Bot, TrendingUp, Settings, RefreshCw, Power, RotateCcw, Activity } from 'lucide-react';
import useAutoTradeStore from '../store/useAutoTradeStore';
import AutoTradingMetrics from '../components/auto-trading/AutoTradingMetrics';
import AutoTradingSettings from '../components/auto-trading/AutoTradingSettings';
import PaperTradeCard from '../components/paper-trading/PaperTradeCard';
import TradeHistory from '../components/paper-trading/TradeHistory';

const AutoTrading = () => {
  const [activeTab, setActiveTab] = useState('overview'); // 'overview', 'settings', 'trades', 'history'
  const [showSettings, setShowSettings] = useState(false);

  const {
    account,
    trades,
    summary,
    loading,
    error,
    fetchAccount,
    fetchTrades,
    fetchSummary,
    startAutoTrading,
    resetAccount,
    updateSettings,
    closeTrade,
  } = useAutoTradeStore();

  const openTrades = (trades || []).filter(t => t.status === 'OPEN');
  const closedTrades = (trades || []).filter(t => t.status && t.status.startsWith('CLOSED'));

  useEffect(() => {
    loadData();

    // Refresh every 30 seconds
    const interval = setInterval(() => {
      loadData();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      await Promise.all([
        fetchAccount(),
        fetchTrades(),
        fetchSummary(),
      ]);
    } catch (err) {
      console.error('Error loading auto-trading data:', err);
    }
  };

  const handleStartAutoTrading = async () => {
    if (window.confirm('Start auto-trading with $1000 virtual balance?')) {
      try {
        await startAutoTrading();
        await loadData();
      } catch (error) {
        alert(`Failed to start auto-trading: ${error.message}`);
      }
    }
  };

  const handleResetAccount = async () => {
    if (window.confirm('⚠️ This will reset your account to $1000 and close all positions. Continue?')) {
      try {
        await resetAccount();
        await loadData();
      } catch (error) {
        alert(`Failed to reset account: ${error.message}`);
      }
    }
  };

  const handleToggleAutoTrading = async () => {
    const newState = !account?.auto_trading_enabled;
    try {
      await updateSettings({ auto_trading_enabled: newState });
      await fetchAccount();
    } catch (error) {
      alert(`Failed to ${newState ? 'enable' : 'disable'} auto-trading: ${error.message}`);
    }
  };

  const handleSettingsSave = async (settings) => {
    try {
      await updateSettings(settings);
      await fetchAccount();
      setShowSettings(false);
    } catch (error) {
      alert(`Failed to update settings: ${error.message}`);
    }
  };

  const handleCloseTrade = async (tradeId) => {
    if (window.confirm('Close this trade at current market price?')) {
      try {
        await closeTrade(tradeId);
        await loadData();
      } catch (error) {
        alert(`Failed to close trade: ${error.message}`);
      }
    }
  };

  const handleRefresh = () => {
    loadData();
  };

  if (loading && !account) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 text-blue-400 animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Loading auto-trading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error && !account) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="bg-gray-800/50 border border-red-500/30 rounded-lg p-8 text-center">
            <h2 className="text-2xl font-bold text-white mb-4">Auto-Trading Not Started</h2>
            <p className="text-gray-400 mb-6">Start auto-trading to let the bot trade for you automatically.</p>
            <button
              onClick={handleStartAutoTrading}
              className="px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-500 text-white rounded-lg font-medium hover:from-blue-600 hover:to-purple-600 transition-all"
            >
              <Bot className="w-5 h-5 inline mr-2" />
              Start Auto-Trading ($1000)
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-lg border border-blue-500/50">
                <Bot className="w-8 h-8 text-blue-400" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-white">Auto-Trading Dashboard</h1>
                <p className="text-gray-400">AI-powered automated paper trading</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Auto-Trading Toggle */}
              <button
                onClick={handleToggleAutoTrading}
                className={`px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${
                  account?.auto_trading_enabled
                    ? 'bg-green-500/20 border border-green-500/50 text-green-400 hover:bg-green-500/30'
                    : 'bg-red-500/20 border border-red-500/50 text-red-400 hover:bg-red-500/30'
                }`}
              >
                <Power className="w-4 h-4" />
                {account?.auto_trading_enabled ? 'Enabled' : 'Disabled'}
              </button>

              {/* Settings */}
              <button
                onClick={() => setShowSettings(true)}
                className="p-2 bg-gray-800/50 border border-gray-700 rounded-lg text-gray-400 hover:text-white hover:border-blue-500/50 transition-all"
              >
                <Settings className="w-5 h-5" />
              </button>

              {/* Reset */}
              <button
                onClick={handleResetAccount}
                className="p-2 bg-gray-800/50 border border-gray-700 rounded-lg text-gray-400 hover:text-red-400 hover:border-red-500/50 transition-all"
              >
                <RotateCcw className="w-5 h-5" />
              </button>

              {/* Refresh */}
              <button
                onClick={handleRefresh}
                className="p-2 bg-gray-800/50 border border-gray-700 rounded-lg text-gray-400 hover:text-white hover:border-blue-500/50 transition-all"
              >
                <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>

          {/* Status Banner */}
          {account?.auto_trading_enabled && (
            <div className="bg-gradient-to-r from-green-500/10 to-blue-500/10 border border-green-500/30 rounded-lg p-4 flex items-center gap-3">
              <Activity className="w-5 h-5 text-green-400 animate-pulse" />
              <div className="flex-1">
                <p className="text-green-400 font-medium">Auto-Trading Active</p>
                <p className="text-gray-400 text-sm">
                  Bot is automatically executing trades based on signals (min confidence: {account.min_signal_confidence * 100}%)
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Performance Metrics */}
        {account && (
          <AutoTradingMetrics
            account={account}
            summary={summary}
            openTradesCount={openTrades.length}
          />
        )}

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
              onClick={() => setActiveTab('trades')}
              className={`px-6 py-3 font-medium transition-all ${
                activeTab === 'trades'
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Open Positions ({openTrades.length})
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`px-6 py-3 font-medium transition-all ${
                activeTab === 'history'
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Trade History ({closedTrades.length})
            </button>
          </div>
        </div>

        {/* Content */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Recent Activity */}
            <div>
              <h2 className="text-xl font-bold text-white mb-4">Recent Open Positions</h2>
              {openTrades.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {openTrades.slice(0, 6).map(trade => (
                    <PaperTradeCard
                      key={trade.id}
                      trade={trade}
                      onClose={() => handleCloseTrade(trade.id)}
                    />
                  ))}
                </div>
              ) : (
                <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-8 text-center">
                  <p className="text-gray-400">No open positions</p>
                  <p className="text-gray-500 text-sm mt-2">
                    Trades will be automatically opened when signals are generated
                  </p>
                </div>
              )}
            </div>

            {/* Recent Closed Trades */}
            <div>
              <h2 className="text-xl font-bold text-white mb-4">Recent Closed Trades</h2>
              {closedTrades.length > 0 ? (
                <div className="bg-gray-800/30 border border-gray-700 rounded-lg overflow-hidden">
                  <TradeHistory trades={closedTrades.slice(0, 5)} />
                </div>
              ) : (
                <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-8 text-center">
                  <p className="text-gray-400">No closed trades yet</p>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'trades' && (
          <div>
            {openTrades.length > 0 ? (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {openTrades.map(trade => (
                  <PaperTradeCard
                    key={trade.id}
                    trade={trade}
                    onClose={() => handleCloseTrade(trade.id)}
                  />
                ))}
              </div>
            ) : (
              <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-12 text-center">
                <Bot className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400 text-lg">No open positions</p>
                <p className="text-gray-500 text-sm mt-2">
                  The bot will automatically open positions when signals meet your criteria
                </p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <div>
            {closedTrades.length > 0 ? (
              <div className="bg-gray-800/30 border border-gray-700 rounded-lg overflow-hidden">
                <TradeHistory trades={closedTrades} />
              </div>
            ) : (
              <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-12 text-center">
                <TrendingUp className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400 text-lg">No trade history yet</p>
                <p className="text-gray-500 text-sm mt-2">
                  Closed trades will appear here
                </p>
              </div>
            )}
          </div>
        )}

        {/* Settings Modal */}
        {showSettings && account && (
          <AutoTradingSettings
            account={account}
            onSave={handleSettingsSave}
            onClose={() => setShowSettings(false)}
          />
        )}
      </div>
    </div>
  );
};

export default AutoTrading;
