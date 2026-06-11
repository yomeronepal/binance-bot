/**
 * MacroFilterWidget — live readout of BTC's daily regime and the macro
 * filter's resulting LONG / SHORT decisions.
 *
 * The same widget renders on the Dashboard (passive overview) and on the
 * Bot Performance page (alongside the Macro Allowed / Macro Blocked
 * filter tabs). Auto-refreshes every 60 s; the backend caches the
 * underlying snapshot for 5 min, so polling cost is negligible.
 *
 * Props:
 *   variant   'compact' | 'full'  — full shows EMAs and 3d/7d returns;
 *                                   compact drops them for tight spaces.
 *                                   Defaults to 'full'.
 *   className extra wrapper classes for layout (margins, spans, etc.)
 */
import { useEffect, useState } from 'react';
import axios from 'axios';
import { Bitcoin } from 'lucide-react';

export default function MacroFilterWidget({ variant = 'full', className = '' }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
    let alive = true;
    const fetchStatus = async () => {
      try {
        const res = await axios.get(`${baseURL}/public/macro-status/`);
        if (alive) {
          setStatus(res.data);
          setError(null);
        }
      } catch (err) {
        if (alive) setError(err?.message || 'fetch failed');
      }
    };
    fetchStatus();
    const id = setInterval(fetchStatus, 60_000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (error && !status) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-xl px-3 py-2 shadow-sm border border-gray-100 dark:border-gray-700 text-sm text-gray-500 dark:text-gray-400 ${className}`}>
        BTC regime — unavailable
      </div>
    );
  }
  if (!status) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-xl px-3 py-2 shadow-sm border border-gray-100 dark:border-gray-700 text-sm text-gray-500 dark:text-gray-400 ${className}`}>
        Loading BTC regime…
      </div>
    );
  }

  const snap = status.snapshot;
  const longDecision = status.long?.decision;
  const shortDecision = status.short?.decision;

  const fmtPct = (v) => `${v >= 0 ? '+' : ''}${(v ?? 0).toFixed(2)}%`;

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-xl px-3 py-2 shadow-sm border border-gray-100 dark:border-gray-700 flex items-center gap-3 flex-wrap text-sm ${className}`}>
      <div className="flex items-center gap-2 text-gray-700 dark:text-gray-200">
        <Bitcoin className="w-4 h-4 text-amber-500" />
        <span className="font-medium">BTC regime</span>
      </div>

      {snap ? (
        <>
          <span className="text-gray-600 dark:text-gray-400">
            ${snap.close?.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </span>
          {variant === 'full' && (
            <>
              <span
                className={`px-2 py-0.5 rounded text-xs font-medium ${
                  snap.above_ema7
                    ? 'bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                    : 'bg-rose-100 dark:bg-rose-500/15 text-rose-700 dark:text-rose-300'
                }`}
              >
                {snap.above_ema7 ? '↑' : '↓'} EMA7
              </span>
              <span
                className={`px-2 py-0.5 rounded text-xs font-medium ${
                  snap.above_ema20
                    ? 'bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                    : 'bg-rose-100 dark:bg-rose-500/15 text-rose-700 dark:text-rose-300'
                }`}
              >
                {snap.above_ema20 ? '↑' : '↓'} EMA20
              </span>
              <span className="text-gray-600 dark:text-gray-400">3d {fmtPct(snap.ret_3d)}</span>
              <span className="text-gray-600 dark:text-gray-400">7d {fmtPct(snap.ret_7d)}</span>
            </>
          )}
        </>
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
