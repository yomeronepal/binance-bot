/**
 * FuturesBalanceCard — Binance USDT futures wallet balance read from
 * FuturesTradingSettings.total_trading_capital.
 *
 * The value is refreshed by the monthly rebalance task
 * (signals.monthly_balance_rebalance) and by the manual
 * ``manage.py rebalance_now`` command. There is no live polling here
 * — the field is the source of truth for the displayed balance, and
 * the "as of" timestamp tells the viewer how stale that is.
 *
 * The admin-only /api/futures/balance/ endpoint is still available
 * if you want a real-time read; it just isn't used here.
 */
import { useEffect, useState } from 'react';
import { Wallet } from 'lucide-react';
import api from '../../services/api';

const fmtUsd = (v) => {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  const n = Number(v);
  const sign = n < 0 ? '-' : '';
  return `${sign}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
};

const fmtTimestamp = (iso) => {
  if (!iso) return 'never';
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return 'unknown';
  }
};

export default function FuturesBalanceCard() {
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    const fetchSettings = async () => {
      try {
        const res = await api.get('/futures/settings/');
        if (alive) {
          setSettings(res.data);
          setError(null);
        }
      } catch (err) {
        if (alive) setError(err?.response?.data?.detail || err?.message || 'fetch failed');
      }
    };
    fetchSettings();
    const id = setInterval(fetchSettings, 60_000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const balance = settings?.total_trading_capital;
  const perTrade = settings?.trade_amount;
  const maxConcurrent = settings?.max_concurrent_trades;
  const updatedAt = settings?.last_balance_updated_at;

  const balanceNum = balance === null || balance === undefined ? null : Number(balance);
  const perTradeNum = perTrade === null || perTrade === undefined ? null : Number(perTrade);
  const backupReserve =
    balanceNum !== null && perTradeNum !== null && maxConcurrent
      ? balanceNum - perTradeNum * maxConcurrent
      : null;

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow px-4 py-4 sm:px-6 sm:py-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-gray-700 dark:text-gray-200">
          <Wallet className="w-5 h-5 text-amber-500" />
          <span className="font-medium">Binance Futures Wallet</span>
        </div>
        <span className="text-xs text-gray-500 dark:text-gray-400" title={updatedAt || ''}>
          {error
            ? <span className="text-rose-600 dark:text-rose-400">{error}</span>
            : `as of ${fmtTimestamp(updatedAt)}`}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <div className="text-xs uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Wallet Balance
          </div>
          <div className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">
            {fmtUsd(balanceNum)}
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Per Trade × Slots
          </div>
          <div className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">
            {perTradeNum !== null && maxConcurrent
              ? `${fmtUsd(perTradeNum)} × ${maxConcurrent}`
              : '—'}
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Backup Reserve
          </div>
          <div className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">
            {fmtUsd(backupReserve)}
          </div>
        </div>
      </div>
    </div>
  );
}
