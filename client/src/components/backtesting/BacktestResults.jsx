/**
 * Backtest Results Display Component
 */
import { useEffect, useState } from 'react';
import { Loader, TrendingUp, TrendingDown, DollarSign, Target, Clock, BarChart3, Activity } from 'lucide-react';
import useBacktestStore from '../../store/useBacktestStore';
import EquityCurveChart from './EquityCurveChart';
import TradesTable from './TradesTable';

const BacktestResults = ({ backtest }) => {
  const {
    fetchBacktestDetails,
    fetchBacktestTrades,
    fetchBacktestMetrics,
    connectBacktestWS,
    stopPolling,
    currentBacktest,
    backtestTrades,
    backtestMetrics,
    loading,
    taskStatus
  } = useBacktestStore();

  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    if (backtest) {
      stopPolling();
      loadBacktestData();
    }

    return () => {
      stopPolling();
    };
  }, [backtest?.id]);

  const loadBacktestData = async () => {
    try {
      const details = await fetchBacktestDetails(backtest.id);

      if (details.status === 'COMPLETED') {
        // Load trades and metrics
        await Promise.all([
          fetchBacktestTrades(backtest.id),
          fetchBacktestMetrics(backtest.id)
        ]);
      } else if (details.status === 'RUNNING' || details.status === 'PENDING') {
        connectBacktestWS(backtest.id, async (completedBacktest) => {
          await Promise.all([
            fetchBacktestTrades(completedBacktest.id),
            fetchBacktestMetrics(completedBacktest.id)
          ]);
        });
      }
    } catch (error) {
      console.error('Error loading backtest data:', error);
    }
  };

  const data = currentBacktest || backtest;

  if (loading && !currentBacktest) {
    return (
      <div className="bg-white dark:bg-gray-800/50 backdrop-blur-sm border border-gray-200 dark:border-gray-700/50 rounded-xl p-12 flex items-center justify-center">
        <Loader className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  const isRunning = data.status === 'RUNNING' || data.status === 'PENDING';
  const isCompleted = data.status === 'COMPLETED';
  const isFailed = data.status === 'FAILED';

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <div className="bg-white dark:bg-gray-800/50 backdrop-blur-sm border border-gray-200 dark:border-gray-700/50 rounded-xl p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">{data.name}</h2>
            <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
              <span>{data.timeframe} • {data.symbols?.join(', ')}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isRunning && (
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg px-4 py-2 flex items-center gap-2">
                <Loader className="w-4 h-4 text-blue-400 animate-spin" />
                <span className="text-blue-400 font-medium">{taskStatus || 'RUNNING'}</span>
              </div>
            )}
            {isCompleted && (
              <div className="bg-green-500/10 border border-green-500/30 rounded-lg px-4 py-2 flex items-center gap-2">
                <Target className="w-4 h-4 text-green-400" />
                <span className="text-green-400 font-medium">COMPLETED</span>
              </div>
            )}
            {isFailed && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-2">
                <span className="text-red-400 font-medium">FAILED</span>
              </div>
            )}
          </div>
        </div>

        {isRunning && (
          <div className="mt-4 space-y-3">
            {data.progress_pct > 0 && (
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div className="bg-blue-500 h-2 rounded-full transition-all duration-500" style={{ width: `${data.progress_pct}%` }} />
              </div>
            )}
            <div className="bg-gray-100 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700/50 rounded-lg p-3 max-h-48 overflow-y-auto">
              {(data.progress_log || []).length === 0 ? (
                <p className="text-gray-500 text-xs">Waiting for logs...</p>
              ) : (
                <div className="space-y-1">
                  {(data.progress_log || []).map((log, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <span className="text-gray-500 font-mono flex-shrink-0">{log.time}</span>
                      <span className={`${log.msg?.includes('Signal:') ? 'text-emerald-400' : 'text-gray-700 dark:text-gray-300'}`}>{log.msg}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {isFailed && data.error_message && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 mt-4">
            <p className="text-red-600 dark:text-red-300 text-sm font-medium">Error:</p>
            <p className="text-red-600/80 dark:text-red-300 text-sm mt-1">{data.error_message}</p>
          </div>
        )}
      </div>

      {/* Results (only show if completed) */}
      {isCompleted && (
        <>
          {/* Metrics Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-gray-800/50 backdrop-blur-sm border border-gray-200 dark:border-gray-700/50 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-4 h-4 text-gray-400" />
                <p className="text-xs text-gray-500 dark:text-gray-400">Total P/L</p>
              </div>
              <p className={`text-2xl font-bold ${parseFloat(data.total_profit_loss || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {parseFloat(data.total_profit_loss || 0) >= 0 ? '+' : ''}
                ${parseFloat(data.total_profit_loss || 0).toFixed(2)}
              </p>
            </div>

            <div className="bg-white dark:bg-gray-800/50 backdrop-blur-sm border border-gray-200 dark:border-gray-700/50 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-4 h-4 text-gray-400" />
                <p className="text-xs text-gray-500 dark:text-gray-400">ROI</p>
              </div>
              <p className={`text-2xl font-bold ${parseFloat(data.roi || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {parseFloat(data.roi || 0) >= 0 ? '+' : ''}
                {parseFloat(data.roi || 0).toFixed(2)}%
              </p>
            </div>

            <div className="bg-white dark:bg-gray-800/50 backdrop-blur-sm border border-gray-200 dark:border-gray-700/50 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Target className="w-4 h-4 text-gray-400" />
                <p className="text-xs text-gray-500 dark:text-gray-400">Win Rate</p>
              </div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {parseFloat(data.win_rate || 0).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {data.winning_trades || 0}W / {data.losing_trades || 0}L
              </p>
            </div>

            <div className="bg-white dark:bg-gray-800/50 backdrop-blur-sm border border-gray-200 dark:border-gray-700/50 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="w-4 h-4 text-gray-400" />
                <p className="text-xs text-gray-500 dark:text-gray-400">Total Trades</p>
              </div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{data.total_trades || 0}</p>
            </div>
          </div>

          {/* Additional Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-gray-800/50 backdrop-blur-sm border border-gray-200 dark:border-gray-700/50 rounded-xl p-4">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Max Drawdown</p>
              <p className="text-lg font-bold text-red-400">
                -{parseFloat(data.max_drawdown || 0).toFixed(2)}%
              </p>
            </div>

            <div className="bg-white dark:bg-gray-800/50 backdrop-blur-sm border border-gray-200 dark:border-gray-700/50 rounded-xl p-4">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Sharpe Ratio</p>
              <p className="text-lg font-bold text-gray-900 dark:text-white">
                {data.sharpe_ratio ? parseFloat(data.sharpe_ratio).toFixed(2) : 'N/A'}
              </p>
            </div>

            <div className="bg-white dark:bg-gray-800/50 backdrop-blur-sm border border-gray-200 dark:border-gray-700/50 rounded-xl p-4">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Profit Factor</p>
              <p className="text-lg font-bold text-gray-900 dark:text-white">
                {data.profit_factor ? parseFloat(data.profit_factor).toFixed(2) : 'N/A'}
              </p>
            </div>

            <div className="bg-white dark:bg-gray-800/50 backdrop-blur-sm border border-gray-200 dark:border-gray-700/50 rounded-xl p-4">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Duration</p>
              <p className="text-lg font-bold text-gray-900 dark:text-white">
                {data.duration_seconds ? `${Math.floor(data.duration_seconds / 60)}m ${data.duration_seconds % 60}s` : 'N/A'}
              </p>
            </div>
          </div>

          {/* Tabs */}
          <div className="bg-white dark:bg-gray-800/50 backdrop-blur-sm border border-gray-200 dark:border-gray-700/50 rounded-xl overflow-hidden">
            <div className="flex border-b border-gray-200 dark:border-gray-700/50">
              <button
                onClick={() => setActiveTab('overview')}
                className={`flex-1 px-6 py-4 font-medium transition-colors ${
                  activeTab === 'overview'
                    ? 'bg-blue-500/10 text-blue-400 border-b-2 border-blue-500'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <div className="flex items-center justify-center gap-2">
                  <Activity className="w-4 h-4" />
                  Equity Curve
                </div>
              </button>
              <button
                onClick={() => setActiveTab('trades')}
                className={`flex-1 px-6 py-4 font-medium transition-colors ${
                  activeTab === 'trades'
                    ? 'bg-blue-500/10 text-blue-400 border-b-2 border-blue-500'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <div className="flex items-center justify-center gap-2">
                  <BarChart3 className="w-4 h-4" />
                  Trades ({backtestTrades.length})
                </div>
              </button>
              <button
                onClick={() => setActiveTab('logs')}
                className={`flex-1 px-6 py-4 font-medium transition-colors ${
                  activeTab === 'logs'
                    ? 'bg-blue-500/10 text-blue-400 border-b-2 border-blue-500'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <div className="flex items-center justify-center gap-2">
                  <Clock className="w-4 h-4" />
                  Logs ({(data.progress_log || []).length})
                </div>
              </button>
            </div>

            <div className="p-6">
              {activeTab === 'overview' && (
                <EquityCurveChart metrics={backtestMetrics} />
              )}
              {activeTab === 'trades' && (
                <TradesTable trades={backtestTrades} />
              )}
              {activeTab === 'logs' && (
                <div className="space-y-1 max-h-96 overflow-y-auto">
                  {(data.progress_log || []).length === 0 ? (
                    <p className="text-gray-500 text-sm">No logs available</p>
                  ) : (
                    (data.progress_log || []).map((log, i) => (
                      <div key={i} className="flex items-start gap-3 py-1.5 border-b border-gray-200 dark:border-gray-800/50 last:border-0">
                        <span className="text-gray-500 font-mono text-xs flex-shrink-0 pt-0.5">{log.time}</span>
                        <span className={`text-sm ${
                          log.msg?.includes('Signal:') ? 'text-emerald-400' :
                          log.msg?.includes('Completed') ? 'text-green-400 font-medium' :
                          log.msg?.includes('Failed') ? 'text-red-400' :
                          'text-gray-700 dark:text-gray-300'
                        }`}>{log.msg}</span>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default BacktestResults;
