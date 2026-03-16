import React, { useEffect, useState } from 'react';
import { useSignalStore } from '../store/useSignalStore';
import { useWebSocket } from '../hooks/useWebSocket';
import SignalCard from '../components/signals/SignalCard';
import SignalFilters from '../components/signals/SignalFilters';
import PullToRefresh from '../components/common/PullToRefresh';
import { Clock, Activity, Calendar } from 'lucide-react';
import axios from 'axios';

/**
 * Dashboard page for displaying real-time trading signals.
 * Features:
 * - Real-time WebSocket updates
 * - Filtering and sorting
 * - Color-coded LONG/SHORT signals
 * - Responsive grid layout
 */
const Dashboard = () => {
  const {
    signals,
    loading,
    error,
    wsConnected,
    fetchSignals,
    processWebSocketMessage,
    setWsConnected,
    getFilteredSignals,
  } = useSignalStore();

  const [selectedSignal, setSelectedSignal] = useState(null);
  const [fearGreed, setFearGreed] = useState(null);

  const fetchFearGreed = async () => {
    try {
      const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
      const res = await axios.get(`${baseURL}/futures/fear-greed/`);
      if (res.data) setFearGreed(res.data);
    } catch (err) {
      console.debug('F&G fetch skipped:', err.message);
    }
  };

  useEffect(() => {
    fetchFearGreed();
    const interval = setInterval(fetchFearGreed, 60000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket URL from environment variable
  const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/signals/';

  // Initialize WebSocket connection
  const {
    isConnected,
    connectionStatus,
    error: wsError,
    lastMessage,
    connect,
    disconnect,
    subscribe,
  } = useWebSocket(WS_URL, {
    onMessage: (message) => {
      console.log('WebSocket message received:', message);
      processWebSocketMessage(message);
    },
    onOpen: () => {
      console.log('WebSocket connected - subscribing to signals');
      // Subscribe to all signals on connection
      subscribe({ direction: 'ALL', timeframe: 'ALL' });
    },
    onClose: () => {
      console.log('WebSocket disconnected');
    },
    reconnectInterval: 3000,
    reconnectAttempts: 5,
    heartbeatInterval: 30000,
  });

  // Sync WebSocket connection state with store
  useEffect(() => {
    setWsConnected(isConnected);
  }, [isConnected, setWsConnected]);

  // Fetch initial signals on mount
  useEffect(() => {
    fetchSignals();
  }, [fetchSignals]);

  // Get filtered and sorted signals
  const filteredSignals = getFilteredSignals();

  // Handle pull-to-refresh
  const handleRefresh = async () => {
    await fetchSignals();
  };

  // Handle signal card click
  const handleSignalClick = (signal) => {
    setSelectedSignal(signal);
    // TODO: Open signal detail modal or navigate to detail page
    console.log('Signal clicked:', signal);
  };

  // Connection status indicator
  const ConnectionStatus = () => {
    const statusConfig = {
      connected: {
        color: 'bg-green-500',
        text: 'Connected',
        icon: '●',
      },
      connecting: {
        color: 'bg-yellow-500',
        text: 'Connecting...',
        icon: '○',
      },
      disconnected: {
        color: 'bg-gray-500',
        text: 'Disconnected',
        icon: '○',
      },
      reconnecting: {
        color: 'bg-orange-500',
        text: 'Reconnecting...',
        icon: '◐',
      },
      error: {
        color: 'bg-red-500',
        text: 'Error',
        icon: '✕',
      },
    };

    const status = statusConfig[connectionStatus] || statusConfig.disconnected;

    return (
      <div className="flex items-center space-x-2">
        <span className={`${status.color} w-3 h-3 rounded-full animate-pulse`}></span>
        <span className="text-sm text-gray-600">
          {status.icon} {status.text}
        </span>
      </div>
    );
  };

  const TradingSessionStatus = () => {
    const [currentTime, setCurrentTime] = useState(new Date());

    useEffect(() => {
      const timer = setInterval(() => setCurrentTime(new Date()), 1000);
      return () => clearInterval(timer);
    }, []);

    const NEPAL_OFFSET_MINUTES = 5 * 60 + 45;
    const US_EST_OFFSET_MINUTES = -5 * 60;

    const getNepalTime = (date) => {
      const utc = date.getTime() + date.getTimezoneOffset() * 60000;
      return new Date(utc + NEPAL_OFFSET_MINUTES * 60000);
    };

    const getUSTime = (date) => {
      const utc = date.getTime() + date.getTimezoneOffset() * 60000;
      const isDST = isUSDaylightSaving(date);
      const offset = isDST ? (US_EST_OFFSET_MINUTES + 60) : US_EST_OFFSET_MINUTES;
      return new Date(utc + offset * 60000);
    };

    const getUTCTime = (date) => {
      return new Date(date.getTime() + date.getTimezoneOffset() * 60000);
    };

    const isUSDaylightSaving = (date) => {
      const jan = new Date(date.getFullYear(), 0, 1);
      const jul = new Date(date.getFullYear(), 6, 1);
      const stdOffset = Math.max(jan.getTimezoneOffset(), jul.getTimezoneOffset());
      return date.getTimezoneOffset() < stdOffset;
    };

    const formatTime = (date) => {
      return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
      });
    };

    const isWithinTradingWindow = () => {
      const nepalTime = getNepalTime(currentTime);
      const hour = nepalTime.getHours();
      const minute = nepalTime.getMinutes();
      const timeInMinutes = hour * 60 + minute;

      const windows = [
        { start: 16 * 60, end: 17 * 60 },
        { start: 21 * 60, end: 23 * 60 }
      ];

      return windows.some(w => timeInMinutes >= w.start && timeInMinutes < w.end);
    };

    const getNextWindow = () => {
      const nepalTime = getNepalTime(currentTime);
      const hour = nepalTime.getHours();
      const minute = nepalTime.getMinutes();
      const timeInMinutes = hour * 60 + minute;

      if (timeInMinutes < 16 * 60) return '16:00 NPT';
      if (timeInMinutes >= 17 * 60 && timeInMinutes < 21 * 60) return '21:00 NPT';
      return '16:00 NPT (tomorrow)';
    };

    const nepalTime = getNepalTime(currentTime);
    const usTime = getUSTime(currentTime);
    const utcTime = getUTCTime(currentTime);
    const isActive = isWithinTradingWindow();

    const tradingWindows = [
      {
        npt: '16:00 - 17:00',
        utc: '10:15 - 11:15',
        us: '05:15 - 06:15 EST'
      },
      {
        npt: '21:00 - 23:00',
        utc: '15:15 - 17:15',
        us: '10:15 - 12:15 EST'
      }
    ];

    return (
      <div className={`rounded-lg border-2 p-4 ${isActive ? 'bg-green-50 border-green-500' : 'bg-gray-50 border-gray-300'}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Activity className={`w-5 h-5 ${isActive ? 'text-green-600 animate-pulse' : 'text-gray-400'}`} />
            <span className={`font-semibold ${isActive ? 'text-green-700' : 'text-gray-600'}`}>
              Trading Session: {isActive ? 'ACTIVE' : 'INACTIVE'}
            </span>
          </div>
          {!isActive && (
            <span className="text-sm text-gray-500">
              Next: {getNextWindow()}
            </span>
          )}
        </div>

        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="text-center p-2 bg-white rounded-lg shadow-sm">
            <div className="flex items-center justify-center gap-1 text-xs text-gray-500 mb-1">
              <Clock className="w-3 h-3" />
              <span>Nepal (NPT)</span>
            </div>
            <div className="font-mono font-bold text-blue-600">{formatTime(nepalTime)}</div>
          </div>
          <div className="text-center p-2 bg-white rounded-lg shadow-sm">
            <div className="flex items-center justify-center gap-1 text-xs text-gray-500 mb-1">
              <Clock className="w-3 h-3" />
              <span>US (EST/EDT)</span>
            </div>
            <div className="font-mono font-bold text-purple-600">{formatTime(usTime)}</div>
          </div>
          <div className="text-center p-2 bg-white rounded-lg shadow-sm">
            <div className="flex items-center justify-center gap-1 text-xs text-gray-500 mb-1">
              <Clock className="w-3 h-3" />
              <span>UTC</span>
            </div>
            <div className="font-mono font-bold text-gray-700">{formatTime(utcTime)}</div>
          </div>
        </div>

        <div className="border-t pt-3">
          <div className="flex items-center gap-1 text-xs text-gray-500 mb-2">
            <Calendar className="w-3 h-3" />
            <span>Trading Windows</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {tradingWindows.map((window, idx) => (
              <div key={idx} className="bg-white rounded p-2 text-xs">
                <div className="font-semibold text-blue-600 mb-1">Window {idx + 1}</div>
                <div className="space-y-0.5">
                  <div><span className="text-gray-500">NPT:</span> <span className="font-mono">{window.npt}</span></div>
                  <div><span className="text-gray-500">UTC:</span> <span className="font-mono">{window.utc}</span></div>
                  <div><span className="text-gray-500">US:</span> <span className="font-mono">{window.us}</span></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  return (
    <PullToRefresh onRefresh={handleRefresh}>
    <div className="min-h-screen bg-gray-50 py-6 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Trading Signals</h1>
              <p className="mt-1 text-sm text-gray-600">
                Real-time LONG/SHORT signals from multiple sources
              </p>
            </div>
            <ConnectionStatus />
          </div>

          {/* Stats Bar */}
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-600">Total Signals</p>
              <p className="text-2xl font-bold text-gray-900">{signals.length}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-600">Active Signals</p>
              <p className="text-2xl font-bold text-green-600">
                {signals.filter((s) => s.status === 'ACTIVE').length}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-600">Filtered Results</p>
              <p className="text-2xl font-bold text-blue-600">{filteredSignals.length}</p>
            </div>
          </div>

          <div className="mt-4">
            <TradingSessionStatus />
          </div>

          {fearGreed && fearGreed.available && (
            <div className="mt-4">
              <FearGreedWidget data={fearGreed} />
            </div>
          )}
        </div>

        {/* Filters */}
        <SignalFilters />

        {/* Error Display */}
        {(error || wsError) && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-center space-x-2">
              <span className="text-red-600 font-bold">⚠</span>
              <p className="text-sm text-red-700">{error || wsError}</p>
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading && signals.length === 0 && (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <p className="mt-4 text-gray-600">Loading signals...</p>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!loading && filteredSignals.length === 0 && (
          <div className="bg-white rounded-lg shadow-md p-12 text-center">
            <div className="text-gray-400 text-6xl mb-4">📊</div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No signals found</h3>
            <p className="text-gray-600">
              {signals.length === 0
                ? 'Waiting for new trading signals to arrive...'
                : 'Try adjusting your filters to see more results.'}
            </p>
          </div>
        )}

        {/* Signals Grid */}
        {filteredSignals.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredSignals.map((signal) => (
              <div
                key={signal.id}
                className="transform transition-all duration-200 hover:scale-105 animate-fadeIn"
              >
                <SignalCard signal={signal} onClick={handleSignalClick} />
              </div>
            ))}
          </div>
        )}

        {/* Footer Stats */}
        {filteredSignals.length > 0 && (
          <div className="mt-6 text-center text-sm text-gray-500">
            Showing {filteredSignals.length} of {signals.length} signals
          </div>
        )}
      </div>
    </div>
    </PullToRefresh>
  );
};

const FearGreedWidget = ({ data }) => {
  const value = data.value;
  const classification = data.classification;
  const enabled = data.enabled;
  const components = data.components || {};
  const impact = data.trading_impact || {};
  const source = data.source || 'unknown';

  const getColor = (val) => {
    if (val <= 24) return { bg: '#ef4444', text: 'text-red-500', bar: 'bg-red-500', light: 'bg-red-50 border-red-200' };
    if (val <= 44) return { bg: '#f97316', text: 'text-orange-500', bar: 'bg-orange-500', light: 'bg-orange-50 border-orange-200' };
    if (val <= 55) return { bg: '#eab308', text: 'text-yellow-500', bar: 'bg-yellow-500', light: 'bg-yellow-50 border-yellow-200' };
    if (val <= 74) return { bg: '#84cc16', text: 'text-lime-500', bar: 'bg-lime-500', light: 'bg-lime-50 border-lime-200' };
    return { bg: '#22c55e', text: 'text-green-500', bar: 'bg-green-500', light: 'bg-green-50 border-green-200' };
  };

  const colors = getColor(value);

  return (
    <div className={`rounded-lg border-2 p-4 ${colors.light}`}>
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex items-center gap-4 flex-1">
          <div className="flex-shrink-0 text-center" style={{ minWidth: '70px' }}>
            <div className={`text-4xl font-black ${colors.text}`}>{value}</div>
            <div className={`text-xs font-semibold mt-0.5 ${colors.text}`}>{classification}</div>
          </div>

          <div className="flex-1">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm font-semibold text-gray-700">Fear & Greed Index</span>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-gray-400">via {source}</span>
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                  enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                }`}>
                  {enabled ? 'Filter Active' : 'Filter Off'}
                </span>
              </div>
            </div>

            <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden shadow-inner">
              <div
                className={`h-full rounded-full transition-all duration-1000 ease-out ${colors.bar}`}
                style={{ width: `${value}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-gray-400 mt-1 px-0.5">
              <span>0 Extreme Fear</span>
              <span>50 Neutral</span>
              <span>100 Extreme Greed</span>
            </div>
          </div>
        </div>

        <div className="flex gap-2">
          <div className={`px-4 py-2 rounded-lg border text-center ${
            impact.long_allowed
              ? 'bg-green-50 border-green-300 text-green-700'
              : 'bg-red-50 border-red-300 text-red-700'
          }`}>
            <div className="font-bold text-sm">LONG</div>
            <div className="text-xs">{impact.long_allowed ? 'Allowed' : 'Blocked'}</div>
          </div>
          <div className={`px-4 py-2 rounded-lg border text-center ${
            impact.short_allowed
              ? 'bg-green-50 border-green-300 text-green-700'
              : 'bg-red-50 border-red-300 text-red-700'
          }`}>
            <div className="font-bold text-sm">SHORT</div>
            <div className="text-xs">{impact.short_allowed ? 'Allowed' : 'Blocked'}</div>
          </div>
        </div>
      </div>

      {Object.keys(components).length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-200 grid grid-cols-2 sm:grid-cols-4 gap-2">
          {Object.entries(components).map(([key, comp]) => (
            <div key={key} className="bg-white rounded-lg px-3 py-2 shadow-sm">
              <div className="text-[10px] text-gray-400 uppercase tracking-wide">{key.replace(/_/g, ' ')}</div>
              <div className="font-mono text-sm font-semibold text-gray-800">
                {comp.raw}
              </div>
              <div className="text-[10px] text-gray-400">score: {comp.score}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Dashboard;
