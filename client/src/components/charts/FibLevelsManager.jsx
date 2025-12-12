/**
 * Fibonacci Levels Manager Component
 * Allows users to input swing high/low and auto-calculate Fib levels
 * Also supports custom support/resistance lines
 */
import { useState, useEffect } from 'react';
import axios from 'axios';

const FibLevelsManager = ({ symbol }) => {
    const [fibSetup, setFibSetup] = useState(null);
    const [annotations, setAnnotations] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [saving, setSaving] = useState(false);

    // Form state
    const [swingHigh, setSwingHigh] = useState('');
    const [swingLow, setSwingLow] = useState('');
    const [direction, setDirection] = useState('UP');
    const [notes, setNotes] = useState('');

    // Custom level form
    const [showAddLevel, setShowAddLevel] = useState(false);
    const [customPrice, setCustomPrice] = useState('');
    const [customLabel, setCustomLabel] = useState('');
    const [customType, setCustomType] = useState('SUPPORT');

    const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

    const fetchData = async () => {
        if (!symbol) return;

        try {
            setLoading(true);
            const cleanSymbol = symbol.replace(/USDT$/i, '').toUpperCase();

            // Fetch Fib setup
            const fibRes = await axios.get(`${baseURL}/chart/fib/${cleanSymbol}/`);
            if (fibRes.data.swing_high) {
                setFibSetup(fibRes.data);
                setSwingHigh(fibRes.data.swing_high);
                setSwingLow(fibRes.data.swing_low);
                setDirection(fibRes.data.direction);
                setNotes(fibRes.data.notes || '');
            }

            // Fetch custom annotations
            const annRes = await axios.get(`${baseURL}/chart/annotations/${cleanSymbol}/`);
            setAnnotations(annRes.data.annotations || []);
        } catch (err) {
            console.error('Error fetching chart data:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [symbol]);

    const saveFibSetup = async () => {
        if (!swingHigh || !swingLow) {
            alert('Please enter both swing high and swing low');
            return;
        }

        try {
            setSaving(true);
            const cleanSymbol = symbol.replace(/USDT$/i, '').toUpperCase();
            const res = await axios.post(`${baseURL}/chart/fib/${cleanSymbol}/`, {
                swing_high: parseFloat(swingHigh),
                swing_low: parseFloat(swingLow),
                direction,
                notes,
            });
            setFibSetup(res.data);
            setShowForm(false);
        } catch (err) {
            alert('Failed to save: ' + err.message);
        } finally {
            setSaving(false);
        }
    };

    const deleteFibSetup = async () => {
        if (!window.confirm('Delete Fibonacci setup?')) return;

        try {
            const cleanSymbol = symbol.replace(/USDT$/i, '').toUpperCase();
            await axios.delete(`${baseURL}/chart/fib/${cleanSymbol}/`);
            setFibSetup(null);
            setSwingHigh('');
            setSwingLow('');
        } catch (err) {
            alert('Failed to delete: ' + err.message);
        }
    };

    const addCustomLevel = async () => {
        if (!customPrice) return;

        try {
            const cleanSymbol = symbol.replace(/USDT$/i, '').toUpperCase();
            await axios.post(`${baseURL}/chart/annotations/`, {
                symbol: cleanSymbol,
                type: customType,
                price_level: parseFloat(customPrice),
                label: customLabel || customType,
                color: customType === 'SUPPORT' ? '#22c55e' : '#ef4444',
            });
            setCustomPrice('');
            setCustomLabel('');
            setShowAddLevel(false);
            fetchData();
        } catch (err) {
            alert('Failed to add: ' + err.message);
        }
    };

    const deleteAnnotation = async (id) => {
        try {
            await axios.delete(`${baseURL}/chart/annotations/${id}/delete/`);
            setAnnotations(prev => prev.filter(a => a.id !== id));
        } catch (err) {
            alert('Failed to delete: ' + err.message);
        }
    };

    const FIB_COLORS = {
        '0.0': '#ef4444',
        '0.236': '#f97316',
        '0.382': '#eab308',
        '0.5': '#22c55e',
        '0.618': '#3b82f6',
        '0.786': '#8b5cf6',
        '1.0': '#ec4899',
    };

    if (loading) {
        return (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">📐 Fibonacci Levels</h2>
                <div className="text-gray-400 animate-pulse">Loading...</div>
            </div>
        );
    }

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-4 sm:p-6">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">📐 Fibonacci Levels</h2>
                <div className="flex gap-2">
                    {fibSetup && (
                        <button
                            onClick={deleteFibSetup}
                            className="px-3 py-1 text-xs bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors"
                        >
                            Delete
                        </button>
                    )}
                    <button
                        onClick={() => setShowForm(!showForm)}
                        className="px-3 py-1 text-xs bg-blue-500/20 text-blue-400 rounded hover:bg-blue-500/30 transition-colors"
                    >
                        {showForm ? 'Cancel' : fibSetup ? 'Edit' : 'Setup Fib'}
                    </button>
                </div>
            </div>

            {/* Fib Setup Form */}
            {showForm && (
                <div className="mb-4 p-4 bg-gray-100 dark:bg-gray-700/50 rounded-lg">
                    <div className="grid grid-cols-2 gap-3 mb-3">
                        <div>
                            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Swing High</label>
                            <input
                                type="number"
                                value={swingHigh}
                                onChange={(e) => setSwingHigh(e.target.value)}
                                className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white"
                                placeholder="0.00"
                                step="any"
                            />
                        </div>
                        <div>
                            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Swing Low</label>
                            <input
                                type="number"
                                value={swingLow}
                                onChange={(e) => setSwingLow(e.target.value)}
                                className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white"
                                placeholder="0.00"
                                step="any"
                            />
                        </div>
                    </div>
                    <div className="mb-3">
                        <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Direction</label>
                        <select
                            value={direction}
                            onChange={(e) => setDirection(e.target.value)}
                            className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white"
                        >
                            <option value="UP">Uptrend (Retracement from high)</option>
                            <option value="DOWN">Downtrend (Retracement from low)</option>
                        </select>
                    </div>
                    <div className="mb-3">
                        <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Notes (optional)</label>
                        <input
                            type="text"
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white"
                            placeholder="e.g., Weekly swing"
                        />
                    </div>
                    <button
                        onClick={saveFibSetup}
                        disabled={saving}
                        className="w-full py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
                    >
                        {saving ? 'Saving...' : 'Save Fibonacci Setup'}
                    </button>
                </div>
            )}

            {/* Fib Levels Display */}
            {fibSetup && fibSetup.levels && (
                <div className="mb-4">
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                        {direction === 'UP' ? '📈' : '📉'} {fibSetup.swing_low} → {fibSetup.swing_high}
                        {fibSetup.notes && <span className="ml-2 text-gray-400">({fibSetup.notes})</span>}
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        {Object.entries(fibSetup.levels).map(([level, price]) => (
                            <div
                                key={level}
                                className="p-2 rounded border text-center"
                                style={{
                                    borderColor: FIB_COLORS[level] || '#6b7280',
                                    backgroundColor: `${FIB_COLORS[level]}15` || 'transparent'
                                }}
                            >
                                <div className="text-xs font-medium" style={{ color: FIB_COLORS[level] }}>{level}</div>
                                <div className="text-sm font-mono text-gray-900 dark:text-white">${price.toFixed(4)}</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Custom Levels Section */}
            <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Custom Levels</h3>
                    <button
                        onClick={() => setShowAddLevel(!showAddLevel)}
                        className="px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded hover:bg-green-500/30"
                    >
                        {showAddLevel ? 'Cancel' : '+ Add Level'}
                    </button>
                </div>

                {/* Add Custom Level Form */}
                {showAddLevel && (
                    <div className="mb-3 p-3 bg-gray-100 dark:bg-gray-700/50 rounded-lg">
                        <div className="grid grid-cols-3 gap-2 mb-2">
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">Type</label>
                                <select
                                    value={customType}
                                    onChange={(e) => setCustomType(e.target.value)}
                                    className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded text-xs text-gray-900 dark:text-white"
                                >
                                    <option value="SUPPORT">Support</option>
                                    <option value="RESISTANCE">Resistance</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">Price</label>
                                <input
                                    type="number"
                                    value={customPrice}
                                    onChange={(e) => setCustomPrice(e.target.value)}
                                    className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded text-xs text-gray-900 dark:text-white"
                                    placeholder="0.00"
                                    step="any"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">Label</label>
                                <input
                                    type="text"
                                    value={customLabel}
                                    onChange={(e) => setCustomLabel(e.target.value)}
                                    className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded text-xs text-gray-900 dark:text-white"
                                    placeholder="S1, R1..."
                                />
                            </div>
                        </div>
                        <button
                            onClick={addCustomLevel}
                            className="w-full py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700"
                        >
                            Add Level
                        </button>
                    </div>
                )}

                {/* Custom Levels List */}
                {annotations.length > 0 ? (
                    <div className="space-y-1">
                        {annotations.map((ann) => (
                            <div
                                key={ann.id}
                                className="flex items-center justify-between p-2 rounded"
                                style={{ backgroundColor: `${ann.color}15` }}
                            >
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: ann.color }}></div>
                                    <span className="text-xs font-medium text-gray-900 dark:text-white">{ann.label || ann.type}</span>
                                    <span className="text-xs font-mono text-gray-600 dark:text-gray-400">${ann.price_level.toFixed(4)}</span>
                                </div>
                                <button
                                    onClick={() => deleteAnnotation(ann.id)}
                                    className="text-red-400 hover:text-red-500 text-xs"
                                >
                                    ×
                                </button>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-xs text-gray-400 text-center py-2">No custom levels</div>
                )}
            </div>
        </div>
    );
};

export default FibLevelsManager;
