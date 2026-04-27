import { useEffect, useState } from 'react';
import { Users, RefreshCw } from 'lucide-react';
import api from '../../services/api';

/**
 * Admin-only dropdown that scopes the futures reports to one account.
 *
 * Hits GET /api/futures/users/ on mount, lists central + every connected
 * user, and emits the chosen scope through onChange. Renders nothing for
 * non-admins so it can be dropped into a shared page without conditional
 * wrapping at the call site.
 *
 * Scope semantics (matches the backend's _resolve_scope_filter):
 *   value=''         => admin sees everything (no user_id query param)
 *   value='central'  => /api/futures/...?user_id=central
 *   value='<int>'    => /api/futures/...?user_id=<int>
 *
 * Props:
 *   value:     current scope ('' | 'central' | '<numeric user id>')
 *   onChange:  (next) => void
 *   isAdmin:   boolean — render nothing if false
 *   className: optional outer class
 */
export default function AccountScopeSelector({ value, onChange, isAdmin, className = '' }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchRows = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get('/futures/users/');
      setRows(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load accounts.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAdmin) fetchRows();
  }, [isAdmin]);

  if (!isAdmin) return null;

  const userRows = rows.filter((r) => r.label === 'user');

  const summaryFor = (val) => {
    if (val === '') return 'All accounts (combined)';
    if (val === 'central') {
      const c = rows.find((r) => r.label === 'central');
      const pnl = c?.stats?.total_pnl ?? 0;
      return `Central account · PnL ${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}`;
    }
    const u = userRows.find((r) => String(r.user_id) === String(val));
    if (!u) return `User ${val}`;
    return `${u.username} · ${u.connection?.api_key_hint || '—'} · PnL ${
      u.stats.total_pnl >= 0 ? '+' : ''
    }${u.stats.total_pnl.toFixed(2)}`;
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <Users className="w-4 h-4 text-gray-500 dark:text-gray-400" />
      <label className="text-sm text-gray-600 dark:text-gray-400 hidden sm:block">
        Account:
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={loading}
        className="text-sm bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded px-2 py-1.5 text-gray-900 dark:text-white min-w-[260px] disabled:opacity-50"
        title={summaryFor(value)}
      >
        <option value="">All accounts (combined)</option>
        <option value="central">
          Central account
          {rows.find((r) => r.label === 'central')
            ? ` (${rows.find((r) => r.label === 'central').stats.total_trades} trades)`
            : ''}
        </option>
        {userRows.length > 0 && (
          <optgroup label="Users">
            {userRows.map((u) => (
              <option key={u.user_id} value={u.user_id}>
                {u.username || u.email || `User ${u.user_id}`}
                {u.connection?.api_key_hint ? ` · ${u.connection.api_key_hint}` : ''}
                {` · ${u.stats.total_trades} trades`}
                {u.connection?.status && u.connection.status !== 'ACTIVE' && u.connection.status !== 'PAUSED'
                  ? ` (${u.connection.status})`
                  : ''}
              </option>
            ))}
          </optgroup>
        )}
      </select>
      <button
        type="button"
        onClick={fetchRows}
        disabled={loading}
        title="Reload accounts"
        className="p-1.5 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white disabled:opacity-50"
      >
        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
      </button>
      {error && (
        <span className="text-xs text-red-600 dark:text-red-400 truncate max-w-xs">{error}</span>
      )}
    </div>
  );
}
