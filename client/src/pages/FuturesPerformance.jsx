
import React, { useEffect, useState } from 'react';
import { Bot, TrendingUp, TrendingDown, Target, BarChart3, Clock, DollarSign, Activity, X, Settings, Power, Calendar } from 'lucide-react';
import axios from 'axios';

const FuturesPerformance = () => {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [summary, setSummary] = useState(null);
    const [openPositions, setOpenPositions] = useState([]);
    const [trades, setTrades] = useState([]);
    const [activeTab, setActiveTab] = useState('overview');
    const [closingTrades, setClosingTrades] = useState({});
    const [showSettings, setShowSettings] = useState(false);
    const [settings, setSettings] = useState(null);
    const [savingSettings, setSavingSettings] = useState(false);

    const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

    const fetchData = async () => {
        try {
            setLoading(true);

            // Fetch summary with statistics
            const summaryRes = await axios.get(`${baseURL}/futures/summary/`);
            setSummary(summaryRes.data);
            setSettings(summaryRes.data.settings);

            // Fetch open positions
            const positionsRes = await axios.get(`${baseURL}/futures/positions/`);
            setOpenPositions(positionsRes.data || []);

            // Fetch trade history
            const tradesRes = await axios.get(`${baseURL}/futures/trades/?limit=50`);
            setTrades(tradesRes.data || []);

            setError(null);
        } catch (err) {
            console.error('Error fetching futures performance:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const toggleTrading = async () => {
        try {
            const newState = !settings?.is_enabled;
            await axios.post(`${baseURL}/futures/toggle/`, { enabled: newState });
            setSettings(prev => ({ ...prev, is_enabled: newState }));
        } catch (err) {
            alert(`Failed to toggle trading: ${err.message}`);
        }
    };

    const updateSettings = async (newSettings) => {
        try {
            setSavingSettings(true);
            await axios.patch(`${baseURL}/futures/settings/`, newSettings);
            setSettings(prev => ({ ...prev, ...newSettings }));
            setShowSettings(false);
        } catch (err) {
            alert(`Failed to update settings: ${err.message}`);
        } finally {
            setSavingSettings(false);
        }
    };

    const closeTrade = async (tradeId) => {
        const confirmed = window.confirm('Are you sure you want to close this position?');
        if (!confirmed) return;

        try {
            setClosingTrades(prev => ({ ...prev, [tradeId]: true }));
            await axios.post(`${baseURL}/futures/trades/${tradeId}/close/`);
            await fetchData();
        } catch (err) {
            alert(`Failed to close trade: ${err.response?.data?.error || err.message}`);
        } finally {
            setClosingTrades(prev => ({ ...prev, [tradeId]: false }));
        }
    };

    useEffect(() => {
        fetchData();
        // Auto-refresh every 30 seconds
        const interval = setInterval(fetchData, 30000);
        return () => clearInterval(interval);
    }, []);

    if (loading && !summary) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 flex items-center justify-center">
                <div className="text-center">
                    <Activity className="w-12 h-12 text-purple-400 animate-pulse mx-auto mb-4" />
                    <p className="text-gray-400">Loading futures performance...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6">
                <div className="max-w-7xl mx-auto">
                    <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-8 text-center">
                        <p className="text-red-400">Failed to load futures performance: {error}</p>
                        <button onClick={fetchData} className="mt-4 px-4 py-2 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30">
                            Retry
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    const stats = summary?.statistics || {};
    const totalPnl = parseFloat(stats.total_pnl || 0);
    const winRate = parseFloat(stats.win_rate || 0);
    const totalTrades = parseInt(stats.total_trades || 0);
    const winningTrades = parseInt(stats.winning_trades || 0);
    const losingTrades = parseInt(stats.losing_trades || 0);
    const openCount = parseInt(stats.open_positions || 0);

    const statCards = [
        {
            label: 'Total P/L',
            value: `${totalPnl >= 0 ? '+' : ''}$${Math.abs(totalPnl).toFixed(2)}`,
            subtext: `From ${totalTrades} closed trades`,
            icon: DollarSign,
            color: totalPnl >= 0 ? 'text-green-400' : 'text-red-400',
            bgGradient: totalPnl >= 0 ? 'from-green-500/20 to-green-600/10' : 'from-red-500/20 to-red-600/10',
        },
        {
            label: 'Win Rate',
            value: `${winRate.toFixed(1)}%`,
            subtext: `${winningTrades}W / ${losingTrades}L`,
            icon: Target,
            color: winRate >= 50 ? 'text-green-400' : 'text-red-400',
            bgGradient: 'from-blue-500/20 to-purple-600/10',
        },
        {
            label: 'Open Positions',
            value: openCount,
            subtext: `Max: ${settings?.max_concurrent_trades || 1}`,
            icon: Activity,
            color: 'text-purple-400',
            bgGradient: 'from-purple-500/20 to-pink-600/10',
        },
        {
            label: 'Position Size',
            value: `$${settings?.trade_amount || 0}`,
            subtext: `${settings?.leverage || 10}x leverage`,
            icon: BarChart3,
            color: 'text-blue-400',
            bgGradient: 'from-blue-500/20 to-cyan-600/10',
        },
    ];

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-4 sm:p-6">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-lg border border-purple-500/50">
                                <Bot className="w-8 h-8 text-purple-400" />
                            </div>
                            <div>
                                <h1 className="text-2xl sm:text-3xl font-bold text-white">Futures Trading Performance</h1>
                                <p className="text-gray-400 text-sm sm:text-base">Real Binance futures trades monitoring</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            {/* Trading Toggle */}
                            <button
                                onClick={toggleTrading}
                                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${settings?.is_enabled
                                    ? 'bg-green-500/20 border border-green-500/50 text-green-400 hover:bg-green-500/30'
                                    : 'bg-red-500/20 border border-red-500/50 text-red-400 hover:bg-red-500/30'
                                    }`}
                            >
                                <Power className="w-4 h-4" />
                                {settings?.is_enabled ? 'Trading ON' : 'Trading OFF'}
                            </button>
                            {/* Settings Button */}
                            <button
                                onClick={() => setShowSettings(true)}
                                className="p-2 bg-gray-700 rounded-lg hover:bg-gray-600 transition-colors"
                            >
                                <Settings className="w-5 h-5 text-gray-300" />
                            </button>
                            {/* Refresh */}
                            <button
                                onClick={fetchData}
                                disabled={loading}
                                className="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 disabled:opacity-50 transition-colors"
                            >
                                {loading ? 'Refreshing...' : 'Refresh'}
                            </button>
                        </div>
                    </div>

                    {/* Status Banner */}
                    <div className={`rounded-lg border p-4 ${settings?.is_enabled
                        ? 'bg-green-500/10 border-green-500/30'
                        : 'bg-yellow-500/10 border-yellow-500/30'
                        }`}>
                        <p className={settings?.is_enabled ? 'text-green-300' : 'text-yellow-300'}>
                            {settings?.is_enabled
                                ? `✅ Auto-trading enabled | $${settings?.trade_amount} × ${settings?.leverage}x = $${settings?.effective_position_size} effective | Symbols: ${settings?.allowed_symbols?.join(', ') || 'All'}`
                                : '⚠️ Auto-trading is disabled. Enable it to execute trades automatically from signals.'}
                        </p>
                    </div>

                    {/* Trading Session Status */}
                    <TradingSessionStatus />
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    {statCards.map((stat, index) => (
                        <div key={index} className="relative overflow-hidden bg-gray-800/30 backdrop-blur-sm border border-gray-700 rounded-lg p-6 hover:border-gray-600 transition-all group">
                            <div className={`absolute inset-0 bg-gradient-to-br ${stat.bgGradient} opacity-0 group-hover:opacity-100 transition-opacity`} />
                            <div className="relative">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-gray-400 text-sm">{stat.label}</span>
                                    <stat.icon className={`w-5 h-5 ${stat.color}`} />
                                </div>
                                <div className={`text-2xl font-bold ${stat.color} mb-1`}>{stat.value}</div>
                                <div className="text-sm text-gray-500">{stat.subtext}</div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Tabs */}
                <div className="mb-6">
                    <div className="flex gap-2 border-b border-gray-700">
                        {['overview', 'open', 'history'].map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`px-6 py-3 font-medium transition-all capitalize ${activeTab === tab
                                    ? 'text-purple-400 border-b-2 border-purple-400'
                                    : 'text-gray-400 hover:text-white'
                                    }`}
                            >
                                {tab === 'open' ? `Open (${openCount})` : tab}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Content */}
                {activeTab === 'overview' && (
                    <div className="space-y-6">
                        {/* Open Positions Preview */}
                        <div>
                            <h2 className="text-xl font-bold text-white mb-4">Open Positions</h2>
                            {openPositions.length > 0 ? (
                                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                    {openPositions.slice(0, 6).map((trade) => (
                                        <TradeCard key={trade.id} trade={trade} onClose={closeTrade} isClosing={closingTrades[trade.id]} />
                                    ))}
                                </div>
                            ) : (
                                <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-8 text-center">
                                    <p className="text-gray-400">No open positions</p>
                                </div>
                            )}
                        </div>

                        {/* Recent Trades */}
                        <div>
                            <h2 className="text-xl font-bold text-white mb-4">Recent Trades</h2>
                            {trades.filter(t => t.status?.startsWith('CLOSED')).length > 0 ? (
                                <div className="bg-gray-800/30 border border-gray-700 rounded-lg overflow-hidden">
                                    <TradeTable trades={trades.filter(t => t.status?.startsWith('CLOSED')).slice(0, 10)} />
                                </div>
                            ) : (
                                <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-8 text-center">
                                    <p className="text-gray-400">No closed trades yet</p>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {activeTab === 'open' && (
                    <div>
                        {openPositions.length > 0 ? (
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {openPositions.map((trade) => (
                                    <TradeCard key={trade.id} trade={trade} onClose={closeTrade} isClosing={closingTrades[trade.id]} />
                                ))}
                            </div>
                        ) : (
                            <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-12 text-center">
                                <Activity className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                                <p className="text-gray-400 text-lg">No open positions</p>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'history' && (
                    <div>
                        {trades.length > 0 ? (
                            <div className="bg-gray-800/30 border border-gray-700 rounded-lg overflow-hidden">
                                <TradeTable trades={trades} />
                            </div>
                        ) : (
                            <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-12 text-center">
                                <BarChart3 className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                                <p className="text-gray-400 text-lg">No trade history yet</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Settings Modal */}
                {showSettings && (
                    <SettingsModal
                        settings={settings}
                        onSave={updateSettings}
                        onClose={() => setShowSettings(false)}
                        saving={savingSettings}
                    />
                )}
            </div>
        </div>
    );
};

// Trade Card Component
const TradeCard = ({ trade, onClose, isClosing }) => {
    const pnl = parseFloat(trade.profit_loss || 0);
    const pnlPct = parseFloat(trade.profit_loss_percentage || 0);
    const isOpen = trade.status === 'OPEN';

    return (
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 hover:border-purple-500/50 transition-all">
            <div className="flex items-start justify-between mb-3">
                <div>
                    <h3 className="text-white font-semibold text-lg">{trade.symbol}</h3>
                    <div className="flex items-center gap-2 mt-1">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${trade.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                            }`}>
                            {trade.direction}
                        </span>
                        <span className="text-xs text-purple-400">{trade.leverage}x</span>
                    </div>
                </div>
                {isOpen && onClose && (
                    <button
                        onClick={() => onClose(trade.id)}
                        disabled={isClosing}
                        className="p-1.5 bg-red-500/20 border border-red-500/50 rounded hover:bg-red-500/30 transition-colors disabled:opacity-50"
                    >
                        {isClosing ? <Activity className="w-4 h-4 text-red-400 animate-spin" /> : <X className="w-4 h-4 text-red-400" />}
                    </button>
                )}
            </div>

            <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                    <span className="text-gray-400">Entry:</span>
                    <span className="text-white font-mono">${parseFloat(trade.entry_price || 0).toFixed(4)}</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-400">Size:</span>
                    <span className="text-white">${parseFloat(trade.position_size_usdt || 0).toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-400">TP / SL:</span>
                    <span className="text-white font-mono text-xs">
                        <span className="text-green-400">${parseFloat(trade.take_profit || 0).toFixed(4)}</span>
                        {' / '}
                        <span className="text-red-400">${parseFloat(trade.stop_loss || 0).toFixed(4)}</span>
                    </span>
                </div>
                {!isOpen && (
                    <div className="border-t border-gray-700 pt-2 mt-2">
                        <div className="flex justify-between">
                            <span className="text-gray-400">P/L:</span>
                            <div className="text-right">
                                <div className={`font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {pnl >= 0 ? '+' : ''}${Math.abs(pnl).toFixed(2)}
                                </div>
                                <div className={`text-xs ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    ({pnl >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%)
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <div className="mt-3 pt-3 border-t border-gray-700 flex items-center justify-between text-xs">
                <div className="flex items-center text-gray-500">
                    <Clock className="w-3 h-3 mr-1" />
                    {trade.entry_time ? new Date(trade.entry_time).toLocaleDateString() : new Date(trade.created_at).toLocaleDateString()}
                </div>
                <span className={`px-2 py-0.5 rounded text-xs ${trade.status === 'OPEN' ? 'bg-blue-500/20 text-blue-400' :
                    trade.status === 'CLOSED_TP' ? 'bg-green-500/20 text-green-400' :
                        trade.status === 'CLOSED_SL' ? 'bg-red-500/20 text-red-400' :
                            'bg-gray-500/20 text-gray-400'
                    }`}>
                    {trade.status?.replace('CLOSED_', '') || trade.status}
                </span>
            </div>
        </div>
    );
};

// Trade Table Component
const TradeTable = ({ trades }) => (
    <div className="overflow-x-auto">
        <table className="w-full">
            <thead className="bg-gray-800/50">
                <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Symbol</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Direction</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Entry</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Exit</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">P/L</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Date</th>
                </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
                {trades.map((trade) => {
                    const pnl = parseFloat(trade.profit_loss || 0);
                    const pnlPct = parseFloat(trade.profit_loss_percentage || 0);
                    return (
                        <tr key={trade.id} className="hover:bg-gray-800/30">
                            <td className="px-4 py-3 text-white font-medium">{trade.symbol}</td>
                            <td className="px-4 py-3">
                                <span className={`px-2 py-1 rounded text-xs font-medium ${trade.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                                    }`}>
                                    {trade.direction} {trade.leverage}x
                                </span>
                            </td>
                            <td className="px-4 py-3 text-gray-300 font-mono text-sm">${parseFloat(trade.entry_price || 0).toFixed(4)}</td>
                            <td className="px-4 py-3 text-gray-300 font-mono text-sm">
                                {trade.exit_price ? `$${parseFloat(trade.exit_price).toFixed(4)}` : '-'}
                            </td>
                            <td className="px-4 py-3">
                                <div className={`font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                                </div>
                                <div className={`text-xs ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    ({pnl >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%)
                                </div>
                            </td>
                            <td className="px-4 py-3">
                                <span className={`px-2 py-1 rounded text-xs ${trade.status === 'OPEN' ? 'bg-blue-500/20 text-blue-400' :
                                    trade.status === 'CLOSED_TP' ? 'bg-green-500/20 text-green-400' :
                                        trade.status === 'CLOSED_SL' ? 'bg-red-500/20 text-red-400' :
                                            'bg-gray-500/20 text-gray-400'
                                    }`}>
                                    {trade.status?.replace('CLOSED_', '') || trade.status}
                                </span>
                            </td>
                            <td className="px-4 py-3 text-gray-400 text-sm">
                                {trade.entry_time ? new Date(trade.entry_time).toLocaleDateString() : '-'}
                            </td>
                        </tr>
                    );
                })}
            </tbody>
        </table>
    </div>
);

// Settings Modal Component
const SettingsModal = ({ settings, onSave, onClose, saving }) => {
    const [formData, setFormData] = useState({
        trade_amount: settings?.trade_amount || 5,
        leverage: settings?.leverage || 10,
        max_concurrent_trades: settings?.max_concurrent_trades || 1,
        min_signal_confidence: parseFloat(settings?.min_signal_confidence || 0.7) * 100,
        trade_long: settings?.trade_long ?? true,
        trade_short: settings?.trade_short ?? true,
    });

    const handleSubmit = (e) => {
        e.preventDefault();
        onSave({
            ...formData,
            min_signal_confidence: formData.min_signal_confidence / 100,
        });
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
            <div className="bg-gray-800 rounded-lg p-6 w-full max-w-md border border-gray-700">
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-bold text-white">Trading Settings</h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-white">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Trade Amount (USDT)</label>
                        <input
                            type="number"
                            value={formData.trade_amount}
                            onChange={(e) => setFormData(prev => ({ ...prev, trade_amount: e.target.value }))}
                            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                            min="1"
                            step="0.01"
                        />
                    </div>

                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Leverage</label>
                        <input
                            type="number"
                            value={formData.leverage}
                            onChange={(e) => setFormData(prev => ({ ...prev, leverage: parseInt(e.target.value) }))}
                            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                            min="1"
                            max="125"
                        />
                    </div>

                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Max Concurrent Trades</label>
                        <input
                            type="number"
                            value={formData.max_concurrent_trades}
                            onChange={(e) => setFormData(prev => ({ ...prev, max_concurrent_trades: parseInt(e.target.value) }))}
                            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                            min="1"
                            max="10"
                        />
                    </div>

                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Min Signal Confidence (%)</label>
                        <input
                            type="number"
                            value={formData.min_signal_confidence}
                            onChange={(e) => setFormData(prev => ({ ...prev, min_signal_confidence: parseInt(e.target.value) }))}
                            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                            min="50"
                            max="99"
                        />
                    </div>

                    <div className="flex gap-4">
                        <label className="flex items-center gap-2 text-gray-300">
                            <input
                                type="checkbox"
                                checked={formData.trade_long}
                                onChange={(e) => setFormData(prev => ({ ...prev, trade_long: e.target.checked }))}
                                className="rounded"
                            />
                            Allow LONG
                        </label>
                        <label className="flex items-center gap-2 text-gray-300">
                            <input
                                type="checkbox"
                                checked={formData.trade_short}
                                onChange={(e) => setFormData(prev => ({ ...prev, trade_short: e.target.checked }))}
                                className="rounded"
                            />
                            Allow SHORT
                        </label>
                    </div>

                    <div className="flex gap-3 pt-4">
                        <button
                            type="button"
                            onClick={onClose}
                            className="flex-1 px-4 py-2 bg-gray-700 text-white rounded hover:bg-gray-600"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={saving}
                            className="flex-1 px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
                        >
                            {saving ? 'Saving...' : 'Save Settings'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

// Trading Session Status Component
const TradingSessionStatus = () => {
    const [currentTime, setCurrentTime] = useState(new Date());

    useEffect(() => {
        const timer = setInterval(() => setCurrentTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    const NEPAL_OFFSET_MINUTES = 5 * 60 + 45;
    const US_EST_OFFSET_MINUTES = -5 * 60;

    const getNepalTime = (date) => {
        const utc = date.getTime() + date.getTimezoneOffset() * 60000;
        return new Date(utc + NEPAL_OFFSET_MINUTES * 60000);
    };

    const getUSTime = (date) => {
        const utc = date.getTime() + date.getTimezoneOffset() * 60000;
        const isDST = isUSDaylightSaving(date);
        const offset = isDST ? (US_EST_OFFSET_MINUTES + 60) : US_EST_OFFSET_MINUTES;
        return new Date(utc + offset * 60000);
    };

    const getUTCTime = (date) => {
        return new Date(date.getTime() + date.getTimezoneOffset() * 60000);
    };

    const isUSDaylightSaving = (date) => {
        const jan = new Date(date.getFullYear(), 0, 1);
        const jul = new Date(date.getFullYear(), 6, 1);
        const stdOffset = Math.max(jan.getTimezoneOffset(), jul.getTimezoneOffset());
        return date.getTimezoneOffset() < stdOffset;
    };

    const formatTime = (date) => {
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: true
        });
    };

    const isWithinTradingWindow = () => {
        const nepalTime = getNepalTime(currentTime);
        const hour = nepalTime.getHours();
        const minute = nepalTime.getMinutes();
        const timeInMinutes = hour * 60 + minute;

        const windows = [
            { start: 17 * 60, end: 18 * 60 },
            { start: 21 * 60, end: 23 * 60 }
        ];

        return windows.some(w => timeInMinutes >= w.start && timeInMinutes < w.end);
    };

    const getNextWindow = () => {
        const nepalTime = getNepalTime(currentTime);
        const hour = nepalTime.getHours();
        const minute = nepalTime.getMinutes();
        const timeInMinutes = hour * 60 + minute;

        if (timeInMinutes < 17 * 60) return '17:00 NPT';
        if (timeInMinutes >= 18 * 60 && timeInMinutes < 21 * 60) return '21:00 NPT';
        return '17:00 NPT (tomorrow)';
    };

    const nepalTime = getNepalTime(currentTime);
    const usTime = getUSTime(currentTime);
    const utcTime = getUTCTime(currentTime);
    const isActive = isWithinTradingWindow();

    const tradingWindows = [
        { npt: '17:00 - 18:00', utc: '11:15 - 12:15', us: '06:15 - 07:15 EST' },
        { npt: '21:00 - 23:00', utc: '15:15 - 17:15', us: '10:15 - 12:15 EST' }
    ];

    return (
        <div className={`mt-4 rounded-lg border-2 p-4 ${isActive ? 'bg-green-500/10 border-green-500/50' : 'bg-gray-800/30 border-gray-700'}`}>
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <Activity className={`w-5 h-5 ${isActive ? 'text-green-400 animate-pulse' : 'text-gray-500'}`} />
                    <span className={`font-semibold ${isActive ? 'text-green-400' : 'text-gray-400'}`}>
                        Trading Session: {isActive ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                    {isActive && (
                        <span className="flex items-center gap-1 px-2 py-0.5 bg-green-500/20 border border-green-500/50 rounded text-xs text-green-400">
                            <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse"></span>
                            LIVE
                        </span>
                    )}
                </div>
                {!isActive && (
                    <span className="text-sm text-gray-500">Next: {getNextWindow()}</span>
                )}
            </div>

            <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="text-center p-2 bg-gray-800/50 rounded-lg border border-gray-700">
                    <div className="flex items-center justify-center gap-1 text-xs text-gray-500 mb-1">
                        <Clock className="w-3 h-3" />
                        <span>Nepal (NPT)</span>
                    </div>
                    <div className="font-mono font-bold text-blue-400">{formatTime(nepalTime)}</div>
                </div>
                <div className="text-center p-2 bg-gray-800/50 rounded-lg border border-gray-700">
                    <div className="flex items-center justify-center gap-1 text-xs text-gray-500 mb-1">
                        <Clock className="w-3 h-3" />
                        <span>US (EST/EDT)</span>
                    </div>
                    <div className="font-mono font-bold text-purple-400">{formatTime(usTime)}</div>
                </div>
                <div className="text-center p-2 bg-gray-800/50 rounded-lg border border-gray-700">
                    <div className="flex items-center justify-center gap-1 text-xs text-gray-500 mb-1">
                        <Clock className="w-3 h-3" />
                        <span>UTC</span>
                    </div>
                    <div className="font-mono font-bold text-gray-300">{formatTime(utcTime)}</div>
                </div>
            </div>

            <div className="border-t border-gray-700 pt-3">
                <div className="flex items-center gap-1 text-xs text-gray-500 mb-2">
                    <Calendar className="w-3 h-3" />
                    <span>Trading Windows (Futures trades execute during these times)</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                    {tradingWindows.map((window, idx) => (
                        <div key={idx} className="bg-gray-800/50 border border-gray-700 rounded p-2 text-xs">
                            <div className="font-semibold text-purple-400 mb-1">Window {idx + 1}</div>
                            <div className="space-y-0.5">
                                <div><span className="text-gray-500">NPT:</span> <span className="font-mono text-gray-300">{window.npt}</span></div>
                                <div><span className="text-gray-500">UTC:</span> <span className="font-mono text-gray-300">{window.utc}</span></div>
                                <div><span className="text-gray-500">US:</span> <span className="font-mono text-gray-300">{window.us}</span></div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default FuturesPerformance;
