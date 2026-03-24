import { Link } from 'react-router-dom';
import { useState } from 'react';
import { TrendingUp, TrendingDown, Clock, Target, ShieldAlert, Zap, BarChart3, ArrowRight } from 'lucide-react';
import usePaperTradeStore from '../../store/usePaperTradeStore';

const formatPrice = (price) => {
  if (!price) return 'N/A';
  const num = parseFloat(price);
  if (num >= 1000) return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (num >= 1) return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  return num.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 8 });
};

const formatTime = (dateString) => {
  if (!dateString) return '';
  const d = new Date(dateString);
  const now = new Date();
  const diff = (now - d) / 1000 / 60;
  if (diff < 1) return 'Just now';
  if (diff < 60) return `${Math.floor(diff)}m ago`;
  if (diff < 1440) return `${Math.floor(diff / 60)}h ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

const ConfidenceRing = ({ value }) => {
  const radius = 18;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;
  const color = value >= 80 ? '#22c55e' : value >= 70 ? '#eab308' : '#ef4444';

  return (
    <div className="relative w-12 h-12 flex-shrink-0">
      <svg className="w-12 h-12 -rotate-90" viewBox="0 0 44 44">
        <circle cx="22" cy="22" r={radius} fill="none" stroke="currentColor" strokeWidth="3" className="text-gray-200 dark:text-gray-700" />
        <circle cx="22" cy="22" r={radius} fill="none" stroke={color} strokeWidth="3" strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" className="transition-all duration-500" />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-gray-900 dark:text-white">
        {Math.round(value)}%
      </span>
    </div>
  );
};

const PriceRow = ({ label, price, icon: Icon, color }) => (
  <div className="flex items-center justify-between py-1.5">
    <div className="flex items-center gap-1.5">
      <Icon className={`w-3.5 h-3.5 ${color}`} />
      <span className="text-xs text-gray-500 dark:text-gray-400">{label}</span>
    </div>
    <span className={`font-mono text-sm font-semibold ${color}`}>${formatPrice(price)}</span>
  </div>
);

const SignalCard = ({ signal, tradingMode = 'paper' }) => {
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

  const direction = signal.direction || signal.signal_type;
  const entry = signal.entry || signal.entry_price;
  const sl = signal.sl || signal.stop_loss;
  const tp = signal.tp || signal.target_price;
  const symbol = signal.symbol_name || signal.symbol_detail?.symbol || signal.symbol;
  const confidence = signal.confidence ? (signal.confidence <= 1 ? signal.confidence * 100 : signal.confidence) : 0;
  const isLong = direction === 'LONG';
  const displayDirection = signal.market_type === 'FUTURES' ? direction : (isLong ? 'BUY' : 'SELL');

  const risk = entry && sl ? Math.abs(parseFloat(entry) - parseFloat(sl)) : 0;
  const reward = entry && tp ? Math.abs(parseFloat(tp) - parseFloat(entry)) : 0;
  const rr = risk > 0 ? (reward / risk).toFixed(1) : '0';

  const accentBorder = isLong ? 'border-l-emerald-500' : 'border-l-rose-500';
  const dirBg = isLong ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : 'bg-rose-500/10 text-rose-600 dark:text-rose-400';
  const DirIcon = isLong ? TrendingUp : TrendingDown;

  return (
    <div className={`relative bg-white dark:bg-gray-800/80 backdrop-blur-sm rounded-xl border border-gray-200/60 dark:border-gray-700/60 border-l-[3px] ${accentBorder} hover:shadow-lg hover:shadow-gray-200/50 dark:hover:shadow-gray-900/50 transition-all duration-300 group overflow-hidden`}>
      {signal.is_priority && (
        <div className="absolute top-0 right-0 w-16 h-16 overflow-hidden">
          <div className="absolute top-2 -right-4 w-20 bg-amber-500 text-white text-[9px] font-bold text-center py-0.5 rotate-45 shadow-sm">
            PRIORITY
          </div>
        </div>
      )}

      <div className="p-4">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className={`p-1.5 rounded-lg ${dirBg}`}>
              <DirIcon className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <h3 className="font-bold text-gray-900 dark:text-white text-base truncate">{symbol}</h3>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${dirBg}`}>
                  {displayDirection}
                </span>
                {signal.timeframe && (
                  <span className="text-[10px] text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-gray-700/50 px-1.5 py-0.5 rounded">
                    {signal.timeframe}
                  </span>
                )}
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                  signal.status === 'ACTIVE' ? 'bg-emerald-100 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' :
                  signal.status === 'EXPIRED' ? 'bg-gray-100 dark:bg-gray-700 text-gray-500' :
                  'bg-blue-100 dark:bg-blue-500/10 text-blue-600'
                }`}>
                  {signal.status}
                </span>
              </div>
            </div>
          </div>
          <ConfidenceRing value={confidence} />
        </div>

        <div className="bg-gray-50 dark:bg-gray-900/40 rounded-lg px-3 py-2 mb-3">
          <PriceRow label="Entry" price={entry} icon={Target} color="text-gray-700 dark:text-gray-300" />
          {tp && <PriceRow label="Take Profit" price={tp} icon={TrendingUp} color="text-emerald-600 dark:text-emerald-400" />}
          {sl && <PriceRow label="Stop Loss" price={sl} icon={ShieldAlert} color="text-rose-600 dark:text-rose-400" />}
        </div>

        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            {risk > 0 && (
              <div className="flex items-center gap-1">
                <BarChart3 className="w-3 h-3 text-blue-500" />
                <span className="text-[11px] text-gray-600 dark:text-gray-400">R/R <span className="font-semibold text-blue-600 dark:text-blue-400">1:{rr}</span></span>
              </div>
            )}
            {signal.trading_type && (
              <span className="text-[11px] text-gray-500 dark:text-gray-400">
                {signal.trading_type === 'SCALPING' ? 'Scalp' : signal.trading_type === 'DAY' ? 'Day' : 'Swing'}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1 text-[11px] text-gray-400">
            <Clock className="w-3 h-3" />
            {formatTime(signal.created_at)}
          </div>
        </div>

        <div className="flex gap-2">
          {tradingMode === 'paper' ? (
            <button
              onClick={handleCreatePaperTrade}
              disabled={isCreatingTrade || signal.status !== 'ACTIVE'}
              className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                isLong
                  ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                  : 'bg-rose-600 hover:bg-rose-700 text-white'
              }`}
            >
              {isCreatingTrade ? 'Creating...' : 'Paper Trade'}
            </button>
          ) : (
            <button
              disabled={signal.status !== 'ACTIVE'}
              className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all disabled:opacity-40 ${
                isLong ? 'bg-emerald-600 hover:bg-emerald-700 text-white' : 'bg-rose-600 hover:bg-rose-700 text-white'
              }`}
            >
              Live Trade
            </button>
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

export default SignalCard;
