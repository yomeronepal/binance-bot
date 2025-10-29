import React from 'react';
import { TrendingUp, TrendingDown, X, Clock, Target, AlertTriangle, DollarSign } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const PaperTradeCard = ({ trade, onClose, onCancel }) => {
  const isLong = trade.direction === 'LONG';
  const isPending = trade.status === 'PENDING';
  const isOpen = trade.status === 'OPEN';
  const isClosed = trade.is_closed;
  const isProfit = trade.is_profitable;

  // Calculate current position on SL-Entry-TP scale (0-100%)
  const getProgressPosition = () => {
    if (!trade.current_price) return 50;

    const entry = parseFloat(trade.entry_price);
    const sl = parseFloat(trade.stop_loss);
    const tp = parseFloat(trade.take_profit);
    const current = parseFloat(trade.current_price);

    if (isLong) {
      // For LONG: SL < Entry < TP
      const totalRange = tp - sl;
      const currentFromSL = current - sl;
      return Math.max(0, Math.min(100, (currentFromSL / totalRange) * 100));
    } else {
      // For SHORT: TP < Entry < SL
      const totalRange = sl - tp;
      const currentFromTP = current - tp;
      return Math.max(0, Math.min(100, (currentFromTP / totalRange) * 100));
    }
  };

  const progressPosition = getProgressPosition();

  // Colors based on direction
  const directionColor = isLong ? 'text-green-400' : 'text-red-400';
  const directionBg = isLong ? 'from-green-500/20 to-green-600/10' : 'from-red-500/20 to-red-600/10';
  const directionBorder = isLong ? 'border-green-500/50' : 'border-red-500/50';

  // Status badge
  const getStatusBadge = () => {
    const badges = {
      PENDING: { text: 'Pending', color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50' },
      OPEN: { text: 'Open', color: 'bg-blue-500/20 text-blue-400 border-blue-500/50' },
      CLOSED_TP: { text: 'TP Hit', color: 'bg-green-500/20 text-green-400 border-green-500/50' },
      CLOSED_SL: { text: 'SL Hit', color: 'bg-red-500/20 text-red-400 border-red-500/50' },
      CLOSED_MANUAL: { text: 'Closed', color: 'bg-gray-500/20 text-gray-400 border-gray-500/50' },
      CANCELLED: { text: 'Cancelled', color: 'bg-gray-500/20 text-gray-400 border-gray-500/50' },
    };

    const badge = badges[trade.status] || badges.OPEN;

    return (
      <span className={`px-2 py-1 rounded-md text-xs font-medium border ${badge.color}`}>
        {badge.text}
      </span>
    );
  };

  return (
    <div className={`bg-gradient-to-br ${directionBg} rounded-lg p-5 border ${directionBorder} backdrop-blur-sm transition-all duration-300 hover:scale-[1.02]`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg bg-gray-800/50 ${directionColor}`}>
            {isLong ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">{trade.symbol}</h3>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-sm font-medium ${directionColor}`}>
                {trade.direction}
              </span>
              <span className="text-gray-500">•</span>
              <span className="text-sm text-gray-400">{trade.market_type}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {getStatusBadge()}
          {isOpen && (
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
            </span>
          )}
        </div>
      </div>

      {/* Trade Info Grid */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-gray-800/30 rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Entry</p>
          <p className="text-sm font-bold text-white">${parseFloat(trade.entry_price).toFixed(4)}</p>
        </div>
        <div className="bg-red-900/20 rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Stop Loss</p>
          <p className="text-sm font-bold text-red-400">${parseFloat(trade.stop_loss).toFixed(4)}</p>
        </div>
        <div className="bg-green-900/20 rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Take Profit</p>
          <p className="text-sm font-bold text-green-400">${parseFloat(trade.take_profit).toFixed(4)}</p>
        </div>
      </div>

      {/* Progress Bar */}
      {isOpen && (
        <div className="mb-4">
          <div className="flex items-center justify-between text-xs text-gray-400 mb-2">
            <span>SL</span>
            <span className="text-white font-medium">
              {trade.current_price ? `$${parseFloat(trade.current_price).toFixed(4)}` : 'Entry'}
            </span>
            <span>TP</span>
          </div>
          <div className="relative h-2 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`absolute h-full transition-all duration-500 ${
                isLong ? 'bg-gradient-to-r from-red-500 via-yellow-500 to-green-500' : 'bg-gradient-to-r from-green-500 via-yellow-500 to-red-500'
              }`}
              style={{ width: `${progressPosition}%` }}
            />
            <div
              className="absolute top-1/2 -translate-y-1/2 w-1 h-4 bg-white rounded-full shadow-lg"
              style={{ left: `${progressPosition}%` }}
            />
          </div>
        </div>
      )}

      {/* Performance */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-gray-800/30 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-gray-400" />
            <p className="text-xs text-gray-500">P/L</p>
            {isOpen && trade.has_live_price && (
              <span className="flex items-center gap-1 px-1.5 py-0.5 bg-green-500/20 border border-green-500/50 rounded text-[10px] text-green-400">
                <span className="w-1 h-1 bg-green-400 rounded-full animate-pulse"></span>
                LIVE
              </span>
            )}
          </div>
          {isClosed ? (
            <>
              <p className={`text-lg font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                {trade.profit_loss_formatted}
              </p>
              <p className={`text-xs ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                {isProfit ? '+' : ''}{parseFloat(trade.profit_loss_percentage).toFixed(2)}%
              </p>
            </>
          ) : isOpen && trade.unrealized_pnl !== undefined ? (
            <>
              <p className={`text-lg font-bold ${trade.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {trade.unrealized_pnl >= 0 ? '+' : ''}${parseFloat(trade.unrealized_pnl).toFixed(2)}
              </p>
              <p className={`text-xs ${trade.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {trade.unrealized_pnl >= 0 ? '+' : ''}{parseFloat(trade.unrealized_pnl_pct).toFixed(2)}%
              </p>
            </>
          ) : (
            <p className="text-lg font-bold text-gray-400">Pending</p>
          )}
        </div>

        <div className="bg-gray-800/30 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <Target className="w-4 h-4 text-gray-400" />
            <p className="text-xs text-gray-500">R/R Ratio</p>
          </div>
          <p className="text-lg font-bold text-purple-400">
            {trade.risk_reward_ratio ? `1:${parseFloat(trade.risk_reward_ratio).toFixed(2)}` : 'N/A'}
          </p>
        </div>
      </div>

      {/* Time Info */}
      <div className="flex items-center justify-between text-xs text-gray-500 mb-4">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          <span>
            {trade.entry_time
              ? formatDistanceToNow(new Date(trade.entry_time), { addSuffix: true })
              : 'Not entered'}
          </span>
        </div>
        {isClosed && trade.duration_hours && (
          <span>Duration: {parseFloat(trade.duration_hours).toFixed(1)}h</span>
        )}
      </div>

      {/* Action Buttons */}
      {(isOpen || isPending) && (
        <div className="flex gap-2">
          {isOpen && onClose && (
            <button
              onClick={() => onClose(trade.id)}
              className="flex-1 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 flex items-center justify-center gap-2"
            >
              <X className="w-4 h-4" />
              Close Trade
            </button>
          )}

          {isPending && onCancel && (
            <button
              onClick={() => onCancel(trade.id)}
              className="flex-1 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 flex items-center justify-center gap-2"
            >
              <AlertTriangle className="w-4 h-4" />
              Cancel Trade
            </button>
          )}
        </div>
      )}

      {/* Signal Info */}
      {trade.signal_timeframe && (
        <div className="mt-4 pt-4 border-t border-gray-700/50 flex items-center justify-between text-xs text-gray-500">
          <span>Timeframe: {trade.signal_timeframe}</span>
          {trade.signal_confidence && (
            <span>Confidence: {(trade.signal_confidence * 100).toFixed(0)}%</span>
          )}
        </div>
      )}
    </div>
  );
};

export default PaperTradeCard;
