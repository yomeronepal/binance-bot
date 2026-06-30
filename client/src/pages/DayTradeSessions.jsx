import { useEffect, useState } from 'react';
import { Clock, Activity, Calendar, RefreshCw, Zap } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const NEPAL_OFFSET_MINUTES = 5 * 60 + 45;

const DayTradeSessions = () => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentTime, setCurrentTime] = useState(new Date());

  const fetchData = async () => {
    try {
      const res = await fetch(`${API_BASE}/daytrade/sessions/`).then(r => r.json());
      setSessions(res.sessions || []);
    } catch (err) {
      console.error('Failed to fetch day-trade sessions:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const getNepalTime = (date) => {
    const utc = date.getTime() + date.getTimezoneOffset() * 60000;
    return new Date(utc + NEPAL_OFFSET_MINUTES * 60000);
  };

  const nepalNow = getNepalTime(currentTime);
  const currentMinutes = nepalNow.getHours() * 60 + nepalNow.getMinutes();
  const currentWeekday = nepalNow.getDay() === 0 ? 6 : nepalNow.getDay() - 1;

  const isSessionActive = (s) => {
    const inTime = currentMinutes >= s.start_hour * 60 && currentMinutes < s.end_hour * 60;
    if (!inTime) return false;
    if (s.active_days && s.active_days.length > 0) {
      return s.active_days.includes(currentWeekday);
    }
    return true;
  };

  const convertToUTC = (h) => {
    let mins = h * 60 - NEPAL_OFFSET_MINUTES;
    if (mins < 0) mins += 1440;
    return `${String(Math.floor(mins / 60) % 24).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`;
  };

  const allDaySessions = sessions.filter(s => !s.active_days || s.active_days.length === 0);
  const weekdaySessions = sessions.filter(s => s.active_days && s.active_days.length > 0);

  const activeSessions = sessions.filter(isSessionActive);
  const anyActive = activeSessions.length > 0;

  const getUpcomingSessions = () => {
    const today = sessions.filter(s => {
      if (s.active_days && s.active_days.length > 0 && !s.active_days.includes(currentWeekday)) return false;
      return s.start_hour * 60 > currentMinutes;
    }).sort((a, b) => a.start_hour - b.start_hour);
    if (today.length > 0) return { sessions: today.slice(0, 3), label: 'today' };

    const tomorrowWeekday = (currentWeekday + 1) % 7;
    const tomorrow = sessions.filter(s => {
      if (s.active_days && s.active_days.length > 0 && !s.active_days.includes(tomorrowWeekday)) return false;
      return true;
    }).sort((a, b) => a.start_hour - b.start_hour);
    return { sessions: tomorrow.slice(0, 3), label: 'tomorrow' };
  };

  const upcoming = getUpcomingSessions();

  const getTimeUntil = (s) => {
    let diff = s.start_hour * 60 - currentMinutes;
    if (diff < 0) diff += 1440;
    const hours = Math.floor(diff / 60);
    const mins = diff % 60;
    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
  };

  const formatTime = (date) => date.toLocaleTimeString('en-US', {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true,
  });

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <Activity className="w-8 h-8 text-blue-500 animate-pulse" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gradient-to-br dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 p-4 sm:p-6">
      <div className="max-w-5xl mx-auto space-y-6">

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">Day-Trade Sessions</h1>
            <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
              {"Auto-optimized 15m day-trade windows from historical win rates (>= 60%)"}
            </p>
          </div>
          <button onClick={fetchData} className="p-2 bg-gray-200 dark:bg-gray-700 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600">
            <RefreshCw className="w-5 h-5 text-gray-600 dark:text-gray-300" />
          </button>
        </div>

        <div className={`rounded-xl border-2 p-4 ${
          anyActive
            ? 'bg-green-50 dark:bg-green-900/20 border-green-500'
            : 'bg-gray-100 dark:bg-gray-800/30 border-gray-300 dark:border-gray-700'
        }`}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <Activity className={`w-6 h-6 ${anyActive ? 'text-green-500 animate-pulse' : 'text-gray-400'}`} />
              <div>
                <div className={`font-bold text-lg ${anyActive ? 'text-green-700 dark:text-green-400' : 'text-gray-600 dark:text-gray-400'}`}>
                  {anyActive ? 'TRADING WINDOW ACTIVE' : 'NO ACTIVE WINDOW'}
                </div>
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  Nepal Time: {formatTime(nepalNow)} | {DAY_NAMES[currentWeekday]}
                </div>
              </div>
            </div>
            <div className="text-right text-sm text-gray-500 dark:text-gray-400">
              <div>{sessions.length} windows configured</div>
              <div>{allDaySessions.length} all-days + {weekdaySessions.length} day-specific</div>
            </div>
          </div>

          {anyActive && (
            <div className="border-t border-green-200 dark:border-green-500/30 pt-3">
              <div className="text-xs font-semibold text-green-700 dark:text-green-400 mb-2">ACTIVE NOW</div>
              <div className="flex flex-wrap gap-2">
                {activeSessions.map(s => (
                  <div key={s.name} className="flex items-center gap-2 bg-green-100 dark:bg-green-500/20 border border-green-300 dark:border-green-500/40 rounded-lg px-3 py-1.5">
                    <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    <span className="font-mono text-sm font-bold text-green-800 dark:text-green-300">
                      {String(s.start_hour).padStart(2, '0')}:00 - {String(s.end_hour).padStart(2, '0')}:00
                    </span>
                    {s.win_rate != null && (
                      <span className="text-[10px] font-bold bg-green-200 dark:bg-green-500/30 text-green-800 dark:text-green-300 px-1.5 py-0.5 rounded">
                        {parseFloat(s.win_rate).toFixed(0)}% WR
                      </span>
                    )}
                    {s.active_days && s.active_days.length > 0 && (
                      <span className="text-[10px] text-green-600 dark:text-green-400">
                        {s.active_days.map(d => DAY_NAMES[d]).join(', ')}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {!anyActive && upcoming.sessions.length > 0 && (
            <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
              <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-2">
                UPCOMING {upcoming.label.toUpperCase()}
              </div>
              <div className="flex flex-wrap gap-2">
                {upcoming.sessions.map(s => (
                  <div key={s.name} className="flex items-center gap-2 bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5">
                    <Clock className="w-3 h-3 text-gray-400" />
                    <span className="font-mono text-sm font-medium text-gray-700 dark:text-gray-300">
                      {String(s.start_hour).padStart(2, '0')}:00 - {String(s.end_hour).padStart(2, '0')}:00
                    </span>
                    {s.win_rate != null && (
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        parseFloat(s.win_rate) >= 70
                          ? 'bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400'
                          : 'bg-yellow-100 dark:bg-yellow-500/20 text-yellow-700 dark:text-yellow-400'
                      }`}>
                        {parseFloat(s.win_rate).toFixed(0)}% WR
                      </span>
                    )}
                    {upcoming.label === 'today' && (
                      <span className="text-[10px] text-blue-500 dark:text-blue-400 font-medium">
                        in {getTimeUntil(s)}
                      </span>
                    )}
                    {s.active_days && s.active_days.length > 0 && (
                      <span className="text-[10px] text-gray-400">
                        {s.active_days.map(d => DAY_NAMES[d]).join(', ')}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {sessions.length === 0 && (
          <div className="rounded-xl border border-dashed border-gray-300 dark:border-gray-700 p-6 text-center text-gray-500 dark:text-gray-400">
            <Calendar className="w-8 h-8 mx-auto mb-3 opacity-60" />
            <p className="font-medium text-gray-700 dark:text-gray-300">No optimized windows yet</p>
            <p className="text-sm mt-1">
              The optimizer needs enough closed day-trade paper trades (default &ge;5 per hour) with
              win rate &ge; 60%. It runs daily, or an admin can run
              <code className="px-1 mx-1 bg-gray-100 dark:bg-gray-800 rounded">optimize_daytrade_sessions --apply</code>.
            </p>
          </div>
        )}

        {allDaySessions.length > 0 && (
          <div>
            <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-500" />
              All-Days Windows
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {allDaySessions.map(s => (
                <SessionCard key={s.name} session={s} active={isSessionActive(s)} convertToUTC={convertToUTC} />
              ))}
            </div>
          </div>
        )}

        {weekdaySessions.length > 0 && (
          <div>
            <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <Calendar className="w-5 h-5 text-purple-500" />
              Day-Specific Windows
            </h2>
            {DAY_NAMES.map((dayName, dayIdx) => {
              const daySessions = weekdaySessions.filter(s => s.active_days && s.active_days.includes(dayIdx));
              if (daySessions.length === 0) return null;
              const isToday = dayIdx === currentWeekday;
              return (
                <div key={dayIdx} className="mb-4">
                  <h3 className={`text-sm font-semibold mb-2 flex items-center gap-2 ${
                    isToday ? 'text-purple-600 dark:text-purple-400' : 'text-gray-500 dark:text-gray-400'
                  }`}>
                    {dayName}
                    {isToday && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-400 rounded font-bold">
                        TODAY
                      </span>
                    )}
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                    {daySessions.map(s => (
                      <SessionCard key={s.name} session={s} active={isSessionActive(s)} convertToUTC={convertToUTC} compact />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}

      </div>
    </div>
  );
};

const SessionCard = ({ session, active, convertToUTC, compact }) => {
  const s = session;
  const startNPT = `${String(s.start_hour).padStart(2, '0')}:00`;
  const endNPT = `${String(s.end_hour).padStart(2, '0')}:00`;
  const startUTC = convertToUTC(s.start_hour);
  const endUTC = convertToUTC(s.end_hour);
  const winRate = s.win_rate != null ? parseFloat(s.win_rate) : null;
  const trades = s.total_trades_analyzed || 0;

  return (
    <div className={`rounded-lg border p-3 transition-all ${
      active
        ? 'bg-green-50 dark:bg-green-900/20 border-green-400 dark:border-green-500/50 shadow-lg shadow-green-500/10'
        : 'bg-white dark:bg-gray-800/50 border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
    }`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`font-mono font-bold ${compact ? 'text-sm' : 'text-lg'} ${
            active ? 'text-green-700 dark:text-green-400' : 'text-gray-800 dark:text-gray-200'
          }`}>
            {startNPT} - {endNPT}
          </span>
          {active && (
            <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 bg-green-500/20 text-green-700 dark:text-green-400 rounded font-bold">
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
              LIVE
            </span>
          )}
          <span className="text-[9px] px-1 py-0.5 bg-cyan-100 dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-400 rounded font-medium">
            AI
          </span>
        </div>
        {winRate !== null && (
          <span className={`text-xs font-bold px-2 py-0.5 rounded ${
            winRate >= 70 ? 'bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400'
            : winRate >= 60 ? 'bg-lime-100 dark:bg-lime-500/20 text-lime-700 dark:text-lime-400'
            : 'bg-yellow-100 dark:bg-yellow-500/20 text-yellow-700 dark:text-yellow-400'
          }`}>
            {winRate.toFixed(1)}% WR
          </span>
        )}
      </div>

      <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          <span>UTC: {startUTC} - {endUTC}</span>
        </div>
        {trades > 0 && <span>{trades} trades analyzed</span>}
      </div>

      {s.active_days && s.active_days.length > 0 && !compact && (
        <div className="mt-2 flex gap-1">
          {DAY_NAMES.map((d, i) => (
            <span key={i} className={`text-[10px] px-1.5 py-0.5 rounded ${
              s.active_days.includes(i)
                ? 'bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-400 font-bold'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-400'
            }`}>
              {d}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export default DayTradeSessions;
