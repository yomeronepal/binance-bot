import { TrendingUp, TrendingDown, Clock } from 'lucide-react';

const formatPrice = (price) => {
  if (price === null || price === undefined) return 'N/A';
  const n = parseFloat(price);
  if (Number.isNaN(n)) return 'N/A';
  if (n >= 1000) return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (n >= 1) return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  return n.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 8 });
};

const ConfidenceBar = ({ value }) => {
  const pct = (Number(value) || 0) * 100;
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

const MetricPill = ({ label, value, color = 'text-gray-900 dark:text-white' }) => (
  <div className="flex flex-col items-center p-2 bg-gray-50 dark:bg-gray-900/40 rounded-lg flex-1">
    <span className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wider">{label}</span>
    <span className={`text-sm font-bold ${color}`}>{value}</span>
  </div>
);

const DayTradeSignalCard = ({ signal }) => {
  const isLong = signal.direction === 'LONG';
  const entry = parseFloat(signal.entry);
  const risk = Math.abs(entry - parseFloat(signal.stop_loss));
  const reward = Math.abs(parseFloat(signal.tp2) - entry);
  const rr = risk > 0 ? (reward / risk).toFixed(1) : '0';

  const borderColor = isLong ? 'border-emerald-500/30' : 'border-rose-500/30';
  const accentGradient = isLong
    ? 'from-emerald-500/20 via-transparent to-transparent'
    : 'from-rose-500/20 via-transparent to-transparent';
  const DirIcon = isLong ? TrendingUp : TrendingDown;

  return (
    <div className={`relative bg-white dark:bg-gray-800/90 backdrop-blur-sm rounded-xl border ${borderColor} hover:shadow-xl transition-all duration-300 overflow-hidden group`}>
      <div className={`absolute inset-0 bg-gradient-to-br ${accentGradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none`} />
      <div className="relative p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-bold text-gray-900 dark:text-white truncate">{signal.symbol}</span>
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${isLong ? 'bg-emerald-500/20 text-emerald-500' : 'bg-rose-500/20 text-rose-500'}`}>
              <DirIcon className="w-3 h-3" />
              {signal.direction}
            </span>
            {signal.is_priority && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500 text-white animate-pulse">
                ⭐ PRIORITY
              </span>
            )}
          </div>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400">FUT</span>
        </div>

        <ConfidenceBar value={signal.confidence} />

        <div className="flex gap-2">
          <MetricPill label="Entry" value={formatPrice(signal.entry)} />
          <MetricPill label="Stop" value={formatPrice(signal.stop_loss)} color="text-rose-500" />
        </div>
        <div className="flex gap-2">
          <MetricPill label="TP1" value={formatPrice(signal.tp1)} color="text-emerald-500" />
          <MetricPill label="TP2" value={formatPrice(signal.tp2)} color="text-emerald-600" />
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-gray-200 dark:border-gray-700/50 text-xs">
          <span className="text-gray-500 dark:text-gray-400">Score <span className="font-semibold text-gray-900 dark:text-white">{Number(signal.score).toFixed(1)}</span></span>
          <span className="text-gray-500 dark:text-gray-400">R:R <span className="font-semibold text-gray-900 dark:text-white">1:{rr}</span></span>
          <span className="flex items-center gap-1 text-gray-500 dark:text-gray-400" title={signal.created_at}>
            <Clock className="w-3 h-3" />
            {signal.created_at ? new Date(signal.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default DayTradeSignalCard;
