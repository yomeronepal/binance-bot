/**
 * Signal List page component
 * Displays all trading signals with filtering
 */
import { useEffect, useState } from 'react';
import { useSignalStore } from '../../store/useSignalStore';
import SignalCard from '../../components/common/SignalCard';

// Mock signals - same as dashboard
const mockSignals = [
  {
    id: 1,
    symbol: 'BTCUSDT',
    signal_type: 'BUY',
    entry_price: '42500.00',
    target_price: '45000.00',
    stop_loss: '41000.00',
    confidence: 85,
    status: 'ACTIVE',
    description: 'Strong bullish momentum with high volume',
    created_at: new Date().toISOString(),
  },
  {
    id: 2,
    symbol: 'ETHUSDT',
    signal_type: 'SELL',
    entry_price: '2250.00',
    target_price: '2100.00',
    stop_loss: '2350.00',
    confidence: 72,
    status: 'ACTIVE',
    description: 'Bearish divergence detected on 4H chart',
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: 3,
    symbol: 'BNBUSDT',
    signal_type: 'BUY',
    entry_price: '315.00',
    target_price: '335.00',
    stop_loss: '305.00',
    confidence: 68,
    status: 'EXECUTED',
    description: 'Breakout above resistance level',
    created_at: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    id: 4,
    symbol: 'ADAUSDT',
    signal_type: 'HOLD',
    entry_price: '0.4850',
    target_price: '0.5200',
    stop_loss: '0.4650',
    confidence: 55,
    status: 'ACTIVE',
    description: 'Wait for confirmation before entry',
    created_at: new Date(Date.now() - 10800000).toISOString(),
  },
];

const SignalList = () => {
  const { signals, fetchSignals, isLoading } = useSignalStore();
  const [filter, setFilter] = useState('ALL');
  const [useMockData] = useState(true);

  useEffect(() => {
    fetchSignals();
  }, []);

  const displaySignals = useMockData ? mockSignals : signals;

  const filteredSignals = displaySignals.filter((signal) => {
    if (filter === 'ALL') return true;
    return signal.signal_type === filter || signal.status === filter;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Trading Signals
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Browse and analyze all trading signals
        </p>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setFilter('ALL')}
            className={`btn ${
              filter === 'ALL' ? 'btn-primary' : 'btn-secondary'
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilter('BUY')}
            className={`btn ${
              filter === 'BUY' ? 'btn-primary' : 'btn-secondary'
            }`}
          >
            Buy
          </button>
          <button
            onClick={() => setFilter('SELL')}
            className={`btn ${
              filter === 'SELL' ? 'btn-primary' : 'btn-secondary'
            }`}
          >
            Sell
          </button>
          <button
            onClick={() => setFilter('HOLD')}
            className={`btn ${
              filter === 'HOLD' ? 'btn-primary' : 'btn-secondary'
            }`}
          >
            Hold
          </button>
          <button
            onClick={() => setFilter('ACTIVE')}
            className={`btn ${
              filter === 'ACTIVE' ? 'btn-primary' : 'btn-secondary'
            }`}
          >
            Active
          </button>
          <button
            onClick={() => setFilter('EXECUTED')}
            className={`btn ${
              filter === 'EXECUTED' ? 'btn-primary' : 'btn-secondary'
            }`}
          >
            Executed
          </button>
        </div>
      </div>

      {/* Signals Grid */}
      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      ) : filteredSignals.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredSignals.map((signal) => (
            <SignalCard key={signal.id} signal={signal} />
          ))}
        </div>
      ) : (
        <div className="card text-center py-12">
          <p className="text-gray-500 dark:text-gray-400">
            No signals match your filter
          </p>
        </div>
      )}
    </div>
  );
};

export default SignalList;
