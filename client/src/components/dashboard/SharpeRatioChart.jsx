/**
 * Sharpe Ratio Over Time Chart Component
 * Line chart showing risk-adjusted returns trend
 */
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

const SharpeRatioChart = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500">
        No data available
      </div>
    );
  }

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-lg">
          <p className="text-white font-medium mb-2">{data.date}</p>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between gap-4">
              <span className="text-gray-400">Sharpe Ratio:</span>
              <span className={`font-medium ${
                data.sharpeRatio > 1 ? 'text-green-400' :
                data.sharpeRatio > 0 ? 'text-yellow-400' :
                'text-red-400'
              }`}>
                {data.sharpeRatio.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-gray-400">Return:</span>
              <span className="text-white font-medium">{data.return.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-gray-400">Volatility:</span>
              <span className="text-gray-300">{data.volatility.toFixed(2)}%</span>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis
          dataKey="date"
          stroke="#9ca3af"
          tick={{ fill: '#9ca3af', fontSize: 12 }}
        />
        <YAxis
          stroke="#9ca3af"
          tick={{ fill: '#9ca3af' }}
          label={{ value: 'Sharpe Ratio', angle: -90, position: 'insideLeft', fill: '#9ca3af' }}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine
          y={1}
          stroke="#10b981"
          strokeDasharray="3 3"
          label={{ value: 'Good (>1)', position: 'right', fill: '#10b981', fontSize: 12 }}
        />
        <ReferenceLine
          y={0}
          stroke="#6b7280"
          strokeDasharray="3 3"
        />
        <Line
          type="monotone"
          dataKey="sharpeRatio"
          stroke="#8b5cf6"
          strokeWidth={2}
          dot={{ fill: '#8b5cf6', r: 4 }}
          activeDot={{ r: 6 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default SharpeRatioChart;
