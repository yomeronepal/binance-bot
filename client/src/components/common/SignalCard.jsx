/**
 * Signal Card Component
 * Displays a trading signal in a card format
 * Compatible with backend signal format (direction, entry, sl, tp)
 */
import { Link } from 'react-router-dom';

const SignalCard = ({ signal }) => {
  // Support both old and new signal formats
  const direction = signal.direction || signal.signal_type;
  const entry = signal.entry || signal.entry_price;
  const sl = signal.sl || signal.stop_loss;
  const tp = signal.tp || signal.target_price;
  const symbol = signal.symbol_name || signal.symbol_detail?.symbol || signal.symbol;
  const confidence = signal.confidence ? (signal.confidence <= 1 ? signal.confidence * 100 : signal.confidence) : 0;

  // Display BUY/SELL for spot, LONG/SHORT for futures
  const displayDirection = signal.market_type === 'FUTURES'
    ? direction
    : (direction === 'LONG' ? 'BUY' : direction === 'SHORT' ? 'SELL' : direction);

  const getSignalTypeColor = (type) => {
    switch (type) {
      case 'LONG':
      case 'BUY':
        return 'bg-success text-white';
      case 'SHORT':
      case 'SELL':
        return 'bg-danger text-white';
      case 'HOLD':
        return 'bg-warning text-white';
      default:
        return 'bg-gray-500 text-white';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'ACTIVE':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'EXPIRED':
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300';
      case 'EXECUTED':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'CANCELLED':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const formatPrice = (price) => {
    if (!price) return 'N/A';
    return parseFloat(price).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 8,
    });
  };

  return (
    <div className="card hover:shadow-lg transition-shadow duration-200">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-xl font-bold text-gray-900 dark:text-white">
            {symbol}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {formatDate(signal.created_at)}
          </p>
        </div>
        <div className="flex space-x-2">
          <span
            className={`px-3 py-1 rounded-full text-sm font-semibold ${getSignalTypeColor(direction)}`}
          >
            {displayDirection}
          </span>
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(signal.status)}`}
          >
            {signal.status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">Entry</p>
          <p className="text-lg font-semibold text-gray-900 dark:text-white">
            ${formatPrice(entry)}
          </p>
        </div>

        {tp && (
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Take Profit</p>
            <p className="text-lg font-semibold text-success">
              ${formatPrice(tp)}
            </p>
          </div>
        )}

        {sl && (
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Stop Loss</p>
            <p className="text-lg font-semibold text-danger">
              ${formatPrice(sl)}
            </p>
          </div>
        )}

        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">Confidence</p>
          <div className="flex items-center">
            <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2 mr-2">
              <div
                className={`h-2 rounded-full ${
                  confidence >= 70
                    ? 'bg-success'
                    : confidence >= 50
                    ? 'bg-warning'
                    : 'bg-danger'
                }`}
                style={{ width: `${confidence}%` }}
              />
            </div>
            <span className="text-sm font-medium text-gray-900 dark:text-white">
              {Math.round(confidence)}%
            </span>
          </div>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {signal.timeframe && (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
            {signal.timeframe}
          </span>
        )}
        {signal.trading_type && (
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
            signal.trading_type === 'SCALPING'
              ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
              : signal.trading_type === 'DAY'
              ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
              : 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200'
          }`}>
            {signal.trading_type === 'SCALPING' ? '⚡ Scalping' : signal.trading_type === 'DAY' ? '📊 Day' : '📈 Swing'}
          </span>
        )}
        {signal.estimated_duration_hours && (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200">
            ⏱️ {signal.estimated_duration_hours < 1
              ? `${Math.round(signal.estimated_duration_hours * 60)} min`
              : signal.estimated_duration_hours < 24
              ? `${Math.round(signal.estimated_duration_hours)} hrs`
              : `${Math.round(signal.estimated_duration_hours / 24)} days`}
          </span>
        )}
      </div>

      {signal.description && (
        <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">
          {signal.description}
        </p>
      )}

      <div className="flex justify-end">
        <Link
          to={`/spot-signals/${signal.id}`}
          className="btn btn-primary text-sm"
        >
          View Details
        </Link>
      </div>
    </div>
  );
};

export default SignalCard;
