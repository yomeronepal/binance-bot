import { useEffect, useState } from 'react';
import { Clock, Calendar, RefreshCw, Zap, TrendingUp } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const NEPAL_OFFSET_MINUTES = 5 * 60 + 45;

const getNepalTime = (date) => {
  const utc = date.getTime() + date.getTimezoneOffset() * 60000;
  return new Date(utc + NEPAL_OFFSET_MINUTES * 60000);
};

const hourToUtc = (h) => {
  let mins = h * 60 - NEPAL_OFFSET_MINUTES;
  if (mins < 0) mins += 1440;
  return `${String(Math.floor(mins / 60) % 24).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`;
};

const winRateColor = (wr) => {
  if (wr == null) return 'text-gray-400';
  if (wr >= 60) return 'text-green-500';
  if (wr >= 50) return 'text-amber-500';
  return 'text-red-500';
};

const DayTradeSessions = () => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [now, setNow] = useState(new Date());

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_BASE}/daytrade/sessions/`);
      const data = await res.json();
      setSessions(data.sessions || []);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch day-trade sessions:', err);
      setError('Failed to load sessions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
    const interval = setInterval(fetchSessions, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const nepalNow = getNepalTime(now);
  const npHour = nepalNow.getHours();
  const npWeekday = nepalNow.getDay() === 0 ? 6 : nepalNow.getDay() - 1;

  const isActive = (s) => {
    const inHour = npHour >= s.start_hour && npHour < s.end_hour;
    if (!inHour) return false;
    return !s.active_days || s.active_days.length === 0 || s.active_days.includes(npWeekday);
  };

  const activeNow = sessions.filter(isActive);

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Zap className="w-6 h-6 text-cyan-500" />
            Day-Trade Sessions
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Auto-optimized favourable windows (NPT) discovered from closed day-trade paper trades.
          </p>
        </div>
        <button
          onClick={() => { setLoading(true); fetchSessions(); }}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-3 text-sm">
        <span className="inline-flex items-center gap-1.5 text-gray-600 dark:text-gray-300">
          <Clock className="w-4 h-4" />
          Nepal time: <span className="font-mono font-semibold">{nepalNow.toTimeString().slice(0, 8)}</span> ({DAY_NAMES[npWeekday]})
        </span>
        <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${activeNow.length ? 'bg-green-100 dark:bg-green-500/20 text-green-600' : 'bg-gray-100 dark:bg-gray-700 text-gray-500'}`}>
          {activeNow.length ? `${activeNow.length} window(s) active now` : 'No window active now'}
        </span>
      </div>

      {error && (
        <div className="p-4 mb-4 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-600 text-sm">{error}</div>
      )}

      {!loading && sessions.length === 0 && (
        <div className="p-6 rounded-xl border border-dashed border-gray-300 dark:border-gray-700 text-center text-gray-500 dark:text-gray-400">
          <Calendar className="w-8 h-8 mx-auto mb-3 opacity-60" />
          <p className="font-medium text-gray-700 dark:text-gray-300">No optimized windows yet</p>
          <p className="text-sm mt-1">
            The session optimizer needs enough closed day-trade paper trades (default ≥5 per hour bucket).
            It runs daily, or an admin can run <code className="px-1 bg-gray-100 dark:bg-gray-800 rounded">optimize_daytrade_sessions --apply</code>.
          </p>
        </div>
      )}

      {sessions.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800/50">
              <tr className="text-left text-xs uppercase text-gray-500 dark:text-gray-400">
                <th className="px-4 py-3">Window (NPT)</th>
                <th className="px-4 py-3">Window (UTC)</th>
                <th className="px-4 py-3">Days</th>
                <th className="px-4 py-3">Win rate</th>
                <th className="px-4 py-3">Trades</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {sessions.map((s) => (
                <tr key={s.name} className="hover:bg-gray-50 dark:hover:bg-gray-800/30">
                  <td className="px-4 py-3 font-mono text-gray-900 dark:text-white">
                    {String(s.start_hour).padStart(2, '0')}:00–{String(s.end_hour).padStart(2, '0')}:00
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-500">
                    {hourToUtc(s.start_hour)}–{hourToUtc(s.end_hour)}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-300">
                    {s.active_days && s.active_days.length
                      ? s.active_days.map((d) => DAY_NAMES[d]).join(', ')
                      : 'All days'}
                  </td>
                  <td className={`px-4 py-3 font-semibold ${winRateColor(s.win_rate)}`}>
                    <span className="inline-flex items-center gap-1">
                      <TrendingUp className="w-3.5 h-3.5" />
                      {s.win_rate != null ? `${s.win_rate}%` : '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-300">{s.total_trades_analyzed}</td>
                  <td className="px-4 py-3">
                    {isActive(s) ? (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 dark:bg-green-500/20 text-green-600">Active now</span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-500">Idle</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="mt-4 text-xs text-gray-400">
        Analytics only — these windows drive the Day-Trade Bot Performance filters, not signal generation.
      </p>
    </div>
  );
};

export default DayTradeSessions;
