/**
 * TradingSessionStatus component
 * Displays current trading session status with real-time clock and trading windows
 */
import { useEffect, useState } from 'react';
import { Clock, Activity, Calendar } from 'lucide-react';

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

  const isWithinGW1Window = () => {
    const nepalTime = getNepalTime(currentTime);
    const hour = nepalTime.getHours();
    const minute = nepalTime.getMinutes();
    const timeInMinutes = hour * 60 + minute;

    // GW1: 17:00-18:00 NPT
    return timeInMinutes >= 17 * 60 && timeInMinutes < 18 * 60;
  };

  const isWithinGW2Window = () => {
    const nepalTime = getNepalTime(currentTime);
    const hour = nepalTime.getHours();
    const minute = nepalTime.getMinutes();
    const timeInMinutes = hour * 60 + minute;
    const dayOfWeek = nepalTime.getDay(); // 0=Sun, 3=Wed, 4=Thu

    // GW2: 21:00-23:00 NPT on Sunday (0), Wednesday (3), Thursday (4)
    const isGW2Time = timeInMinutes >= 21 * 60 && timeInMinutes < 23 * 60;
    const isGW2Day = dayOfWeek === 0 || dayOfWeek === 3 || dayOfWeek === 4;

    return isGW2Time && isGW2Day;
  };

  const isWithinWindow2 = () => {
    const nepalTime = getNepalTime(currentTime);
    const hour = nepalTime.getHours();
    const minute = nepalTime.getMinutes();
    const timeInMinutes = hour * 60 + minute;

    // Window 2: 21:00-23:00 NPT (any day)
    return timeInMinutes >= 21 * 60 && timeInMinutes < 23 * 60;
  };

  const isWithinTradingWindow = () => {
    return isWithinGW1Window() || isWithinWindow2();
  };

  const getActiveWindow = () => {
    if (isWithinGW1Window()) return 'GW1';
    if (isWithinGW2Window()) return 'GW2';
    if (isWithinWindow2()) return 'Window 2';
    return null;
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
  const isGW1Active = isWithinGW1Window();
  const isGW2Active = isWithinGW2Window();
  const activeWindow = getActiveWindow();

  const tradingWindows = [
    {
      npt: '17:00 - 18:00',
      utc: '11:15 - 12:15',
      us: '06:15 - 07:15 EST'
    },
    {
      npt: '21:00 - 23:00',
      utc: '15:15 - 17:15',
      us: '10:15 - 12:15 EST'
    }
  ];

  const gw2Window = {
    npt: '21:00 - 23:00',
    utc: '15:15 - 17:15',
    us: '10:15 - 12:15 EST',
    days: 'Sun, Wed, Thu'
  };

  return (
    <div className={`rounded-lg border-2 p-4 ${isActive ? 'bg-green-50 dark:bg-green-900/20 border-green-500' : 'bg-gray-50 dark:bg-gray-800/30 border-gray-300 dark:border-gray-700'}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className={`w-5 h-5 ${isActive ? 'text-green-600 dark:text-green-400 animate-pulse' : 'text-gray-400'}`} />
          <span className={`font-semibold ${isActive ? 'text-green-700 dark:text-green-400' : 'text-gray-600 dark:text-gray-400'}`}>
            Trading Session: {isActive ? 'ACTIVE' : 'INACTIVE'}
          </span>
          {isActive && activeWindow && (
            <span className={`flex items-center gap-1 px-2 py-0.5 border rounded text-xs font-semibold ${
              activeWindow === 'GW1' ? 'bg-amber-500/20 border-amber-500/50 text-amber-600 dark:text-amber-400' :
              activeWindow === 'GW2' ? 'bg-purple-500/20 border-purple-500/50 text-purple-600 dark:text-purple-400' :
              'bg-green-500/20 border-green-500/50 text-green-600 dark:text-green-400'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${
                activeWindow === 'GW1' ? 'bg-amber-500 dark:bg-amber-400' :
                activeWindow === 'GW2' ? 'bg-purple-500 dark:bg-purple-400' :
                'bg-green-500 dark:bg-green-400'
              }`}></span>
              {activeWindow}
            </span>
          )}
        </div>
        {!isActive && (
          <span className="text-sm text-gray-500 dark:text-gray-400">
            Next: {getNextWindow()}
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
          {tradingWindows.map((window, idx) => {
            const isWindowActive = (idx === 0 && isGW1Active) || (idx === 1 && (isGW2Active || isWithinWindow2()));
            return (
              <div key={idx} className={`rounded p-2 text-xs border ${
                isWindowActive
                  ? 'bg-amber-50 dark:bg-amber-900/20 border-2 border-amber-500 shadow-md'
                  : 'bg-white dark:bg-gray-800/50 border-gray-200 dark:border-gray-700'
              }`}>
                <div className="flex items-center justify-between mb-1">
                  <div className={`font-semibold ${
                    isWindowActive
                      ? 'text-amber-600 dark:text-amber-400'
                      : 'text-blue-600 dark:text-blue-400'
                  }`}>
                    Window {idx + 1}
                  </div>
                  {isWindowActive && (
                    <span className="text-[10px] font-bold text-amber-600 dark:text-amber-400 px-1.5 py-0.5 bg-amber-500/20 rounded">
                      ACTIVE
                    </span>
                  )}
                </div>
                <div className="space-y-0.5">
                  <div><span className="text-gray-500 dark:text-gray-400">NPT:</span> <span className="font-mono dark:text-gray-300">{window.npt}</span></div>
                  <div><span className="text-gray-500 dark:text-gray-400">UTC:</span> <span className="font-mono dark:text-gray-300">{window.utc}</span></div>
                  <div><span className="text-gray-500 dark:text-gray-400">US:</span> <span className="font-mono dark:text-gray-300">{window.us}</span></div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="border-t dark:border-gray-700 pt-3 mt-3">
        <div className="flex items-center gap-1 text-xs text-purple-600 dark:text-purple-400 mb-2">
          <Calendar className="w-3 h-3" />
          <span className="font-semibold">Golden Window 2 (GW2) - Premium Trading Window</span>
        </div>
        <div className={`rounded-lg p-3 ${isGW2Active ? 'bg-purple-50 dark:bg-purple-900/20 border-2 border-purple-500' : 'bg-white dark:bg-gray-800/50 border dark:border-gray-700'}`}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-purple-600 dark:text-purple-400">GW2</span>
              {isGW2Active && (
                <span className="flex items-center gap-1 px-2 py-0.5 bg-purple-500/20 border border-purple-500/50 rounded text-xs text-purple-600 dark:text-purple-400">
                  <span className="w-1.5 h-1.5 bg-purple-500 dark:bg-purple-400 rounded-full animate-pulse"></span>
                  ACTIVE
                </span>
              )}
            </div>
            <span className="text-xs text-purple-600 dark:text-purple-400 font-medium">{gw2Window.days}</span>
          </div>
          <div className="space-y-1 text-xs">
            <div><span className="text-gray-500 dark:text-gray-400">NPT:</span> <span className="font-mono font-semibold text-purple-600 dark:text-purple-400">{gw2Window.npt}</span></div>
            <div><span className="text-gray-500 dark:text-gray-400">UTC:</span> <span className="font-mono dark:text-gray-300">{gw2Window.utc}</span></div>
            <div><span className="text-gray-500 dark:text-gray-400">US:</span> <span className="font-mono dark:text-gray-300">{gw2Window.us}</span></div>
          </div>
          <div className="mt-2 pt-2 border-t dark:border-gray-700">
            <p className="text-xs text-gray-600 dark:text-gray-400">
              Special high-probability trading window on Sunday, Wednesday & Thursday evenings
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TradingSessionStatus;
