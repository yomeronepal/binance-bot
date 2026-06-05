import { useState, useEffect } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useSignalStore } from '../store/useSignalStore';
import FuturesSignalCard from '../components/signals/FuturesSignalCard';
import PullToRefresh from '../components/common/PullToRefresh';

const Futures = () => {
  const {
    futuresSignals,
    fetchFuturesSignals,
    futuresSymbolsCount,
    fetchFuturesSymbolsCount,
    isLoading: loading,
    error,
    handleSignalCreated,
    handleSignalUpdated,
    handleSignalDeleted
  } = useSignalStore();

  const [filters, setFilters] = useState({
    direction: 'ALL',
    status: 'ALL',
    timeframe: 'ALL'
  });
  // WebSocket connection
  const { lastMessage, isConnected } = useWebSocket(
    `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/signals/'}`
  );

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      const data = lastMessage;

      // Only handle futures signals
      if (data.market_type === 'FUTURES' || (data.signal && data.signal.market_type === 'FUTURES')) {
        if (data.type === 'signal_created') {
          handleSignalCreated(data.signal);
        } else if (data.type === 'signal_updated') {
          handleSignalUpdated(data.signal);
        } else if (data.type === 'signal_deleted') {
          handleSignalDeleted(data.signal_id, 'FUTURES');
        }
      }
    }
  }, [lastMessage, handleSignalCreated, handleSignalUpdated, handleSignalDeleted]);

  // Fetch futures signals and symbol count on mount
  useEffect(() => {
    fetchFuturesSignals();
    fetchFuturesSymbolsCount();
  }, [fetchFuturesSignals, fetchFuturesSymbolsCount]);

  // Apply filters
  const filteredSignals = futuresSignals.filter((signal) => {
    if (filters.direction !== 'ALL' && signal.direction !== filters.direction) {
      return false;
    }
    if (filters.status !== 'ALL' && signal.status !== filters.status) {
      return false;
    }
    if (filters.timeframe !== 'ALL' && signal.timeframe !== filters.timeframe) {
      return false;
    }
    return true;
  });

  // Stats calculation
  const stats = {
    total: filteredSignals.length,
    long: filteredSignals.filter(s => s.direction === 'LONG').length,
    short: filteredSignals.filter(s => s.direction === 'SHORT').length,
    avgConfidence: filteredSignals.length > 0
      ? (filteredSignals.reduce((sum, s) => sum + s.confidence, 0) / filteredSignals.length * 100).toFixed(1)
      : 0,
  };

  // Handle pull-to-refresh
  const handleRefresh = async () => {
    await Promise.all([
      fetchFuturesSignals(),
      fetchFuturesSymbolsCount()
    ]);
  };

  return (
    <PullToRefresh onRefresh={handleRefresh}>
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Futures Signals</h1>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                Real-time USDT perpetual futures trading signals with up to 10x leverage
              </p>
            </div>

            {/* Connection Status */}
            <div className="flex items-center space-x-2">
              <div className={`h-3 w-3 rounded-full ${
                isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
              }`}></div>
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {isConnected ? 'Live' : 'Disconnected'}
              </span>
            </div>
          </div>

          {/* Stats */}
          <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-5">
            <div className="bg-purple-100 dark:bg-purple-900/30 overflow-hidden shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                <dt className="text-sm font-medium text-purple-600 dark:text-purple-400 truncate">
                  Coins Scanned
                </dt>
                <dd className="mt-1 text-3xl font-semibold text-purple-700 dark:text-purple-300">
                  {futuresSymbolsCount}
                </dd>
              </div>
            </div>

            <div className="bg-gray-100 dark:bg-gray-700 overflow-hidden shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                <dt className="text-sm font-medium text-gray-600 dark:text-gray-400 truncate">
                  Total Signals
                </dt>
                <dd className="mt-1 text-3xl font-semibold text-gray-900 dark:text-white">
                  {stats.total}
                </dd>
              </div>
            </div>

            <div className="bg-green-100 dark:bg-green-900/30 overflow-hidden shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                <dt className="text-sm font-medium text-green-600 dark:text-green-400 truncate">
                  Long Signals
                </dt>
                <dd className="mt-1 text-3xl font-semibold text-green-700 dark:text-green-300">
                  {stats.long}
                </dd>
              </div>
            </div>

            <div className="bg-red-100 dark:bg-red-900/30 overflow-hidden shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                <dt className="text-sm font-medium text-red-600 dark:text-red-400 truncate">
                  Short Signals
                </dt>
                <dd className="mt-1 text-3xl font-semibold text-red-700 dark:text-red-300">
                  {stats.short}
                </dd>
              </div>
            </div>

            <div className="bg-blue-100 dark:bg-blue-900/30 overflow-hidden shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                <dt className="text-sm font-medium text-blue-600 dark:text-blue-400 truncate">
                  Avg Confidence
                </dt>
                <dd className="mt-1 text-3xl font-semibold text-blue-700 dark:text-blue-300">
                  {stats.avgConfidence}%
                </dd>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Filters</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Direction Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Direction
              </label>
              <div className="flex flex-wrap gap-2">
                {['ALL', 'LONG', 'SHORT'].map((dir) => (
                  <button
                    key={dir}
                    onClick={() => setFilters({ ...filters, direction: dir })}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      filters.direction === dir
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                    }`}
                  >
                    {dir}
                  </button>
                ))}
              </div>
            </div>

            {/* Status Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Status
              </label>
              <div className="flex flex-wrap gap-2">
                {['ALL', 'ACTIVE', 'EXPIRED', 'EXECUTED'].map((status) => (
                  <button
                    key={status}
                    onClick={() => setFilters({ ...filters, status })}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      filters.status === status
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                    }`}
                  >
                    {status}
                  </button>
                ))}
              </div>
            </div>

            {/* Timeframe Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Timeframe
              </label>
              <div className="flex flex-wrap gap-2">
                {['ALL', '1m', '5m', '15m', '1h', '4h', '1d'].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setFilters({ ...filters, timeframe: tf })}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      filters.timeframe === tf
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Signals Grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-12">
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent"></div>
            <p className="mt-2 text-gray-600 dark:text-gray-400">Loading futures signals...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-100 dark:bg-red-900/20 border border-red-300 dark:border-red-500 text-red-700 dark:text-red-300 px-4 py-3 rounded">
            <p className="font-bold">Error loading signals</p>
            <p className="text-sm">{error}</p>
          </div>
        )}

        {!loading && !error && filteredSignals.length === 0 && (
          <div className="text-center py-12 bg-gray-100 dark:bg-gray-800 rounded-lg">
            <svg className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-700 dark:text-gray-300">No futures signals</h3>
            <p className="mt-1 text-sm text-gray-500">
              No futures signals match your current filters
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {filteredSignals.map((signal) => (
            <FuturesSignalCard key={signal.id} signal={signal} />
          ))}
        </div>
      </div>
    </div>
    </PullToRefresh>
  );
};

export default Futures;
