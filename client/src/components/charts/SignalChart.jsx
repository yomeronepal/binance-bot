/**
 * Signal Chart Component using Recharts
 * Visualizes entry price, target price, and stop loss
 */
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';

const SignalChart = ({ signal }) => {
  if (!signal) {
    return (
      <div className="card flex items-center justify-center h-64">
        <p className="text-gray-500 dark:text-gray-400">No signal data available</p>
      </div>
    );
  }

  // Generate mock price data around the signal prices
  const generatePriceData = () => {
    const entryPrice = parseFloat(signal.entry_price);
    const targetPrice = signal.target_price ? parseFloat(signal.target_price) : entryPrice * 1.05;
    const stopLoss = signal.stop_loss ? parseFloat(signal.stop_loss) : entryPrice * 0.95;

    const data = [];
    const dataPoints = 50;
    const priceRange = Math.abs(targetPrice - stopLoss);
    const center = entryPrice;

    for (let i = 0; i < dataPoints; i++) {
      const timestamp = new Date(Date.now() - (dataPoints - i) * 60000);
      const volatility = (Math.random() - 0.5) * (priceRange * 0.1);
      const trend = ((i / dataPoints) - 0.5) * (priceRange * 0.2);
      const price = center + trend + volatility;

      data.push({
        time: timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        price: price.toFixed(2),
      });
    }

    return data;
  };

  const priceData = generatePriceData();
  const entryPrice = parseFloat(signal.entry_price);
  const targetPrice = signal.target_price ? parseFloat(signal.target_price) : null;
  const stopLoss = signal.stop_loss ? parseFloat(signal.stop_loss) : null;

  return (
    <div className="card">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          {signal.symbol} - {signal.signal_type}
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Entry: ${entryPrice.toFixed(2)}
          {targetPrice && ` | Target: $${targetPrice.toFixed(2)}`}
          {stopLoss && ` | Stop Loss: $${stopLoss.toFixed(2)}`}
        </p>
      </div>

      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={priceData}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-gray-300 dark:stroke-gray-600" />
          <XAxis
            dataKey="time"
            tick={{ fill: 'currentColor' }}
            className="text-gray-600 dark:text-gray-400"
          />
          <YAxis
            domain={['auto', 'auto']}
            tick={{ fill: 'currentColor' }}
            className="text-gray-600 dark:text-gray-400"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(255, 255, 255, 0.95)',
              border: '1px solid #ccc',
              borderRadius: '8px',
            }}
          />
          <Legend />

          {/* Entry Price Line */}
          <ReferenceLine
            y={entryPrice}
            stroke="#3b82f6"
            strokeDasharray="5 5"
            label={{ value: 'Entry', fill: '#3b82f6', position: 'right' }}
          />

          {/* Target Price Line */}
          {targetPrice && (
            <ReferenceLine
              y={targetPrice}
              stroke="#10b981"
              strokeDasharray="5 5"
              label={{ value: 'Target', fill: '#10b981', position: 'right' }}
            />
          )}

          {/* Stop Loss Line */}
          {stopLoss && (
            <ReferenceLine
              y={stopLoss}
              stroke="#ef4444"
              strokeDasharray="5 5"
              label={{ value: 'Stop Loss', fill: '#ef4444', position: 'right' }}
            />
          )}

          {/* Price Line */}
          <Line
            type="monotone"
            dataKey="price"
            stroke="#8884d8"
            strokeWidth={2}
            dot={false}
            name="Price"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default SignalChart;
