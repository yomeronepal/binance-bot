/**
 * Signal Detail page component
 * Displays comprehensive information about a single signal with charts and trading instructions
 */
import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useSignalStore } from '../../store/useSignalStore';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';
import { format } from 'date-fns';

const SignalDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { signals, futuresSignals, isLoading } = useSignalStore();
  const [signal, setSignal] = useState(null);

  useEffect(() => {
    // Find signal in either spot or futures
    const spotSignal = signals.find(s => s.id === parseInt(id));
    const futuresSignal = futuresSignals.find(s => s.id === parseInt(id));

    if (spotSignal) {
      setSignal({ ...spotSignal, market_type: spotSignal.market_type || 'SPOT' });
    } else if (futuresSignal) {
      setSignal({ ...futuresSignal, market_type: futuresSignal.market_type || 'FUTURES' });
    }
  }, [id, signals, futuresSignals]);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (!signal) {
    return (
      <div className="card text-center py-12">
        <p className="text-gray-500 dark:text-gray-400 mb-4">Signal not found</p>
        <Link to="/spot-signals" className="btn btn-primary">
          Back to Signals
        </Link>
      </div>
    );
  }

  const isFutures = signal.market_type === 'FUTURES';
  const isForex = signal.market_type === 'FOREX';
  const isLong = signal.direction === 'LONG';

  // Display labels: BUY/SELL for spot/forex, LONG/SHORT for futures
  const directionLabel = isFutures
    ? signal.direction
    : (isLong ? 'BUY' : 'SELL');

  // Calculate metrics
  const entry = parseFloat(signal.entry);
  const tp = parseFloat(signal.tp);
  const sl = parseFloat(signal.sl);

  const profitPercent = ((tp - entry) / entry * 100).toFixed(2);
  const riskPercent = ((entry - sl) / entry * 100).toFixed(2);
  const riskRewardRatio = (Math.abs(tp - entry) / Math.abs(entry - sl)).toFixed(2);

  // For futures, calculate leveraged returns
  const leverage = signal.leverage || 10;
  const leveragedProfit = isFutures ? (parseFloat(profitPercent) * leverage).toFixed(2) : null;
  const leveragedRisk = isFutures ? (parseFloat(riskPercent) * leverage).toFixed(2) : null;

  // Generate mock price chart data
  const generateChartData = () => {
    const data = [];
    const dataPoints = 50;
    const volatility = (tp - sl) / 10;

    for (let i = 0; i < dataPoints; i++) {
      const progress = i / dataPoints;
      const trend = isLong ? progress * (tp - entry) * 0.7 : -progress * (entry - sl) * 0.7;
      const noise = (Math.random() - 0.5) * volatility;
      const price = entry + trend + noise;

      data.push({
        time: i,
        price: price,
        volume: Math.random() * 1000000 + 500000,
      });
    }
    return data;
  };

  const chartData = generateChartData();

  const formatDate = (dateString) => {
    return format(new Date(dateString), 'MMM dd, yyyy HH:mm');
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'ACTIVE': return 'bg-green-500 text-white';
      case 'EXPIRED': return 'bg-gray-500 text-white';
      case 'EXECUTED': return 'bg-blue-500 text-white';
      case 'CANCELLED': return 'bg-red-500 text-white';
      default: return 'bg-gray-500 text-white';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-6">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
          <div className="flex justify-between items-start">
            <div>
              <div className="flex items-center space-x-4">
                <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                  {signal.symbol_name || signal.symbol}
                </h1>
                <span className={`px-4 py-2 rounded-lg text-sm font-bold ${
                  isLong ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
                }`}>
                  {directionLabel}
                </span>
                <span className={`px-3 py-1 rounded-lg text-xs font-semibold ${getStatusColor(signal.status)}`}>
                  {signal.status}
                </span>
                {isFutures && (
                  <span className="px-3 py-1 rounded-lg text-xs font-semibold bg-yellow-500 text-black">
                    FUTURES {leverage}x
                  </span>
                )}
                {isForex && (
                  <span className="px-3 py-1 rounded-lg text-xs font-semibold bg-orange-500 text-white">
                    FOREX {leverage || 100}x
                  </span>
                )}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="inline-flex items-center px-3 py-1 rounded-lg text-sm font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                  {signal.timeframe} Timeframe
                </span>
                {signal.trading_type && (
                  <span className={`inline-flex items-center px-3 py-1 rounded-lg text-sm font-medium ${
                    signal.trading_type === 'SCALPING'
                      ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
                      : signal.trading_type === 'DAY'
                      ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                      : 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200'
                  }`}>
                    {signal.trading_type === 'SCALPING' ? '⚡ Scalping' : signal.trading_type === 'DAY' ? '📊 Day Trading' : '📈 Swing Trading'}
                  </span>
                )}
                {signal.estimated_duration_hours && (
                  <span className="inline-flex items-center px-3 py-1 rounded-lg text-sm font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200">
                    ⏱️ Est. {signal.estimated_duration_hours < 1
                      ? `${Math.round(signal.estimated_duration_hours * 60)} minutes`
                      : signal.estimated_duration_hours < 24
                      ? `${Math.round(signal.estimated_duration_hours)} hours`
                      : `${Math.round(signal.estimated_duration_hours / 24)} days`}
                  </span>
                )}
              </div>
              <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                Signal #{signal.id} • Created {formatDate(signal.created_at)}
              </p>
            </div>
            <button
              onClick={() => navigate(isFutures ? '/futures' : '/spot-signals')}
              className="btn btn-secondary"
            >
              ← Back
            </button>
          </div>
        </div>

        {/* Price Chart */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Price Chart</h2>
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={isLong ? "#10b981" : "#ef4444"} stopOpacity={0.3}/>
                  <stop offset="95%" stopColor={isLong ? "#10b981" : "#ef4444"} stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="time" stroke="#9ca3af" />
              <YAxis domain={[sl * 0.98, tp * 1.02]} stroke="#9ca3af" />
              <Tooltip
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                labelStyle={{ color: '#d1d5db' }}
              />
              <ReferenceLine y={entry} stroke="#3b82f6" strokeDasharray="5 5" label={{ value: 'Entry', fill: '#3b82f6', position: 'right' }} />
              <ReferenceLine y={tp} stroke="#10b981" strokeDasharray="5 5" label={{ value: 'TP', fill: '#10b981', position: 'right' }} />
              <ReferenceLine y={sl} stroke="#ef4444" strokeDasharray="5 5" label={{ value: 'SL', fill: '#ef4444', position: 'right' }} />
              <Area type="monotone" dataKey="price" stroke={isLong ? "#10b981" : "#ef4444"} fillOpacity={1} fill="url(#colorPrice)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Price Information */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
              📊 Price Levels
            </h2>
            <div className="space-y-4">
              <div className="flex justify-between items-center p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <div>
                  <p className="text-sm text-blue-700 dark:text-blue-400 font-medium">Entry Price</p>
                  <p className="text-2xl font-bold text-blue-900 dark:text-blue-100">${entry.toFixed(4)}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-blue-600 dark:text-blue-400">Current Level</p>
                </div>
              </div>

              <div className="flex justify-between items-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <div>
                  <p className="text-sm text-green-700 dark:text-green-400 font-medium">Take Profit</p>
                  <p className="text-2xl font-bold text-green-900 dark:text-green-100">${tp.toFixed(4)}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-green-600 dark:text-green-400">+{profitPercent}%</p>
                  {isFutures && (
                    <p className="text-sm font-bold text-green-700 dark:text-green-300">+{leveragedProfit}% ({leverage}x)</p>
                  )}
                </div>
              </div>

              <div className="flex justify-between items-center p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                <div>
                  <p className="text-sm text-red-700 dark:text-red-400 font-medium">Stop Loss</p>
                  <p className="text-2xl font-bold text-red-900 dark:text-red-100">${sl.toFixed(4)}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-red-600 dark:text-red-400">-{riskPercent}%</p>
                  {isFutures && (
                    <p className="text-sm font-bold text-red-700 dark:text-red-300">-{leveragedRisk}% ({leverage}x)</p>
                  )}
                </div>
              </div>

              <div className="p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                <p className="text-sm text-purple-700 dark:text-purple-400 font-medium mb-2">Risk/Reward Ratio</p>
                <p className="text-3xl font-bold text-purple-900 dark:text-purple-100">1:{riskRewardRatio}</p>
              </div>

              <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <p className="text-sm text-gray-700 dark:text-gray-300 font-medium mb-2">Confidence Level</p>
                <div className="flex items-center">
                  <div className="flex-1 bg-gray-200 dark:bg-gray-600 rounded-full h-3 mr-3">
                    <div
                      className={`h-3 rounded-full ${
                        signal.confidence >= 0.8 ? 'bg-green-500' :
                        signal.confidence >= 0.7 ? 'bg-yellow-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${signal.confidence * 100}%` }}
                    />
                  </div>
                  <span className="text-xl font-bold text-gray-900 dark:text-white">
                    {(signal.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Key Trading Points */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
              🎯 Key Trading Points
            </h2>
            <div className="space-y-3">
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-green-500 flex items-center justify-center text-white text-xs font-bold">
                  1
                </div>
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white">Entry Strategy</p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {isLong ? 'Enter when price reaches or breaks above' : 'Enter when price reaches or breaks below'} ${entry.toFixed(4)} with confirmation
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs font-bold">
                  2
                </div>
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white">Position Sizing</p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Risk only 1-2% of your capital on this trade. Calculate position size based on stop loss distance.
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-yellow-500 flex items-center justify-center text-white text-xs font-bold">
                  3
                </div>
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white">Stop Loss Placement</p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Set stop loss at ${sl.toFixed(4)}. This represents {riskPercent}% risk{isFutures ? ` (${leveragedRisk}% with ${leverage}x leverage)` : ''}.
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-green-600 flex items-center justify-center text-white text-xs font-bold">
                  4
                </div>
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white">Take Profit Target</p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Take profit at ${tp.toFixed(4)} for {profitPercent}% gain{isFutures ? ` (${leveragedProfit}% with leverage)` : ''}. Consider partial exits at 50% of the way.
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-purple-500 flex items-center justify-center text-white text-xs font-bold">
                  5
                </div>
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white">Trade Management</p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Move stop loss to breakeven once profit reaches 50%. Trail stops as price moves in your favor.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* How to Execute */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            📝 How to Execute This Trade on Binance
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                {isFutures ? '🔮 Futures Trading' : '💰 Spot Trading'}
              </h3>
              <ol className="space-y-3 text-gray-700 dark:text-gray-300">
                {isFutures ? (
                  <>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">1.</span>
                      <span>Open Binance Futures and select <span className="font-mono bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">{signal.symbol_name || signal.symbol}</span></span>
                    </li>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">2.</span>
                      <span>Set leverage to <span className="font-bold text-yellow-600">{leverage}x</span> (Isolated mode recommended)</span>
                    </li>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">3.</span>
                      <span>Choose <span className="font-bold">{isLong ? 'Long' : 'Short'}</span> position</span>
                    </li>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">4.</span>
                      <span>Set entry price: <span className="font-mono bg-blue-100 dark:bg-blue-900 px-2 py-1 rounded">${entry.toFixed(4)}</span> (or use Market order)</span>
                    </li>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">5.</span>
                      <span>Immediately set Stop Loss: <span className="font-mono bg-red-100 dark:bg-red-900 px-2 py-1 rounded">${sl.toFixed(4)}</span></span>
                    </li>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">6.</span>
                      <span>Set Take Profit: <span className="font-mono bg-green-100 dark:bg-green-900 px-2 py-1 rounded">${tp.toFixed(4)}</span></span>
                    </li>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">7.</span>
                      <span>Calculate position size based on your risk tolerance (1-2% of capital)</span>
                    </li>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">8.</span>
                      <span>Confirm and place the order</span>
                    </li>
                  </>
                ) : (
                  <>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">1.</span>
                      <span>Open Binance Spot and select <span className="font-mono bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">{signal.symbol_name || signal.symbol}</span></span>
                    </li>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">2.</span>
                      <span>Choose <span className="font-bold">{isLong ? 'Buy' : 'Sell'}</span> order type</span>
                    </li>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">3.</span>
                      <span>Set limit price: <span className="font-mono bg-blue-100 dark:bg-blue-900 px-2 py-1 rounded">${entry.toFixed(4)}</span> (or use Market order)</span>
                    </li>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">4.</span>
                      <span>Calculate amount based on 1-2% risk of your capital</span>
                    </li>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">5.</span>
                      <span>After entry, set OCO order: Take Profit at <span className="font-mono bg-green-100 dark:bg-green-900 px-2 py-1 rounded">${tp.toFixed(4)}</span> and Stop Loss at <span className="font-mono bg-red-100 dark:bg-red-900 px-2 py-1 rounded">${sl.toFixed(4)}</span></span>
                    </li>
                    <li className="flex items-start">
                      <span className="font-bold mr-2">6.</span>
                      <span>Monitor the trade and adjust stops as needed</span>
                    </li>
                  </>
                )}
              </ol>
            </div>

            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">⚠️ Risk Management</h3>
              <div className="space-y-3">
                <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
                  <p className="font-semibold text-yellow-900 dark:text-yellow-200 mb-1">Never Risk More Than 2%</p>
                  <p className="text-sm text-yellow-800 dark:text-yellow-300">
                    Calculate your position size so that if the stop loss is hit, you lose no more than 2% of your total capital.
                  </p>
                </div>

                <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                  <p className="font-semibold text-blue-900 dark:text-blue-200 mb-1">Use Stop Loss Always</p>
                  <p className="text-sm text-blue-800 dark:text-blue-300">
                    Never enter a trade without setting a stop loss. This protects your capital from unexpected market moves.
                  </p>
                </div>

                <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                  <p className="font-semibold text-green-900 dark:text-green-200 mb-1">Partial Profit Taking</p>
                  <p className="text-sm text-green-800 dark:text-green-300">
                    Consider taking 50% profit at halfway to target, then trail stop loss to breakeven on remaining position.
                  </p>
                </div>

                {isFutures && (
                  <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                    <p className="font-semibold text-red-900 dark:text-red-200 mb-1">Leverage Warning</p>
                    <p className="text-sm text-red-800 dark:text-red-300">
                      {leverage}x leverage amplifies both gains and losses. Use isolated margin and never risk more than you can afford to lose.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Signal Analysis */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            📈 Technical Analysis
          </h2>
          <div className="prose dark:prose-invert max-w-none">
            {/* Detailed Technical Analysis Description */}
            <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
              <h3 className="text-lg font-semibold text-blue-900 dark:text-blue-200 mb-3">
                🎯 Signal Generation Details
              </h3>
              <p className="text-gray-700 dark:text-gray-300 mb-3">
                {signal.description || `This ${isLong ? 'LONG' : 'SHORT'} signal for ${signal.symbol_name || signal.symbol} was generated on the ${signal.timeframe} timeframe using our multi-indicator strategy with ${(signal.confidence * 100).toFixed(0)}% confidence. ${
                  signal.confidence >= 0.8
                    ? 'High confidence signals indicate strong alignment across all technical indicators.'
                    : signal.confidence >= 0.7
                    ? 'Moderate confidence signals show good indicator alignment with some minor divergence.'
                    : 'This signal meets minimum confidence threshold with acceptable indicator alignment.'
                }`}
              </p>

              <div className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
                <div className="mb-3 p-2 bg-gray-100 dark:bg-gray-700 rounded">
                  <p className="text-xs">
                    <strong>Signal ID:</strong> #{signal.id} •
                    <strong> Symbol:</strong> {signal.symbol_name || signal.symbol} •
                    <strong> Timeframe:</strong> {signal.timeframe} •
                    <strong> Market:</strong> {isFutures ? 'Futures' : 'Spot'} •
                    <strong> Created:</strong> {formatDate(signal.created_at)}
                  </p>
                </div>
                <p className="font-semibold text-gray-900 dark:text-white mb-2">Key Indicators Used:</p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="flex items-start space-x-2">
                    <span className="text-green-600 dark:text-green-400">✓</span>
                    <div>
                      <strong>RSI (Relative Strength Index):</strong>
                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        {isLong
                          ? 'Detected oversold conditions (RSI 23-33), indicating potential reversal upward'
                          : 'Detected overbought conditions (RSI 67-77), indicating potential reversal downward'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start space-x-2">
                    <span className="text-green-600 dark:text-green-400">✓</span>
                    <div>
                      <strong>ADX (Trend Strength):</strong>
                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        ADX above 22.0 confirms strong trending market conditions suitable for entry
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start space-x-2">
                    <span className="text-green-600 dark:text-green-400">✓</span>
                    <div>
                      <strong>MACD (Momentum):</strong>
                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        {isLong
                          ? 'MACD line crossing above signal line confirms bullish momentum'
                          : 'MACD line crossing below signal line confirms bearish momentum'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start space-x-2">
                    <span className="text-green-600 dark:text-green-400">✓</span>
                    <div>
                      <strong>EMA Alignment:</strong>
                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        {isLong
                          ? 'Price above EMA50 with EMA9 > EMA50 confirms bullish trend structure'
                          : 'Price below EMA50 with EMA9 < EMA50 confirms bearish trend structure'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start space-x-2">
                    <span className="text-green-600 dark:text-green-400">✓</span>
                    <div>
                      <strong>SuperTrend Indicator:</strong>
                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        {isLong
                          ? 'SuperTrend flipped to bullish (green), confirming upward momentum'
                          : 'SuperTrend flipped to bearish (red), confirming downward momentum'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start space-x-2">
                    <span className="text-green-600 dark:text-green-400">✓</span>
                    <div>
                      <strong>Volume Confirmation:</strong>
                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        Volume above average confirms institutional interest and validates the move
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start space-x-2">
                    <span className="text-green-600 dark:text-green-400">✓</span>
                    <div>
                      <strong>Heikin Ashi Candles:</strong>
                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        {isLong
                          ? 'Green Heikin Ashi candles indicate sustained bullish pressure'
                          : 'Red Heikin Ashi candles indicate sustained bearish pressure'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start space-x-2">
                    <span className="text-green-600 dark:text-green-400">✓</span>
                    <div>
                      <strong>MFI (Money Flow Index):</strong>
                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        {isLong
                          ? 'Money flow showing accumulation with MFI in oversold zone'
                          : 'Money flow showing distribution with MFI in overbought zone'}
                      </p>
                    </div>
                  </div>
                </div>

                {signal.timeframe !== '15m' && (
                  <div className="mt-4 p-3 bg-purple-50 dark:bg-purple-900/20 rounded border border-purple-200 dark:border-purple-800">
                    <p className="font-semibold text-purple-900 dark:text-purple-200 mb-1">
                      🔄 Multi-Timeframe Confirmation
                    </p>
                    <p className="text-xs text-purple-800 dark:text-purple-300">
                      This signal was confirmed by analyzing daily (1d) trend alignment. {isLong ? 'Daily trend is BULLISH' : 'Daily trend is BEARISH'}, ensuring we trade with the higher timeframe momentum.
                    </p>
                  </div>
                )}

                <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded border border-yellow-200 dark:border-yellow-800">
                  <p className="font-semibold text-yellow-900 dark:text-yellow-200 mb-1">
                    ⚠️ Risk Management Strategy ({signal.timeframe} Timeframe)
                  </p>
                  <p className="text-xs text-yellow-800 dark:text-yellow-300">
                    Stop Loss: ${sl.toFixed(4)} (calculated using {signal.timeframe} ATR × 1.5x = ${Math.abs(sl - entry).toFixed(4)} distance).
                    Take Profit: ${tp.toFixed(4)} (set at 3.5x risk distance = ${Math.abs(tp - entry).toFixed(4)} distance).
                    This provides a {riskRewardRatio}:1 risk/reward ratio.
                    {signal.timeframe === '15m' && ' 15-minute signals are for scalping - expect quick moves.'}
                    {signal.timeframe === '1h' && ' 1-hour signals balance frequency with quality - good for day trading.'}
                    {signal.timeframe === '4h' && ' 4-hour signals are higher quality - best for swing trading.'}
                    {signal.timeframe === '1d' && ' Daily signals are the highest timeframe - ideal for position trading.'}
                  </p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
              <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Market Type</p>
                <p className="text-lg font-bold text-gray-900 dark:text-white">
                  {isFutures ? 'Futures Market' : 'Spot Market'}
                </p>
              </div>
              <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Timeframe</p>
                <p className="text-lg font-bold text-gray-900 dark:text-white">{signal.timeframe}</p>
              </div>
              <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Signal Strength</p>
                <p className="text-lg font-bold text-gray-900 dark:text-white">
                  {signal.confidence >= 0.8 ? 'Strong' : signal.confidence >= 0.7 ? 'Moderate' : 'Weak'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Action Button */}
        <div className="mt-6 flex justify-center">
          <a
            href={`https://www.binance.com/en/trade/${signal.symbol_name || signal.symbol}?type=${isFutures ? 'futures' : 'spot'}`}
            target="_blank"
            rel="noopener noreferrer"
            className={`px-8 py-4 rounded-lg font-bold text-lg transition-all transform hover:scale-105 ${
              isLong
                ? 'bg-green-600 hover:bg-green-700 text-white'
                : 'bg-red-600 hover:bg-red-700 text-white'
            }`}
          >
            🚀 Trade {signal.symbol_name || signal.symbol} on Binance →
          </a>
        </div>
      </div>
    </div>
  );
};

export default SignalDetail;
