import { useState } from 'react';

const FearGreedWidget = ({ data }) => {
  const [expanded, setExpanded] = useState(false);
  const value = data.value;
  const classification = data.classification;
  const enabled = data.enabled;
  const components = data.components || {};
  const impact = data.trading_impact || {};
  const source = data.source || 'unknown';

  const getColor = (val) => {
    if (val <= 24) return { bg: '#ef4444', text: 'text-red-500', bar: 'bg-red-500', border: 'border-red-300 dark:border-red-500/30', light: 'bg-red-50 dark:bg-red-500/10' };
    if (val <= 44) return { bg: '#f97316', text: 'text-orange-500', bar: 'bg-orange-500', border: 'border-orange-300 dark:border-orange-500/30', light: 'bg-orange-50 dark:bg-orange-500/10' };
    if (val <= 55) return { bg: '#eab308', text: 'text-yellow-500', bar: 'bg-yellow-500', border: 'border-yellow-300 dark:border-yellow-500/30', light: 'bg-yellow-50 dark:bg-yellow-500/10' };
    if (val <= 74) return { bg: '#84cc16', text: 'text-lime-500', bar: 'bg-lime-500', border: 'border-lime-300 dark:border-lime-500/30', light: 'bg-lime-50 dark:bg-lime-500/10' };
    return { bg: '#22c55e', text: 'text-green-500', bar: 'bg-green-500', border: 'border-green-300 dark:border-green-500/30', light: 'bg-green-50 dark:bg-green-500/10' };
  };

  const colors = getColor(value);

  return (
    <div
      className={`rounded-xl border ${colors.border} ${colors.light} p-4 cursor-pointer transition-all hover:shadow-md`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex items-center gap-4 flex-1">
          <div className="flex-shrink-0 text-center" style={{ minWidth: '70px' }}>
            <div className={`text-4xl font-black ${colors.text}`}>{value}</div>
            <div className={`text-xs font-semibold mt-0.5 ${colors.text}`}>{classification}</div>
          </div>

          <div className="flex-1">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">Fear & Greed Index</span>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-gray-400">{source}</span>
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                  enabled
                    ? 'bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400'
                    : 'bg-gray-100 dark:bg-gray-600/30 text-gray-500 dark:text-gray-400'
                }`}>
                  {enabled ? 'Filter Active' : 'Filter Off'}
                </span>
              </div>
            </div>

            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3.5 overflow-hidden shadow-inner">
              <div
                className={`h-full rounded-full transition-all duration-1000 ease-out ${colors.bar}`}
                style={{ width: `${value}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-gray-400 mt-1 px-0.5">
              <span>0 Extreme Fear</span>
              <span>50 Neutral</span>
              <span>100 Extreme Greed</span>
            </div>
          </div>
        </div>

        <div className="flex gap-2 flex-shrink-0">
          <div className={`px-3 py-2 rounded-lg border text-center ${
            impact.long_allowed
              ? 'bg-green-50 dark:bg-green-500/10 border-green-300 dark:border-green-500/30 text-green-700 dark:text-green-400'
              : 'bg-red-50 dark:bg-red-500/10 border-red-300 dark:border-red-500/30 text-red-700 dark:text-red-400'
          }`}>
            <div className="font-bold text-sm">LONG</div>
            <div className="text-xs">{impact.long_allowed ? 'Allowed' : 'Blocked'}</div>
          </div>
          <div className={`px-3 py-2 rounded-lg border text-center ${
            impact.short_allowed
              ? 'bg-green-50 dark:bg-green-500/10 border-green-300 dark:border-green-500/30 text-green-700 dark:text-green-400'
              : 'bg-red-50 dark:bg-red-500/10 border-red-300 dark:border-red-500/30 text-red-700 dark:text-red-400'
          }`}>
            <div className="font-bold text-sm">SHORT</div>
            <div className="text-xs">{impact.short_allowed ? 'Allowed' : 'Blocked'}</div>
          </div>
        </div>
      </div>

      {expanded && Object.keys(components).length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 grid grid-cols-2 sm:grid-cols-4 gap-2">
          {Object.entries(components).map(([key, comp]) => (
            <div key={key} className="bg-white dark:bg-gray-800/50 rounded-lg px-3 py-2 shadow-sm">
              <div className="text-[10px] text-gray-400 uppercase tracking-wide">{key.replace(/_/g, ' ')}</div>
              <div className="font-mono text-sm font-semibold text-gray-800 dark:text-gray-200">
                {comp.raw}
              </div>
              <div className="text-[10px] text-gray-400">score: {comp.score}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FearGreedWidget;
