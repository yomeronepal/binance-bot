import React from 'react';
import { DollarSign, TrendingUp, Target, BarChart3, Percent, Award } from 'lucide-react';

const AutoTradingMetrics = ({ account, summary, openTradesCount }) => {
  if (!account) return null;

  const metrics = summary?.performance || {};

  // Calculate derived metrics
  const balanceChange = account.balance - account.initial_balance;
  const balanceChangePercent = ((balanceChange / account.initial_balance) * 100).toFixed(2);
  const equityChangePercent = ((account.equity / account.initial_balance - 1) * 100).toFixed(2);

  const totalPnl = parseFloat(account.total_pnl || 0);
  const realizedPnl = parseFloat(account.realized_pnl || 0);
  const unrealizedPnl = parseFloat(account.unrealized_pnl || 0);

  const isProfitable = totalPnl >= 0;

  const stats = [
    {
      label: 'Balance',
      value: `$${parseFloat(account.balance).toFixed(2)}`,
      subtext: `${balanceChange >= 0 ? '+' : ''}$${Math.abs(balanceChange).toFixed(2)} (${balanceChangePercent}%)`,
      icon: DollarSign,
      color: balanceChange >= 0 ? 'text-green-400' : 'text-red-400',
      gradient: balanceChange >= 0 ? 'from-green-500/20 to-green-600/10' : 'from-red-500/20 to-red-600/10',
      trend: balanceChange >= 0 ? 'up' : 'down',
    },
    {
      label: 'Equity',
      value: `$${parseFloat(account.equity).toFixed(2)}`,
      subtext: `${equityChangePercent >= 0 ? '+' : ''}${equityChangePercent}% from initial`,
      icon: BarChart3,
      color: equityChangePercent >= 0 ? 'text-blue-400' : 'text-orange-400',
      gradient: 'from-blue-500/20 to-blue-600/10',
      trend: 'neutral',
    },
    {
      label: 'Total P/L',
      value: `${totalPnl >= 0 ? '+' : ''}$${Math.abs(totalPnl).toFixed(2)}`,
      subtext: `Realized: ${realizedPnl >= 0 ? '+' : ''}$${Math.abs(realizedPnl).toFixed(2)} | Unrealized: ${unrealizedPnl >= 0 ? '+' : ''}$${Math.abs(unrealizedPnl).toFixed(2)}`,
      icon: TrendingUp,
      color: isProfitable ? 'text-green-400' : 'text-red-400',
      gradient: isProfitable ? 'from-green-500/20 to-green-600/10' : 'from-red-500/20 to-red-600/10',
      trend: isProfitable ? 'up' : 'down',
    },
    {
      label: 'Win Rate',
      value: `${parseFloat(account.win_rate || 0).toFixed(1)}%`,
      subtext: `${account.winning_trades || 0}W / ${account.losing_trades || 0}L`,
      icon: Percent,
      color: account.win_rate >= 50 ? 'text-green-400' : 'text-red-400',
      gradient: account.win_rate >= 50 ? 'from-green-500/20 to-green-600/10' : 'from-red-500/20 to-red-600/10',
      trend: account.win_rate >= 50 ? 'up' : 'down',
    },
    {
      label: 'Total Trades',
      value: account.total_trades || 0,
      subtext: `${openTradesCount} open positions`,
      icon: Target,
      color: 'text-purple-400',
      gradient: 'from-purple-500/20 to-purple-600/10',
      trend: 'neutral',
    },
    {
      label: 'Open Positions',
      value: openTradesCount,
      subtext: `Max: ${account.max_open_trades || 5}`,
      icon: Award,
      color: 'text-cyan-400',
      gradient: 'from-cyan-500/20 to-cyan-600/10',
      trend: 'neutral',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
      {stats.map((stat, index) => (
        <div
          key={index}
          className="relative overflow-hidden bg-gray-800/30 backdrop-blur-sm border border-gray-700 rounded-lg p-6 hover:border-gray-600 transition-all group"
        >
          {/* Background Gradient */}
          <div className={`absolute inset-0 bg-gradient-to-br ${stat.gradient} opacity-0 group-hover:opacity-100 transition-opacity`} />

          <div className="relative">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <stat.icon className={`w-5 h-5 ${stat.color}`} />
                <span className="text-gray-400 text-sm font-medium">{stat.label}</span>
              </div>

              {/* Trend Indicator */}
              {stat.trend === 'up' && (
                <div className="px-2 py-1 bg-green-500/20 border border-green-500/30 rounded text-green-400 text-xs font-medium">
                  ↑
                </div>
              )}
              {stat.trend === 'down' && (
                <div className="px-2 py-1 bg-red-500/20 border border-red-500/30 rounded text-red-400 text-xs font-medium">
                  ↓
                </div>
              )}
            </div>

            <div className={`text-2xl font-bold ${stat.color} mb-1`}>
              {stat.value}
            </div>

            <div className="text-sm text-gray-500">
              {stat.subtext}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default AutoTradingMetrics;
