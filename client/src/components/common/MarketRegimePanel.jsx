/**
 * MarketRegimePanel — collapsible container for the macro-regime readouts
 * (BTC / equity / commodity filters, plus an optional Fear & Greed widget).
 *
 * Groups the otherwise-stacked widgets under one toggle so they don't
 * dominate a page, while still showing the full data when expanded. The
 * open/closed choice is persisted to localStorage.
 *
 * Props:
 *   fearGreed   optional Fear & Greed payload; rendered inside when available
 *   storageKey  localStorage key for the open/closed state (shared by default)
 *   className   extra wrapper classes
 */
import { useState } from 'react';
import { Activity, ChevronDown } from 'lucide-react';
import { usePolling } from '../../hooks/usePolling';
import FearGreedWidget from './FearGreedWidget';
import MacroFilterWidget from './MacroFilterWidget';
import EquityMacroFilterWidget from './EquityMacroFilterWidget';
import CommodityMacroFilterWidget from './CommodityMacroFilterWidget';

export default function MarketRegimePanel({
  fearGreed = null,
  storageKey = 'market_regime_open',
  className = '',
}) {
  const [open, setOpen] = useState(
    () => localStorage.getItem(storageKey) !== 'false'
  );

  // Self-fetch Fear & Greed when a parent doesn't supply it (e.g. Bot
  // Performance), so the panel shows the same data everywhere. When a
  // parent passes `fearGreed` (Dashboard), skip the extra request.
  const [internalFearGreed, setInternalFearGreed] = useState(null);
  usePolling(
    async () => {
      try {
        const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
        const res = await fetch(`${API_BASE}/futures/fear-greed/`);
        if (res.ok) setInternalFearGreed(await res.json());
      } catch (error) {
        console.debug('F&G fetch skipped:', error.message);
      }
    },
    60000,
    fearGreed == null
  );
  const fg = fearGreed ?? internalFearGreed;

  const toggle = () => {
    setOpen((prev) => {
      const next = !prev;
      localStorage.setItem(storageKey, String(next));
      return next;
    });
  };

  return (
    <div
      className={`bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 ${className}`}
    >
      <button
        onClick={toggle}
        aria-expanded={open}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-200">
          <Activity className="w-4 h-4 text-primary-500" />
          Market Regime
        </span>
        <ChevronDown
          className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-3">
          {fg && fg.available && <FearGreedWidget data={fg} />}
          <MacroFilterWidget />
          <EquityMacroFilterWidget />
          <CommodityMacroFilterWidget />
        </div>
      )}
    </div>
  );
}
