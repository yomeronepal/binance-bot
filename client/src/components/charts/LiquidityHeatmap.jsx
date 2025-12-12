/**
 * Liquidity Heatmap Component
 * Displays order book depth with visual intensity for bid/ask walls
 */
import { useState, useEffect } from 'react';
import axios from 'axios';

const LiquidityHeatmap = ({ symbol }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

    useEffect(() => {
        const fetchOrderBook = async () => {
            if (!symbol) return;

            try {
                setLoading(true);
                // Clean symbol - remove USDT if present, API will add it
                const cleanSymbol = symbol.replace(/USDT$/i, '').toUpperCase();
                const response = await axios.get(`${baseURL}/market/orderbook/${cleanSymbol}/`);
                setData(response.data);
                setError(null);
            } catch (err) {
                console.error('Error fetching order book:', err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchOrderBook();
        // Refresh every 10 seconds
        const interval = setInterval(fetchOrderBook, 10000);
        return () => clearInterval(interval);
    }, [symbol, baseURL]);

    if (loading && !data) {
        return (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">📊 Liquidity Heatmap</h2>
                <div className="flex items-center justify-center h-64">
                    <div className="animate-pulse text-gray-400">Loading order book...</div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">📊 Liquidity Heatmap</h2>
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-center text-red-400">
                    Failed to load: {error}
                </div>
            </div>
        );
    }

    const { bids = [], asks = [], summary = {}, current_price = 0, walls = {} } = data || {};

    // Get max volume for scaling
    const maxBidQty = Math.max(...bids.map(b => b.quantity), 0);
    const maxAskQty = Math.max(...asks.map(a => a.quantity), 0);
    const maxQty = Math.max(maxBidQty, maxAskQty);

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-4 sm:p-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                    📊 Liquidity Heatmap
                </h2>
                <div className="flex items-center gap-4 text-sm">
                    <div className="flex items-center gap-2">
                        <span className="text-gray-500 dark:text-gray-400">Bid/Ask Ratio:</span>
                        <span className={`font-bold ${summary.bid_ask_ratio > 1 ? 'text-green-500' : 'text-red-500'}`}>
                            {summary.bid_ask_ratio?.toFixed(2) || '0.00'}
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-gray-500 dark:text-gray-400">Current:</span>
                        <span className="font-bold text-gray-900 dark:text-white">${current_price?.toFixed(4)}</span>
                    </div>
                </div>
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                    <div className="text-xs text-green-400">Total Bid Volume</div>
                    <div className="text-lg font-bold text-green-500">{summary.total_bid_volume?.toFixed(2) || 0}</div>
                </div>
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                    <div className="text-xs text-red-400">Total Ask Volume</div>
                    <div className="text-lg font-bold text-red-500">{summary.total_ask_volume?.toFixed(2) || 0}</div>
                </div>
                <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                    <div className="text-xs text-green-400">Bid Walls</div>
                    <div className="text-lg font-bold text-green-500">{summary.bid_walls || 0}</div>
                </div>
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                    <div className="text-xs text-red-400">Ask Walls</div>
                    <div className="text-lg font-bold text-red-500">{summary.ask_walls || 0}</div>
                </div>
            </div>

            {/* Heatmap Visualization */}
            <div className="grid grid-cols-2 gap-4">
                {/* Bids (Buy Orders) */}
                <div>
                    <h3 className="text-sm font-semibold text-green-500 mb-2">Buy Orders (Bids)</h3>
                    <div className="space-y-1 max-h-64 overflow-y-auto">
                        {bids.slice(0, 20).map((bid, i) => (
                            <div key={i} className="relative flex items-center gap-2 text-xs">
                                {/* Intensity bar */}
                                <div
                                    className="absolute left-0 h-full bg-green-500/30 rounded"
                                    style={{ width: `${(bid.quantity / maxQty) * 100}%` }}
                                />
                                <div className="relative z-10 flex items-center justify-between w-full px-2 py-1">
                                    <span className="font-mono text-green-600 dark:text-green-400">${bid.price.toFixed(4)}</span>
                                    <span className={`font-mono ${bid.intensity > 0.5 ? 'text-green-500 font-bold' : 'text-gray-500 dark:text-gray-400'}`}>
                                        {bid.quantity.toFixed(4)}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Asks (Sell Orders) */}
                <div>
                    <h3 className="text-sm font-semibold text-red-500 mb-2">Sell Orders (Asks)</h3>
                    <div className="space-y-1 max-h-64 overflow-y-auto">
                        {asks.slice(0, 20).map((ask, i) => (
                            <div key={i} className="relative flex items-center gap-2 text-xs">
                                {/* Intensity bar */}
                                <div
                                    className="absolute right-0 h-full bg-red-500/30 rounded"
                                    style={{ width: `${(ask.quantity / maxQty) * 100}%` }}
                                />
                                <div className="relative z-10 flex items-center justify-between w-full px-2 py-1">
                                    <span className="font-mono text-red-600 dark:text-red-400">${ask.price.toFixed(4)}</span>
                                    <span className={`font-mono ${ask.intensity > 0.5 ? 'text-red-500 font-bold' : 'text-gray-500 dark:text-gray-400'}`}>
                                        {ask.quantity.toFixed(4)}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Significant Walls */}
            {(walls.bids?.length > 0 || walls.asks?.length > 0) && (
                <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">🧱 Significant Walls</h3>
                    <div className="grid grid-cols-2 gap-4 text-xs">
                        {walls.bids?.length > 0 && (
                            <div>
                                <span className="text-green-500 font-medium">Buy Walls:</span>
                                <div className="mt-1 space-y-1">
                                    {walls.bids.slice(0, 3).map((w, i) => (
                                        <div key={i} className="flex justify-between bg-green-500/10 rounded px-2 py-1">
                                            <span className="font-mono">${w.price.toFixed(4)}</span>
                                            <span className="font-bold">{w.quantity.toFixed(2)}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        {walls.asks?.length > 0 && (
                            <div>
                                <span className="text-red-500 font-medium">Sell Walls:</span>
                                <div className="mt-1 space-y-1">
                                    {walls.asks.slice(0, 3).map((w, i) => (
                                        <div key={i} className="flex justify-between bg-red-500/10 rounded px-2 py-1">
                                            <span className="font-mono">${w.price.toFixed(4)}</span>
                                            <span className="font-bold">{w.quantity.toFixed(2)}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Legend */}
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-1">
                        <div className="w-3 h-3 bg-green-500/50 rounded"></div>
                        <span>Strong buy support</span>
                    </div>
                    <div className="flex items-center gap-1">
                        <div className="w-3 h-3 bg-red-500/50 rounded"></div>
                        <span>Strong sell resistance</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default LiquidityHeatmap;
