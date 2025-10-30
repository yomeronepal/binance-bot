/**
 * Trades Table Component
 */
import { useState } from 'react';
import { TrendingUp, TrendingDown, ArrowUpDown, BarChart3 } from 'lucide-react';
import { format } from 'date-fns';

const TradesTable = ({ trades }) => {
  const [sortBy, setSortBy] = useState('opened_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [filterDirection, setFilterDirection] = useState('ALL');
  const [filterStatus, setFilterStatus] = useState('ALL');

  if (!trades || trades.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <BarChart3 className="w-12 h-12 text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400">No trades available</p>
        </div>
      </div>
    );
  }

  // Filter trades
  let filteredTrades = [...trades];
  if (filterDirection !== 'ALL') {
    filteredTrades = filteredTrades.filter(t => t.direction === filterDirection);
  }
  if (filterStatus !== 'ALL') {
    filteredTrades = filteredTrades.filter(t => t.status === filterStatus);
  }

  // Sort trades
  filteredTrades.sort((a, b) => {
    let aVal = a[sortBy];
    let bVal = b[sortBy];

    // Handle dates
    if (sortBy === 'opened_at' || sortBy === 'closed_at') {
      aVal = new Date(aVal).getTime();
      bVal = new Date(bVal).getTime();
    }

    // Handle numbers
    if (sortBy === 'profit_loss' || sortBy === 'profit_loss_percentage' || sortBy === 'entry_price' || sortBy === 'exit_price') {
      aVal = parseFloat(aVal || 0);
      bVal = parseFloat(bVal || 0);
    }

    if (sortOrder === 'asc') {
      return aVal > bVal ? 1 : -1;
    } else {
      return aVal < bVal ? 1 : -1;
    }
  });

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const getStatusBadge = (status) => {
    const colors = {
      'CLOSED_TP': 'bg-green-500/20 text-green-400 border-green-500/30',
      'CLOSED_SL': 'bg-red-500/20 text-red-400 border-red-500/30',
      'CLOSED_MANUAL': 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    };
    const color = colors[status] || 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    const label = status.replace('CLOSED_', '').replace('_', ' ');

    return (
      <span className={`px-2 py-1 rounded border text-xs font-medium ${color}`}>
        {label}
      </span>
    );
  };

  const SortIcon = ({ field }) => {
    if (sortBy !== field) {
      return <ArrowUpDown className="w-3 h-3 text-gray-500" />;
    }
    return sortOrder === 'asc' ?
      <TrendingUp className="w-3 h-3 text-blue-400" /> :
      <TrendingDown className="w-3 h-3 text-blue-400" />;
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-4">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Direction</label>
          <select
            value={filterDirection}
            onChange={(e) => setFilterDirection(e.target.value)}
            className="bg-gray-900/50 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All</option>
            <option value="LONG">Long</option>
            <option value="SHORT">Short</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Status</label>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-gray-900/50 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All</option>
            <option value="CLOSED_TP">Take Profit</option>
            <option value="CLOSED_SL">Stop Loss</option>
            <option value="CLOSED_MANUAL">Manual</option>
          </select>
        </div>
        <div className="ml-auto text-sm text-gray-400">
          Showing {filteredTrades.length} of {trades.length} trades
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-3 px-4">
                <button
                  onClick={() => handleSort('symbol')}
                  className="flex items-center gap-2 text-xs font-medium text-gray-400 hover:text-white transition-colors"
                >
                  Symbol
                  <SortIcon field="symbol" />
                </button>
              </th>
              <th className="text-left py-3 px-4">
                <button
                  onClick={() => handleSort('direction')}
                  className="flex items-center gap-2 text-xs font-medium text-gray-400 hover:text-white transition-colors"
                >
                  Direction
                  <SortIcon field="direction" />
                </button>
              </th>
              <th className="text-right py-3 px-4">
                <button
                  onClick={() => handleSort('entry_price')}
                  className="flex items-center justify-end gap-2 text-xs font-medium text-gray-400 hover:text-white transition-colors w-full"
                >
                  Entry
                  <SortIcon field="entry_price" />
                </button>
              </th>
              <th className="text-right py-3 px-4">
                <button
                  onClick={() => handleSort('exit_price')}
                  className="flex items-center justify-end gap-2 text-xs font-medium text-gray-400 hover:text-white transition-colors w-full"
                >
                  Exit
                  <SortIcon field="exit_price" />
                </button>
              </th>
              <th className="text-right py-3 px-4">
                <button
                  onClick={() => handleSort('profit_loss')}
                  className="flex items-center justify-end gap-2 text-xs font-medium text-gray-400 hover:text-white transition-colors w-full"
                >
                  P/L
                  <SortIcon field="profit_loss" />
                </button>
              </th>
              <th className="text-right py-3 px-4">
                <button
                  onClick={() => handleSort('profit_loss_percentage')}
                  className="flex items-center justify-end gap-2 text-xs font-medium text-gray-400 hover:text-white transition-colors w-full"
                >
                  P/L %
                  <SortIcon field="profit_loss_percentage" />
                </button>
              </th>
              <th className="text-center py-3 px-4">
                <button
                  onClick={() => handleSort('status')}
                  className="flex items-center justify-center gap-2 text-xs font-medium text-gray-400 hover:text-white transition-colors w-full"
                >
                  Status
                  <SortIcon field="status" />
                </button>
              </th>
              <th className="text-right py-3 px-4">
                <button
                  onClick={() => handleSort('opened_at')}
                  className="flex items-center justify-end gap-2 text-xs font-medium text-gray-400 hover:text-white transition-colors w-full"
                >
                  Opened
                  <SortIcon field="opened_at" />
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredTrades.map((trade, index) => {
              const isProfitable = parseFloat(trade.profit_loss || 0) >= 0;
              return (
                <tr
                  key={trade.id || index}
                  className="border-b border-gray-800 hover:bg-gray-800/30 transition-colors"
                >
                  <td className="py-3 px-4">
                    <span className="text-white font-medium">{trade.symbol}</span>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${
                      trade.direction === 'LONG'
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-red-500/20 text-red-400'
                    }`}>
                      {trade.direction === 'LONG' ? (
                        <TrendingUp className="w-3 h-3" />
                      ) : (
                        <TrendingDown className="w-3 h-3" />
                      )}
                      {trade.direction}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className="text-gray-300">
                      ${parseFloat(trade.entry_price || 0).toFixed(2)}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className="text-gray-300">
                      ${parseFloat(trade.exit_price || 0).toFixed(2)}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className={`font-semibold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
                      {isProfitable ? '+' : ''}${parseFloat(trade.profit_loss || 0).toFixed(2)}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className={`font-semibold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
                      {isProfitable ? '+' : ''}{parseFloat(trade.profit_loss_percentage || 0).toFixed(2)}%
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center">
                    {getStatusBadge(trade.status)}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className="text-gray-400 text-xs">
                      {format(new Date(trade.opened_at), 'MMM d, HH:mm')}
                    </span>
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

export default TradesTable;
