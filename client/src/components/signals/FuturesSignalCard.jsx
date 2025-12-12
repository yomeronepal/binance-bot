import { format } from 'date-fns';
import { Link } from 'react-router-dom';
import { useState } from 'react';
import usePaperTradeStore from '../../store/usePaperTradeStore';

const FuturesSignalCard = ({ signal, tradingMode = 'paper' }) => {
  const isLong = signal.direction === 'LONG';
  const [isCreatingTrade, setIsCreatingTrade] = useState(false);
  const { createTradeFromSignal } = usePaperTradeStore();

  const handleCreatePaperTrade = async () => {
    setIsCreatingTrade(true);
    try {
      await createTradeFromSignal(signal.id, 100); // Default $100 position
      alert('Paper trade created successfully!');
    } catch (error) {
      alert(`Failed to create paper trade: ${error.message}`);
    } finally {
      setIsCreatingTrade(false);
    }
  };

  const calculateRiskReward = () => {
    const risk = Math.abs(signal.entry - signal.sl);
    const reward = Math.abs(signal.tp - signal.entry);
    return risk > 0 ? (reward / risk).toFixed(2) : '0';
  };

  const calculateROI = () => {
    const leverage = signal.leverage || 10;
    const priceChange = Math.abs(signal.tp - signal.entry);
    const percentChange = (priceChange / signal.entry) * 100;
    return (percentChange * leverage).toFixed(1);
  };

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-xl shadow-lg border ${isLong ? 'border-green-400/30 dark:border-green-500/30' : 'border-red-400/30 dark:border-red-500/30'
      } hover:shadow-xl transition-all duration-300 overflow-hidden`}>
      {/* Header */}
      <div className={`px-4 sm:px-6 py-4 border-b border-gray-200 dark:border-gray-700 ${isLong ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'
        }`}>
        {/* Top row - Symbol and Direction */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg sm:text-xl font-bold text-gray-900 dark:text-white flex flex-wrap items-center gap-2">
              {signal.is_priority && (
                <span className="text-xs bg-amber-500 text-white px-2 py-1 rounded animate-pulse">
                  ⭐ PRIORITY
                </span>
              )}
              <span className="truncate">{signal.symbol_name || signal.symbol?.symbol || signal.symbol}</span>
              <span className="text-xs bg-yellow-100 dark:bg-yellow-500/20 text-yellow-700 dark:text-yellow-300 px-2 py-1 rounded whitespace-nowrap">
                FUTURES
              </span>
            </h3>
          </div>
          <div className="flex-shrink-0 text-right">
            <span className={`inline-flex items-center px-3 py-1.5 rounded-lg text-sm font-bold ${isLong
                ? 'bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400 border border-green-300 dark:border-green-500/30'
                : 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 border border-red-300 dark:border-red-500/30'
              }`}>
              {isLong ? '📈' : '📉'} {signal.direction}
            </span>
            <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {signal.leverage}x Leverage
            </div>
          </div>
        </div>

        {/* Tags row */}
        <div className="flex flex-wrap gap-2 mt-3">
          <span className="text-xs bg-blue-100 dark:bg-blue-500/20 text-blue-600 dark:text-blue-300 px-2 py-1 rounded">
            {signal.timeframe}
          </span>
          {signal.trading_type && (
            <span className={`text-xs px-2 py-1 rounded ${signal.trading_type === 'SCALPING'
                ? 'bg-purple-100 dark:bg-purple-500/20 text-purple-600 dark:text-purple-300'
                : signal.trading_type === 'DAY'
                  ? 'bg-yellow-100 dark:bg-yellow-500/20 text-yellow-700 dark:text-yellow-300'
                  : 'bg-indigo-100 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-300'
              }`}>
              {signal.trading_type === 'SCALPING' ? '⚡ Scalping' : signal.trading_type === 'DAY' ? '📊 Day' : '📈 Swing'}
            </span>
          )}
          {signal.estimated_duration_hours && (
            <span className="text-xs bg-gray-200 dark:bg-gray-600/50 text-gray-700 dark:text-gray-300 px-2 py-1 rounded">
              ⏱️ {signal.estimated_duration_hours < 1
                ? `${Math.round(signal.estimated_duration_hours * 60)} min`
                : signal.estimated_duration_hours < 24
                  ? `${Math.round(signal.estimated_duration_hours)} hrs`
                  : `${Math.round(signal.estimated_duration_hours / 24)} days`}
            </span>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="px-6 py-4">
        {/* Confidence */}
        <div className="mb-4">
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600 dark:text-gray-400">Confidence</span>
            <span className="text-gray-900 dark:text-white font-medium">{(signal.confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div
              className={`h-2 rounded-full ${signal.confidence >= 0.8 ? 'bg-green-500' :
                  signal.confidence >= 0.7 ? 'bg-yellow-500' :
                    'bg-red-500'
                }`}
              style={{ width: `${signal.confidence * 100}%` }}
            ></div>
          </div>
        </div>

        {/* Price Levels */}
        <div className="space-y-3 bg-gray-100 dark:bg-gray-900/50 rounded-lg p-4">
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-600 dark:text-gray-400">Entry Price</span>
            <span className="text-gray-900 dark:text-white font-mono font-bold">${parseFloat(signal.entry).toFixed(4)}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-green-600 dark:text-green-400">Take Profit</span>
            <span className="text-green-600 dark:text-green-300 font-mono font-bold">${parseFloat(signal.tp).toFixed(4)}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-red-600 dark:text-red-400">Stop Loss</span>
            <span className="text-red-600 dark:text-red-300 font-mono font-bold">${parseFloat(signal.sl).toFixed(4)}</span>
          </div>
        </div>

        {/* Risk/Reward Metrics */}
        <div className="mt-4 grid grid-cols-2 gap-4">
          <div className="bg-blue-100 dark:bg-blue-900/20 rounded-lg p-3">
            <p className="text-xs text-blue-600 dark:text-blue-400 mb-1">Risk/Reward</p>
            <p className="text-lg font-bold text-blue-700 dark:text-blue-300">1:{calculateRiskReward()}</p>
          </div>
          <div className="bg-purple-100 dark:bg-purple-900/20 rounded-lg p-3">
            <p className="text-xs text-purple-600 dark:text-purple-400 mb-1">Potential ROI</p>
            <p className="text-lg font-bold text-purple-700 dark:text-purple-300">+{calculateROI()}%</p>
          </div>
        </div>

        {/* Description */}
        {signal.description && (
          <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
              {signal.description}
            </p>
          </div>
        )}

        {/* Footer */}
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 flex justify-between items-center text-xs text-gray-500">
          <span>
            {signal.created_at && format(new Date(signal.created_at), 'MMM dd, HH:mm')}
          </span>
          <span className={`px-2 py-1 rounded ${signal.status === 'ACTIVE' ? 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400' :
              signal.status === 'EXPIRED' ? 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400' :
                'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400'
            }`}>
            {signal.status}
          </span>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="px-6 py-4 bg-gray-100 dark:bg-gray-900/50 border-t border-gray-200 dark:border-gray-700 flex space-x-2">
        {tradingMode === 'paper' ? (
          <button
            onClick={handleCreatePaperTrade}
            disabled={isCreatingTrade || signal.status !== 'ACTIVE'}
            className="flex-1 py-2 px-4 rounded-lg font-medium text-center bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isCreatingTrade ? 'Creating...' : '📝 Create Paper Trade'}
          </button>
        ) : (
          <a
            href={`https://www.binance.com/en/trade/${signal.symbol?.symbol || signal.symbol}?type=futures`}
            target="_blank"
            rel="noopener noreferrer"
            className={`flex-1 py-2 px-4 rounded-lg font-medium text-center transition-colors ${isLong
                ? 'bg-green-600 hover:bg-green-700 text-white'
                : 'bg-red-600 hover:bg-red-700 text-white'
              }`}
          >
            💰 Trade Now
          </a>
        )}
        <Link
          to={`/spot-signals/${signal.id}`}
          className="flex-1 py-2 px-4 rounded-lg font-medium text-center bg-blue-600 hover:bg-blue-700 text-white transition-colors"
        >
          View Details
        </Link>
      </div>
    </div>
  );
};

export default FuturesSignalCard;
