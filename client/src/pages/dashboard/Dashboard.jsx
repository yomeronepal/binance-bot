/**
 * Dashboard page component
 * Main landing page after login with signal overview
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSignalStore } from '../../store/useSignalStore';
import { useAuthStore } from '../../store/useAuthStore';
import SignalCard from '../../components/common/SignalCard';

// Mock signals data for development
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
];

const Dashboard = () => {
  const { user } = useAuthStore();
  const { signals, fetchSignals, isLoading, connectWebSocket, disconnectWebSocket } = useSignalStore();
  const [useMockData, setUseMockData] = useState(true);

  useEffect(() => {
    // Try to fetch real signals
    fetchSignals().catch(() => {
      console.log('Using mock data');
      setUseMockData(true);
    });

    // Connect to WebSocket for real-time updates
    // connectWebSocket();

    // Cleanup on unmount
    return () => {
      // disconnectWebSocket();
    };
  }, []);

  const displaySignals = useMockData ? mockSignals : signals;
  const activeSignals = displaySignals.filter((s) => s.status === 'ACTIVE');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Welcome back, {user?.username}!
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Here's an overview of your trading signals
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
            Active Signals
          </h3>
          <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
            {activeSignals.length}
          </p>
        </div>

        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
            Total Signals
          </h3>
          <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
            {displaySignals.length}
          </p>
        </div>

        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
            Success Rate
          </h3>
          <p className="mt-2 text-3xl font-bold text-success">78%</p>
        </div>
      </div>

      {/* Recent Signals */}
      <div>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Recent Signals
          </h2>
          <Link to="/signals" className="btn btn-primary">
            View All
          </Link>
        </div>

        {isLoading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          </div>
        ) : displaySignals.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {displaySignals.slice(0, 6).map((signal) => (
              <SignalCard key={signal.id} signal={signal} />
            ))}
          </div>
        ) : (
          <div className="card text-center py-12">
            <p className="text-gray-500 dark:text-gray-400">
              No signals available yet
            </p>
          </div>
        )}
      </div>

      {useMockData && (
        <div className="card bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            📊 <strong>Note:</strong> Currently displaying mock data for demo purposes.
            Connect your backend API to see live signals.
          </p>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
