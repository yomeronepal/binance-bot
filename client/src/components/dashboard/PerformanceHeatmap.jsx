/**
 * Performance Heatmap Component
 * Visual heatmap showing performance across symbols and time periods
 */
import { useState } from 'react';

const PerformanceHeatmap = ({ data }) => {
  const [hoveredCell, setHoveredCell] = useState(null);

  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500">
        No data available
      </div>
    );
  }

  // Get color based on performance value
  const getColor = (value) => {
    if (value === null || value === undefined) return '#1f2937'; // gray-800

    const intensity = Math.min(Math.abs(value) / 30, 1); // Normalize to 0-1

    if (value > 0) {
      // Green shades for positive
      const r = Math.round(16 + (34 - 16) * (1 - intensity));
      const g = Math.round(185 + (239 - 185) * intensity);
      const b = Math.round(129 + (68 - 129) * (1 - intensity));
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      // Red shades for negative
      const r = Math.round(239);
      const g = Math.round(68 + (185 - 68) * (1 - intensity));
      const b = Math.round(68 + (129 - 68) * (1 - intensity));
      return `rgb(${r}, ${g}, ${b})`;
    }
  };

  return (
    <div className="relative">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="text-left text-xs text-gray-400 font-medium p-2">Symbol</th>
              {data[0].periods.map((period) => (
                <th key={period.name} className="text-center text-xs text-gray-400 font-medium p-2">
                  {period.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.symbol}>
                <td className="text-sm text-white font-medium p-2">{row.symbol}</td>
                {row.periods.map((cell, idx) => (
                  <td
                    key={idx}
                    className="relative p-0"
                    onMouseEnter={() => setHoveredCell({ symbol: row.symbol, ...cell })}
                    onMouseLeave={() => setHoveredCell(null)}
                  >
                    <div
                      className="h-12 flex items-center justify-center text-xs font-medium transition-all duration-200 cursor-pointer hover:opacity-80"
                      style={{ backgroundColor: getColor(cell.value) }}
                    >
                      {cell.value !== null && cell.value !== undefined
                        ? `${cell.value > 0 ? '+' : ''}${cell.value.toFixed(1)}%`
                        : '-'}
                    </div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Tooltip */}
      {hoveredCell && (
        <div className="absolute top-0 left-1/2 transform -translate-x-1/2 -translate-y-full mb-2 bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-lg z-10">
          <p className="text-white font-medium mb-2">{hoveredCell.symbol} - {hoveredCell.name}</p>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between gap-4">
              <span className="text-gray-400">Return:</span>
              <span className={`font-medium ${hoveredCell.value >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {hoveredCell.value >= 0 ? '+' : ''}{hoveredCell.value.toFixed(2)}%
              </span>
            </div>
            {hoveredCell.trades && (
              <div className="flex justify-between gap-4">
                <span className="text-gray-400">Trades:</span>
                <span className="text-white font-medium">{hoveredCell.trades}</span>
              </div>
            )}
            {hoveredCell.winRate !== undefined && (
              <div className="flex justify-between gap-4">
                <span className="text-gray-400">Win Rate:</span>
                <span className="text-blue-400 font-medium">{hoveredCell.winRate.toFixed(1)}%</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-4 flex items-center justify-center gap-2">
        <span className="text-xs text-gray-400">Performance:</span>
        <div className="flex items-center gap-1">
          <div className="w-8 h-4 rounded" style={{ backgroundColor: getColor(-20) }}></div>
          <div className="w-8 h-4 rounded" style={{ backgroundColor: getColor(-10) }}></div>
          <div className="w-8 h-4 rounded" style={{ backgroundColor: getColor(0) }}></div>
          <div className="w-8 h-4 rounded" style={{ backgroundColor: getColor(10) }}></div>
          <div className="w-8 h-4 rounded" style={{ backgroundColor: getColor(20) }}></div>
        </div>
        <span className="text-xs text-gray-400">(-20% to +20%)</span>
      </div>
    </div>
  );
};

export default PerformanceHeatmap;
