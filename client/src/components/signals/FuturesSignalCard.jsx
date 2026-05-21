import { format } from 'date-fns';
import { Link } from 'react-router-dom';
import { useState } from 'react';
import { TrendingUp, TrendingDown, Shield, Target, Zap, BarChart3, Clock, ArrowRight, ExternalLink, RefreshCw } from 'lucide-react';
import usePaperTradeStore from '../../store/usePaperTradeStore';
import AssetClassBadge from '../common/AssetClassBadge';

const formatPrice = (price) => {
  if (!price) return 'N/A';
  const num = parseFloat(price);
  if (num >= 1000) return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (num >= 1) return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  return num.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 8 });
};

const ConfidenceBar = ({ value }) => {
  const pct = value * 100;
  const color = pct >= 80 ? 'from-emerald-400 to-emerald-600' : pct >= 70 ? 'from-yellow-400 to-amber-500' : 'from-rose-400 to-rose-600';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full bg-gradient-to-r ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-bold text-gray-900 dark:text-white w-9 text-right">{pct.toFixed(0)}%</span>
    </div>
  );
};

const MetricPill = ({ label, value, color = 'text-blue-600 dark:text-blue-400' }) => (
  <div className="flex flex-col items-center p-2 bg-gray-50 dark:bg-gray-900/40 rounded-lg flex-1">
    <span className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wider">{label}</span>
    <span className={`text-sm font-bold ${color}`}>{value}</span>
  </div>
);

const FuturesSignalCard = ({ signal, tradingMode = 'paper' }) => {
  const isLong = signal.direction === 'LONG';
  const [isCreatingTrade, setIsCreatingTrade] = useState(false);
  const { createTradeFromSignal } = usePaperTradeStore();

  const handleCreatePaperTrade = async () => {
    setIsCreatingTrade(true);
    try {
      await createTradeFromSignal(signal.id, 100);
      alert('Paper trade created successfully!');
    } catch (error) {
      alert(`Failed to create paper trade: ${error.message}`);
    } finally {
      setIsCreatingTrade(false);
    }
  };

  const risk = Math.abs(parseFloat(signal.entry) - parseFloat(signal.sl));
  const reward = Math.abs(parseFloat(signal.tp) - parseFloat(signal.entry));
  const rr = risk > 0 ? (reward / risk).toFixed(1) : '0';
  const leverage = signal.leverage || 10;
  const roi = ((reward / parseFloat(signal.entry)) * 100 * leverage).toFixed(1);
  const symbol = signal.symbol_name || signal.symbol?.symbol || signal.symbol;
  const isReversed = signal.is_neutral_reversal || signal.meta?.neutral_reversal;

  const accentGradient = isLong
    ? 'from-emerald-500/20 via-transparent to-transparent'
    : 'from-rose-500/20 via-transparent to-transparent';
  const borderColor = isLong ? 'border-emerald-500/30' : 'border-rose-500/30';
  const DirIcon = isLong ? TrendingUp : TrendingDown;

  return (
    <div className={`relative bg-white dark:bg-gray-800/90 backdrop-blur-sm rounded-xl border ${borderColor} hover:shadow-xl hover:shadow-gray-200/40 dark:hover:shadow-black/40 transition-all duration-300 overflow-hidden group`}>
      <div className={`absolute inset-0 bg-gradient-to-br ${accentGradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none`} />

      {signal.is_priority && (
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-amber-400 via-amber-500 to-orange-500 animate-pulse" />
      )}

      <div className="relative p-4">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className={`relative p-2 rounded-xl ${isLong ? 'bg-emerald-500/10' : 'bg-rose-500/10'}`}>
              <DirIcon className={`w-5 h-5 ${isLong ? 'text-emerald-500' : 'text-rose-500'}`} />
              {signal.is_priority && (
                <Zap className="absolute -top-1 -right-1 w-3 h-3 text-amber-500 fill-amber-500" />
              )}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <h3 className="font-bold text-gray-900 dark:text-white text-base truncate">{symbol}</h3>
                <span className="text-[9px] font-bold bg-yellow-500/20 text-yellow-600 dark:text-yellow-400 px-1.5 py-0.5 rounded-md border border-yellow-500/20">
                  FUTURES
                </span>
              </div>
              <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${isLong ? 'bg-emerald-100 dark:bg-emerald-500/15 text-emerald-600 dark:text-emerald-400' : 'bg-rose-100 dark:bg-rose-500/15 text-rose-600 dark:text-rose-400'}`}>
                  {signal.direction}
                </span>
                <AssetClassBadge assetClass={signal.asset_class} />
                <span className="text-[10px] text-gray-400 bg-gray-100 dark:bg-gray-700/50 px-1.5 py-0.5 rounded">{signal.timeframe}</span>
                <span className="text-[10px] font-medium text-violet-600 dark:text-violet-400 bg-violet-100 dark:bg-violet-500/10 px-1.5 py-0.5 rounded">
                  {leverage}x
                </span>
                {isReversed && (
                  <span className="flex items-center gap-0.5 text-[10px] text-cyan-600 dark:text-cyan-400 bg-cyan-100 dark:bg-cyan-500/10 px-1.5 py-0.5 rounded">
                    <RefreshCw className="w-2.5 h-2.5" />REV
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${
              signal.status === 'ACTIVE' ? 'bg-emerald-100 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 animate-pulse' :
              signal.status === 'EXPIRED' ? 'bg-gray-100 dark:bg-gray-700 text-gray-500' :
              'bg-blue-100 dark:bg-blue-500/10 text-blue-600'
            }`}>
              {signal.status}
            </span>
            <div className="text-[10px] text-gray-400 mt-1 flex items-center gap-0.5 justify-end">
              <Clock className="w-2.5 h-2.5" />
              {signal.created_at && format(new Date(signal.created_at), 'MMM dd, HH:mm')}
            </div>
          </div>
        </div>

        <div className="mb-3">
          <div className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">Confidence</div>
          <ConfidenceBar value={signal.confidence} />
        </div>

        <div className="bg-gray-50 dark:bg-gray-900/40 rounded-lg p-3 mb-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Target className="w-3.5 h-3.5 text-gray-500" />
              <span className="text-xs text-gray-500 dark:text-gray-400">Entry</span>
            </div>
            <span className="font-mono text-sm font-bold text-gray-900 dark:text-white">${formatPrice(signal.entry)}</span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
              <span className="text-xs text-emerald-600 dark:text-emerald-400">Take Profit</span>
            </div>
            <span className="font-mono text-sm font-bold text-emerald-600 dark:text-emerald-400">${formatPrice(signal.tp)}</span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-rose-500" />
              <span className="text-xs text-rose-600 dark:text-rose-400">Stop Loss</span>
            </div>
            <span className="font-mono text-sm font-bold text-rose-600 dark:text-rose-400">${formatPrice(signal.sl)}</span>
          </div>
        </div>

        <div className="flex gap-2 mb-3">
          <MetricPill label="R/R" value={`1:${rr}`} />
          <MetricPill label="ROI" value={`+${roi}%`} color="text-emerald-600 dark:text-emerald-400" />
          <MetricPill label="Leverage" value={`${leverage}x`} color="text-violet-600 dark:text-violet-400" />
        </div>

        {signal.trading_type && (
          <div className="flex items-center gap-2 mb-3">
            <span className={`text-[10px] px-2 py-0.5 rounded-full ${
              signal.trading_type === 'SCALPING' ? 'bg-purple-100 dark:bg-purple-500/10 text-purple-600 dark:text-purple-400' :
              signal.trading_type === 'DAY' ? 'bg-yellow-100 dark:bg-yellow-500/10 text-yellow-700 dark:text-yellow-400' :
              'bg-indigo-100 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400'
            }`}>
              {signal.trading_type === 'SCALPING' ? 'Scalping' : signal.trading_type === 'DAY' ? 'Day Trade' : 'Swing Trade'}
            </span>
            {signal.estimated_duration_hours && (
              <span className="text-[10px] text-gray-400 flex items-center gap-0.5">
                <Clock className="w-2.5 h-2.5" />
                {signal.estimated_duration_hours < 1
                  ? `${Math.round(signal.estimated_duration_hours * 60)}m`
                  : signal.estimated_duration_hours < 24
                    ? `${Math.round(signal.estimated_duration_hours)}h`
                    : `${Math.round(signal.estimated_duration_hours / 24)}d`}
              </span>
            )}
          </div>
        )}

        <div className="flex gap-2">
          {tradingMode === 'paper' ? (
            <button
              onClick={handleCreatePaperTrade}
              disabled={isCreatingTrade || signal.status !== 'ACTIVE'}
              className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                isLong
                  ? 'bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white shadow-sm shadow-emerald-500/20'
                  : 'bg-gradient-to-r from-rose-500 to-rose-600 hover:from-rose-600 hover:to-rose-700 text-white shadow-sm shadow-rose-500/20'
              }`}
            >
              {isCreatingTrade ? 'Creating...' : 'Paper Trade'}
            </button>
          ) : (
            <a
              href={`https://www.binance.com/en/trade/${symbol}?type=futures`}
              target="_blank"
              rel="noopener noreferrer"
              className={`flex-1 flex items-center justify-center gap-1 py-2 rounded-lg text-xs font-semibold transition-all ${
                isLong
                  ? 'bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white'
                  : 'bg-gradient-to-r from-rose-500 to-rose-600 hover:from-rose-600 hover:to-rose-700 text-white'
              }`}
            >
              Trade <ExternalLink className="w-3 h-3" />
            </a>
          )}
          <Link
            to={`/spot-signals/${signal.id}`}
            className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium bg-gray-100 dark:bg-gray-700/50 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600/50 transition-colors"
          >
            Details <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>
    </div>
  );
};

export default FuturesSignalCard;
