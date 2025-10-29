import React, { useState } from 'react';
import { X, Save, AlertCircle } from 'lucide-react';

const AutoTradingSettings = ({ account, onSave, onClose }) => {
  const [settings, setSettings] = useState({
    auto_trading_enabled: account?.auto_trading_enabled ?? true,
    auto_trade_spot: account?.auto_trade_spot ?? true,
    auto_trade_futures: account?.auto_trade_futures ?? true,
    min_signal_confidence: account?.min_signal_confidence ?? 0.70,
    max_position_size: account?.max_position_size ?? 10.00,
    max_open_trades: account?.max_open_trades ?? 5,
  });

  const handleChange = (field, value) => {
    setSettings(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(settings);
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-gray-800 border border-gray-700 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700">
          <h2 className="text-2xl font-bold text-white">Auto-Trading Settings</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Auto-Trading Toggle */}
          <div className="space-y-2">
            <label className="flex items-center justify-between">
              <div>
                <div className="text-white font-medium">Enable Auto-Trading</div>
                <div className="text-sm text-gray-400">Automatically execute trades when signals are generated</div>
              </div>
              <input
                type="checkbox"
                checked={settings.auto_trading_enabled}
                onChange={(e) => handleChange('auto_trading_enabled', e.target.checked)}
                className="w-5 h-5 rounded border-gray-600 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800"
              />
            </label>
          </div>

          {/* Market Types */}
          <div className="space-y-4">
            <div className="text-white font-medium">Market Types</div>

            <label className="flex items-center justify-between">
              <div>
                <div className="text-gray-300">Spot Trading</div>
                <div className="text-sm text-gray-400">Trade spot markets</div>
              </div>
              <input
                type="checkbox"
                checked={settings.auto_trade_spot}
                onChange={(e) => handleChange('auto_trade_spot', e.target.checked)}
                className="w-5 h-5 rounded border-gray-600 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800"
              />
            </label>

            <label className="flex items-center justify-between">
              <div>
                <div className="text-gray-300">Futures Trading</div>
                <div className="text-sm text-gray-400">Trade futures markets with leverage</div>
              </div>
              <input
                type="checkbox"
                checked={settings.auto_trade_futures}
                onChange={(e) => handleChange('auto_trade_futures', e.target.checked)}
                className="w-5 h-5 rounded border-gray-600 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800"
              />
            </label>
          </div>

          {/* Risk Management */}
          <div className="space-y-4">
            <div className="text-white font-medium">Risk Management</div>

            {/* Min Signal Confidence */}
            <div className="space-y-2">
              <label className="text-gray-300 text-sm">
                Minimum Signal Confidence
                <span className="text-blue-400 ml-2">{(settings.min_signal_confidence * 100).toFixed(0)}%</span>
              </label>
              <input
                type="range"
                min="0.5"
                max="1.0"
                step="0.05"
                value={settings.min_signal_confidence}
                onChange={(e) => handleChange('min_signal_confidence', parseFloat(e.target.value))}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer"
              />
              <div className="text-xs text-gray-400">
                Only trade signals with confidence above this threshold
              </div>
            </div>

            {/* Max Position Size */}
            <div className="space-y-2">
              <label className="text-gray-300 text-sm">
                Max Position Size
                <span className="text-blue-400 ml-2">{settings.max_position_size}%</span>
              </label>
              <input
                type="range"
                min="1"
                max="50"
                step="1"
                value={settings.max_position_size}
                onChange={(e) => handleChange('max_position_size', parseFloat(e.target.value))}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer"
              />
              <div className="text-xs text-gray-400">
                Maximum percentage of balance per trade
              </div>
            </div>

            {/* Max Open Trades */}
            <div className="space-y-2">
              <label className="text-gray-300 text-sm">
                Max Open Trades
                <span className="text-blue-400 ml-2">{settings.max_open_trades}</span>
              </label>
              <input
                type="range"
                min="1"
                max="20"
                step="1"
                value={settings.max_open_trades}
                onChange={(e) => handleChange('max_open_trades', parseInt(e.target.value))}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer"
              />
              <div className="text-xs text-gray-400">
                Maximum number of concurrent open positions
              </div>
            </div>
          </div>

          {/* Warning */}
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-yellow-400">
              <div className="font-medium mb-1">Important</div>
              <div className="text-yellow-400/80">
                Changes will apply to new trades. Existing open positions are not affected.
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-3 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-3 bg-gradient-to-r from-blue-500 to-purple-500 text-white rounded-lg hover:from-blue-600 hover:to-purple-600 transition-all font-medium flex items-center justify-center gap-2"
            >
              <Save className="w-4 h-4" />
              Save Settings
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AutoTradingSettings;
