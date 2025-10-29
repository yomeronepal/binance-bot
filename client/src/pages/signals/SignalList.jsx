/**
 * Spot Signal List page component
 * Displays all spot trading signals with filtering and real-time updates
 */
import { useEffect, useState } from 'react';
import { useSignalStore } from '../../store/useSignalStore';
import { useWebSocket } from '../../hooks/useWebSocket';
import SignalCard from '../../components/common/SignalCard';

const SignalList = () => {
  const {
    signals,
    fetchSignals,
    isLoading,
    spotSymbolsCount,
    fetchSpotSymbolsCount,
    handleSignalCreated,
    handleSignalUpdated,
    handleSignalDeleted
  } = useSignalStore();

  const [filters, setFilters] = useState({
    direction: 'ALL',
    status: 'ALL',
    timeframe: 'ALL'
  });
  const [connectionStatus, setConnectionStatus] = useState('disconnected');

  // WebSocket connection for real-time updates
  const { lastMessage, isConnected } = useWebSocket(
    `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/signals/'}`,
    {
      onOpen: () => setConnectionStatus('connected'),
      onClose: () => setConnectionStatus('disconnected'),
      onError: () => setConnectionStatus('error'),
    }
  );

  // Handle WebSocket messages for spot signals only
  useEffect(() => {
    if (lastMessage) {
      try {
        const data = JSON.parse(lastMessage);

        // Only handle spot signals
        if (!data.market_type || data.market_type === 'SPOT' || (data.signal && data.signal.market_type === 'SPOT')) {
          if (data.type === 'signal_created') {
            handleSignalCreated(data.signal);
          } else if (data.type === 'signal_updated') {
            handleSignalUpdated(data.signal);
          } else if (data.type === 'signal_deleted') {
            handleSignalDeleted(data.signal_id, 'SPOT');
          }
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    }
  }, [lastMessage, handleSignalCreated, handleSignalUpdated, handleSignalDeleted]);

  // Fetch signals and symbol count on mount
  useEffect(() => {
    fetchSignals();
    fetchSpotSymbolsCount();
  }, [fetchSignals, fetchSpotSymbolsCount]);

  // Apply filters
  const filteredSignals = signals.filter((signal) => {
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
    active: filteredSignals.filter(s => s.status === 'ACTIVE').length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              Spot Trading Signals
            </h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              Real-time spot market trading signals
            </p>
          </div>
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
        <div className="mt-6 grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-4">
            <p className="text-sm text-purple-600 dark:text-purple-400">Coins Scanned</p>
            <p className="text-2xl font-bold text-purple-700 dark:text-purple-300">{spotSymbolsCount}</p>
          </div>
          <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">Total Signals</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total}</p>
          </div>
          <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-4">
            <p className="text-sm text-green-600 dark:text-green-400">Buy</p>
            <p className="text-2xl font-bold text-green-700 dark:text-green-300">{stats.long}</p>
          </div>
          <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4">
            <p className="text-sm text-red-600 dark:text-red-400">Sell</p>
            <p className="text-2xl font-bold text-red-700 dark:text-red-300">{stats.short}</p>
          </div>
          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
            <p className="text-sm text-blue-600 dark:text-blue-400">Active</p>
            <p className="text-2xl font-bold text-blue-700 dark:text-blue-300">{stats.active}</p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
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
                      ? 'bg-primary-600 text-white'
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
                      ? 'bg-primary-600 text-white'
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
                      ? 'bg-primary-600 text-white'
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

      {/* Signals Grid */}
      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      ) : filteredSignals.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredSignals.map((signal) => (
            <div key={signal.id} className="transform transition-all duration-200 hover:scale-105">
              <SignalCard signal={signal} />
            </div>
          ))}
        </div>
      ) : (
        <div className="card text-center py-12">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">No signals</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            No spot signals match your current filters
          </p>
        </div>
      )}
    </div>
  );
};

export default SignalList;
