import { useEffect, useRef } from 'react';

/**
 * Run a callback on an interval, but pause while the tab is hidden and
 * fire once immediately when it becomes visible again. Avoids burning
 * network/battery polling a backgrounded tab.
 *
 * @param {Function} callback - function to run each tick
 * @param {number} intervalMs - polling interval in milliseconds
 * @param {boolean} enabled - whether polling is active (default true)
 */
export const usePolling = (callback, intervalMs, enabled = true) => {
  const savedCallback = useRef(callback);
  savedCallback.current = callback;

  useEffect(() => {
    if (!enabled) return undefined;

    let timer = null;

    const tick = () => savedCallback.current();

    const start = () => {
      if (timer === null) {
        timer = setInterval(tick, intervalMs);
      }
    };

    const stop = () => {
      if (timer !== null) {
        clearInterval(timer);
        timer = null;
      }
    };

    const handleVisibility = () => {
      if (document.hidden) {
        stop();
      } else {
        tick();
        start();
      }
    };

    // Initial run + start, unless the tab is already hidden
    if (!document.hidden) {
      tick();
      start();
    }
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      stop();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [intervalMs, enabled]);
};

export default usePolling;
