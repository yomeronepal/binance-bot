/**
 * CommodityMacroFilterWidget — live readout of GLD's daily regime
 * (with CL shown alongside for energy-name context) and the
 * commodity macro filter's resulting LONG / SHORT decisions for
 * COMMODITY-class signals.
 *
 * Symmetric to MacroFilterWidget (BTC, crypto) and
 * EquityMacroFilterWidget (SPY/QQQ, stocks). Auto-refreshes every 60s;
 * the backend caches the underlying snapshot for 5min.
 *
 * Props:
 *   variant   'compact' | 'full' — full shows EMA flags and 3d/7d.
 *   className extra wrapper classes for layout.
 */
import { useState } from 'react';
import axios from 'axios';
import { Gem } from 'lucide-react';
import { usePolling } from '../../hooks/usePolling';

const fmtPct = (v) => `${v >= 0 ? '+' : ''}${(v ?? 0).toFixed(2)}%`;

const Pill = ({ on, label }) => (
  <span
    className={`px-2 py-0.5 rounded text-xs font-medium ${
      on
        ? 'bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
        : 'bg-rose-100 dark:bg-rose-500/15 text-rose-700 dark:text-rose-300'
    }`}
  >
    {on ? '↑' : '↓'} {label}
  </span>
);

const Leg = ({ name, leg }) => {
  if (!leg) {
    return (
      <span className="text-gray-500 dark:text-gray-400 italic text-xs">
        {name}: unavailable
      </span>
    );
  }
  return (
    <span className="flex items-center gap-2 flex-wrap">
      <span className="text-gray-500 dark:text-gray-400 text-xs font-medium">{name}</span>
      <span className="text-gray-600 dark:text-gray-400">
        ${leg.close?.toLocaleString(undefined, { maximumFractionDigits: 2 })}
      </span>
      <Pill on={leg.above_ema7} label="EMA7" />
      <Pill on={leg.above_ema20} label="EMA20" />
      <span className="text-gray-600 dark:text-gray-400">3d {fmtPct(leg.ret_3d)}</span>
      <span className="text-gray-600 dark:text-gray-400">7d {fmtPct(leg.ret_7d)}</span>
    </span>
  );
};

export default function CommodityMacroFilterWidget({ variant = 'full', className = '' }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  usePolling(async () => {
    const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
    try {
      const res = await axios.get(`${baseURL}/public/commodity-macro-status/`);
      setStatus(res.data);
      setError(null);
    } catch (err) {
      setError(err?.message || 'fetch failed');
    }
  }, 60_000);

  if (error && !status) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-xl px-3 py-2 shadow-sm border border-gray-100 dark:border-gray-700 text-sm text-gray-500 dark:text-gray-400 ${className}`}>
        Commodity regime — unavailable
      </div>
    );
  }
  if (!status) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-xl px-3 py-2 shadow-sm border border-gray-100 dark:border-gray-700 text-sm text-gray-500 dark:text-gray-400 ${className}`}>
        Loading commodity regime…
      </div>
    );
  }

  const snap = status.snapshot;
  const longDecision = status.long?.decision;
  const shortDecision = status.short?.decision;

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-xl px-3 py-2 shadow-sm border border-gray-100 dark:border-gray-700 flex items-center gap-3 flex-wrap text-sm ${className}`}>
      <div className="flex items-center gap-2 text-gray-700 dark:text-gray-200">
        <Gem className="w-4 h-4 text-yellow-500" />
        <span className="font-medium">Commodity regime</span>
      </div>

      {snap ? (
        <div className="flex items-center gap-4 flex-wrap">
          <Leg name="XAU" leg={snap.gold} />
          {variant === 'full' && <Leg name="CL" leg={snap.oil} />}
        </div>
      ) : (
        <span className="text-gray-500 dark:text-gray-400 italic">snapshot unavailable</span>
      )}

      <span className="ml-auto flex items-center gap-2">
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
            longDecision === 'ALLOW'
              ? 'bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
              : 'bg-rose-100 dark:bg-rose-500/15 text-rose-700 dark:text-rose-300'
          }`}
          title={status.long?.reason}
        >
          LONG: {longDecision}
        </span>
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
            shortDecision === 'ALLOW'
              ? 'bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
              : 'bg-rose-100 dark:bg-rose-500/15 text-rose-700 dark:text-rose-300'
          }`}
          title={status.short?.reason}
        >
          SHORT: {shortDecision}
        </span>
      </span>
    </div>
  );
}
