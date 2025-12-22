/**
 * PullToRefresh component for PWA
 * Provides native-feeling pull-to-refresh functionality on touch devices
 */
import { useState, useRef, useCallback, useEffect } from 'react';
import { RefreshCw } from 'lucide-react';

const PullToRefresh = ({
  onRefresh,
  children,
  disabled = false,
  threshold = 80,
  maxPull = 120,
  className = ''
}) => {
  const [pulling, setPulling] = useState(false);
  const [pullDistance, setPullDistance] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const containerRef = useRef(null);
  const startY = useRef(0);
  const currentY = useRef(0);

  const isAtTop = useCallback(() => {
    if (!containerRef.current) return false;
    // Check if we're at the top of the page
    return window.scrollY <= 0;
  }, []);

  const handleTouchStart = useCallback((e) => {
    if (disabled || refreshing) return;
    if (!isAtTop()) return;

    startY.current = e.touches[0].clientY;
    currentY.current = startY.current;
    setPulling(true);
  }, [disabled, refreshing, isAtTop]);

  const handleTouchMove = useCallback((e) => {
    if (!pulling || disabled || refreshing) return;
    if (!isAtTop()) {
      setPulling(false);
      setPullDistance(0);
      return;
    }

    currentY.current = e.touches[0].clientY;
    const diff = currentY.current - startY.current;

    if (diff > 0) {
      // Apply resistance to the pull
      const resistance = 0.5;
      const distance = Math.min(diff * resistance, maxPull);
      setPullDistance(distance);

      // Prevent default scroll when pulling down
      if (distance > 10) {
        e.preventDefault();
      }
    }
  }, [pulling, disabled, refreshing, isAtTop, maxPull]);

  const handleTouchEnd = useCallback(async () => {
    if (!pulling) return;

    setPulling(false);

    if (pullDistance >= threshold && onRefresh) {
      setRefreshing(true);
      setPullDistance(threshold);

      try {
        await onRefresh();
      } catch (error) {
        console.error('Refresh failed:', error);
      } finally {
        setRefreshing(false);
        setPullDistance(0);
      }
    } else {
      setPullDistance(0);
    }
  }, [pulling, pullDistance, threshold, onRefresh]);

  // Add touch event listeners
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const options = { passive: false };

    container.addEventListener('touchstart', handleTouchStart, options);
    container.addEventListener('touchmove', handleTouchMove, options);
    container.addEventListener('touchend', handleTouchEnd, options);

    return () => {
      container.removeEventListener('touchstart', handleTouchStart);
      container.removeEventListener('touchmove', handleTouchMove);
      container.removeEventListener('touchend', handleTouchEnd);
    };
  }, [handleTouchStart, handleTouchMove, handleTouchEnd]);

  const progress = Math.min(pullDistance / threshold, 1);
  const rotation = progress * 180;
  const scale = 0.5 + progress * 0.5;
  const opacity = Math.min(progress * 1.5, 1);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {/* Pull indicator */}
      <div
        className="absolute left-0 right-0 flex justify-center items-center overflow-hidden transition-all duration-100 z-50"
        style={{
          height: `${pullDistance}px`,
          top: 0,
          transform: 'translateY(-100%)',
          marginTop: `${pullDistance}px`
        }}
      >
        <div
          className={`flex items-center justify-center w-10 h-10 rounded-full
            ${refreshing
              ? 'bg-blue-500 dark:bg-blue-600'
              : pullDistance >= threshold
                ? 'bg-green-500 dark:bg-green-600'
                : 'bg-gray-200 dark:bg-gray-700'
            } shadow-lg transition-colors duration-200`}
          style={{
            transform: `scale(${scale})`,
            opacity: opacity
          }}
        >
          <RefreshCw
            className={`w-5 h-5 text-white ${refreshing ? 'animate-spin' : ''}`}
            style={{
              transform: refreshing ? 'none' : `rotate(${rotation}deg)`,
              transition: refreshing ? 'none' : 'transform 0.1s ease-out'
            }}
          />
        </div>
      </div>

      {/* Content with transform when pulling */}
      <div
        style={{
          transform: `translateY(${pullDistance}px)`,
          transition: pulling ? 'none' : 'transform 0.3s ease-out'
        }}
      >
        {children}
      </div>

      {/* Refreshing overlay text */}
      {refreshing && (
        <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50">
          <div className="bg-blue-500 dark:bg-blue-600 text-white text-sm px-4 py-2 rounded-full shadow-lg flex items-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span>Refreshing...</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default PullToRefresh;
