import React from 'react';
import { TrendingUp, TrendingDown, Target, Clock, DollarSign } from 'lucide-react';
import { format } from 'date-fns';

const TradeHistory = ({ trades, loading }) => {
  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-gray-800 rounded-lg p-4 animate-pulse">
            <div className="flex gap-4">
              <div className="h-12 w-12 bg-gray-700 rounded-lg"></div>
              <div className="flex-1">
                <div className="h-4 bg-gray-700 rounded w-1/4 mb-2"></div>
                <div className="h-3 bg-gray-700 rounded w-1/2"></div>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!trades || trades.length === 0) {
    return (
      <div className="bg-gray-800/50 rounded-lg p-12 text-center">
        <div className="w-16 h-16 bg-gray-700/50 rounded-full flex items-center justify-center mx-auto mb-4">
          <Target className="w-8 h-8 text-gray-500" />
        </div>
        <h3 className="text-lg font-semibold text-gray-400 mb-2">No Closed Trades</h3>
        <p className="text-sm text-gray-500">Your completed trades will appear here</p>
      </div>
    );
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'CLOSED_TP':
        return 'text-green-400 bg-green-500/20 border-green-500/50';
      case 'CLOSED_SL':
        return 'text-red-400 bg-red-500/20 border-red-500/50';
      case 'CLOSED_MANUAL':
        return 'text-blue-400 bg-blue-500/20 border-blue-500/50';
      case 'CANCELLED':
        return 'text-gray-400 bg-gray-500/20 border-gray-500/50';
      default:
        return 'text-gray-400 bg-gray-500/20 border-gray-500/50';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'CLOSED_TP':
        return 'TP Hit';
      case 'CLOSED_SL':
        return 'SL Hit';
      case 'CLOSED_MANUAL':
        return 'Manual Close';
      case 'CANCELLED':
        return 'Cancelled';
      default:
        return status;
    }
  };

  return (
    <div className="bg-gray-800/30 rounded-lg overflow-hidden border border-gray-700/50">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-800/50 border-b border-gray-700">
              <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Symbol
              </th>
              <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Direction
              </th>
              <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Entry / Exit
              </th>
              <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                P/L
              </th>
              <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Duration
              </th>
              <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Date
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {trades.map((trade) => {
              const isLong = trade.direction === 'LONG';
              const isProfit = trade.is_profitable;

              return (
                <tr
                  key={trade.id}
                  className="hover:bg-gray-700/30 transition-colors duration-150"
                >
                  {/* Symbol */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white">{trade.symbol}</span>
                      <span className="text-xs text-gray-500">{trade.market_type}</span>
                    </div>
                  </td>

                  {/* Direction */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      {isLong ? (
                        <TrendingUp className="w-4 h-4 text-green-400" />
                      ) : (
                        <TrendingDown className="w-4 h-4 text-red-400" />
                      )}
                      <span className={`font-medium ${isLong ? 'text-green-400' : 'text-red-400'}`}>
                        {trade.direction}
                      </span>
                    </div>
                  </td>

                  {/* Entry / Exit */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm">
                      <div className="text-gray-300">
                        ${parseFloat(trade.entry_price).toFixed(4)}
                      </div>
                      {trade.exit_price && (
                        <div className={isProfit ? 'text-green-400' : 'text-red-400'}>
                          ${parseFloat(trade.exit_price).toFixed(4)}
                        </div>
                      )}
                    </div>
                  </td>

                  {/* P/L */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <DollarSign className={`w-4 h-4 ${isProfit ? 'text-green-400' : 'text-red-400'}`} />
                      <div>
                        <div className={`font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                          {trade.profit_loss_formatted}
                        </div>
                        <div className={`text-xs ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                          {isProfit ? '+' : ''}{parseFloat(trade.profit_loss_percentage).toFixed(2)}%
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Duration */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2 text-gray-400">
                      <Clock className="w-4 h-4" />
                      <span className="text-sm">
                        {trade.duration_hours ? `${parseFloat(trade.duration_hours).toFixed(1)}h` : 'N/A'}
                      </span>
                    </div>
                  </td>

                  {/* Status */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 rounded-md text-xs font-medium border ${getStatusColor(trade.status)}`}>
                      {getStatusText(trade.status)}
                    </span>
                  </td>

                  {/* Date */}
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                    {trade.exit_time ? format(new Date(trade.exit_time), 'MMM dd, HH:mm') : 'N/A'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TradeHistory;
