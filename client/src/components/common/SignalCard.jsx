/**
 * Signal Card Component
 * Displays a trading signal in a card format
 */
import { Link } from 'react-router-dom';

const SignalCard = ({ signal }) => {
  const getSignalTypeColor = (type) => {
    switch (type) {
      case 'BUY':
        return 'bg-success text-white';
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
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="card hover:shadow-lg transition-shadow duration-200">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-xl font-bold text-gray-900 dark:text-white">
            {signal.symbol}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {formatDate(signal.created_at)}
          </p>
        </div>
        <div className="flex space-x-2">
          <span
            className={`px-3 py-1 rounded-full text-sm font-semibold ${getSignalTypeColor(
              signal.signal_type
            )}`}
          >
            {signal.signal_type}
          </span>
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(
              signal.status
            )}`}
          >
            {signal.status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">Entry Price</p>
          <p className="text-lg font-semibold text-gray-900 dark:text-white">
            ${parseFloat(signal.entry_price).toFixed(2)}
          </p>
        </div>

        {signal.target_price && (
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Target Price</p>
            <p className="text-lg font-semibold text-success">
              ${parseFloat(signal.target_price).toFixed(2)}
            </p>
          </div>
        )}

        {signal.stop_loss && (
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Stop Loss</p>
            <p className="text-lg font-semibold text-danger">
              ${parseFloat(signal.stop_loss).toFixed(2)}
            </p>
          </div>
        )}

        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">Confidence</p>
          <div className="flex items-center">
            <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2 mr-2">
              <div
                className={`h-2 rounded-full ${
                  signal.confidence >= 70
                    ? 'bg-success'
                    : signal.confidence >= 50
                    ? 'bg-warning'
                    : 'bg-danger'
                }`}
                style={{ width: `${signal.confidence}%` }}
              />
            </div>
            <span className="text-sm font-medium text-gray-900 dark:text-white">
              {signal.confidence}%
            </span>
          </div>
        </div>
      </div>

      {signal.description && (
        <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">
          {signal.description}
        </p>
      )}

      <div className="flex justify-end">
        <Link
          to={`/signals/${signal.id}`}
          className="btn btn-primary text-sm"
        >
          View Details
        </Link>
      </div>
    </div>
  );
};

export default SignalCard;
