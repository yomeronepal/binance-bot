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
    console.warn('WebSocket is not connected');
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
      console.log('User not authenticated, skipping WebSocket connection');
      return;
    }

    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    try {
      setConnectionStatus('connecting');
      console.log('Connecting to WebSocket:', url);

      ws.current = new WebSocket(url);

      ws.current.onopen = (event) => {
        console.log('WebSocket connected');
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
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      ws.current.onerror = (event) => {
        console.error('WebSocket error:', event);
        setError('WebSocket connection error');
        setConnectionStatus('error');

        if (onError) {
          onError(event);
        }
      };

      ws.current.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        setIsConnected(false);
        setConnectionStatus('disconnected');
        stopHeartbeat();

        if (onClose) {
          onClose(event);
        }

        // Attempt reconnection
        if (
          reconnectCount.current < reconnectAttempts &&
          event.code !== 1000 && // Normal closure
          event.code !== 4001 // Authentication failure
        ) {
          reconnectCount.current += 1;
          console.log(
            `Attempting to reconnect (${reconnectCount.current}/${reconnectAttempts})...`
          );
          setConnectionStatus('reconnecting');

          reconnectTimer.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        }
      };
    } catch (err) {
      console.error('Error creating WebSocket connection:', err);
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
