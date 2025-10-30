/**
 * Strategy Performance Dashboard
 * Visualizes backtest results across multiple configurations and volatility levels
 */
import { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, Target, Zap, PieChart, Activity } from 'lucide-react';
import WinRateByVolatilityChart from '../components/dashboard/WinRateByVolatilityChart';
import PnLBySymbolChart from '../components/dashboard/PnLBySymbolChart';
import ConfigurationComparisonTable from '../components/dashboard/ConfigurationComparisonTable';
import PerformanceHeatmap from '../components/dashboard/PerformanceHeatmap';
import SharpeRatioChart from '../components/dashboard/SharpeRatioChart';
import { fetchStrategyPerformance } from '../services/api';

const StrategyDashboard = () => {
  const [performanceData, setPerformanceData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('30d');

  useEffect(() => {
    loadPerformanceData();
  }, [timeRange]);

  const loadPerformanceData = async () => {
    try {
      setLoading(true);
      const data = await fetchStrategyPerformance(timeRange);
      setPerformanceData(data);
    } catch (error) {
      console.error('Error loading performance data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Calculate summary statistics
  const summaryStats = performanceData ? {
    avgWinRate: performanceData.bySymbol.reduce((sum, s) => sum + s.winRate, 0) / performanceData.bySymbol.length,
    totalPnL: performanceData.bySymbol.reduce((sum, s) => sum + s.pnl, 0),
    bestSymbol: performanceData.bySymbol.reduce((best, s) => s.pnl > best.pnl ? s : best, performanceData.bySymbol[0]),
    avgSharpe: performanceData.bySymbol.reduce((sum, s) => sum + (s.sharpeRatio || 0), 0) / performanceData.bySymbol.length
  } : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-8 h-8 text-purple-400" />
            Strategy Performance Dashboard
          </h1>
          <p className="text-gray-400 mt-1">
            Comprehensive analysis of backtest results and strategy optimization
          </p>
        </div>

        {/* Time Range Selector */}
        <div className="flex gap-2">
          {['7d', '30d', '90d', 'all'].map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                timeRange === range
                  ? 'bg-purple-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {range === 'all' ? 'All Time' : range.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
        </div>
      ) : performanceData ? (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="bg-gradient-to-br from-blue-500/10 to-blue-600/5 border border-blue-500/30 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="bg-blue-500/10 p-3 rounded-lg">
                  <Target className="w-6 h-6 text-blue-400" />
                </div>
                <span className="text-sm text-blue-300">Average</span>
              </div>
              <p className="text-3xl font-bold text-white mb-1">
                {summaryStats.avgWinRate.toFixed(1)}%
              </p>
              <p className="text-gray-400 text-sm">Win Rate</p>
            </div>

            <div className="bg-gradient-to-br from-green-500/10 to-green-600/5 border border-green-500/30 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="bg-green-500/10 p-3 rounded-lg">
                  <TrendingUp className="w-6 h-6 text-green-400" />
                </div>
                <span className="text-sm text-green-300">Total</span>
              </div>
              <p className="text-3xl font-bold text-white mb-1">
                {summaryStats.totalPnL >= 0 ? '+' : ''}${summaryStats.totalPnL.toFixed(2)}
              </p>
              <p className="text-gray-400 text-sm">Profit & Loss</p>
            </div>

            <div className="bg-gradient-to-br from-purple-500/10 to-purple-600/5 border border-purple-500/30 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="bg-purple-500/10 p-3 rounded-lg">
                  <Zap className="w-6 h-6 text-purple-400" />
                </div>
                <span className="text-sm text-purple-300">Best</span>
              </div>
              <p className="text-3xl font-bold text-white mb-1">
                {summaryStats.bestSymbol.symbol}
              </p>
              <p className="text-gray-400 text-sm">
                +{summaryStats.bestSymbol.pnlPercent.toFixed(1)}% Return
              </p>
            </div>

            <div className="bg-gradient-to-br from-orange-500/10 to-orange-600/5 border border-orange-500/30 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="bg-orange-500/10 p-3 rounded-lg">
                  <Activity className="w-6 h-6 text-orange-400" />
                </div>
                <span className="text-sm text-orange-300">Risk-Adj</span>
              </div>
              <p className="text-3xl font-bold text-white mb-1">
                {summaryStats.avgSharpe.toFixed(2)}
              </p>
              <p className="text-gray-400 text-sm">Avg Sharpe Ratio</p>
            </div>
          </div>

          {/* Charts Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Win Rate by Volatility */}
            <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6">
              <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                <Target className="w-5 h-5 text-blue-400" />
                Win Rate by Volatility
              </h2>
              <WinRateByVolatilityChart data={performanceData.byVolatility} />
            </div>

            {/* PnL by Symbol */}
            <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6">
              <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-green-400" />
                P&L by Symbol
              </h2>
              <PnLBySymbolChart data={performanceData.bySymbol} />
            </div>

            {/* Sharpe Ratio Over Time */}
            <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6">
              <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5 text-purple-400" />
                Sharpe Ratio Trend
              </h2>
              <SharpeRatioChart data={performanceData.sharpeOverTime} />
            </div>

            {/* Performance Heatmap */}
            <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6">
              <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                <PieChart className="w-5 h-5 text-orange-400" />
                Performance Heatmap
              </h2>
              <PerformanceHeatmap data={performanceData.heatmap} />
            </div>
          </div>

          {/* Configuration Comparison */}
          <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6">
            <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-indigo-400" />
              Configuration Comparison
            </h2>
            <p className="text-gray-400 text-sm mb-6">
              Compare performance across different volatility-aware configurations
            </p>
            <ConfigurationComparisonTable data={performanceData.configurations} />
          </div>

          {/* AI Optimizer Results (if available) */}
          {performanceData.mlOptimization && (
            <div className="bg-gradient-to-br from-purple-500/10 to-indigo-500/5 border border-purple-500/30 rounded-xl p-6">
              <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                <Zap className="w-5 h-5 text-purple-400" />
                AI Optimizer Results
              </h2>
              <p className="text-gray-400 text-sm mb-6">
                Best parameters discovered through machine learning optimization
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="bg-gray-900/50 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-2">Expected Win Rate</p>
                  <p className="text-2xl font-bold text-purple-400">
                    {performanceData.mlOptimization.expectedWinRate.toFixed(1)}%
                  </p>
                </div>
                <div className="bg-gray-900/50 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-2">Expected Return</p>
                  <p className="text-2xl font-bold text-green-400">
                    +{performanceData.mlOptimization.expectedReturn.toFixed(1)}%
                  </p>
                </div>
                <div className="bg-gray-900/50 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-2">Confidence</p>
                  <p className="text-2xl font-bold text-blue-400">
                    {performanceData.mlOptimization.confidence.toFixed(1)}%
                  </p>
                </div>
              </div>

              <div className="bg-gray-900/50 rounded-lg p-4">
                <h3 className="text-white font-medium mb-3">Optimized Parameters</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  {Object.entries(performanceData.mlOptimization.parameters).map(([key, value]) => (
                    <div key={key} className="flex justify-between items-center">
                      <span className="text-gray-400">{key}:</span>
                      <span className="text-white font-medium">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-12 text-center">
          <BarChart3 className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-400 mb-2">No Data Available</h3>
          <p className="text-gray-500">
            Run some backtests to see strategy performance analytics
          </p>
        </div>
      )}
    </div>
  );
};

export default StrategyDashboard;
