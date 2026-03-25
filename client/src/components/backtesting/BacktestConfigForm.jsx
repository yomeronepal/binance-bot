import { useState, useEffect, useMemo } from 'react';
import { Play, AlertCircle, Loader, Database, Info, ChevronDown, ChevronRight } from 'lucide-react';
import useBacktestStore from '../../store/useBacktestStore';
import api from '../../services/api';

const VOLATILITY_COLORS = {
  low: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  medium: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  high: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
};

const BacktestConfigForm = ({ onBacktestCreated }) => {
  const { createBacktest, loading, error } = useBacktestStore();

  const [datasets, setDatasets] = useState([]);
  const [symbols, setSymbols] = useState([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);

  const [formData, setFormData] = useState({
    name: '',
    selectedSymbols: [],
    timeframe: '4h',
    start_date: '',
    end_date: '',
    initial_capital: '10000',
    position_size: '100',
    min_confidence: '0.73',
    long_rsi_min: '23',
    long_rsi_max: '33',
    short_rsi_min: '67',
    short_rsi_max: '77',
    long_adx_min: '22',
    short_adx_min: '22',
    long_volume_multiplier: '1.2',
    short_volume_multiplier: '1.2',
    sl_percentage: '2.5',
    tp_percentage: '6.0',
    sl_atr_multiplier: '3.0',
    tp_atr_multiplier: '9.0',
    risk_reward_ratio: '3.0',
    macd_weight: '2.0',
    rsi_weight: '1.5',
    price_ema_weight: '1.8',
    adx_weight: '1.7',
    ha_weight: '1.6',
    volume_weight: '1.4',
    ema_alignment_weight: '1.2',
    di_weight: '1.0',
    bb_weight: '0.8',
    volatility_weight: '0.5',
    supertrend_weight: '1.9',
    mfi_weight: '1.3',
    psar_weight: '1.1',
    fibonacci_weight: '2.5',
    fib_lookback_candles: '50',
    fib_entry_zone_min: '0.5',
    fib_entry_zone_max: '0.618',
    rsi_period: '14',
    macd_fast: '12',
    macd_slow: '26',
    macd_signal: '9',
    ema_fast: '9',
    ema_medium: '21',
    ema_slow: '50',
    ema_trend: '200',
    atr_period: '14',
    adx_period: '14',
    bb_period: '20',
    bb_std_dev: '2.0',
    volume_ma_period: '20',
    supertrend_period: '10',
    supertrend_multiplier: '3.0',
    mfi_period: '14',
    psar_acceleration: '0.02',
    psar_maximum: '0.2',
  });

  const [expandedSections, setExpandedSections] = useState({
    entry: true,
    risk: false,
    weights: false,
    indicators: false,
    fibonacci: false,
  });

  const [formErrors, setFormErrors] = useState({});

  useEffect(() => {
    fetchDatasets();
  }, []);

  const fetchDatasets = async () => {
    try {
      setDatasetsLoading(true);
      const res = await api.get('/backtest/datasets/');
      const data = res.data;
      setDatasets(data.datasets || []);
      setSymbols(data.symbols || []);
      if (data.symbols?.length > 0) {
        setFormData(prev => ({ ...prev, selectedSymbols: [data.symbols[0]] }));
      }
    } catch (err) {
      console.error('Failed to fetch datasets:', err);
      setSymbols(['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOGEUSDT']);
    } finally {
      setDatasetsLoading(false);
    }
  };

  const ALL_TIMEFRAMES = ['5m', '15m', '1h', '4h', '1d'];

  const availableTimeframes = useMemo(() => {
    if (formData.selectedSymbols.length === 0 || datasets.length === 0) return ALL_TIMEFRAMES;
    const tfs = formData.selectedSymbols.map(sym =>
      datasets.filter(d => d.symbol === sym).map(d => d.timeframe)
    );
    if (tfs.length === 0) return ALL_TIMEFRAMES;
    const intersection = tfs.reduce((a, b) => a.filter(t => b.includes(t)));
    return intersection.length > 0 ? intersection : ALL_TIMEFRAMES;
  }, [formData.selectedSymbols, datasets]);

  const hasDataForTimeframe = useMemo(() => {
    const lookup = {};
    ALL_TIMEFRAMES.forEach(tf => {
      lookup[tf] = formData.selectedSymbols.length === 0 ||
        datasets.some(d => formData.selectedSymbols.includes(d.symbol) && d.timeframe === tf);
    });
    return lookup;
  }, [formData.selectedSymbols, datasets]);

  const selectedDataset = useMemo(() => {
    if (formData.selectedSymbols.length === 0) return null;
    const matching = datasets.filter(d => formData.selectedSymbols.includes(d.symbol));
    if (matching.length === 0) return null;
    const earliest = matching.reduce((a, b) => a.start_date < b.start_date ? a : b);
    const latest = matching.reduce((a, b) => a.end_date > b.end_date ? a : b);
    const tfMatching = matching.filter(d => d.timeframe === formData.timeframe);
    return {
      start_date: earliest.start_date,
      end_date: latest.end_date,
      total_candles: tfMatching.reduce((sum, d) => sum + d.candles, 0),
    };
  }, [formData.selectedSymbols, formData.timeframe, datasets]);

  useEffect(() => {
    if (selectedDataset) {
      setFormData(prev => ({
        ...prev,
        start_date: selectedDataset.start_date,
        end_date: selectedDataset.end_date,
      }));
    }
  }, [selectedDataset]);

  useEffect(() => {
    if (formData.selectedSymbols.length > 0 && !hasDataForTimeframe[formData.timeframe]) {
      const preferred = ['4h', '1h', '15m', '5m', '1d'];
      const best = preferred.find(tf => hasDataForTimeframe[tf]);
      if (best) {
        setFormData(prev => ({ ...prev, timeframe: best }));
      }
    }
  }, [formData.selectedSymbols, hasDataForTimeframe]);

  const toggleSymbol = (sym) => {
    setFormData(prev => {
      const selected = prev.selectedSymbols.includes(sym)
        ? prev.selectedSymbols.filter(s => s !== sym)
        : [...prev.selectedSymbols, sym];
      return { ...prev, selectedSymbols: selected };
    });
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (formErrors[name]) {
      setFormErrors(prev => { const n = { ...prev }; delete n[name]; return n; });
    }
  };

  const validateForm = () => {
    const errors = {};
    if (!formData.name.trim()) errors.name = 'Name is required';
    if (formData.selectedSymbols.length === 0) errors.symbols = 'Select at least one symbol';
    if (!formData.timeframe) errors.timeframe = 'Select a timeframe';
    if (formData.selectedSymbols.length === 0) errors.symbols = 'Select at least one symbol';
    if (parseFloat(formData.initial_capital) <= 0) errors.initial_capital = 'Must be > 0';
    if (parseFloat(formData.position_size) <= 0) errors.position_size = 'Must be > 0';
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;

    try {
      const startDate = selectedDataset?.start_date || '2023-01-01';
      const endDate = selectedDataset?.end_date || '2024-12-31';

      const config = {
        name: formData.name,
        symbols: formData.selectedSymbols,
        timeframe: formData.timeframe,
        start_date: new Date(startDate).toISOString(),
        end_date: new Date(endDate).toISOString(),
        initial_capital: parseFloat(formData.initial_capital),
        position_size: parseFloat(formData.position_size),
        strategy_params: Object.fromEntries(
          Object.entries(formData)
            .filter(([k]) => !['name', 'selectedSymbols', 'timeframe', 'start_date', 'end_date', 'initial_capital', 'position_size'].includes(k))
            .map(([k, v]) => [k, parseFloat(v)])
        ),
      };

      const backtest = await createBacktest(config);
      if (onBacktestCreated) onBacktestCreated(backtest);
    } catch (err) {
      console.error('Failed to create backtest:', err);
    }
  };

  const getVolatility = (sym) => {
    const d = datasets.find(ds => ds.symbol === sym);
    return d?.volatility || 'medium';
  };

  if (datasetsLoading) {
    return (
      <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700/50 rounded-xl p-8 flex items-center justify-center gap-3">
        <Loader className="w-5 h-5 animate-spin text-blue-500" />
        <span className="text-gray-600 dark:text-gray-400">Loading datasets...</span>
      </div>
    );
  }

  const inputClass = "w-full bg-gray-50 dark:bg-gray-900/50 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";
  const labelClass = "block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5 uppercase tracking-wider";

  const toggleSection = (key) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const renderSection = (key, title, fields) => (
    <div className="border border-gray-200 dark:border-gray-700/50 rounded-lg overflow-hidden">
      <button type="button" onClick={() => toggleSection(key)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-800/80 hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors">
        <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">{title}</span>
        {expandedSections[key] ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
      </button>
      {expandedSections[key] && (
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2 p-3">
          {fields.map(f => (
            <div key={f.name}>
              <span className="text-[10px] text-gray-500 dark:text-gray-500 block mb-0.5">{f.label}</span>
              <input type="number" name={f.name} value={formData[f.name]} onChange={handleChange}
                min={f.min || '0'} max={f.max} step={f.step || '1'} className={inputClass} />
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700/50 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-5">
        <Database className="w-5 h-5 text-blue-500" />
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">New Backtest</h2>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-lg p-3 flex items-start gap-2 mb-5">
          <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
          <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className={labelClass}>Backtest Name</label>
          <input type="text" name="name" value={formData.name} onChange={handleChange}
            placeholder="e.g., BTC 4h RSI Strategy" className={inputClass} />
          {formErrors.name && <p className="text-red-500 text-xs mt-1">{formErrors.name}</p>}
        </div>

        <div>
          <label className={labelClass}>Select Symbols</label>
          <div className="flex flex-wrap gap-2">
            {symbols.map(sym => {
              const vol = getVolatility(sym);
              const selected = formData.selectedSymbols.includes(sym);
              const ds = datasets.find(d => d.symbol === sym && d.timeframe === (availableTimeframes[0] || '4h'));
              return (
                <button key={sym} type="button" onClick={() => toggleSymbol(sym)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                    selected
                      ? 'bg-blue-600 text-white border-blue-600 shadow-sm shadow-blue-500/20'
                      : `${VOLATILITY_COLORS[vol]} border hover:opacity-80`
                  }`}
                >
                  <span>{sym.replace('USDT', '')}</span>
                  {ds && <span className="ml-1 opacity-60">{(ds.candles / 1000).toFixed(0)}K</span>}
                </button>
              );
            })}
          </div>
          {formErrors.symbols && <p className="text-red-500 text-xs mt-1">{formErrors.symbols}</p>}
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className={labelClass}>Timeframe</label>
            <select name="timeframe" value={formData.timeframe} onChange={handleChange} className={inputClass}>
              {ALL_TIMEFRAMES.map(tf => {
                const hasData = hasDataForTimeframe[tf];
                const ds = datasets.find(d => formData.selectedSymbols.includes(d.symbol) && d.timeframe === tf);
                return (
                  <option key={tf} value={tf}>
                    {tf}{hasData && ds ? ` (${(ds.candles / 1000).toFixed(0)}K candles)` : ''}
                  </option>
                );
              })}
            </select>
          </div>
          <div>
            <label className={labelClass}>Capital ($)</label>
            <input type="number" name="initial_capital" value={formData.initial_capital} onChange={handleChange} min="100" step="100" className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Position ($)</label>
            <input type="number" name="position_size" value={formData.position_size} onChange={handleChange} min="10" step="10" className={inputClass} />
          </div>
        </div>

        {selectedDataset && (
          <input type="hidden" name="start_date" value={selectedDataset.start_date} />
        )}
        {selectedDataset && (
          <input type="hidden" name="end_date" value={selectedDataset.end_date} />
        )}

        {selectedDataset && (
          <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/20 rounded-lg">
            <Info className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
            <span className="text-xs text-blue-600 dark:text-blue-400">
              Data: {selectedDataset.start_date} to {selectedDataset.end_date} ({selectedDataset.total_candles.toLocaleString()} candles)
            </span>
          </div>
        )}

        {renderSection('entry', 'Entry & Exit Rules', [
          { name: 'min_confidence', label: 'Confidence', step: '0.01', min: '0', max: '1' },
          { name: 'long_rsi_min', label: 'Long RSI Min', min: '0', max: '50' },
          { name: 'long_rsi_max', label: 'Long RSI Max', min: '0', max: '50' },
          { name: 'short_rsi_min', label: 'Short RSI Min', min: '50', max: '100' },
          { name: 'short_rsi_max', label: 'Short RSI Max', min: '50', max: '100' },
          { name: 'long_adx_min', label: 'Long ADX Min', min: '0' },
          { name: 'short_adx_min', label: 'Short ADX Min', min: '0' },
          { name: 'long_volume_multiplier', label: 'Long Vol Multi', step: '0.1', min: '0' },
          { name: 'short_volume_multiplier', label: 'Short Vol Multi', step: '0.1', min: '0' },
        ])}

        {renderSection('risk', 'Risk Management', [
          { name: 'sl_percentage', label: 'SL %', step: '0.5', min: '0' },
          { name: 'tp_percentage', label: 'TP %', step: '0.5', min: '0' },
          { name: 'sl_atr_multiplier', label: 'SL ATR Multi', step: '0.5', min: '0' },
          { name: 'tp_atr_multiplier', label: 'TP ATR Multi', step: '0.5', min: '0' },
          { name: 'risk_reward_ratio', label: 'R/R Ratio', step: '0.5', min: '0' },
        ])}

        {renderSection('weights', 'Indicator Weights', [
          { name: 'macd_weight', label: 'MACD', step: '0.1' },
          { name: 'rsi_weight', label: 'RSI', step: '0.1' },
          { name: 'price_ema_weight', label: 'Price EMA', step: '0.1' },
          { name: 'adx_weight', label: 'ADX', step: '0.1' },
          { name: 'ha_weight', label: 'Heikin-Ashi', step: '0.1' },
          { name: 'volume_weight', label: 'Volume', step: '0.1' },
          { name: 'ema_alignment_weight', label: 'EMA Align', step: '0.1' },
          { name: 'di_weight', label: 'DI (+/-)', step: '0.1' },
          { name: 'bb_weight', label: 'Bollinger', step: '0.1' },
          { name: 'volatility_weight', label: 'Volatility', step: '0.1' },
          { name: 'supertrend_weight', label: 'SuperTrend', step: '0.1' },
          { name: 'mfi_weight', label: 'MFI', step: '0.1' },
          { name: 'psar_weight', label: 'PSAR', step: '0.1' },
          { name: 'fibonacci_weight', label: 'Fibonacci', step: '0.1' },
        ])}

        {renderSection('indicators', 'Indicator Periods', [
          { name: 'rsi_period', label: 'RSI Period', min: '1' },
          { name: 'macd_fast', label: 'MACD Fast', min: '1' },
          { name: 'macd_slow', label: 'MACD Slow', min: '1' },
          { name: 'macd_signal', label: 'MACD Signal', min: '1' },
          { name: 'ema_fast', label: 'EMA Fast', min: '1' },
          { name: 'ema_medium', label: 'EMA Medium', min: '1' },
          { name: 'ema_slow', label: 'EMA Slow', min: '1' },
          { name: 'ema_trend', label: 'EMA Trend', min: '1' },
          { name: 'atr_period', label: 'ATR Period', min: '1' },
          { name: 'adx_period', label: 'ADX Period', min: '1' },
          { name: 'bb_period', label: 'BB Period', min: '1' },
          { name: 'bb_std_dev', label: 'BB Std Dev', step: '0.1', min: '0' },
          { name: 'volume_ma_period', label: 'Vol MA Period', min: '1' },
          { name: 'supertrend_period', label: 'SuperTrend Period', min: '1' },
          { name: 'supertrend_multiplier', label: 'SuperTrend Multi', step: '0.5', min: '0' },
          { name: 'mfi_period', label: 'MFI Period', min: '1' },
          { name: 'psar_acceleration', label: 'PSAR Accel', step: '0.01', min: '0' },
          { name: 'psar_maximum', label: 'PSAR Max', step: '0.01', min: '0' },
        ])}

        {renderSection('fibonacci', 'Fibonacci Settings', [
          { name: 'fib_lookback_candles', label: 'Lookback Candles', min: '10' },
          { name: 'fib_entry_zone_min', label: 'Entry Zone Min', step: '0.01', min: '0', max: '1' },
          { name: 'fib_entry_zone_max', label: 'Entry Zone Max', step: '0.01', min: '0', max: '1' },
        ])}

        <button type="submit" disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white py-2.5 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors">
          {loading ? (
            <><Loader className="w-4 h-4 animate-spin" /> Running...</>
          ) : (
            <><Play className="w-4 h-4" /> Run Backtest</>
          )}
        </button>
      </form>
    </div>
  );
};

export default BacktestConfigForm;
