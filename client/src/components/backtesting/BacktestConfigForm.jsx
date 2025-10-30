/**
 * Backtest Configuration Form Component
 */
import { useState } from 'react';
import { Play, AlertCircle, Loader } from 'lucide-react';
import useBacktestStore from '../../store/useBacktestStore';

const BacktestConfigForm = ({ onBacktestCreated }) => {
  const { createBacktest, loading, error } = useBacktestStore();

  const [formData, setFormData] = useState({
    name: '',
    symbols: 'BTCUSDT,ETHUSDT',
    timeframe: '5m',
    start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0],
    initial_capital: '10000',
    position_size: '100',
    // Strategy parameters
    rsi_period: '14',
    rsi_oversold: '30',
    rsi_overbought: '70',
    ema_fast_period: '9',
    ema_slow_period: '21',
    macd_fast_period: '12',
    macd_slow_period: '26',
    macd_signal_period: '9',
    volume_threshold: '1.5',
    min_confidence: '0.7',
    stop_loss_pct: '2',
    take_profit_pct: '4'
  });

  const [formErrors, setFormErrors] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    // Clear error for this field
    if (formErrors[name]) {
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[name];
        return newErrors;
      });
    }
  };

  const validateForm = () => {
    const errors = {};

    if (!formData.name.trim()) {
      errors.name = 'Name is required';
    }

    if (!formData.symbols.trim()) {
      errors.symbols = 'At least one symbol is required';
    }

    const startDate = new Date(formData.start_date);
    const endDate = new Date(formData.end_date);

    if (startDate >= endDate) {
      errors.start_date = 'Start date must be before end date';
    }

    if (parseFloat(formData.initial_capital) <= 0) {
      errors.initial_capital = 'Initial capital must be greater than 0';
    }

    if (parseFloat(formData.position_size) <= 0) {
      errors.position_size = 'Position size must be greater than 0';
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      // Parse symbols
      const symbols = formData.symbols
        .split(',')
        .map(s => s.trim().toUpperCase())
        .filter(s => s.length > 0);

      // Build strategy params
      const strategy_params = {
        rsi_period: parseInt(formData.rsi_period),
        rsi_oversold: parseFloat(formData.rsi_oversold),
        rsi_overbought: parseFloat(formData.rsi_overbought),
        ema_fast_period: parseInt(formData.ema_fast_period),
        ema_slow_period: parseInt(formData.ema_slow_period),
        macd_fast_period: parseInt(formData.macd_fast_period),
        macd_slow_period: parseInt(formData.macd_slow_period),
        macd_signal_period: parseInt(formData.macd_signal_period),
        volume_threshold: parseFloat(formData.volume_threshold),
        min_confidence: parseFloat(formData.min_confidence),
        stop_loss_pct: parseFloat(formData.stop_loss_pct),
        take_profit_pct: parseFloat(formData.take_profit_pct)
      };

      // Create backtest configuration
      const config = {
        name: formData.name,
        symbols,
        timeframe: formData.timeframe,
        start_date: new Date(formData.start_date).toISOString(),
        end_date: new Date(formData.end_date).toISOString(),
        initial_capital: parseFloat(formData.initial_capital),
        position_size: parseFloat(formData.position_size),
        strategy_params
      };

      const backtest = await createBacktest(config);

      if (onBacktestCreated) {
        onBacktestCreated(backtest);
      }
    } catch (err) {
      console.error('Failed to create backtest:', err);
    }
  };

  return (
    <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6">
      <h2 className="text-xl font-semibold text-white mb-6">Configure Backtest</h2>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-start gap-3 mb-6">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-red-400 font-medium">Failed to create backtest</p>
            <p className="text-red-300 text-sm mt-1">{error}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Configuration */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-white border-b border-gray-700 pb-2">
            Basic Configuration
          </h3>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Backtest Name *
            </label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              placeholder="e.g., BTC Strategy Test"
              className={`w-full bg-gray-900/50 border ${formErrors.name ? 'border-red-500' : 'border-gray-700'} rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500`}
            />
            {formErrors.name && (
              <p className="text-red-400 text-sm mt-1">{formErrors.name}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Symbols * (comma-separated)
            </label>
            <input
              type="text"
              name="symbols"
              value={formData.symbols}
              onChange={handleChange}
              placeholder="e.g., BTCUSDT, ETHUSDT, BNBUSDT"
              className={`w-full bg-gray-900/50 border ${formErrors.symbols ? 'border-red-500' : 'border-gray-700'} rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500`}
            />
            {formErrors.symbols && (
              <p className="text-red-400 text-sm mt-1">{formErrors.symbols}</p>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Timeframe
              </label>
              <select
                name="timeframe"
                value={formData.timeframe}
                onChange={handleChange}
                className="w-full bg-gray-900/50 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="1m">1 Minute</option>
                <option value="5m">5 Minutes</option>
                <option value="15m">15 Minutes</option>
                <option value="1h">1 Hour</option>
                <option value="4h">4 Hours</option>
                <option value="1d">1 Day</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Initial Capital ($)
              </label>
              <input
                type="number"
                name="initial_capital"
                value={formData.initial_capital}
                onChange={handleChange}
                min="0"
                step="100"
                className={`w-full bg-gray-900/50 border ${formErrors.initial_capital ? 'border-red-500' : 'border-gray-700'} rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500`}
              />
              {formErrors.initial_capital && (
                <p className="text-red-400 text-sm mt-1">{formErrors.initial_capital}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Position Size ($)
              </label>
              <input
                type="number"
                name="position_size"
                value={formData.position_size}
                onChange={handleChange}
                min="0"
                step="10"
                className={`w-full bg-gray-900/50 border ${formErrors.position_size ? 'border-red-500' : 'border-gray-700'} rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500`}
              />
              {formErrors.position_size && (
                <p className="text-red-400 text-sm mt-1">{formErrors.position_size}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Start Date
              </label>
              <input
                type="date"
                name="start_date"
                value={formData.start_date}
                onChange={handleChange}
                className={`w-full bg-gray-900/50 border ${formErrors.start_date ? 'border-red-500' : 'border-gray-700'} rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500`}
              />
              {formErrors.start_date && (
                <p className="text-red-400 text-sm mt-1">{formErrors.start_date}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                End Date
              </label>
              <input
                type="date"
                name="end_date"
                value={formData.end_date}
                onChange={handleChange}
                className="w-full bg-gray-900/50 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Strategy Parameters */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-white border-b border-gray-700 pb-2">
            Strategy Parameters
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                RSI Period
              </label>
              <input
                type="number"
                name="rsi_period"
                value={formData.rsi_period}
                onChange={handleChange}
                min="1"
                className="w-full bg-gray-900/50 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                RSI Oversold
              </label>
              <input
                type="number"
                name="rsi_oversold"
                value={formData.rsi_oversold}
                onChange={handleChange}
                min="0"
                max="100"
                className="w-full bg-gray-900/50 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                RSI Overbought
              </label>
              <input
                type="number"
                name="rsi_overbought"
                value={formData.rsi_overbought}
                onChange={handleChange}
                min="0"
                max="100"
                className="w-full bg-gray-900/50 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                EMA Fast Period
              </label>
              <input
                type="number"
                name="ema_fast_period"
                value={formData.ema_fast_period}
                onChange={handleChange}
                min="1"
                className="w-full bg-gray-900/50 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                EMA Slow Period
              </label>
              <input
                type="number"
                name="ema_slow_period"
                value={formData.ema_slow_period}
                onChange={handleChange}
                min="1"
                className="w-full bg-gray-900/50 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Min Confidence
              </label>
              <input
                type="number"
                name="min_confidence"
                value={formData.min_confidence}
                onChange={handleChange}
                min="0"
                max="1"
                step="0.1"
                className="w-full bg-gray-900/50 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Stop Loss (%)
              </label>
              <input
                type="number"
                name="stop_loss_pct"
                value={formData.stop_loss_pct}
                onChange={handleChange}
                min="0"
                step="0.5"
                className="w-full bg-gray-900/50 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Take Profit (%)
              </label>
              <input
                type="number"
                name="take_profit_pct"
                value={formData.take_profit_pct}
                onChange={handleChange}
                min="0"
                step="0.5"
                className="w-full bg-gray-900/50 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <div className="flex justify-end gap-4 pt-4">
          <button
            type="submit"
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white px-8 py-3 rounded-lg font-medium flex items-center gap-2 transition-colors"
          >
            {loading ? (
              <>
                <Loader className="w-5 h-5 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                Run Backtest
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default BacktestConfigForm;
