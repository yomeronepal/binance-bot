/**
 * Backtest List Component
 */
import { Clock, CheckCircle, XCircle, Loader, TrendingUp, TrendingDown } from 'lucide-react';
import { format } from 'date-fns';

const BacktestList = ({ backtests, selectedBacktest, onSelectBacktest, loading }) => {
  const getStatusIcon = (status) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'FAILED':
        return <XCircle className="w-4 h-4 text-red-400" />;
      case 'RUNNING':
        return <Loader className="w-4 h-4 text-blue-400 animate-spin" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'COMPLETED':
        return 'text-green-400';
      case 'FAILED':
        return 'text-red-400';
      case 'RUNNING':
        return 'text-blue-400';
      default:
        return 'text-gray-400';
    }
  };

  if (loading && backtests.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  if (backtests.length === 0) {
    return (
      <div className="text-center py-12">
        <Clock className="w-12 h-12 text-gray-600 mx-auto mb-3" />
        <p className="text-gray-400">No backtests yet</p>
        <p className="text-gray-500 text-sm mt-1">Create your first backtest to get started</p>
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-[600px] overflow-y-auto">
      {backtests.map((backtest) => (
        <button
          key={backtest.id}
          onClick={() => onSelectBacktest(backtest)}
          className={`w-full text-left p-4 rounded-lg border transition-all ${
            selectedBacktest?.id === backtest.id
              ? 'bg-blue-500/10 border-blue-500/50'
              : 'bg-gray-900/30 border-gray-700/50 hover:bg-gray-900/50'
          }`}
        >
          <div className="flex items-start justify-between mb-2">
            <div className="flex-1 min-w-0">
              <h3 className="font-medium text-white truncate">{backtest.name}</h3>
              <p className="text-xs text-gray-400 mt-1">
                {backtest.symbols?.slice(0, 3).join(', ')}
                {backtest.symbols?.length > 3 && ` +${backtest.symbols.length - 3} more`}
              </p>
            </div>
            <div className="flex items-center gap-1 ml-2">
              {getStatusIcon(backtest.status)}
            </div>
          </div>

          <div className="flex items-center justify-between text-xs">
            <span className={`font-medium ${getStatusColor(backtest.status)}`}>
              {backtest.status}
            </span>
            {backtest.status === 'COMPLETED' && backtest.win_rate !== undefined && (
              <div className="flex items-center gap-2">
                <span className="text-gray-400">{parseFloat(backtest.win_rate).toFixed(1)}% WR</span>
                {backtest.roi !== undefined && (
                  <span className={`flex items-center gap-1 ${parseFloat(backtest.roi) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {parseFloat(backtest.roi) >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {parseFloat(backtest.roi).toFixed(1)}%
                  </span>
                )}
              </div>
            )}
          </div>

          {backtest.created_at && (
            <p className="text-xs text-gray-500 mt-2">
              {format(new Date(backtest.created_at), 'MMM d, yyyy HH:mm')}
            </p>
          )}
        </button>
      ))}
    </div>
  );
};

export default BacktestList;
