import React from 'react';
import { useSignalStore } from '../../store/useSignalStore';

/**
 * SignalFilters component for filtering and sorting signals.
 * Provides controls for direction, timeframe, confidence, symbol, and sorting.
 */
const SignalFilters = () => {
  const { filters, sortBy, sortOrder, setFilters, setSorting } = useSignalStore();

  // Timeframe options
  const timeframes = ['ALL', '1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w'];

  // Sort options
  const sortOptions = [
    { value: 'created_at', label: 'Latest' },
    { value: 'confidence', label: 'Confidence' },
    { value: 'profit_percentage', label: 'Profit %' },
    { value: 'risk_reward_ratio', label: 'Risk/Reward' },
  ];

  // Handle filter changes
  const handleDirectionChange = (e) => {
    setFilters({ direction: e.target.value });
  };

  const handleTimeframeChange = (e) => {
    setFilters({ timeframe: e.target.value });
  };

  const handleConfidenceChange = (e) => {
    setFilters({ minConfidence: parseFloat(e.target.value) / 100 });
  };

  const handleSymbolChange = (e) => {
    setFilters({ symbol: e.target.value.toUpperCase() });
  };

  const handleStatusChange = (e) => {
    setFilters({ status: e.target.value });
  };

  const handleSortChange = (e) => {
    setSorting({ sortBy: e.target.value });
  };

  const toggleSortOrder = () => {
    setSorting({ sortOrder: sortOrder === 'desc' ? 'asc' : 'desc' });
  };

  const handleReset = () => {
    setFilters({
      direction: 'ALL',
      timeframe: 'ALL',
      minConfidence: 0,
      symbol: '',
      status: 'ALL',
    });
    setSorting({ sortBy: 'created_at', sortOrder: 'desc' });
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-4 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-800">Filters & Sorting</h2>
        <button
          onClick={handleReset}
          className="text-sm text-blue-600 hover:text-blue-800 font-medium"
        >
          Reset All
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Direction Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Direction
          </label>
          <select
            value={filters.direction}
            onChange={handleDirectionChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All Directions</option>
            <option value="LONG">LONG</option>
            <option value="SHORT">SHORT</option>
          </select>
        </div>

        {/* Timeframe Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Timeframe
          </label>
          <select
            value={filters.timeframe}
            onChange={handleTimeframeChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {timeframes.map((tf) => (
              <option key={tf} value={tf}>
                {tf === 'ALL' ? 'All Timeframes' : tf}
              </option>
            ))}
          </select>
        </div>

        {/* Status Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Status
          </label>
          <select
            value={filters.status}
            onChange={handleStatusChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All Status</option>
            <option value="ACTIVE">Active</option>
            <option value="EXECUTED">Executed</option>
            <option value="EXPIRED">Expired</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>

        {/* Symbol Search */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Symbol
          </label>
          <input
            type="text"
            value={filters.symbol}
            onChange={handleSymbolChange}
            placeholder="e.g., BTCUSDT"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Confidence Slider */}
      <div className="mt-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Minimum Confidence: {Math.round(filters.minConfidence * 100)}%
        </label>
        <input
          type="range"
          min="0"
          max="100"
          step="5"
          value={Math.round(filters.minConfidence * 100)}
          onChange={handleConfidenceChange}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>0%</span>
          <span>50%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Sorting Controls */}
      <div className="mt-4 pt-4 border-t border-gray-200">
        <div className="flex items-center space-x-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Sort By
            </label>
            <select
              value={sortBy}
              onChange={handleSortChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {sortOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={toggleSortOrder}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-md transition-colors duration-200"
              title={`Sort ${sortOrder === 'desc' ? 'Ascending' : 'Descending'}`}
            >
              <span className="flex items-center space-x-2">
                <span className="text-sm font-medium text-gray-700">
                  {sortOrder === 'desc' ? '↓' : '↑'}
                </span>
                <span className="text-sm text-gray-600">
                  {sortOrder === 'desc' ? 'Desc' : 'Asc'}
                </span>
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignalFilters;
