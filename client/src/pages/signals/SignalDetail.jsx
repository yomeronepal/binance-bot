/**
 * Signal Detail page component
 * Displays detailed information about a single signal with chart
 */
import { useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useSignalStore } from '../../store/useSignalStore';
import SignalChart from '../../components/charts/SignalChart';

// Mock signal for detail view
const mockSignal = {
  id: 1,
  symbol: 'BTCUSDT',
  signal_type: 'BUY',
  entry_price: '42500.00',
  target_price: '45000.00',
  stop_loss: '41000.00',
  confidence: 85,
  status: 'ACTIVE',
  description: 'Strong bullish momentum with high volume. RSI showing strong buy signal with MACD crossover. Breaking through resistance at 42000.',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 86400000).toISOString(),
};

const SignalDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { currentSignal, fetchSignalById, isLoading } = useSignalStore();

  useEffect(() => {
    // Try to fetch signal by ID
    // fetchSignalById(id);
  }, [id]);

  // Use mock signal for now
  const signal = mockSignal;

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (!signal) {
    return (
      <div className="card text-center py-12">
        <p className="text-gray-500 dark:text-gray-400 mb-4">Signal not found</p>
        <Link to="/signals" className="btn btn-primary">
          Back to Signals
        </Link>
      </div>
    );
  }

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center space-x-4">
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              {signal.symbol}
            </h1>
            <span
              className={`px-4 py-2 rounded-full text-sm font-semibold ${getSignalTypeColor(
                signal.signal_type
              )}`}
            >
              {signal.signal_type}
            </span>
          </div>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Signal ID: {signal.id}
          </p>
        </div>
        <button
          onClick={() => navigate('/signals')}
          className="btn btn-secondary"
        >
          ← Back
        </button>
      </div>

      {/* Chart */}
      <SignalChart signal={signal} />

      {/* Signal Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Price Information */}
        <div className="card">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
            Price Information
          </h2>
          <div className="space-y-4">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Entry Price</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                ${parseFloat(signal.entry_price).toFixed(2)}
              </p>
            </div>

            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Target Price</p>
              <p className="text-2xl font-bold text-success">
                ${parseFloat(signal.target_price).toFixed(2)}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Profit: {(((parseFloat(signal.target_price) - parseFloat(signal.entry_price)) / parseFloat(signal.entry_price)) * 100).toFixed(2)}%
              </p>
            </div>

            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Stop Loss</p>
              <p className="text-2xl font-bold text-danger">
                ${parseFloat(signal.stop_loss).toFixed(2)}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Risk: {(((parseFloat(signal.entry_price) - parseFloat(signal.stop_loss)) / parseFloat(signal.entry_price)) * 100).toFixed(2)}%
              </p>
            </div>

            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                Confidence Level
              </p>
              <div className="flex items-center">
                <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-4 mr-3">
                  <div
                    className={`h-4 rounded-full ${
                      signal.confidence >= 70
                        ? 'bg-success'
                        : signal.confidence >= 50
                        ? 'bg-warning'
                        : 'bg-danger'
                    }`}
                    style={{ width: `${signal.confidence}%` }}
                  />
                </div>
                <span className="text-lg font-bold text-gray-900 dark:text-white">
                  {signal.confidence}%
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Signal Metadata */}
        <div className="card">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
            Signal Details
          </h2>
          <div className="space-y-4">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Status</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {signal.status}
              </p>
            </div>

            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Created</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {formatDate(signal.created_at)}
              </p>
            </div>

            {signal.expires_at && (
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Expires</p>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {formatDate(signal.expires_at)}
                </p>
              </div>
            )}

            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                Description
              </p>
              <p className="text-gray-700 dark:text-gray-300">
                {signal.description}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Risk/Reward Ratio */}
      <div className="card">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
          Risk/Reward Analysis
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Risk Amount</p>
            <p className="text-xl font-bold text-danger">
              ${(parseFloat(signal.entry_price) - parseFloat(signal.stop_loss)).toFixed(2)}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Reward Amount</p>
            <p className="text-xl font-bold text-success">
              ${(parseFloat(signal.target_price) - parseFloat(signal.entry_price)).toFixed(2)}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Risk/Reward Ratio</p>
            <p className="text-xl font-bold text-primary-600">
              1:{(
                (parseFloat(signal.target_price) - parseFloat(signal.entry_price)) /
                (parseFloat(signal.entry_price) - parseFloat(signal.stop_loss))
              ).toFixed(2)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignalDetail;
