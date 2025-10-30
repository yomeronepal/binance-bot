/**
 * Backtesting Page - Strategy testing and optimization
 */
import { useState, useEffect } from 'react';
import { Activity, TrendingUp, Target, AlertCircle, Plus, RefreshCw } from 'lucide-react';
import useBacktestStore from '../store/useBacktestStore';
import BacktestConfigForm from '../components/backtesting/BacktestConfigForm';
import BacktestList from '../components/backtesting/BacktestList';
import BacktestResults from '../components/backtesting/BacktestResults';

const Backtesting = () => {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedBacktest, setSelectedBacktest] = useState(null);

  const { backtests, loading, error, fetchBacktests, clearCurrentBacktest } = useBacktestStore();

  useEffect(() => {
    fetchBacktests();

    // Cleanup on unmount
    return () => {
      clearCurrentBacktest();
    };
  }, []);

  const handleCreateBacktest = () => {
    setShowCreateForm(true);
    setSelectedBacktest(null);
  };

  const handleSelectBacktest = (backtest) => {
    setSelectedBacktest(backtest);
    setShowCreateForm(false);
  };

  const handleBacktestCreated = (backtest) => {
    setShowCreateForm(false);
    setSelectedBacktest(backtest);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-2">
            <Activity className="w-8 h-8 text-blue-400" />
            Backtesting
          </h1>
          <p className="text-gray-400 mt-1">
            Test your trading strategies on historical data and optimize parameters
          </p>
        </div>
        <button
          onClick={handleCreateBacktest}
          className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-medium flex items-center gap-2 transition-colors"
        >
          <Plus className="w-5 h-5" />
          New Backtest
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-red-400 font-medium">Error</p>
            <p className="text-red-300 text-sm mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-blue-500/10 p-3 rounded-lg">
              <Activity className="w-6 h-6 text-blue-400" />
            </div>
            <span className="text-2xl font-bold text-white">{backtests.length}</span>
          </div>
          <p className="text-gray-400 text-sm">Total Backtests</p>
        </div>

        <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-green-500/10 p-3 rounded-lg">
              <TrendingUp className="w-6 h-6 text-green-400" />
            </div>
            <span className="text-2xl font-bold text-white">
              {backtests.filter(b => b.status === 'COMPLETED').length}
            </span>
          </div>
          <p className="text-gray-400 text-sm">Completed</p>
        </div>

        <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-purple-500/10 p-3 rounded-lg">
              <Target className="w-6 h-6 text-purple-400" />
            </div>
            <span className="text-2xl font-bold text-white">
              {backtests.filter(b => b.status === 'RUNNING').length}
            </span>
          </div>
          <p className="text-gray-400 text-sm">Running</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Sidebar - Backtest List */}
        <div className="lg:col-span-1">
          <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-white">Backtests</h2>
              <button
                onClick={fetchBacktests}
                disabled={loading}
                className="text-gray-400 hover:text-white transition-colors disabled:opacity-50"
                title="Refresh list"
              >
                <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
            <BacktestList
              backtests={backtests}
              selectedBacktest={selectedBacktest}
              onSelectBacktest={handleSelectBacktest}
              loading={loading}
            />
          </div>
        </div>

        {/* Right Panel - Form or Results */}
        <div className="lg:col-span-2">
          {showCreateForm ? (
            <BacktestConfigForm onBacktestCreated={handleBacktestCreated} />
          ) : selectedBacktest ? (
            <BacktestResults backtest={selectedBacktest} />
          ) : (
            <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-12 text-center">
              <Activity className="w-16 h-16 text-gray-600 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-gray-400 mb-2">No Backtest Selected</h3>
              <p className="text-gray-500 mb-6">
                Select a backtest from the list or create a new one to get started
              </p>
              <button
                onClick={handleCreateBacktest}
                className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-medium inline-flex items-center gap-2 transition-colors"
              >
                <Plus className="w-5 h-5" />
                Create New Backtest
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Backtesting;
