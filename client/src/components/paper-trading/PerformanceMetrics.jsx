import React from 'react';
import { TrendingUp, TrendingDown, Activity, DollarSign, Target, Clock } from 'lucide-react';

const PerformanceMetrics = ({ metrics, loading }) => {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-gray-800 rounded-lg p-6 animate-pulse">
            <div className="h-4 bg-gray-700 rounded w-1/2 mb-4"></div>
            <div className="h-8 bg-gray-700 rounded w-3/4"></div>
          </div>
        ))}
      </div>
    );
  }

  if (!metrics) {
    return null;
  }

  // Safe access to metrics with defaults
  const realizedPnl = metrics.total_profit_loss || 0;
  const unrealizedPnl = metrics.unrealized_pnl || 0;
  const totalPnl = metrics.total_pnl || 0;
  const winRate = metrics.win_rate || 0;
  const winningTrades = metrics.winning_trades || metrics.profitable_trades || 0;
  const totalTrades = metrics.total_trades || 0;
  const openTrades = metrics.open_trades || 0;
  const averageDuration = metrics.average_duration_hours || metrics.avg_duration_hours || 0;

  const isTotalProfit = totalPnl >= 0;
  const totalProfitColor = isTotalProfit ? 'text-green-400' : 'text-red-400';
  const totalProfitBg = isTotalProfit ? 'from-green-500/20 to-green-600/10' : 'from-red-500/20 to-red-600/10';

  const isRealizedProfit = realizedPnl >= 0;
  const realizedColor = isRealizedProfit ? 'text-green-400' : 'text-red-400';

  const isUnrealizedProfit = unrealizedPnl >= 0;
  const unrealizedColor = isUnrealizedProfit ? 'text-green-400' : 'text-red-400';

  const stats = [
    {
      label: 'Total P/L',
      value: `${isTotalProfit ? '+' : ''}$${Math.abs(totalPnl).toFixed(2)}`,
      subtext: `Realized: ${isRealizedProfit ? '+' : ''}$${Math.abs(realizedPnl).toFixed(2)} | Unrealized: ${isUnrealizedProfit ? '+' : ''}$${Math.abs(unrealizedPnl).toFixed(2)}`,
      icon: DollarSign,
      color: totalProfitColor,
      gradient: totalProfitBg,
      trend: isTotalProfit ? 'up' : 'down',
    },
    {
      label: 'Win Rate',
      value: `${winRate.toFixed(1)}%`,
      subtext: `${winningTrades}/${totalTrades} trades`,
      icon: Target,
      color: winRate >= 50 ? 'text-green-400' : 'text-orange-400',
      gradient: winRate >= 50 ? 'from-green-500/20 to-green-600/10' : 'from-orange-500/20 to-orange-600/10',
    },
    {
      label: 'Total Trades',
      value: totalTrades,
      subtext: `${openTrades} open`,
      icon: Activity,
      color: 'text-blue-400',
      gradient: 'from-blue-500/20 to-blue-600/10',
    },
    {
      label: 'Avg Duration',
      value: averageDuration > 0 ? `${averageDuration.toFixed(1)}h` : 'N/A',
      subtext: averageDuration > 0 ? (averageDuration < 24 ? 'Fast trades' : 'Swing trades') : 'No closed trades',
      icon: Clock,
      color: 'text-purple-400',
      gradient: 'from-purple-500/20 to-purple-600/10',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {stats.map((stat, index) => {
        const Icon = stat.icon;
        return (
          <div
            key={index}
            className={`bg-gradient-to-br ${stat.gradient} rounded-lg p-6 border border-gray-700/50 backdrop-blur-sm transition-all duration-300 hover:scale-105 hover:border-gray-600`}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-gray-400 font-medium">{stat.label}</span>
              <Icon className={`w-5 h-5 ${stat.color}`} />
            </div>

            <div className="flex items-baseline gap-2 mb-1">
              <span className={`text-2xl font-bold ${stat.color}`}>
                {stat.value}
              </span>
              {stat.trend && (
                <span className="flex items-center">
                  {stat.trend === 'up' ? (
                    <TrendingUp className="w-4 h-4 text-green-400" />
                  ) : (
                    <TrendingDown className="w-4 h-4 text-red-400" />
                  )}
                </span>
              )}
            </div>

            {stat.subtext && (
              <p className="text-xs text-gray-500">{stat.subtext}</p>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default PerformanceMetrics;
