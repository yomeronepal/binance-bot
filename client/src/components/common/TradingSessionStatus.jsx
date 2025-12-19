/**
 * TradingSessionStatus component
 * Displays current trading session status with real-time clock and trading windows
 * Now fetches sessions dynamically from the backend API
 */
import { useEffect, useState } from 'react';
import { Clock, Activity, Calendar } from 'lucide-react';

const API_BASE_URL = '/api';

const TradingSessionStatus = () => {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch trading sessions from API
  const fetchSessions = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/trading-sessions/`);
      if (!response.ok) {
        throw new Error('Failed to fetch trading sessions');
      }
      const data = await response.json();
      setSessions(data);
      setLoading(false);
      setError(null); // Clear any previous errors
    } catch (err) {
      console.error('Error fetching trading sessions:', err);
      setError(err.message);
      setLoading(false);
      // Fall back to hardcoded sessions if API fails
      setSessions([
        {
          id: 1,
          name: 'GW1',
          session_type: 'ACTIVE_TRADING_WINDOW',
          start_hour: 17,
          start_minute: 0,
          end_hour: 18,
          end_minute: 0,
          active_days: []
        },
        {
          id: 2,
          name: 'GW2',
          session_type: 'GOLDEN_WINDOW',
          start_hour: 21,
          start_minute: 0,
          end_hour: 23,
          end_minute: 0,
          active_days: [6, 2, 3] // Sun, Wed, Thu
        },
        {
          id: 3,
          name: 'Window 2',
          session_type: 'ACTIVE_TRADING_WINDOW',
          start_hour: 21,
          start_minute: 0,
          end_hour: 23,
          end_minute: 0,
          active_days: []
        }
      ]);
    }
  };

  // Initial fetch and periodic refresh
  useEffect(() => {
    fetchSessions();

    // Poll for updates every 60 seconds to catch new sessions added in database
    const refreshInterval = setInterval(() => {
      fetchSessions();
    }, 60000); // 60 seconds

    return () => clearInterval(refreshInterval);
  }, []);

  // Clock timer
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

  // Convert NPT hour/minute to UTC
  const convertNPTtoUTC = (hour, minute) => {
    // NPT is UTC + 5:45, so UTC is NPT - 5:45
    let utcMinutes = (hour * 60 + minute) - (5 * 60 + 45);

    // Handle day wrap
    if (utcMinutes < 0) {
      utcMinutes += 24 * 60;
    }

    const utcHour = Math.floor(utcMinutes / 60) % 24;
    const utcMinute = utcMinutes % 60;

    return {
      hour: utcHour,
      minute: utcMinute,
      formatted: `${String(utcHour).padStart(2, '0')}:${String(utcMinute).padStart(2, '0')}`
    };
  };

  // Convert NPT hour/minute to US EST/EDT
  const convertNPTtoUS = (hour, minute) => {
    // First convert to UTC
    const utc = convertNPTtoUTC(hour, minute);

    // EST is UTC - 5, EDT is UTC - 4
    // For simplicity, we'll use EST (UTC - 5) - user can adjust based on DST
    let usMinutes = (utc.hour * 60 + utc.minute) - (5 * 60);

    // Handle day wrap
    if (usMinutes < 0) {
      usMinutes += 24 * 60;
    }

    const usHour = Math.floor(usMinutes / 60) % 24;
    const usMinute = usMinutes % 60;

    return {
      hour: usHour,
      minute: usMinute,
      formatted: `${String(usHour).padStart(2, '0')}:${String(usMinute).padStart(2, '0')}`
    };
  };

  // Format session time window with all timezones
  const formatSessionWindow = (session) => {
    const nptStart = `${String(session.start_hour).padStart(2, '0')}:${String(session.start_minute).padStart(2, '0')}`;
    const nptEnd = `${String(session.end_hour).padStart(2, '0')}:${String(session.end_minute).padStart(2, '0')}`;

    const utcStart = convertNPTtoUTC(session.start_hour, session.start_minute);
    const utcEnd = convertNPTtoUTC(session.end_hour, session.end_minute);

    const usStart = convertNPTtoUS(session.start_hour, session.start_minute);
    const usEnd = convertNPTtoUS(session.end_hour, session.end_minute);

    return {
      npt: `${nptStart} - ${nptEnd}`,
      utc: `${utcStart.formatted} - ${utcEnd.formatted}`,
      us: `${usStart.formatted} - ${usEnd.formatted}`
    };
  };

  // Check if current time is within a session's time window
  const isWithinSessionTime = (session) => {
    const nepalTime = getNepalTime(currentTime);
    const hour = nepalTime.getHours();
    const minute = nepalTime.getMinutes();
    const currentMinutes = hour * 60 + minute;

    const startMinutes = session.start_hour * 60 + session.start_minute;
    const endMinutes = session.end_hour * 60 + session.end_minute;

    return currentMinutes >= startMinutes && currentMinutes < endMinutes;
  };

  // Check if current day is active for session
  const isSessionDayActive = (session) => {
    if (!session.active_days || session.active_days.length === 0) {
      return true; // All days active
    }
    const nepalTime = getNepalTime(currentTime);
    const dayOfWeek = nepalTime.getDay(); // 0=Sun, 1=Mon, ..., 6=Sat

    // Convert JS day (0=Sun) to Python day (0=Mon)
    // JS: Sun=0, Mon=1, Tue=2, Wed=3, Thu=4, Fri=5, Sat=6
    // Python: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    const pythonDay = dayOfWeek === 0 ? 6 : dayOfWeek - 1;

    return session.active_days.includes(pythonDay);
  };

  // Get active session (prioritize GOLDEN_WINDOW)
  const getActiveSession = () => {
    const activeSessions = sessions.filter(session => {
      const inTime = isWithinSessionTime(session);
      const inDay = isSessionDayActive(session);

      if (session.session_type === 'GOLDEN_WINDOW') {
        return inTime && inDay;
      }
      return inTime;
    });

    // Prioritize GOLDEN_WINDOW
    const goldenWindow = activeSessions.find(s => s.session_type === 'GOLDEN_WINDOW');
    return goldenWindow || activeSessions[0] || null;
  };

  // Get next session time
  const getNextSessionTime = () => {
    const nepalTime = getNepalTime(currentTime);
    const currentMinutes = nepalTime.getHours() * 60 + nepalTime.getMinutes();

    // Find next session
    const sortedSessions = [...sessions].sort((a, b) => {
      const aStart = a.start_hour * 60 + a.start_minute;
      const bStart = b.start_hour * 60 + b.start_minute;
      return aStart - bStart;
    });

    for (const session of sortedSessions) {
      const sessionStart = session.start_hour * 60 + session.start_minute;
      if (sessionStart > currentMinutes) {
        return `${String(session.start_hour).padStart(2, '0')}:${String(session.start_minute).padStart(2, '0')} NPT`;
      }
    }

    // If no session found today, show first session tomorrow
    if (sortedSessions.length > 0) {
      const firstSession = sortedSessions[0];
      return `${String(firstSession.start_hour).padStart(2, '0')}:${String(firstSession.start_minute).padStart(2, '0')} NPT (tomorrow)`;
    }

    return 'N/A';
  };

  const nepalTime = getNepalTime(currentTime);
  const usTime = getUSTime(currentTime);
  const utcTime = getUTCTime(currentTime);
  const activeSession = getActiveSession();
  const isActive = activeSession !== null;

  // Group sessions for display
  const displaySessions = sessions.filter(s =>
    !s.active_days || s.active_days.length === 0
  );

  const goldenSessions = sessions.filter(s =>
    s.session_type === 'GOLDEN_WINDOW' && s.active_days && s.active_days.length > 0
  );

  if (loading) {
    return (
      <div className="rounded-lg border-2 p-4 bg-gray-50 dark:bg-gray-800/30 border-gray-300 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-gray-400 animate-spin" />
          <span className="text-gray-600 dark:text-gray-400">Loading trading sessions...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-lg border-2 p-4 transition-all duration-300 ${isActive
      ? 'bg-green-50 dark:bg-green-900/20 border-green-500 shadow-lg'
      : 'bg-gray-50 dark:bg-gray-800/30 border-gray-300 dark:border-gray-700'
      }`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className={`w-5 h-5 transition-all ${isActive ? 'text-green-600 dark:text-green-400 animate-pulse' : 'text-gray-400'
            }`} />
          <span className={`font-semibold transition-colors ${isActive ? 'text-green-700 dark:text-green-400' : 'text-gray-600 dark:text-gray-400'
            }`}>
            Trading Session: {isActive ? 'ACTIVE' : 'INACTIVE'}
          </span>
          {isActive && activeSession && (
            <span className={`flex items-center gap-1 px-2 py-0.5 border rounded text-xs font-semibold transition-all ${activeSession.session_type === 'GOLDEN_WINDOW'
              ? 'bg-purple-500/20 border-purple-500/50 text-purple-600 dark:text-purple-400'
              : 'bg-green-500/20 border-green-500/50 text-green-600 dark:text-green-400'
              }`}>
              <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${activeSession.session_type === 'GOLDEN_WINDOW'
                ? 'bg-purple-500 dark:bg-purple-400'
                : 'bg-green-500 dark:bg-green-400'
                }`}></span>
              {activeSession.name}
            </span>
          )}
        </div>
        {!isActive && (
          <span className="text-sm text-gray-500 dark:text-gray-400">
            Next: {getNextSessionTime()}
          </span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center p-2 bg-white dark:bg-gray-800/50 rounded-lg shadow-sm dark:border dark:border-gray-700">
          <div className="flex items-center justify-center gap-1 text-xs text-gray-500 dark:text-gray-400 mb-1">
            <Clock className="w-3 h-3" />
            <span>Nepal (NPT)</span>
          </div>
          <div className="font-mono font-bold text-blue-600 dark:text-blue-400">{formatTime(nepalTime)}</div>
        </div>
        <div className="text-center p-2 bg-white dark:bg-gray-800/50 rounded-lg shadow-sm dark:border dark:border-gray-700">
          <div className="flex items-center justify-center gap-1 text-xs text-gray-500 dark:text-gray-400 mb-1">
            <Clock className="w-3 h-3" />
            <span>US (EST/EDT)</span>
          </div>
          <div className="font-mono font-bold text-purple-600 dark:text-purple-400">{formatTime(usTime)}</div>
        </div>
        <div className="text-center p-2 bg-white dark:bg-gray-800/50 rounded-lg shadow-sm dark:border dark:border-gray-700">
          <div className="flex items-center justify-center gap-1 text-xs text-gray-500 dark:text-gray-400 mb-1">
            <Clock className="w-3 h-3" />
            <span>UTC</span>
          </div>
          <div className="font-mono font-bold text-gray-700 dark:text-gray-300">{formatTime(utcTime)}</div>
        </div>
      </div>

      <div className="border-t dark:border-gray-700 pt-3">
        <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 mb-2">
          <Calendar className="w-3 h-3" />
          <span>Trading Windows (Paper trades only execute during these times)</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {displaySessions.map((session, idx) => {
            const isSessionActive = activeSession?.id === session.id;
            const timeWindows = formatSessionWindow(session);

            return (
              <div key={session.id} className={`rounded p-2 text-xs border ${isSessionActive
                ? 'bg-amber-50 dark:bg-amber-900/20 border-2 border-amber-500 shadow-md'
                : 'bg-white dark:bg-gray-800/50 border-gray-200 dark:border-gray-700'
                }`}>
                <div className="flex items-center justify-between mb-1">
                  <div className={`font-semibold ${isSessionActive
                    ? 'text-amber-600 dark:text-amber-400'
                    : 'text-blue-600 dark:text-blue-400'
                    }`}>
                    {session.name}
                  </div>
                  {isSessionActive && (
                    <span className="text-[10px] font-bold text-amber-600 dark:text-amber-400 px-1.5 py-0.5 bg-amber-500/20 rounded">
                      ACTIVE
                    </span>
                  )}
                </div>
                <div className="space-y-0.5">
                  <div><span className="text-gray-500 dark:text-gray-400">NPT:</span> <span className="font-mono dark:text-gray-300">{timeWindows.npt}</span></div>
                  <div><span className="text-gray-500 dark:text-gray-400">UTC:</span> <span className="font-mono dark:text-gray-300">{timeWindows.utc}</span></div>
                  <div><span className="text-gray-500 dark:text-gray-400">US EST:</span> <span className="font-mono dark:text-gray-300">{timeWindows.us}</span></div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {goldenSessions.length > 0 && (
        <div className="border-t dark:border-gray-700 pt-3 mt-3">
          <div className="flex items-center gap-1 text-xs text-purple-600 dark:text-purple-400 mb-2">
            <Calendar className="w-3 h-3" />
            <span className="font-semibold">Golden Window 2 (GW2) - Premium Trading Window</span>
          </div>
          {goldenSessions.map(session => {
            const isSessionActive = activeSession?.id === session.id;
            const timeWindows = formatSessionWindow(session);
            const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
            const activeDayNames = session.active_days?.map(d => dayNames[d]).join(', ') || 'All Days';

            return (
              <div key={session.id} className={`rounded-lg p-3 ${isSessionActive ? 'bg-purple-50 dark:bg-purple-900/20 border-2 border-purple-500' : 'bg-white dark:bg-gray-800/50 border dark:border-gray-700'}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-purple-600 dark:text-purple-400">{session.name}</span>
                    {isSessionActive && (
                      <span className="flex items-center gap-1 px-2 py-0.5 bg-purple-500/20 border border-purple-500/50 rounded text-xs text-purple-600 dark:text-purple-400">
                        <span className="w-1.5 h-1.5 bg-purple-500 dark:bg-purple-400 rounded-full animate-pulse"></span>
                        ACTIVE
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-purple-600 dark:text-purple-400 font-medium">{activeDayNames}</span>
                </div>
                <div className="space-y-1 text-xs">
                  <div><span className="text-gray-500 dark:text-gray-400">NPT:</span> <span className="font-mono font-semibold text-purple-600 dark:text-purple-400">{timeWindows.npt}</span></div>
                  <div><span className="text-gray-500 dark:text-gray-400">UTC:</span> <span className="font-mono text-purple-600 dark:text-purple-400">{timeWindows.utc}</span></div>
                  <div><span className="text-gray-500 dark:text-gray-400">US EST:</span> <span className="font-mono text-purple-600 dark:text-purple-400">{timeWindows.us}</span></div>
                </div>
                <div className="mt-2 pt-2 border-t dark:border-gray-700">
                  <p className="text-xs text-gray-600 dark:text-gray-400">
                    {session.description || 'Special high-probability trading window'}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default TradingSessionStatus;
