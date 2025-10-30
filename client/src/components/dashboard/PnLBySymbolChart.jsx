/**
 * PnL by Symbol Chart Component
 * Horizontal bar chart showing profit/loss for each trading symbol
 */
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts';

const PnLBySymbolChart = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500">
        No data available
      </div>
    );
  }

  // Sort by PnL descending
  const sortedData = [...data].sort((a, b) => b.pnlPercent - a.pnlPercent);

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-lg">
          <p className="text-white font-medium mb-2">{data.symbol}</p>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between gap-4">
              <span className="text-gray-400">P&L:</span>
              <span className={`font-medium ${data.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {data.pnl >= 0 ? '+' : ''}${data.pnl.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-gray-400">Return:</span>
              <span className={`font-medium ${data.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {data.pnlPercent >= 0 ? '+' : ''}{data.pnlPercent.toFixed(2)}%
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-gray-400">Trades:</span>
              <span className="text-white font-medium">{data.trades}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-gray-400">Win Rate:</span>
              <span className="text-blue-400 font-medium">{data.winRate.toFixed(1)}%</span>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={sortedData}
        layout="vertical"
        margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis
          type="number"
          stroke="#9ca3af"
          tick={{ fill: '#9ca3af' }}
          label={{ value: 'Return (%)', position: 'insideBottom', offset: -5, fill: '#9ca3af' }}
        />
        <YAxis
          type="category"
          dataKey="symbol"
          stroke="#9ca3af"
          tick={{ fill: '#9ca3af' }}
          width={80}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(59, 130, 246, 0.1)' }} />
        <ReferenceLine x={0} stroke="#6b7280" strokeDasharray="3 3" />
        <Bar dataKey="pnlPercent" radius={[0, 4, 4, 0]}>
          {sortedData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.pnlPercent >= 0 ? '#10b981' : '#ef4444'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};

export default PnLBySymbolChart;
