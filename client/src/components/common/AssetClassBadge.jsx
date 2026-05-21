/**
 * AssetClassBadge — tiny chip that shows CRYPTO / STOCK / COMMODITY
 * next to a signal or paper-trade symbol.
 *
 * Tolerates missing/legacy data: rows from before the asset_class
 * field landed return null instead of rendering a fallback chip,
 * because guessing the class from the symbol string in the UI
 * would diverge from whatever the backend classifier produced.
 *
 * Props:
 *   assetClass  'CRYPTO' | 'STOCK' | 'COMMODITY' | undefined
 *   className   extra wrapper classes for layout
 */
import { Bitcoin, LineChart, Gem } from 'lucide-react';

const renderCrypto = () => (
  <>
    <Bitcoin className="w-3 h-3" />
    Crypto
  </>
);
const renderStock = () => (
  <>
    <LineChart className="w-3 h-3" />
    Stock
  </>
);
const renderCommodity = () => (
  <>
    <Gem className="w-3 h-3" />
    Commodity
  </>
);

const VARIANTS = {
  CRYPTO: {
    label: 'Crypto',
    classes: 'bg-amber-100 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300',
    render: renderCrypto,
  },
  STOCK: {
    label: 'Stock',
    classes: 'bg-sky-100 dark:bg-sky-500/15 text-sky-700 dark:text-sky-300',
    render: renderStock,
  },
  COMMODITY: {
    label: 'Commodity',
    classes: 'bg-yellow-100 dark:bg-yellow-500/15 text-yellow-700 dark:text-yellow-300',
    render: renderCommodity,
  },
};

export default function AssetClassBadge({ assetClass, className = '' }) {
  if (!assetClass) return null;
  const variant = VARIANTS[String(assetClass).toUpperCase()];
  if (!variant) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${variant.classes} ${className}`}
      title={`Asset class: ${variant.label}`}
    >
      {variant.render()}
    </span>
  );
}
