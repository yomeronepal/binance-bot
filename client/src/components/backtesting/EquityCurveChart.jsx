/**
 * Equity Curve Chart Component
 */
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { format } from 'date-fns';
import { TrendingUp } from 'lucide-react';

const EquityCurveChart = ({ metrics }) => {
  if (!metrics || !metrics.equity_curve || metrics.equity_curve.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <TrendingUp className="w-12 h-12 text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400">No equity curve data available</p>
        </div>
      </div>
    );
  }

  // Format data for recharts
  const chartData = metrics.equity_curve.map((point) => ({
    timestamp: point.timestamp,
    equity: parseFloat(point.equity || 0),
    pnl: parseFloat(point.total_pnl || 0),
    openTrades: point.open_trades || 0
  }));

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-gray-900/95 backdrop-blur-sm border border-gray-700 rounded-lg p-4 shadow-xl">
          <p className="text-gray-300 text-sm mb-2">
            {format(new Date(data.timestamp), 'MMM d, yyyy HH:mm')}
          </p>
          <div className="space-y-1">
            <div className="flex items-center justify-between gap-4">
              <span className="text-blue-400 text-sm">Equity:</span>
              <span className="text-white font-semibold">${data.equity.toFixed(2)}</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-green-400 text-sm">P/L:</span>
              <span className={`font-semibold ${data.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {data.pnl >= 0 ? '+' : ''}${data.pnl.toFixed(2)}
              </span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-purple-400 text-sm">Open Trades:</span>
              <span className="text-white font-semibold">{data.openTrades}</span>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Equity Curve</h3>
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-blue-500 rounded"></div>
            <span className="text-gray-400">Equity</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-500 rounded"></div>
            <span className="text-gray-400">P/L</span>
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(timestamp) => format(new Date(timestamp), 'MMM d')}
            stroke="#9CA3AF"
            style={{ fontSize: '12px' }}
          />
          <YAxis
            yAxisId="left"
            stroke="#9CA3AF"
            style={{ fontSize: '12px' }}
            tickFormatter={(value) => `$${value.toFixed(0)}`}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            stroke="#9CA3AF"
            style={{ fontSize: '12px' }}
            tickFormatter={(value) => `$${value.toFixed(0)}`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="line"
            formatter={(value) => <span className="text-gray-300">{value}</span>}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="equity"
            stroke="#3B82F6"
            strokeWidth={2}
            dot={false}
            name="Equity"
            animationDuration={500}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="pnl"
            stroke="#10B981"
            strokeWidth={2}
            dot={false}
            name="Total P/L"
            animationDuration={500}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default EquityCurveChart;
