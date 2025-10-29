import React from 'react';
import { format } from 'date-fns';

/**
 * SignalCard component for displaying individual trading signals.
 * Color-coded for LONG (green) and SHORT (red).
 *
 * @param {object} signal - Signal data
 * @param {function} onClick - Click handler
 */
const SignalCard = ({ signal, onClick }) => {
  const isLong = signal.direction === 'LONG';
  const confidence = Math.round((signal.confidence || 0) * 100);

  // Color schemes
  const directionColors = {
    LONG: {
      bg: 'bg-green-50',
      border: 'border-green-200',
      badge: 'bg-green-500',
      text: 'text-green-700',
      hover: 'hover:bg-green-100',
    },
    SHORT: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      badge: 'bg-red-500',
      text: 'text-red-700',
      hover: 'hover:bg-red-100',
    },
  };

  const colors = directionColors[signal.direction] || directionColors.LONG;

  // Confidence color
  const getConfidenceColor = (conf) => {
    if (conf >= 80) return 'text-green-600 font-bold';
    if (conf >= 60) return 'text-blue-600 font-semibold';
    if (conf >= 40) return 'text-yellow-600';
    return 'text-gray-600';
  };

  // Status badge color
  const getStatusColor = (status) => {
    const statusColors = {
      ACTIVE: 'bg-green-500',
      EXECUTED: 'bg-blue-500',
      EXPIRED: 'bg-gray-500',
      CANCELLED: 'bg-red-500',
    };
    return statusColors[status] || 'bg-gray-500';
  };

  // Format price
  const formatPrice = (price) => {
    return parseFloat(price).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 8,
    });
  };

  // Calculate profit/loss percentages
  const profitPercent = signal.profit_percentage?.toFixed(2) || 'N/A';
  const riskReward = signal.risk_reward_ratio?.toFixed(2) || 'N/A';

  return (
    <div
      className={`${colors.bg} ${colors.border} ${colors.hover} border-2 rounded-lg p-4 cursor-pointer transition-all duration-200 hover:shadow-lg`}
      onClick={() => onClick && onClick(signal)}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          {/* Symbol */}
          <h3 className="text-lg font-bold text-gray-800">
            {signal.symbol_detail?.symbol || signal.symbol || 'N/A'}
          </h3>

          {/* Direction Badge */}
          <span
            className={`${colors.badge} text-white text-xs font-bold px-2 py-1 rounded`}
          >
            {signal.direction}
          </span>

          {/* Status Badge */}
          <span
            className={`${getStatusColor(signal.status)} text-white text-xs px-2 py-1 rounded`}
          >
            {signal.status}
          </span>
        </div>

        {/* Timeframe */}
        <span className="text-sm text-gray-600 font-medium">
          {signal.timeframe || '1h'}
        </span>
      </div>

      {/* Prices Grid */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        {/* Entry Price */}
        <div>
          <p className="text-xs text-gray-500 mb-1">Entry</p>
          <p className="text-sm font-bold text-gray-800">
            ${formatPrice(signal.entry)}
          </p>
        </div>

        {/* Stop Loss */}
        <div>
          <p className="text-xs text-gray-500 mb-1">Stop Loss</p>
          <p className="text-sm font-bold text-red-600">
            ${formatPrice(signal.sl)}
          </p>
        </div>

        {/* Take Profit */}
        <div>
          <p className="text-xs text-gray-500 mb-1">Take Profit</p>
          <p className="text-sm font-bold text-green-600">
            ${formatPrice(signal.tp)}
          </p>
        </div>
      </div>

      {/* Metrics */}
      <div className="flex items-center justify-between mb-3 pt-3 border-t border-gray-200">
        {/* Confidence */}
        <div className="flex items-center space-x-1">
          <span className="text-xs text-gray-500">Confidence:</span>
          <span className={`text-sm font-bold ${getConfidenceColor(confidence)}`}>
            {confidence}%
          </span>
        </div>

        {/* Profit % */}
        <div className="flex items-center space-x-1">
          <span className="text-xs text-gray-500">Profit:</span>
          <span className="text-sm font-semibold text-blue-600">
            {profitPercent}%
          </span>
        </div>

        {/* Risk/Reward */}
        <div className="flex items-center space-x-1">
          <span className="text-xs text-gray-500">R:R</span>
          <span className="text-sm font-semibold text-purple-600">
            1:{riskReward}
          </span>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>
          {signal.source && (
            <>
              Source: <span className="font-medium">{signal.source}</span>
            </>
          )}
        </span>
        <span>{format(new Date(signal.created_at), 'MMM dd, HH:mm')}</span>
      </div>

      {/* Description (if available) */}
      {signal.description && (
        <div className="mt-2 pt-2 border-t border-gray-200">
          <p className="text-xs text-gray-600 line-clamp-2">{signal.description}</p>
        </div>
      )}
    </div>
  );
};

export default SignalCard;
