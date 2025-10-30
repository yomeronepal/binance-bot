/**
 * Configuration Comparison Table Component
 * Compare performance across different volatility-aware configurations
 */
import { TrendingUp, TrendingDown, Target, DollarSign, Activity } from 'lucide-react';

const ConfigurationComparisonTable = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="text-center text-gray-500 py-8">
        No configuration data available
      </div>
    );
  }

  // Sort by total PnL descending
  const sortedData = [...data].sort((a, b) => b.totalPnL - a.totalPnL);

  const getVolatilityBadge = (level) => {
    const colors = {
      HIGH: 'bg-red-500/10 border-red-500/30 text-red-400',
      MEDIUM: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400',
      LOW: 'bg-green-500/10 border-green-500/30 text-green-400'
    };
    return colors[level] || 'bg-gray-500/10 border-gray-500/30 text-gray-400';
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left text-xs font-medium text-gray-400 uppercase tracking-wider pb-3 px-3">
              Volatility
            </th>
            <th className="text-left text-xs font-medium text-gray-400 uppercase tracking-wider pb-3 px-3">
              Configuration
            </th>
            <th className="text-center text-xs font-medium text-gray-400 uppercase tracking-wider pb-3 px-3">
              Symbols
            </th>
            <th className="text-right text-xs font-medium text-gray-400 uppercase tracking-wider pb-3 px-3">
              Win Rate
            </th>
            <th className="text-right text-xs font-medium text-gray-400 uppercase tracking-wider pb-3 px-3">
              Total P&L
            </th>
            <th className="text-right text-xs font-medium text-gray-400 uppercase tracking-wider pb-3 px-3">
              Avg Return
            </th>
            <th className="text-right text-xs font-medium text-gray-400 uppercase tracking-wider pb-3 px-3">
              Sharpe
            </th>
            <th className="text-right text-xs font-medium text-gray-400 uppercase tracking-wider pb-3 px-3">
              Max DD
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700/50">
          {sortedData.map((config, idx) => (
            <tr key={idx} className="hover:bg-gray-700/20 transition-colors">
              <td className="py-4 px-3">
                <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium border ${getVolatilityBadge(config.volatility)}`}>
                  {config.volatility}
                </span>
              </td>
              <td className="py-4 px-3">
                <div className="text-sm">
                  <div className="text-white font-medium">{config.name}</div>
                  <div className="text-gray-400 text-xs mt-0.5">
                    SL: {config.slMultiplier}x | TP: {config.tpMultiplier}x | ADX: {config.adxThreshold}
                  </div>
                </div>
              </td>
              <td className="py-4 px-3 text-center">
                <div className="text-sm text-white">{config.symbols.length}</div>
                <div className="text-xs text-gray-400">{config.totalTrades} trades</div>
              </td>
              <td className="py-4 px-3 text-right">
                <div className="flex items-center justify-end gap-1">
                  {config.winRate >= 50 ? (
                    <TrendingUp className="w-4 h-4 text-green-400" />
                  ) : (
                    <TrendingDown className="w-4 h-4 text-red-400" />
                  )}
                  <span className={`text-sm font-medium ${config.winRate >= 50 ? 'text-green-400' : 'text-yellow-400'}`}>
                    {config.winRate.toFixed(1)}%
                  </span>
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  {config.wins}W / {config.losses}L
                </div>
              </td>
              <td className="py-4 px-3 text-right">
                <div className={`text-sm font-bold ${config.totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {config.totalPnL >= 0 ? '+' : ''}${config.totalPnL.toFixed(2)}
                </div>
              </td>
              <td className="py-4 px-3 text-right">
                <div className={`text-sm font-medium ${config.avgReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {config.avgReturn >= 0 ? '+' : ''}{config.avgReturn.toFixed(2)}%
                </div>
              </td>
              <td className="py-4 px-3 text-right">
                <div className={`text-sm font-medium ${
                  config.sharpeRatio > 1 ? 'text-green-400' :
                  config.sharpeRatio > 0 ? 'text-yellow-400' :
                  'text-red-400'
                }`}>
                  {config.sharpeRatio ? config.sharpeRatio.toFixed(2) : 'N/A'}
                </div>
              </td>
              <td className="py-4 px-3 text-right">
                <div className="text-sm font-medium text-red-400">
                  -{config.maxDrawdown.toFixed(2)}%
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Summary Stats */}
      <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-900/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-blue-400" />
            <p className="text-xs text-gray-400">Best Configuration</p>
          </div>
          <p className="text-sm font-bold text-white">{sortedData[0].name}</p>
          <p className="text-xs text-green-400 mt-1">
            +{sortedData[0].avgReturn.toFixed(1)}% avg return
          </p>
        </div>

        <div className="bg-gray-900/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-green-400" />
            <p className="text-xs text-gray-400">Highest Win Rate</p>
          </div>
          <p className="text-sm font-bold text-white">
            {[...data].sort((a, b) => b.winRate - a.winRate)[0].name}
          </p>
          <p className="text-xs text-green-400 mt-1">
            {[...data].sort((a, b) => b.winRate - a.winRate)[0].winRate.toFixed(1)}%
          </p>
        </div>

        <div className="bg-gray-900/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-purple-400" />
            <p className="text-xs text-gray-400">Best Risk-Adjusted</p>
          </div>
          <p className="text-sm font-bold text-white">
            {[...data].sort((a, b) => (b.sharpeRatio || 0) - (a.sharpeRatio || 0))[0].name}
          </p>
          <p className="text-xs text-purple-400 mt-1">
            Sharpe: {[...data].sort((a, b) => (b.sharpeRatio || 0) - (a.sharpeRatio || 0))[0].sharpeRatio?.toFixed(2) || 'N/A'}
          </p>
        </div>

        <div className="bg-gray-900/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-4 h-4 text-yellow-400" />
            <p className="text-xs text-gray-400">Total Across All</p>
          </div>
          <p className="text-sm font-bold text-white">
            {data.reduce((sum, c) => sum + c.totalTrades, 0)} trades
          </p>
          <p className={`text-xs mt-1 ${
            data.reduce((sum, c) => sum + c.totalPnL, 0) >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {data.reduce((sum, c) => sum + c.totalPnL, 0) >= 0 ? '+' : ''}
            ${data.reduce((sum, c) => sum + c.totalPnL, 0).toFixed(2)}
          </p>
        </div>
      </div>
    </div>
  );
};

export default ConfigurationComparisonTable;
