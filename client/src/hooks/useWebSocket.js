import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuthStore } from '../store/useAuthStore';

/**
 * Custom hook for WebSocket connection management.
 * Handles connection, reconnection, message handling, and cleanup.
 *
 * @param {string} url - WebSocket URL
 * @param {object} options - Configuration options
 * @returns {object} WebSocket state and methods
 */
export const useWebSocket = (url, options = {}) => {
  const {
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnectInterval = 3000,
    reconnectAttempts = 5,
    heartbeatInterval = 30000,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [error, setError] = useState(null);

  const ws = useRef(null);
  const reconnectCount = useRef(0);
  const heartbeatTimer = useRef(null);
  const reconnectTimer = useRef(null);
  const { isAuthenticated } = useAuthStore();

  /**
   * Send message to WebSocket server
   */
  const sendMessage = useCallback((data) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data));
      return true;
    }
    return false;
  }, []);

  /**
   * Start heartbeat to keep connection alive
   */
  const startHeartbeat = useCallback(() => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current);
    }

    heartbeatTimer.current = setInterval(() => {
      sendMessage({ type: 'ping' });
    }, heartbeatInterval);
  }, [heartbeatInterval, sendMessage]);

  /**
   * Stop heartbeat
   */
  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = null;
    }
  }, []);

  /**
   * Connect to WebSocket
   */
  const connect = useCallback(() => {
    if (!isAuthenticated) {
      return;
    }

    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      setConnectionStatus('connecting');

      const accessToken = localStorage.getItem('accessToken');
      const authedUrl = accessToken
        ? `${url}${url.includes('?') ? '&' : '?'}token=${accessToken}`
        : url;

      ws.current = new WebSocket(authedUrl);

      ws.current.onopen = (event) => {
        setIsConnected(true);
        setConnectionStatus('connected');
        setError(null);
        reconnectCount.current = 0;

        startHeartbeat();

        if (onOpen) {
          onOpen(event);
        }
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);

          if (onMessage) {
            onMessage(data);
          }
        } catch {
          setError('Failed to parse message');
        }
      };

      ws.current.onerror = (event) => {
        setError('WebSocket connection error');
        setConnectionStatus('error');

        if (onError) {
          onError(event);
        }
      };

      ws.current.onclose = (event) => {
        setIsConnected(false);
        setConnectionStatus('disconnected');
        stopHeartbeat();

        if (onClose) {
          onClose(event);
        }

        // Attempt reconnection with exponential backoff + jitter so a
        // backend restart doesn't trigger a synchronized reconnect storm.
        if (
          reconnectCount.current < reconnectAttempts &&
          event.code !== 1000 && // Normal closure
          event.code !== 4001 // Authentication failure
        ) {
          const attempt = reconnectCount.current;
          reconnectCount.current += 1;
          setConnectionStatus('reconnecting');

          const backoff = Math.min(30000, reconnectInterval * 2 ** attempt);
          const delay = backoff + Math.floor(Math.random() * 1000);

          reconnectTimer.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };
    } catch (err) {
      setError(err.message);
      setConnectionStatus('error');
    }
  }, [
    url,
    isAuthenticated,
    onOpen,
    onMessage,
    onClose,
    onError,
    reconnectAttempts,
    reconnectInterval,
    startHeartbeat,
    stopHeartbeat,
  ]);

  /**
   * Disconnect WebSocket
   */
  const disconnect = useCallback(() => {
    stopHeartbeat();

    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }

    if (ws.current) {
      ws.current.close(1000, 'Client disconnecting');
      ws.current = null;
    }

    setIsConnected(false);
    setConnectionStatus('disconnected');
  }, [stopHeartbeat]);

  /**
   * Subscribe to specific filters
   */
  const subscribe = useCallback(
    (filters) => {
      sendMessage({
        type: 'subscribe',
        filters,
      });
    },
    [sendMessage]
  );

  /**
   * Unsubscribe from updates
   */
  const unsubscribe = useCallback(() => {
    sendMessage({
      type: 'unsubscribe',
    });
  }, [sendMessage]);

  /**
   * Request specific signal details
   */
  const getSignal = useCallback(
    (signalId) => {
      sendMessage({
        type: 'get_signal',
        signal_id: signalId,
      });
    },
    [sendMessage]
  );

  // Auto-connect on mount if authenticated
  useEffect(() => {
    if (isAuthenticated) {
      connect();
    }

    // Cleanup on unmount
    return () => {
      disconnect();
    };
  }, [isAuthenticated]); // Only reconnect when auth state changes

  return {
    isConnected,
    connectionStatus,
    lastMessage,
    error,
    sendMessage,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    getSignal,
  };
};

export default useWebSocket;
