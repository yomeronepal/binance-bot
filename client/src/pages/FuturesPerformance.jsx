
import React, { useEffect, useState } from 'react';
import { Bot, TrendingUp, TrendingDown, Target, BarChart3, Clock, DollarSign, Activity, X, Settings, Power, Calendar, RefreshCw, AlertTriangle } from 'lucide-react';
import { useAuthStore } from '../store/useAuthStore';
import api from '../services/api';
import { ShieldAlert } from 'lucide-react';
import PullToRefresh from '../components/common/PullToRefresh';
import FearGreedWidget from '../components/common/FearGreedWidget';

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
    const [fearGreed, setFearGreed] = useState(null);

    const { user } = useAuthStore();
    const isSuperUser = user?.is_superuser;

    // Use relative paths since api instance has baseURL configured
    // const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

    const fetchData = async () => {
        try {
            setLoading(true);

            const [summaryRes, positionsRes, tradesRes, fgRes] = await Promise.all([
                api.get('/futures/summary/'),
                api.get('/futures/positions/'),
                api.get('/futures/trades/?limit=50'),
                api.get('/futures/fear-greed/').catch(() => ({ data: null })),
            ]);

            setSummary(summaryRes.data);
            setSettings(summaryRes.data.settings);

            const positionsData = positionsRes.data;
            setOpenPositions(Array.isArray(positionsData) ? positionsData : (positionsData?.results || []));

            const tradesData = tradesRes.data;
            setTrades(Array.isArray(tradesData) ? tradesData : (tradesData?.results || []));

            if (fgRes.data) setFearGreed(fgRes.data);

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
            await api.post('/futures/toggle/', { enabled: newState });
            setSettings(prev => ({ ...prev, is_enabled: newState }));
        } catch (err) {
            alert(`Failed to toggle trading: ${err.message}`);
        }
    };

    const updateSettings = async (newSettings) => {
        try {
            setSavingSettings(true);
            await api.patch('/futures/settings/', newSettings);
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
            await api.post(`/futures/trades/${tradeId}/close/`);
            await fetchData();
        } catch (err) {
            alert(`Failed to close trade: ${err.response?.data?.error || err.message}`);
        } finally {
            setClosingTrades(prev => ({ ...prev, [tradeId]: false }));
        }
    };

    useEffect(() => {
        if (isSuperUser) {
            fetchData();
            // Auto-refresh every 30 seconds
            const interval = setInterval(fetchData, 30000);
            return () => clearInterval(interval);
        }
    }, [isSuperUser]);

    if (!isSuperUser) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
                <div className="text-center p-8 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-red-200 dark:border-red-900">
                    <ShieldAlert className="w-16 h-16 text-red-500 mx-auto mb-4" />
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Access Denied</h2>
                    <p className="text-gray-600 dark:text-gray-400">This area is restricted to Super Administrators only.</p>
                </div>
            </div>
        );
    }

    if (loading && !summary) {
        return (
            <div className="min-h-screen bg-gray-50 dark:bg-gradient-to-br dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 flex items-center justify-center">
                <div className="text-center">
                    <Activity className="w-12 h-12 text-purple-500 dark:text-purple-400 animate-pulse mx-auto mb-4" />
                    <p className="text-gray-600 dark:text-gray-400">Loading futures performance...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen bg-gray-50 dark:bg-gradient-to-br dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 p-6">
                <div className="max-w-7xl mx-auto">
                    <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-lg p-8 text-center">
                        <p className="text-red-600 dark:text-red-400">Failed to load futures performance: {error}</p>
                        <button onClick={fetchData} className="mt-4 px-4 py-2 bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 rounded hover:bg-red-200 dark:hover:bg-red-500/30">
                            Retry
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    const stats = summary?.statistics || {};
    const realizedPnl = parseFloat(stats.realized_pnl || stats.total_pnl || 0);
    const unrealizedPnl = parseFloat(stats.unrealized_pnl || 0);
    const totalPnl = parseFloat(stats.total_pnl || 0);
    const winRate = parseFloat(stats.win_rate || 0);
    const totalTrades = parseInt(stats.total_trades || 0);
    const winningTrades = parseInt(stats.winning_trades || 0);
    const losingTrades = parseInt(stats.losing_trades || 0);
    const openCount = parseInt(stats.open_positions_count || stats.open_positions || 0);

    // Use open_positions from summary if available (contains live data)
    const livePositions = summary?.open_positions || openPositions;

    const statCards = [
        {
            label: 'Total P/L',
            value: `${totalPnl >= 0 ? '+' : ''}$${Math.abs(totalPnl).toFixed(2)}`,
            subtext: `Realized: $${realizedPnl.toFixed(2)} | Unrealized: $${unrealizedPnl.toFixed(2)}`,
            icon: DollarSign,
            color: totalPnl >= 0 ? 'text-green-400' : 'text-red-400',
            bgGradient: totalPnl >= 0 ? 'from-green-500/20 to-green-600/10' : 'from-red-500/20 to-red-600/10',
        },
        {
            label: 'Unrealized P/L',
            value: `${unrealizedPnl >= 0 ? '+' : ''}$${Math.abs(unrealizedPnl).toFixed(2)}`,
            subtext: `From ${openCount} open position${openCount !== 1 ? 's' : ''}`,
            icon: Activity,
            color: unrealizedPnl >= 0 ? 'text-green-400' : 'text-red-400',
            bgGradient: unrealizedPnl >= 0 ? 'from-green-500/20 to-green-600/10' : 'from-red-500/20 to-red-600/10',
        },
        {
            label: 'Win Rate',
            value: `${winRate.toFixed(1)}%`,
            subtext: `${winningTrades}W / ${losingTrades}L (${totalTrades} trades)`,
            icon: Target,
            color: winRate >= 50 ? 'text-green-400' : 'text-red-400',
            bgGradient: 'from-blue-500/20 to-purple-600/10',
        },
        {
            label: 'Position Size',
            value: `$${settings?.trade_amount || 0}`,
            subtext: `${settings?.leverage || 10}x = $${settings?.effective_position_size || 0} effective`,
            icon: BarChart3,
            color: 'text-blue-400',
            bgGradient: 'from-blue-500/20 to-cyan-600/10',
        },
    ];

    // Handle pull-to-refresh
    const handleRefresh = async () => {
        await fetchData();
    };

    return (
        <PullToRefresh onRefresh={handleRefresh} disabled={!isSuperUser}>
        <div className="min-h-screen bg-gray-50 dark:bg-gradient-to-br dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 p-4 sm:p-6">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-gradient-to-br from-purple-100 to-pink-100 dark:from-purple-500/20 dark:to-pink-500/20 rounded-lg border border-purple-300 dark:border-purple-500/50">
                                <Bot className="w-8 h-8 text-purple-600 dark:text-purple-400" />
                            </div>
                            <div>
                                <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">Futures Trading Performance</h1>
                                <p className="text-gray-600 dark:text-gray-400 text-sm sm:text-base">Real Binance futures trades monitoring</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            {/* Trading Toggle */}
                            <button
                                onClick={toggleTrading}
                                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${settings?.is_enabled
                                    ? 'bg-green-100 dark:bg-green-500/20 border border-green-300 dark:border-green-500/50 text-green-600 dark:text-green-400 hover:bg-green-200 dark:hover:bg-green-500/30'
                                    : 'bg-red-100 dark:bg-red-500/20 border border-red-300 dark:border-red-500/50 text-red-600 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-500/30'
                                    }`}
                            >
                                <Power className="w-4 h-4" />
                                {settings?.is_enabled ? 'Trading ON' : 'Trading OFF'}
                            </button>
                            {/* Settings Button */}
                            <button
                                onClick={() => setShowSettings(true)}
                                className="p-2 bg-gray-200 dark:bg-gray-700 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
                            >
                                <Settings className="w-5 h-5 text-gray-600 dark:text-gray-300" />
                            </button>
                            {/* Refresh */}
                            <button
                                onClick={fetchData}
                                disabled={loading}
                                className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-white rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors"
                            >
                                {loading ? 'Refreshing...' : 'Refresh'}
                            </button>
                        </div>
                    </div>

                    {/* Status Banner */}
                    <div className={`rounded-lg border p-4 ${settings?.is_enabled
                        ? 'bg-green-50 dark:bg-green-500/10 border-green-200 dark:border-green-500/30'
                        : 'bg-yellow-50 dark:bg-yellow-500/10 border-yellow-200 dark:border-yellow-500/30'
                        }`}>
                        <p className={settings?.is_enabled ? 'text-green-700 dark:text-green-300' : 'text-yellow-700 dark:text-yellow-300'}>
                            {settings?.is_enabled
                                ? `✅ Auto-trading enabled | $${settings?.trade_amount} × ${settings?.leverage}x = $${settings?.effective_position_size} effective | Symbols: ${settings?.allowed_symbols?.join(', ') || 'All'}`
                                : '⚠️ Auto-trading is disabled. Enable it to execute trades automatically from signals.'}
                        </p>
                    </div>

                    {fearGreed && fearGreed.available && <FearGreedWidget data={fearGreed} />}
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    {statCards.map((stat, index) => (
                        <div key={index} className="relative overflow-hidden bg-white dark:bg-gray-800/30 backdrop-blur-sm border border-gray-200 dark:border-gray-700 rounded-lg p-6 hover:border-gray-300 dark:hover:border-gray-600 transition-all group shadow-sm">
                            <div className={`absolute inset-0 bg-gradient-to-br ${stat.bgGradient} opacity-0 group-hover:opacity-100 transition-opacity`} />
                            <div className="relative">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-gray-600 dark:text-gray-400 text-sm">{stat.label}</span>
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
                    <div className="flex gap-2 border-b border-gray-200 dark:border-gray-700">
                        {['overview', 'open', 'history'].map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`px-6 py-3 font-medium transition-all capitalize ${activeTab === tab
                                    ? 'text-purple-600 dark:text-purple-400 border-b-2 border-purple-600 dark:border-purple-400'
                                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-white'
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
                            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Open Positions</h2>
                            {openPositions.length > 0 ? (
                                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                    {openPositions.slice(0, 6).map((trade) => (
                                        <TradeCard key={trade.id} trade={trade} onClose={closeTrade} isClosing={closingTrades[trade.id]} />
                                    ))}
                                </div>
                            ) : (
                                <div className="bg-gray-100 dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-8 text-center">
                                    <p className="text-gray-500 dark:text-gray-400">No open positions</p>
                                </div>
                            )}
                        </div>

                        {/* Recent Trades */}
                        <div>
                            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Recent Trades</h2>
                            {trades.filter(t => t.status?.startsWith('CLOSED')).length > 0 ? (
                                <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden shadow-sm">
                                    <TradeTable trades={trades.filter(t => t.status?.startsWith('CLOSED')).slice(0, 10)} />
                                </div>
                            ) : (
                                <div className="bg-gray-100 dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-8 text-center">
                                    <p className="text-gray-500 dark:text-gray-400">No closed trades yet</p>
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
                            <div className="bg-gray-100 dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-12 text-center">
                                <Activity className="w-16 h-16 text-gray-400 dark:text-gray-600 mx-auto mb-4" />
                                <p className="text-gray-500 dark:text-gray-400 text-lg">No open positions</p>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'history' && (
                    <div>
                        {trades.length > 0 ? (
                            <div className="bg-white dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden shadow-sm">
                                <TradeTable trades={trades} />
                            </div>
                        ) : (
                            <div className="bg-gray-100 dark:bg-gray-800/30 border border-gray-200 dark:border-gray-700 rounded-lg p-12 text-center">
                                <BarChart3 className="w-16 h-16 text-gray-400 dark:text-gray-600 mx-auto mb-4" />
                                <p className="text-gray-500 dark:text-gray-400 text-lg">No trade history yet</p>
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
        </PullToRefresh>
    );
};

// Trade Card Component with Live Data
const TradeCard = ({ trade, onClose, isClosing }) => {
    const pnl = parseFloat(trade.profit_loss || 0);
    const pnlPct = parseFloat(trade.profit_loss_percentage || 0);
    const unrealizedPnl = parseFloat(trade.unrealized_pnl || 0);
    const unrealizedPnlPct = parseFloat(trade.unrealized_pnl_percentage || 0);
    const markPrice = parseFloat(trade.mark_price || 0);
    const liquidationPrice = parseFloat(trade.liquidation_price || 0);
    const isOpen = trade.status === 'OPEN';
    const lastSync = trade.last_sync_time ? new Date(trade.last_sync_time) : null;

    // Calculate distance to liquidation
    const entryPrice = parseFloat(trade.entry_price || 0);
    const distanceToLiq = liquidationPrice && entryPrice ?
        Math.abs(((liquidationPrice - entryPrice) / entryPrice) * 100) : 0;
    const isLiqNear = distanceToLiq > 0 && distanceToLiq < 10; // Warning if within 10%

    return (
        <div className={`bg-white dark:bg-gray-800/50 border rounded-lg p-4 transition-all shadow-sm ${
            isOpen && unrealizedPnl >= 0
                ? 'border-green-300 dark:border-green-500/30 hover:border-green-400 dark:hover:border-green-500/50'
                : isOpen && unrealizedPnl < 0
                    ? 'border-red-300 dark:border-red-500/30 hover:border-red-400 dark:hover:border-red-500/50'
                    : 'border-gray-200 dark:border-gray-700 hover:border-purple-400 dark:hover:border-purple-500/50'
        }`}>
            <div className="flex items-start justify-between mb-3">
                <div>
                    <h3 className="text-gray-900 dark:text-white font-semibold text-lg">{trade.symbol}</h3>
                    <div className="flex items-center gap-2 mt-1">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${trade.direction === 'LONG' ? 'bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400' : 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400'
                            }`}>
                            {trade.direction}
                        </span>
                        <span className="text-xs text-purple-600 dark:text-purple-400">{trade.leverage}x</span>
                        {trade.margin_type && (
                            <span className="text-xs text-gray-500 dark:text-gray-400">{trade.margin_type}</span>
                        )}
                    </div>
                </div>
                {isOpen && onClose && (
                    <button
                        onClick={() => onClose(trade.id)}
                        disabled={isClosing}
                        className="p-1.5 bg-red-100 dark:bg-red-500/20 border border-red-300 dark:border-red-500/50 rounded hover:bg-red-200 dark:hover:bg-red-500/30 transition-colors disabled:opacity-50"
                    >
                        {isClosing ? <Activity className="w-4 h-4 text-red-500 dark:text-red-400 animate-spin" /> : <X className="w-4 h-4 text-red-500 dark:text-red-400" />}
                    </button>
                )}
            </div>

            <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-gray-400">Entry:</span>
                    <span className="text-gray-900 dark:text-white font-mono">${parseFloat(trade.entry_price || 0).toFixed(4)}</span>
                </div>

                {/* Live Mark Price for open trades */}
                {isOpen && markPrice > 0 && (
                    <div className="flex justify-between">
                        <span className="text-gray-500 dark:text-gray-400">Mark Price:</span>
                        <span className={`font-mono font-semibold ${
                            (trade.direction === 'LONG' && markPrice > entryPrice) ||
                            (trade.direction === 'SHORT' && markPrice < entryPrice)
                                ? 'text-green-600 dark:text-green-400'
                                : 'text-red-600 dark:text-red-400'
                        }`}>
                            ${markPrice.toFixed(4)}
                        </span>
                    </div>
                )}

                <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-gray-400">Size:</span>
                    <span className="text-gray-900 dark:text-white">${parseFloat(trade.position_size_usdt || 0).toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-gray-400">TP / SL:</span>
                    <span className="text-gray-900 dark:text-white font-mono text-xs">
                        <span className="text-green-600 dark:text-green-400">${parseFloat(trade.take_profit || 0).toFixed(4)}</span>
                        {' / '}
                        <span className="text-red-600 dark:text-red-400">${parseFloat(trade.stop_loss || 0).toFixed(4)}</span>
                    </span>
                </div>

                {/* Liquidation Price for open trades */}
                {isOpen && liquidationPrice > 0 && (
                    <div className="flex justify-between items-center">
                        <span className="text-gray-500 dark:text-gray-400 flex items-center gap-1">
                            {isLiqNear && <AlertTriangle className="w-3 h-3 text-orange-500" />}
                            Liq. Price:
                        </span>
                        <span className={`font-mono text-xs ${isLiqNear ? 'text-orange-500 font-semibold' : 'text-gray-600 dark:text-gray-400'}`}>
                            ${liquidationPrice.toFixed(4)} ({distanceToLiq.toFixed(1)}% away)
                        </span>
                    </div>
                )}

                {/* Live Unrealized P/L for open trades */}
                {isOpen && (
                    <div className="border-t border-gray-200 dark:border-gray-700 pt-2 mt-2">
                        <div className="flex justify-between">
                            <span className="text-gray-500 dark:text-gray-400">Unrealized P/L:</span>
                            <div className="text-right">
                                <div className={`font-bold text-lg ${unrealizedPnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                    {unrealizedPnl >= 0 ? '+' : ''}${Math.abs(unrealizedPnl).toFixed(2)}
                                </div>
                                <div className={`text-xs ${unrealizedPnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                    ({unrealizedPnl >= 0 ? '+' : ''}{unrealizedPnlPct.toFixed(2)}%)
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Realized P/L for closed trades */}
                {!isOpen && (
                    <div className="border-t border-gray-200 dark:border-gray-700 pt-2 mt-2">
                        <div className="flex justify-between">
                            <span className="text-gray-500 dark:text-gray-400">P/L:</span>
                            <div className="text-right">
                                <div className={`font-semibold ${pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                    {pnl >= 0 ? '+' : ''}${Math.abs(pnl).toFixed(2)}
                                </div>
                                <div className={`text-xs ${pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                    ({pnl >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%)
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 text-gray-500">
                    <div className="flex items-center">
                        <Clock className="w-3 h-3 mr-1" />
                        {trade.entry_time ? `${new Date(trade.entry_time).toLocaleDateString()} ${new Date(trade.entry_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : new Date(trade.created_at).toLocaleDateString()}
                    </div>
                    {isOpen && lastSync && (
                        <div className="flex items-center text-gray-400" title={`Last synced: ${lastSync.toLocaleString()}`}>
                            <RefreshCw className="w-3 h-3 mr-1" />
                            {formatTimeAgo(lastSync)}
                        </div>
                    )}
                </div>
                <span className={`px-2 py-0.5 rounded text-xs ${trade.status === 'OPEN' ? 'bg-blue-100 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400' :
                    trade.status === 'CLOSED_TP' ? 'bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400' :
                        trade.status === 'CLOSED_SL' ? 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400' :
                            'bg-gray-100 dark:bg-gray-500/20 text-gray-600 dark:text-gray-400'
                    }`}>
                    {trade.status?.replace('CLOSED_', '') || trade.status}
                </span>
            </div>
        </div>
    );
};

// Helper function to format time ago
const formatTimeAgo = (date) => {
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
};

// Trade Table Component with Live Data
const TradeTable = ({ trades }) => (
    <div className="overflow-x-auto">
        <table className="w-full">
            <thead className="bg-gray-100 dark:bg-gray-800/50">
                <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Symbol</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Direction</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Entry</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Mark/Exit</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">P/L</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Liq. Price</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Date</th>
                </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {trades.map((trade) => {
                    const isOpen = trade.status === 'OPEN';
                    const pnl = isOpen ? parseFloat(trade.unrealized_pnl || 0) : parseFloat(trade.profit_loss || 0);
                    const pnlPct = isOpen ? parseFloat(trade.unrealized_pnl_percentage || 0) : parseFloat(trade.profit_loss_percentage || 0);
                    const markPrice = parseFloat(trade.mark_price || 0);
                    const liquidationPrice = parseFloat(trade.liquidation_price || 0);
                    const entryPrice = parseFloat(trade.entry_price || 0);
                    const distanceToLiq = liquidationPrice && entryPrice ?
                        Math.abs(((liquidationPrice - entryPrice) / entryPrice) * 100) : 0;
                    const isLiqNear = distanceToLiq > 0 && distanceToLiq < 10;

                    return (
                        <tr key={trade.id} className={`hover:bg-gray-50 dark:hover:bg-gray-800/30 ${
                            isOpen && pnl >= 0 ? 'bg-green-50/30 dark:bg-green-900/10' :
                            isOpen && pnl < 0 ? 'bg-red-50/30 dark:bg-red-900/10' : ''
                        }`}>
                            <td className="px-4 py-3 text-gray-900 dark:text-white font-medium">{trade.symbol}</td>
                            <td className="px-4 py-3">
                                <span className={`px-2 py-1 rounded text-xs font-medium ${trade.direction === 'LONG' ? 'bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400' : 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400'
                                    }`}>
                                    {trade.direction} {trade.leverage}x
                                </span>
                            </td>
                            <td className="px-4 py-3 text-gray-700 dark:text-gray-300 font-mono text-sm">${parseFloat(trade.entry_price || 0).toFixed(4)}</td>
                            <td className="px-4 py-3 font-mono text-sm">
                                {isOpen && markPrice > 0 ? (
                                    <span className={`font-semibold ${
                                        (trade.direction === 'LONG' && markPrice > entryPrice) ||
                                        (trade.direction === 'SHORT' && markPrice < entryPrice)
                                            ? 'text-green-600 dark:text-green-400'
                                            : 'text-red-600 dark:text-red-400'
                                    }`}>
                                        ${markPrice.toFixed(4)}
                                    </span>
                                ) : trade.exit_price ? (
                                    <span className="text-gray-700 dark:text-gray-300">${parseFloat(trade.exit_price).toFixed(4)}</span>
                                ) : '-'}
                            </td>
                            <td className="px-4 py-3">
                                <div className={`font-semibold ${pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                                </div>
                                <div className={`text-xs ${pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                    ({pnl >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%)
                                </div>
                            </td>
                            <td className="px-4 py-3 text-sm">
                                {isOpen && liquidationPrice > 0 ? (
                                    <div className={isLiqNear ? 'text-orange-500 font-semibold' : 'text-gray-500 dark:text-gray-400'}>
                                        <div className="font-mono">${liquidationPrice.toFixed(4)}</div>
                                        <div className="text-xs">({distanceToLiq.toFixed(1)}% away)</div>
                                    </div>
                                ) : '-'}
                            </td>
                            <td className="px-4 py-3">
                                <span className={`px-2 py-1 rounded text-xs ${trade.status === 'OPEN' ? 'bg-blue-100 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400' :
                                    trade.status === 'CLOSED_TP' ? 'bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400' :
                                        trade.status === 'CLOSED_SL' ? 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400' :
                                            'bg-gray-100 dark:bg-gray-500/20 text-gray-600 dark:text-gray-400'
                                    }`}>
                                    {trade.status?.replace('CLOSED_', '') || trade.status}
                                </span>
                            </td>
                            <td className="px-4 py-3 text-gray-500 dark:text-gray-400 text-sm">
                                <div>{trade.entry_time ? `${new Date(trade.entry_time).toLocaleDateString()} ${new Date(trade.entry_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : '-'}</div>
                                {isOpen && trade.last_sync_time && (
                                    <div className="text-xs text-gray-400 flex items-center gap-1">
                                        <RefreshCw className="w-3 h-3" />
                                        {formatTimeAgo(new Date(trade.last_sync_time))}
                                    </div>
                                )}
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 dark:bg-black/70 p-4">
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md border border-gray-200 dark:border-gray-700 shadow-xl">
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-bold text-gray-900 dark:text-white">Trading Settings</h2>
                    <button onClick={onClose} className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-white">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Trade Amount (USDT)</label>
                        <input
                            type="number"
                            value={formData.trade_amount}
                            onChange={(e) => setFormData(prev => ({ ...prev, trade_amount: e.target.value }))}
                            className="w-full bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-gray-900 dark:text-white"
                            min="1"
                            step="0.01"
                        />
                    </div>

                    <div>
                        <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Leverage</label>
                        <input
                            type="number"
                            value={formData.leverage}
                            onChange={(e) => setFormData(prev => ({ ...prev, leverage: parseInt(e.target.value) }))}
                            className="w-full bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-gray-900 dark:text-white"
                            min="1"
                            max="125"
                        />
                    </div>

                    <div>
                        <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Max Concurrent Trades</label>
                        <input
                            type="number"
                            value={formData.max_concurrent_trades}
                            onChange={(e) => setFormData(prev => ({ ...prev, max_concurrent_trades: parseInt(e.target.value) }))}
                            className="w-full bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-gray-900 dark:text-white"
                            min="1"
                            max="10"
                        />
                    </div>

                    <div>
                        <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Min Signal Confidence (%)</label>
                        <input
                            type="number"
                            value={formData.min_signal_confidence}
                            onChange={(e) => setFormData(prev => ({ ...prev, min_signal_confidence: parseInt(e.target.value) }))}
                            className="w-full bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-gray-900 dark:text-white"
                            min="50"
                            max="99"
                        />
                    </div>

                    <div className="flex gap-4">
                        <label className="flex items-center gap-2 text-gray-700 dark:text-gray-300">
                            <input
                                type="checkbox"
                                checked={formData.trade_long}
                                onChange={(e) => setFormData(prev => ({ ...prev, trade_long: e.target.checked }))}
                                className="rounded"
                            />
                            Allow LONG
                        </label>
                        <label className="flex items-center gap-2 text-gray-700 dark:text-gray-300">
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
                            className="flex-1 px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-white rounded hover:bg-gray-300 dark:hover:bg-gray-600"
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

export default FuturesPerformance;
