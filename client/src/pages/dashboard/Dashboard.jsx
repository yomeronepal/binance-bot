/**
 * Dashboard page component
 * Main landing page after login with signal overview and real-time WebSocket updates
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSignalStore } from '../../store/useSignalStore';
import { useAuthStore } from '../../store/useAuthStore';
import { useWebSocket } from '../../hooks/useWebSocket';
import SignalCard from '../../components/common/SignalCard';
import FuturesSignalCard from '../../components/signals/FuturesSignalCard';

// Mock signals data for development
const mockSignals = [
  {
    id: 1,
    symbol: 'BTCUSDT',
    direction: 'LONG',
    entry: '42500.00',
    tp: '45000.00',
    sl: '41000.00',
    confidence: 0.85,
    timeframe: '4h',
    status: 'ACTIVE',
    description: 'Strong bullish momentum with high volume',
    created_at: new Date().toISOString(),
  },
  {
    id: 2,
    symbol: 'ETHUSDT',
    direction: 'SHORT',
    entry: '2250.00',
    tp: '2100.00',
    sl: '2350.00',
    confidence: 0.72,
    timeframe: '1h',
    status: 'ACTIVE',
    description: 'Bearish divergence detected on 4H chart',
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: 3,
    symbol: 'BNBUSDT',
    direction: 'LONG',
    entry: '315.00',
    tp: '335.00',
    sl: '305.00',
    confidence: 0.68,
    timeframe: '1d',
    status: 'EXECUTED',
    description: 'Breakout above resistance level',
    created_at: new Date(Date.now() - 7200000).toISOString(),
  },
];

const Dashboard = () => {
  const { user } = useAuthStore();
  const {
    signals,
    futuresSignals,
    fetchSignals,
    fetchFuturesSignals,
    isLoading: loading,
    processWebSocketMessage,
    setWsConnected
  } = useSignalStore();
  const [useMockData, setUseMockData] = useState(true);
  const [tradingMode, setTradingMode] = useState('paper'); // 'paper' or 'live'
  const [successRate, setSuccessRate] = useState(null);

  // WebSocket URL
  const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/signals/';

  // Initialize WebSocket connection
  const { isConnected, connectionStatus, subscribe } = useWebSocket(WS_URL, {
    onMessage: (message) => {
      console.log('WebSocket message received:', message);
      processWebSocketMessage(message);
      if (useMockData && message.type === 'signal_created') {
        setUseMockData(false); // Switch to real data once we receive real signals
      }
    },
    onOpen: () => {
      console.log('WebSocket connected - subscribing to signals');
      subscribe({ direction: 'ALL', timeframe: 'ALL' });
    },
    reconnectInterval: 3000,
    reconnectAttempts: 5,
    heartbeatInterval: 30000,
  });

  // Sync WebSocket connection state
  useEffect(() => {
    setWsConnected(isConnected);
  }, [isConnected, setWsConnected]);

  // Fetch initial signals for both spot and futures
  useEffect(() => {
    Promise.all([fetchSignals(), fetchFuturesSignals()]).then(() => {
      setUseMockData(false);
    }).catch((error) => {
      console.log('Using mock data:', error);
      setUseMockData(true);
    });
  }, [fetchSignals, fetchFuturesSignals]);

  // Fetch success rate from paper trading performance
  useEffect(() => {
    const fetchSuccessRate = async () => {
      try {
        const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const response = await fetch(`${API_BASE}/api/public/paper-trading/performance/`);
        if (response.ok) {
          const data = await response.json();
          setSuccessRate(data.win_rate);
        }
      } catch (error) {
        console.error('Failed to fetch success rate:', error);
        // Keep default value (null) if fetch fails
      }
    };

    fetchSuccessRate();
    // Refresh success rate every 30 seconds
    const interval = setInterval(fetchSuccessRate, 30000);
    return () => clearInterval(interval);
  }, []);

  const displaySignals = useMockData ? mockSignals : signals;
  const displayFuturesSignals = useMockData ? [] : futuresSignals;
  const activeSignals = displaySignals.filter((s) => s.status === 'ACTIVE');
  const activeFuturesSignals = displayFuturesSignals.filter((s) => s.status === 'ACTIVE');

  // Connection status badge
  const ConnectionBadge = () => {
    const statusConfig = {
      connected: { color: 'bg-green-500', text: 'Connected' },
      connecting: { color: 'bg-yellow-500', text: 'Connecting...' },
      disconnected: { color: 'bg-gray-500', text: 'Disconnected' },
      reconnecting: { color: 'bg-orange-500', text: 'Reconnecting...' },
      error: { color: 'bg-red-500', text: 'Error' },
    };
    const status = statusConfig[connectionStatus] || statusConfig.disconnected;

    return (
      <div className="flex items-center space-x-2">
        <span className={`${status.color} w-2 h-2 rounded-full animate-pulse`}></span>
        <span className="text-xs text-gray-600 dark:text-gray-400">{status.text}</span>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              Welcome back, {user?.username}!
            </h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              Here's an overview of your trading signals
            </p>
          </div>
          <div className="flex items-center gap-4">
            {/* Trading Mode Toggle */}
            <div className="flex items-center gap-2 bg-white dark:bg-gray-800 rounded-lg p-1 shadow-md">
              <button
                onClick={() => setTradingMode('paper')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                  tradingMode === 'paper'
                    ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-md'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                📝 Paper Trading
              </button>
              <button
                onClick={() => setTradingMode('live')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                  tradingMode === 'live'
                    ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white shadow-md'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                💰 Live Trading
              </button>
            </div>
            <ConnectionBadge />
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20">
          <h3 className="text-sm font-medium text-blue-700 dark:text-blue-300">
            Active Spot Signals
          </h3>
          <p className="mt-2 text-3xl font-bold text-blue-900 dark:text-blue-100">
            {activeSignals.length}
          </p>
          <p className="mt-1 text-xs text-blue-600 dark:text-blue-400">
            Spot market
          </p>
        </div>

        <div className="card bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-800/20">
          <h3 className="text-sm font-medium text-purple-700 dark:text-purple-300">
            Active Futures Signals
          </h3>
          <p className="mt-2 text-3xl font-bold text-purple-900 dark:text-purple-100">
            {activeFuturesSignals.length}
          </p>
          <p className="mt-1 text-xs text-purple-600 dark:text-purple-400">
            Futures market
          </p>
        </div>

        <div className="card bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20">
          <h3 className="text-sm font-medium text-green-700 dark:text-green-300">
            Total Active
          </h3>
          <p className="mt-2 text-3xl font-bold text-green-900 dark:text-green-100">
            {activeSignals.length + activeFuturesSignals.length}
          </p>
          <p className="mt-1 text-xs text-green-600 dark:text-green-400">
            All markets
          </p>
        </div>

        <div className="card bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-900/20 dark:to-orange-800/20">
          <h3 className="text-sm font-medium text-orange-700 dark:text-orange-300">
            Success Rate
          </h3>
          <p className="mt-2 text-3xl font-bold text-orange-900 dark:text-orange-100">
            {successRate !== null ? `${successRate.toFixed(1)}%` : '...'}
          </p>
          <p className="mt-1 text-xs text-orange-600 dark:text-orange-400">
            Overall performance
          </p>
        </div>
      </div>

      {/* Backtesting Promo Card */}
      <Link
        to="/backtesting"
        className="block bg-gradient-to-r from-blue-600 to-purple-600 dark:from-blue-700 dark:to-purple-700 rounded-xl p-6 shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-[1.02]"
      >
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-2xl">🎯</span>
              <h3 className="text-xl font-bold text-white">
                Test Your Strategy with Backtesting
              </h3>
              <span className="bg-yellow-400 text-yellow-900 text-xs px-2 py-1 rounded-full font-bold">
                NEW
              </span>
            </div>
            <p className="text-blue-100 mb-3">
              Run your trading strategies on historical data to see how they would have performed. Optimize parameters and maximize your win rate before going live!
            </p>
            <div className="flex items-center gap-4 text-sm text-blue-100">
              <div className="flex items-center gap-1">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                Historical Data Analysis
              </div>
              <div className="flex items-center gap-1">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                Performance Metrics
              </div>
              <div className="flex items-center gap-1">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                Strategy Optimization
              </div>
            </div>
          </div>
          <div className="flex items-center">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>
      </Link>

      {/* Recent Spot Signals */}
      <div>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Recent Spot Signals
          </h2>
          <Link to="/spot-signals" className="btn btn-primary">
            View All Spot
          </Link>
        </div>

        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          </div>
        ) : displaySignals.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {displaySignals.slice(0, 4).map((signal) => (
              <div
                key={signal.id}
                className="transform transition-all duration-200 hover:scale-105"
              >
                <SignalCard signal={signal} tradingMode={tradingMode} />
              </div>
            ))}
          </div>
        ) : (
          <div className="card text-center py-12">
            <p className="text-gray-500 dark:text-gray-400">
              No spot signals available yet
            </p>
          </div>
        )}
      </div>

      {/* Recent Futures Signals */}
      <div>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Recent Futures Signals
          </h2>
          <Link to="/futures" className="btn btn-primary">
            View All Futures
          </Link>
        </div>

        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          </div>
        ) : displayFuturesSignals.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {displayFuturesSignals.slice(0, 4).map((signal) => (
              <div
                key={signal.id}
                className="transform transition-all duration-200 hover:scale-105"
              >
                <FuturesSignalCard signal={signal} tradingMode={tradingMode} />
              </div>
            ))}
          </div>
        ) : (
          <div className="card text-center py-12">
            <p className="text-gray-500 dark:text-gray-400">
              No futures signals available yet
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
