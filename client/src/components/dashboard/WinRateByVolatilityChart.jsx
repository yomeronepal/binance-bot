/**
 * Win Rate by Volatility Chart Component
 * Bar chart showing win rates across HIGH/MEDIUM/LOW volatility levels
 */
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell } from 'recharts';

const WinRateByVolatilityChart = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500">
        No data available
      </div>
    );
  }

  // Colors for volatility levels
  const colorMap = {
    HIGH: '#ef4444',
    MEDIUM: '#f59e0b',
    LOW: '#10b981'
  };

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-lg">
          <p className="text-white font-medium mb-2">{data.volatility} Volatility</p>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between gap-4">
              <span className="text-gray-400">Win Rate:</span>
              <span className="text-green-400 font-medium">{data.winRate.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-gray-400">Trades:</span>
              <span className="text-white font-medium">{data.totalTrades}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-gray-400">Wins:</span>
              <span className="text-green-400 font-medium">{data.wins}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-gray-400">Losses:</span>
              <span className="text-red-400 font-medium">{data.losses}</span>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis
          dataKey="volatility"
          stroke="#9ca3af"
          tick={{ fill: '#9ca3af' }}
        />
        <YAxis
          stroke="#9ca3af"
          tick={{ fill: '#9ca3af' }}
          label={{ value: 'Win Rate (%)', angle: -90, position: 'insideLeft', fill: '#9ca3af' }}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(59, 130, 246, 0.1)' }} />
        <Bar dataKey="winRate" radius={[8, 8, 0, 0]}>
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={colorMap[entry.volatility] || '#3b82f6'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};

export default WinRateByVolatilityChart;
